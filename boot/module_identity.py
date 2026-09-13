# SPDX-License-Identifier: BSD-3-Clause
"""Internal offline module-signing identity preparation, never enrollment.

Only encrypted PKCS8 leaves this process. The password arrives over an inherited
FD, never argv/environment/logs. Firmware/MOK, DKMS and host packages are untouched.
A matching certificate profile is not proof of enrollment, module trust or load.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

MODULE_ONLY = ObjectIdentifier('1.3.6.1.4.1.2312.16.1.2')
MAX_CERTIFICATE = 65536


@dataclass(frozen=True)
class Identity:
    certificate: bytes
    encrypted_key: bytes
    fingerprint: str


def inspect_certificate(raw: bytes, now: datetime) -> str:
    """Require our narrow module-only, non-CA, self-issued RSA profile.

    This restricts the certificate's role in shim, not which modules it can sign.
    Actual use also needs current enrollment/revocation, admitted module digest,
    kernel ABI and native generation/effect authorization.
    """
    if not 0 < len(raw) <= MAX_CERTIFICATE or now.tzinfo is None:
        raise ValueError('module-certificate-input')
    cert = x509.load_der_x509_certificate(raw)
    if cert.public_bytes(serialization.Encoding.DER) != raw:
        raise ValueError('module-certificate-noncanonical')
    key = cert.public_key()
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size not in (3072, 4096):
        raise ValueError('module-certificate-key')
    if key.public_numbers().e != 65537 or cert.issuer != cert.subject:
        raise ValueError('module-certificate-issuer')
    if (not isinstance(cert.signature_hash_algorithm, hashes.SHA256)
            or not cert.not_valid_before_utc <= now < cert.not_valid_after_utc):
        raise ValueError('module-certificate-validity')
    key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), hashes.SHA256())
    constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints)
    usage = cert.extensions.get_extension_for_class(x509.KeyUsage)
    extended = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
    if not constraints.critical or constraints.value.ca or constraints.value.path_length is not None:
        raise ValueError('module-certificate-ca')
    allowed = x509.KeyUsage(True, False, False, False, False, False, False, False, False)
    if not usage.critical or usage.value != allowed:
        raise ValueError('module-certificate-key-usage')
    if set(extended.value) != {MODULE_ONLY, ExtendedKeyUsageOID.CODE_SIGNING}:
        raise ValueError('module-certificate-not-module-only')
    allowed_extensions = {x509.ExtensionOID.BASIC_CONSTRAINTS, x509.ExtensionOID.KEY_USAGE,
                          x509.ExtensionOID.EXTENDED_KEY_USAGE, x509.ExtensionOID.SUBJECT_KEY_IDENTIFIER}
    if any(extension.oid not in allowed_extensions for extension in cert.extensions):
        raise ValueError('module-certificate-extra-extension')
    return hashlib.sha256(raw).hexdigest()


def generate(password: bytes, now: datetime) -> Identity:
    if not 20 <= len(password) <= 1024 or b'\0' in password or now.tzinfo is None:
        raise ValueError('module-key-password-or-time')
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'niayan local module signing')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING, MODULE_ONLY]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256()))
    der = cert.public_bytes(serialization.Encoding.DER)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.BestAvailableEncryption(password))
    return Identity(der, private, inspect_certificate(der, now))


def publish(parent_fd: int, name: str, identity: Identity) -> None:
    """Fresh directory only. Partial writes remain identifiable; never overwrite.

    Parent must be a private directory of the invoking owner. identity.json is
    written last; incomplete directories are not usable signing identities.
    Encrypted keys and public certificates are separate from OS/root snapshots.
    """
    info = os.fstat(parent_fd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077
            or not name or name in ('.', '..') or '/' in name or '\0' in name):
        raise ValueError('module-key-private-parent')
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
    try:
        manifest = {'format': 1, 'role': 'kernel-module-only', 'certificate_sha256': identity.fingerprint,
                    'private_key': 'encrypted-pkcs8', 'mok_enrollment': 'not-performed',
                    'driver_build_signature_and_load': 'not-performed'}
        for filename, data in (('module.der', identity.certificate), ('module.key.enc', identity.encrypted_key),
                               ('identity.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode('ascii'))):
            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                offset = 0
                for _ in range(256):
                    if offset == len(data):
                        break
                    count = os.write(fd, data[offset:])
                    if count <= 0:
                        raise OSError('module-identity-write')
                    offset += count
                if offset != len(data):
                    raise OSError('module-identity-write-budget')
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(directory)
        os.fsync(parent_fd)
    finally:
        os.close(directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--password-fd', type=int, required=True)
    args = parser.parse_args()
    if args.password_fd < 3:
        raise ValueError('use-a-dedicated-password-fd')
    # A regular inherited FD makes input bounded/nonblocking; no tty/password prompt
    # inside this offline builder. A protected memfd is suitable for orchestration.
    info = os.fstat(args.password_fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077
            or not 20 <= info.st_size <= 1024):
        raise ValueError('password-fd-must-be-bounded-regular')
    password = os.pread(args.password_fd, 1025, 0)
    parent = os.open(args.output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        identity = generate(password, datetime.now(timezone.utc))
        publish(parent, args.output.name, identity)
    finally:
        os.close(parent)


if __name__ == '__main__':
    main()
