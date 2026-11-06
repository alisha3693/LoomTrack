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
from .security import utc_now
from .util import HttpError


@dataclass
class AppContext:
    db: sqlite3.Connection
    today: Callable[[], str]
    classify: Callable[[str], Awaitable[Classification]]
    upload_dir: Path


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
    """Session token from the Authorization header (the app) or the cookie (address-bar visits)."""
    h = request.headers.get("authorization", "")
    return h[7:] if h.startswith("Bearer ") else request.cookies.get(SESSION_COOKIE)


async def optional_user(request: Request, c: AppContext = Depends(ctx)) -> User | None:
    token = bearer(request)
    if not token:
        return None
    row = c.db.execute(
        """SELECT u.id, u.name, u.role, u.unit_id, u.lang, u.buyer_id, u.must_change_secret, u.can_write FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.expires_at > ?""",
        (token, utc_now()),
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
staff = require_role("merchandiser", "supervisor")
signed_in = require_role("merchandiser", "supervisor", "buyer")
