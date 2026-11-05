"""Sign-in and signed staff media."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..deps import SESSION_COOKIE, AppContext, User, bearer, ctx, staff
from ..security import session_expiry, verify_secret, verify_signed_path, new_token
from ..util import HttpError

router = APIRouter(prefix="/api")

# Per-login lockout: 5 wrong tries → 5 minutes. In memory is enough for one server.
_attempts: dict[str, tuple[int, float]] = {}
MAX_TRIES, LOCK_SECONDS = 5, 300
COOKIE_DAYS = {"supervisor": 90, "merchandiser": 14}  # matches security.session_expiry


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=80)
    secret: str = Field(min_length=4, max_length=100)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response, c: AppContext = Depends(ctx)):
    key = body.login.strip().lower()
    n, until = _attempts.get(key, (0, 0.0))
    if until < time.time():
        n = 0
    if n >= MAX_TRIES:
        raise HttpError(429, "Too many attempts. Wait 5 minutes.")

    user = c.db.execute("SELECT id, name, role, unit_id, lang, secret_hash FROM users WHERE lower(login) = ?", (key,)).fetchone()
    if user is None or not verify_secret(body.secret, user["secret_hash"]):
        _attempts[key] = (n + 1, time.time() + LOCK_SECONDS)
        raise HttpError(401, "Wrong login or PIN")
    _attempts.pop(key, None)

    token = new_token()
    c.db.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)", (token, user["id"], session_expiry(user["role"])))
    # Same session token as a cookie, so the API also works when opened in the browser.
    # SameSite=Lax stops other sites from making this browser send state-changing requests.
    response.set_cookie(
        SESSION_COOKIE, token, max_age=COOKIE_DAYS[user["role"]] * 86400,
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )
    safe = {k: user[k] for k in ("id", "name", "role", "unit_id", "lang")}
    return {"token": token, "user": safe}


@router.get("/auth/me")
async def me(user: User = Depends(staff), c: AppContext = Depends(ctx)):
    unit = c.db.execute("SELECT name FROM units WHERE id = ?", (user.unit_id,)).fetchone() if user.unit_id else None
    return {"user": {**user.__dict__, "unit_name": unit["name"] if unit else None}}


@router.post("/auth/logout")
async def logout(request: Request, response: Response, c: AppContext = Depends(ctx)):
    token = bearer(request)
    if token:
        c.db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/media/photos/{photo_id}")
async def staff_photo(photo_id: int, exp: str | None = None, sig: str | None = None, c: AppContext = Depends(ctx)):
    if not verify_signed_path(f"/api/media/photos/{photo_id}", exp, sig):
        raise HttpError(403, "Link expired")
    row = c.db.execute("SELECT path, mime FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if row is None:
        raise HttpError(404, "Not found")
    return FileResponse(row["path"], media_type=row["mime"])


@router.get("/media/audio/{update_id}")
async def staff_audio(update_id: str, exp: str | None = None, sig: str | None = None, c: AppContext = Depends(ctx)):
    if not verify_signed_path(f"/api/media/audio/{update_id}", exp, sig):
        raise HttpError(403, "Link expired")
    row = c.db.execute("SELECT audio_path FROM daily_updates WHERE id = ?", (update_id,)).fetchone()
    if row is None or not row["audio_path"]:
        raise HttpError(404, "Not found")
    return FileResponse(row["audio_path"])
