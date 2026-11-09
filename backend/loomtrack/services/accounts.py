"""Buyer sign-in accounts: the office creates them, the buyer changes the password on first use."""

from __future__ import annotations

import re
import secrets
import sqlite3

from ..db import transaction
from ..security import hash_secret, verify_secret
from ..util import HttpError

MIN_PASSWORD = 8
# No 0/O or 1/l/I, so a password read out over the phone is not misheard.
_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def temporary_password() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(12))


def _buyer_user(db: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = db.execute("SELECT id, buyer_id FROM users WHERE id = ? AND role = 'buyer'", (user_id,)).fetchone()
    if row is None:
        raise HttpError(404, "Account not found")
    return row


def list_logins(db: sqlite3.Connection, buyer_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT id, name, login, must_change_secret AS pending, can_write AS canWrite FROM users WHERE buyer_id = ? ORDER BY name", (buyer_id,))]


def create_login(db: sqlite3.Connection, buyer_id: int, name: str, email: str, can_write: bool = True) -> dict:
    """Returns the new login with its temporary password, which is shown once and never stored."""
    name, login = name.strip(), email.strip().lower()
    if not name:
        raise HttpError(400, "Enter the person's name")
    if not _EMAIL.match(login):
        raise HttpError(400, "Enter a valid email address")
    if db.execute("SELECT 1 FROM buyers WHERE id = ?", (buyer_id,)).fetchone() is None:
        raise HttpError(404, "Buyer not found")
    if db.execute("SELECT 1 FROM users WHERE lower(login) = ?", (login,)).fetchone():
        raise HttpError(409, "That email already has an account")
    password = temporary_password()
    db.execute(
        "INSERT INTO users (name, role, login, secret_hash, lang, buyer_id, must_change_secret, can_write) VALUES (?,?,?,?,?,?,1,?)",
        (name, "buyer", login, hash_secret(password), "en", buyer_id, 1 if can_write else 0),
    )
    return {"login": login, "password": password}


def reset_password(db: sqlite3.Connection, user_id: int) -> dict:
    _buyer_user(db, user_id)
    password = temporary_password()
    with transaction(db):
        db.execute("UPDATE users SET secret_hash = ?, must_change_secret = 1 WHERE id = ?", (hash_secret(password), user_id))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"password": password}


def set_access(db: sqlite3.Connection, user_id: int, can_write: bool) -> None:
    """Switch an account between full access and view-only. Takes effect on its next request."""
    _buyer_user(db, user_id)
    db.execute("UPDATE users SET can_write = ? WHERE id = ?", (1 if can_write else 0, user_id))


def update_details(db: sqlite3.Connection, user_id: int, name: str | None, email: str | None) -> None:
    """Change a person's name and/or the email they sign in with. A new email signs them out everywhere."""
    row = db.execute("SELECT login FROM users WHERE id = ? AND role = 'buyer'", (user_id,)).fetchone()
    if row is None:
        raise HttpError(404, "Account not found")
    new_name = name.strip() if name is not None else None
    if new_name is not None and not new_name:
        raise HttpError(400, "Enter the person's name")
    new_login = email.strip().lower() if email is not None else None
    if new_login is not None:
        if not _EMAIL.match(new_login):
            raise HttpError(400, "Enter a valid email address")
        if db.execute("SELECT 1 FROM users WHERE lower(login) = ? AND id != ?", (new_login, user_id)).fetchone():
            raise HttpError(409, "That email already has an account")
    with transaction(db):
        if new_name is not None:
            db.execute("UPDATE users SET name = ? WHERE id = ?", (new_name, user_id))
        if new_login is not None and new_login != row["login"].lower():
            db.execute("UPDATE users SET login = ? WHERE id = ?", (new_login, user_id))
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def remove_login(db: sqlite3.Connection, user_id: int) -> None:
    _buyer_user(db, user_id)
    with transaction(db):
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def change_password(db: sqlite3.Connection, user_id: int, current: str, new: str, keep_token: str | None) -> None:
    row = db.execute("SELECT secret_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not verify_secret(current, row["secret_hash"]):
        raise HttpError(400, "Your current password is not right")
    if len(new) < MIN_PASSWORD:
        raise HttpError(400, f"Use at least {MIN_PASSWORD} characters")
    if new == current:
        raise HttpError(400, "Choose a password different from the current one")
    with transaction(db):
        db.execute("UPDATE users SET secret_hash = ?, must_change_secret = 0 WHERE id = ?", (hash_secret(new), user_id))
        # Other devices signed in with the old password are signed out.
        db.execute("DELETE FROM sessions WHERE user_id = ? AND token != ?", (user_id, keep_token or ""))
