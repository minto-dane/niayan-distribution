# SPDX-License-Identifier: MIT
"""Bounded single-frame libzstd bridge for unprivileged intake.

Native libzstd is part of the tool's TCB, not a proven SPARK implementation.
No dictionary lookup, shell, streaming-to-disk, concatenation, or skippable frame.
"""
from __future__ import annotations
import ctypes as C
from nia_common import Invalid

def decode(raw:bytes,limit:int)->bytes:
    if not raw.startswith(b'\x28\xb5\x2f\xfd'):raise Invalid('zstd: expected ordinary single frame')
    try:lib=C.CDLL('libzstd.so.1')
    except OSError as exc:raise Invalid('zstd shared library unavailable') from exc
    lib.ZSTD_isError.argtypes=[C.c_size_t];lib.ZSTD_isError.restype=C.c_uint
    lib.ZSTD_findFrameCompressedSize.argtypes=[C.c_void_p,C.c_size_t];lib.ZSTD_findFrameCompressedSize.restype=C.c_size_t
    lib.ZSTD_getFrameContentSize.argtypes=[C.c_void_p,C.c_size_t];lib.ZSTD_getFrameContentSize.restype=C.c_ulonglong
    lib.ZSTD_getDictID_fromFrame.argtypes=[C.c_void_p,C.c_size_t];lib.ZSTD_getDictID_fromFrame.restype=C.c_uint
    lib.ZSTD_decompress.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t];lib.ZSTD_decompress.restype=C.c_size_t
    source=C.create_string_buffer(raw)
    size=lib.ZSTD_findFrameCompressedSize(source,len(raw))
    if lib.ZSTD_isError(size) or size!=len(raw):raise Invalid('zstd: truncated/concatenated/trailing frame')
    if lib.ZSTD_getDictID_fromFrame(source,len(raw)):raise Invalid('zstd dictionaries not qualified')
    length=lib.ZSTD_getFrameContentSize(source,len(raw))
    if length>=2**64-2:raise Invalid('zstd frame must declare bounded content length')
    if length>limit:raise Invalid('zstd output limit')
    dest=C.create_string_buffer(max(1,length))
    actual=lib.ZSTD_decompress(dest,length,source,len(raw))
    if lib.ZSTD_isError(actual) or actual!=length:raise Invalid('zstd content length/decompression failure')
    return dest.raw[:actual]
