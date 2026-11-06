"""Secrets, sessions and signed media URLs."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone


def hash_secret(secret: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(secret.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32).hex()
    return f"{salt}:{digest}"


def verify_secret(secret: str, stored: str) -> bool:
    salt, digest = stored.split(":")
    candidate = hashlib.scrypt(secret.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32).hex()
    return hmac.compare_digest(candidate, digest)


def new_token() -> str:
    return secrets.token_urlsafe(32)


# Supervisors stay signed in on their phone for a season; office sessions are shorter.
SESSION_DAYS = {"supervisor": 90, "merchandiser": 14, "buyer": 30}


def session_expiry(role: str) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS[role])).isoformat()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Staff media (photos, voice notes) is loaded by <img>/<audio> tags, which
# can't send a Bearer header, so the API hands out short-lived signed URLs.
_SIGNING_KEY = (os.environ.get("LOOMTRACK_SIGNING_KEY") or secrets.token_hex(32)).encode()


def _sig(path: str, exp: int) -> str:
    return hmac.new(_SIGNING_KEY, f"{path}:{exp}".encode(), hashlib.sha256).hexdigest()


def sign_path(path: str, ttl_seconds: int = 3600) -> str:
    exp = int(time.time()) + ttl_seconds
    return f"{path}?exp={exp}&sig={_sig(path, exp)}"


def verify_signed_path(path: str, exp: str | None, sig: str | None) -> bool:
    if not exp or not sig or not exp.isdigit() or int(exp) < time.time():
        return False
    return hmac.compare_digest(sig, _sig(path, int(exp)))
