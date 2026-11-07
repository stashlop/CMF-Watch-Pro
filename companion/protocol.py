"""CMF Watch Pro packet framing and crypto (offline, pure functions).

Faithful re-implementation of the framing in Gadgetbridge's ``CmfCharacteristic`` (AGPLv3), so it can be
built and checked on the PC without a watch. Nothing here does any I/O.

Frame (big-endian):
    0xF5 | u16 chunk_len | u16 cmd1 | u16 chunk_count | u16 chunk_index(1-based) | u16 cmd2 | chunk

A chunk is either plaintext (payload + CRC32) or AES-128-CBC encrypted (payload + CRC32, PKCS7-padded).
CRC32 is the standard zlib/java.util.zip CRC32. The AES IV is the fixed value from the official protocol.
These byte-level choices come from Gadgetbridge and are UNVERIFIED against this watch.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PAYLOAD_HEADER = 0xF5
AES_IV = bytes([0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x5A])
HEADER_LEN = 11


def crc32_le(data: bytes) -> bytes:
    """Standard CRC32 as 4 little-endian bytes (Gadgetbridge's BLETypeConversions.fromUint32)."""
    return struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF)


def aes_encrypt(payload: bytes, key: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("session key must be 16 bytes (AES-128)")
    padder = padding.PKCS7(128).padder()
    data = padder.update(payload) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).encryptor()
    return enc.update(data) + enc.finalize()


def aes_decrypt(blob: bytes, key: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("session key must be 16 bytes (AES-128)")
    dec = Cipher(algorithms.AES(key), modes.CBC(AES_IV)).decryptor()
    data = dec.update(blob) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(data) + unpadder.finalize()


def max_chunk(mtu: int, encrypted: bool) -> int:
    """Largest source-payload slice per chunk, mirroring makeChunks*()."""
    write = mtu - 3  # ATT write header
    if encrypted:
        return ((write - HEADER_LEN) // 16) * 16 - 4 - 1  # 4 CRC + 1 pad byte, per the driver
    return write - HEADER_LEN - 4 - 2


@dataclass(frozen=True)
class Packet:
    cmd1: int
    cmd2: int
    chunk_count: int
    chunk_index: int  # 1-based
    chunk: bytes      # the on-wire chunk (already encrypted if applicable)

    def to_bytes(self) -> bytes:
        return struct.pack(">BHHHHH", PAYLOAD_HEADER, len(self.chunk), self.cmd1,
                           self.chunk_count, self.chunk_index, self.cmd2) + self.chunk


def encode(cmd1: int, cmd2: int, payload: bytes, *, key: bytes | None, mtu: int = 247) -> list[bytes]:
    """Build the on-wire packets for one command. ``key`` None => plaintext; else AES-encrypted."""
    encrypted = key is not None
    size = max(1, max_chunk(mtu, encrypted))
    if encrypted and not payload:
        slices = [b""]
    else:
        slices = [payload[i:i + size] for i in range(0, len(payload), size)] or [b""]
    out = []
    for i, sl in enumerate(slices):
        body = sl + crc32_le(sl)
        chunk = aes_encrypt(body, key) if encrypted else body
        out.append(Packet(cmd1, cmd2, len(slices), i + 1, chunk).to_bytes())
    return out


def decode_chunk(frame: bytes, *, key: bytes | None) -> tuple[int, int, int, int, bytes]:
    """Parse one frame -> (cmd1, cmd2, chunk_count, chunk_index, recovered_payload_slice).

    Verifies the CRC32 trailer. Raises ValueError on a bad header or CRC mismatch.
    """
    if len(frame) < HEADER_LEN or frame[0] != PAYLOAD_HEADER:
        raise ValueError("not a CMF frame")
    chunk_len, cmd1, count, index, cmd2 = struct.unpack_from(">HHHHH", frame, 1)
    chunk = frame[HEADER_LEN:HEADER_LEN + chunk_len]
    if len(chunk) != chunk_len:
        raise ValueError("truncated frame")
    body = aes_decrypt(chunk, key) if key is not None else chunk
    if len(body) < 4:
        raise ValueError("chunk too short for CRC")
    payload, crc = body[:-4], body[-4:]
    if crc != crc32_le(payload):
        raise ValueError("CRC mismatch")
    return cmd1, cmd2, count, index, payload
