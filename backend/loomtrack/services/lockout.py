"""Locking out password guessing, by sign-in name and by network address, kept in the database so a restart does not clear it.

A sign-in name is locked after 5 wrong tries in 5 minutes, for 5 minutes. A network address is locked after 20 wrong tries
(for any names) in 15 minutes, for 15 minutes. The address limit is higher on purpose: a whole factory unit can share one
public address, and several people mistyping a PIN must not lock out the rest. A right password clears the name's count but
not the address's, so one valid account cannot be used to keep guessing at others.
"""

from __future__ import annotations

import math
import sqlite3
import time

from ..util import HttpError

# scope -> (wrong tries allowed, seconds they are counted over, seconds locked)
LIMITS = {"login": (5, 300, 300), "ip": (20, 900, 900)}


def _wait(seconds: float) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


def check(db: sqlite3.Connection, login: str, ip: str, now: float | None = None) -> None:
    """Raise 429 if this name or this address is locked."""
    now = time.time() if now is None else now
    for scope, key in (("login", login), ("ip", ip)):
        row = db.execute("SELECT locked_until FROM login_attempts WHERE scope = ? AND key = ?", (scope, key)).fetchone()
        if row and row["locked_until"] > now:
            raise HttpError(429, f"Too many attempts. Wait {_wait(row['locked_until'] - now)}.")


def record_failure(db: sqlite3.Connection, login: str, ip: str, now: float | None = None) -> None:
    now = time.time() if now is None else now
    for scope, key in (("login", login), ("ip", ip)):
        tries, window, lock = LIMITS[scope]
        row = db.execute("SELECT fails, last_fail FROM login_attempts WHERE scope = ? AND key = ?", (scope, key)).fetchone()
        fails = 1 if row is None or now - row["last_fail"] > window else row["fails"] + 1
        locked_until = now + lock if fails >= tries else 0
        db.execute(
            """INSERT INTO login_attempts (scope, key, fails, last_fail, locked_until) VALUES (?,?,?,?,?)
               ON CONFLICT(scope, key) DO UPDATE SET fails = excluded.fails, last_fail = excluded.last_fail, locked_until = excluded.locked_until""",
            (scope, key, 0 if locked_until else fails, now, locked_until),
        )
    # Rows whose lock and counting window are both over carry no information any more.
    db.execute("DELETE FROM login_attempts WHERE locked_until < ? AND last_fail < ?", (now, now - max(w for _, w, _ in LIMITS.values())))


def record_success(db: sqlite3.Connection, login: str) -> None:
    db.execute("DELETE FROM login_attempts WHERE scope = 'login' AND key = ?", (login,))
