# SPDX-License-Identifier: BSD-3-Clause
"""Loopback HTTPS tests with ephemeral, private test certificates and real TUF."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
from pathlib import Path
import ssl
import tempfile
import threading
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from repository import HTTPSFetcher, Repository, initialize, sha, tuf_errors
from test_repository import SignedRepository


class HTTPSTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.remote = SignedRepository()
        self.status = {}
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                origin = case.remote.metadata_url.rsplit('/metadata/', 1)[0]
                data = case.remote.files.get(origin + self.path)
                status = case.status.get(self.path, 200 if data is not None else 404)
                self.send_response(status)
                if status == 302:
                    self.send_header('Location', 'https://outside.example.test/forbidden')
                body = data if data is not None and status == 200 else b''
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Nia loopback test')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
                .sign(key, hashes.SHA256()))
        self.certificate = self.directory / 'test-ca.pem'
        self.certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        private = self.directory / 'test-key.pem'
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
        private.chmod(0o600)
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.certificate, private)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01})
        self.thread.start()
        origin = 'https://127.0.0.1:' + str(self.server.server_address[1])
        self.remote.metadata_url = origin + '/metadata/'
        self.remote.targets_url = origin + '/targets/'
        self.remote.files = {}
        self.remote.publish()
        self.cache = self.directory / 'cache'
        self.remote.provision(self.cache)
        self.fetchers = []

    def tearDown(self):
        for fetcher in self.fetchers:
            fetcher.close()
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.temporary.cleanup()
        self.assertFalse(self.thread.is_alive())

    def client(self, trust_test_ca=True):
        fetcher = HTTPSFetcher(self.remote.metadata_url, self.remote.targets_url)
        if trust_test_ca:
            fetcher.session.verify = str(self.certificate)
        self.fetchers.append(fetcher)
        return Repository(self.cache, sha(self.remote.bootstrap), self.remote.metadata_url,
                          self.remote.targets_url, fetcher=fetcher)

    def test_actual_https_and_signed_artifact(self):
        with self.client() as client:
            data = client.target('packages/sample.deb')
        self.assertEqual(data, self.remote.targets['packages/sample.deb'])
        self.assertGreater(self.fetchers[0].bytes, len(data))

    def test_untrusted_tls_certificate_is_rejected(self):
        with self.assertRaises(tuf_errors.DownloadError):
            with self.client(False):
                pass

    def test_redirect_is_rejected_without_following_it(self):
        self.status['/metadata/2.root.json'] = 302
        with self.assertRaises(tuf_errors.DownloadHTTPError) as raised:
            with self.client():
                pass
        self.assertEqual(raised.exception.status_code, 302)
        self.assertEqual(self.fetchers[0].requests, 1)

    def test_corrupt_payload_from_real_https_fails_verification(self):
        url = next(u for u in self.remote.files if u.startswith(self.remote.targets_url))
        self.remote.files[url] = b'damaged'
        with self.client() as client:
            with self.assertRaises(tuf_errors.RepositoryError):
                client.target('packages/sample.deb')


if __name__ == '__main__':
    unittest.main()
