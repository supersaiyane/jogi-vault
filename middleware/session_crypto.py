"""Session password encryption for Jogi Vault."""
from __future__ import annotations

import os
import base64
import hashlib

from flask import session, current_app
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _session_encrypt(pwd: str) -> str:
    """Encrypt vault password before storing in session cookie."""
    key = hashlib.sha256(current_app.secret_key.encode()).digest()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, pwd.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _session_decrypt() -> str:
    """Decrypt vault password from session cookie."""
    enc = session.get("vault_password", "")
    if not enc:
        return ""
    raw = base64.b64decode(enc)
    key = hashlib.sha256(current_app.secret_key.encode()).digest()
    return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode()
