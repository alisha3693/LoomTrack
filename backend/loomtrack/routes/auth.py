"""Sign-in and signed staff media."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..deps import SESSION_COOKIE, AppContext, User, bearer, client_ip, ctx, signed_in
from ..services import accounts, lockout
from . import notifications
from ..security import hash_token, session_expiry, verify_secret, verify_signed_path, new_token
from ..util import HttpError

router = APIRouter(prefix="/api")

COOKIE_DAYS = {"supervisor": 90, "merchandiser": 14, "buyer": 30}  # matches security.session_expiry


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=80)
    secret: str = Field(min_length=4, max_length=100)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response, c: AppContext = Depends(ctx)):
    key, ip = body.login.strip().lower(), client_ip(request)
    lockout.check(c.db, key, ip)

    user = c.db.execute("SELECT id, name, role, unit_id, lang, buyer_id, must_change_secret, secret_hash FROM users WHERE lower(login) = ?", (key,)).fetchone()
    if user is None or not verify_secret(body.secret, user["secret_hash"]):
        lockout.record_failure(c.db, key, ip)
        raise HttpError(401, "Wrong login or PIN")
    lockout.record_success(c.db, key)

    # The session lives in an HttpOnly cookie, so no script on the page can read it, and the database keeps only its hash.
    # SameSite=Lax stops other sites from making this browser send state-changing requests.
    token = new_token()
    c.db.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)", (hash_token(token), user["id"], session_expiry(user["role"])))
    response.set_cookie(
        SESSION_COOKIE, token, max_age=COOKIE_DAYS[user["role"]] * 86400,
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )
    return {"ok": True}


@router.get("/auth/me")
async def me(user: User = Depends(signed_in), c: AppContext = Depends(ctx)):
    unit = c.db.execute("SELECT name FROM units WHERE id = ?", (user.unit_id,)).fetchone() if user.unit_id else None
    buyer = c.db.execute("SELECT name FROM buyers WHERE id = ?", (user.buyer_id,)).fetchone() if user.buyer_id else None
    return {"user": {**user.__dict__, "unit_name": unit["name"] if unit else None, "buyer_name": buyer["name"] if buyer else None}}


class PasswordIn(BaseModel):
    current: str = Field(min_length=1, max_length=100)
    new: str = Field(min_length=1, max_length=100)


@router.post("/auth/password")
async def change_password(body: PasswordIn, request: Request, user: User = Depends(signed_in), c: AppContext = Depends(ctx)):
    accounts.change_password(c.db, user.id, body.current, body.new, bearer(request))
    return {"ok": True}


def _profile(c: AppContext, user: User) -> dict:
    """A buyer's phone belongs to their company; an office person's belongs to them. Supervisors sign in with their phone."""
    if user.role == "supervisor":
        raise HttpError(403, "A supervisor's phone number is their sign-in; the office changes it on the Units page")
    u = c.db.execute("SELECT name, login, phone FROM users WHERE id = ?", (user.id,)).fetchone()
    if user.role == "buyer":
        b = c.db.execute("SELECT name, whatsapp_number FROM buyers WHERE id = ?", (user.buyer_id,)).fetchone()
        return {"role": "buyer", "name": u["name"], "email": u["login"], "phone": b["whatsapp_number"], "company": b["name"]}
    return {"role": "merchandiser", "name": u["name"], "email": u["login"], "phone": u["phone"], "company": None}


@router.get("/auth/profile")
async def profile(user: User = Depends(signed_in), c: AppContext = Depends(ctx)):
    """The signed-in person's own name, sign-in email and phone number, for the "My details" page."""
    return _profile(c, user)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    currentPassword: str | None = Field(default=None, max_length=100)  # needed only when the email changes


@router.patch("/auth/profile")
async def update_profile(body: ProfileIn, request: Request, user: User = Depends(signed_in), c: AppContext = Depends(ctx)):
    """Change your own name, sign-in email and phone number in one go.

    Changing the email asks for the current password, so someone at an unlocked phone cannot take the account over.
    For a buyer the number is the company's WhatsApp number for order alerts; typing it here is the agreement to receive them.
    """
    before = _profile(c, user)
    new_email = body.email.strip().lower()
    if new_email != before["email"].lower():
        row = c.db.execute("SELECT secret_hash FROM users WHERE id = ?", (user.id,)).fetchone()
        if not body.currentPassword or not verify_secret(body.currentPassword, row["secret_hash"]):
            raise HttpError(400, "Enter your current password to change your email")
    phone = notifications.clean_number(body.phone) if (body.phone or "").strip() else None  # validate before saving anything
    accounts.update_details(c.db, user.id, body.name, body.email, bearer(request), roles=("buyer", "merchandiser"))
    if phone != before["phone"]:
        if user.role == "buyer":
            c.db.execute(
                """UPDATE buyers SET whatsapp_number = ?, whatsapp_opt_in = ?,
                     whatsapp_opt_in_at = CASE WHEN ? THEN datetime('now') END, whatsapp_opt_in_by = CASE WHEN ? THEN ? END
                   WHERE id = ?""",
                (phone, int(phone is not None), phone is not None, phone is not None, user.id, user.buyer_id),
            )
        else:
            c.db.execute("UPDATE users SET phone = ? WHERE id = ?", (phone, user.id))
    return _profile(c, user)


@router.post("/auth/logout")
async def logout(request: Request, response: Response, c: AppContext = Depends(ctx)):
    token = bearer(request)
    if token:
        c.db.execute("DELETE FROM sessions WHERE token = ?", (hash_token(token),))
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
