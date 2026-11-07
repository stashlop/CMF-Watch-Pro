"""Session-key derivation and K1 loading for the CMF companion app.

The watch uses server-based pairing: a 16-byte key "K1" is issued when the OWNER pairs the watch with the
official CMF app under their own account. It cannot be generated locally. Per connection, the watch sends a
nonce and both sides derive a session key:

    session_key = SHA-256(nonce || K1)[:16]

(from Gadgetbridge's AUTH_NONCE_REPLY handling). This module only derives keys and loads the owner's K1 from
a local file or env var. It never obtains K1 by any other means, and the K1 file is gitignored.

To get your K1, follow Gadgetbridge's documented steps with your OWN device/account:
https://gadgetbridge.org/basics/pairing/nothing-cmf-server/
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

K1_ENV = "CMF_K1"
K1_FILE = Path(__file__).resolve().parents[1] / "data" / "companion" / "k1.key"


def session_key(nonce: bytes, k1: bytes) -> bytes:
    """Derive the per-connection session key: SHA-256(nonce || K1)[:16]."""
    if len(k1) != 16:
        raise ValueError("K1 must be 16 bytes")
    return hashlib.sha256(nonce + k1).digest()[:16]


def parse_k1(text: str) -> bytes:
    """Accept '0x'-prefixed or bare 32-hex-char K1."""
    s = text.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if not re.fullmatch(r"[0-9a-f]{32}", s):
        raise ValueError("K1 must be 32 hex characters (16 bytes)")
    return bytes.fromhex(s)


def load_k1() -> bytes | None:
    """Load K1 from $CMF_K1 or data/companion/k1.key, or None if the owner hasn't provided it."""
    env = os.environ.get(K1_ENV)
    if env:
        return parse_k1(env)
    if K1_FILE.exists():
        return parse_k1(K1_FILE.read_text(encoding="utf-8"))
    return None
