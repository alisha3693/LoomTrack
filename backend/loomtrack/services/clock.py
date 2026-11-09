"""The app's date. On a test machine it can be set by hand, so a tester can step to the next working day.

The setting is one row in the database, so every screen and every user sees the same date. It only works where
LOOMTRACK_ALLOW_RESET is switched on (the same switch as the "Reset test data" button), never on the live site.
"""

from __future__ import annotations

import sqlite3

from .. import config


def test_date(db: sqlite3.Connection) -> str | None:
    if not config.allow_reset():
        return None
    row = db.execute("SELECT test_date FROM app_clock WHERE id = 1").fetchone()
    return row["test_date"] if row else None


def today(db: sqlite3.Connection) -> str:
    return test_date(db) or config.today()


def set_test_date(db: sqlite3.Connection, date: str | None) -> None:
    db.execute(
        "INSERT INTO app_clock (id, test_date) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET test_date = excluded.test_date", (date,)
    )
