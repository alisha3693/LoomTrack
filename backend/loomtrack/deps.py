"""Request-scoped dependencies: app context and the signed-in user.

All async on purpose: FastAPI runs plain `def` dependencies in a thread pool,
and the single SQLite connection must only be used from the event loop.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import Depends, Request

from .ai.classifier import Classification
from .security import hash_token, utc_now
from .util import HttpError


@dataclass
class AppContext:
    db: sqlite3.Connection
    today: Callable[[], str]
    classify: Callable[[str], Awaitable[Classification]]
    upload_dir: Path
    transcribe: Callable[[str], Awaitable[str | None]]  # a voice recording's path to the Tamil words in it
    backup_dir: Path | None = None


@dataclass
class User:
    id: int
    name: str
    role: str
    unit_id: int | None
    lang: str
    buyer_id: int | None = None
    must_change_secret: int = 0
    can_write: int = 1


async def ctx(request: Request) -> AppContext:
    return request.app.state.ctx


SESSION_COOKIE = "loomtrack_session"


def bearer(request: Request) -> str | None:
    """The session token: from the HttpOnly cookie (what the app uses) or an Authorization header (scripts and tests)."""
    h = request.headers.get("authorization", "")
    return h[7:] if h.startswith("Bearer ") else request.cookies.get(SESSION_COOKIE)


def client_ip(request: Request) -> str:
    """The caller's network address. Behind a tunnel or proxy on this same machine the connection comes from
    loopback, so the address the proxy passed on is believed; from anywhere else those headers are ignored."""
    peer = request.client.host if request.client else "unknown"
    if peer in ("127.0.0.1", "::1", "localhost"):
        passed = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if passed:
            return passed[:64]
    return peer


_READ_ONLY = ("GET", "HEAD", "OPTIONS")


async def optional_user(request: Request, c: AppContext = Depends(ctx)) -> User | None:
    token = bearer(request)
    if not token:
        return None
    # A cookie is sent by the browser on its own, so a page on another site could try to use it. SameSite=Lax already stops
    # that; this also refuses a change the browser itself says came from another site. A header token is never sent that way.
    if not request.headers.get("authorization", "").startswith("Bearer ") and request.method not in _READ_ONLY \
            and request.headers.get("sec-fetch-site") == "cross-site":
        raise HttpError(403, "That request came from another site")
    row = c.db.execute(
        """SELECT u.id, u.name, u.role, u.unit_id, u.lang, u.buyer_id, u.must_change_secret, u.can_write FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.expires_at > ?""",
        (hash_token(token), utc_now()),
    ).fetchone()
    return User(**dict(row)) if row else None


def require_role(*roles: str):
    async def dep(user: User | None = Depends(optional_user)) -> User:
        if user is None:
            raise HttpError(401, "Sign in required")
        if user.role not in roles:
            raise HttpError(403, "Not allowed for your role")
        return user

    return dep


merchandiser = require_role("merchandiser")
supervisor = require_role("supervisor")
signed_in = require_role("merchandiser", "supervisor", "buyer")
