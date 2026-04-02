"""Login rate limiting for Jogi Vault."""
from __future__ import annotations

import time
from collections import defaultdict

_login_attempts = defaultdict(list)
_RATE_WINDOW = 300    # 5 minutes
_RATE_MAX = 5         # max attempts per window


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    return len(_login_attempts[ip]) >= _RATE_MAX


def _record_login_attempt(ip: str) -> None:
    _login_attempts[ip].append(time.time())
