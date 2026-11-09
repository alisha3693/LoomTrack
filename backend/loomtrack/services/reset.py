"""Start testing again from an empty shop floor, keeping what the buyers asked for.

Removed: orders and everything under them (plans, supervisor updates and photos, delay notices, approvals,
materials, conversations, files), changes buyers asked for on orders, and the record of messages sent.
Kept: buyers, people and sign-ins, units, plan templates, and the requests buyers sent. A request that had
become an order goes back to waiting for an answer, so it can be accepted again.
A copy of the database is saved first. The button is off unless LOOMTRACK_ALLOW_RESET is set (see config).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..db import transaction
from ..util import HttpError

# Tables that refuse deletes on purpose; the guard is lifted only inside the one transaction that clears them.
_GUARDED = ("approval_events", "date_changes", "order_messages", "request_messages")


def _count(db: sqlite3.Connection, sql: str) -> int:
    return db.execute(sql).fetchone()[0]


def preview(db: sqlite3.Connection) -> dict:
    """What a reset would remove and what it keeps, for the confirmation screen."""
    return {
        "removes": {
            "orders": _count(db, "SELECT COUNT(*) FROM orders"),
            "supervisorUpdates": _count(db, "SELECT COUNT(*) FROM daily_updates"),
            "changeRequests": _count(db, "SELECT COUNT(*) FROM order_requests WHERE kind = 'amendment'"),
            "sentMessages": _count(db, "SELECT COUNT(*) FROM outbox_messages"),
        },
        "keeps": {
            "requests": _count(db, "SELECT COUNT(*) FROM order_requests WHERE kind = 'new_order'"),
            "reopened": _count(db, "SELECT COUNT(*) FROM order_requests WHERE kind = 'new_order' AND status = 'accepted'"),
            "buyers": _count(db, "SELECT COUNT(*) FROM buyers"),
            "templates": _count(db, "SELECT COUNT(*) FROM templates"),
        },
    }


def _backup(db: sqlite3.Connection, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"before-reset-{datetime.now():%Y%m%d-%H%M%S}.db"
    copy = sqlite3.connect(target)
    try:
        db.backup(copy)
    finally:
        copy.close()
    return target


def _remove_files(paths: list[str], upload_dir: Path) -> None:
    """Delete uploaded files, but only ones inside the uploads folder."""
    root = upload_dir.resolve()
    for p in paths:
        try:
            f = Path(p).resolve()
            if f.is_relative_to(root):
                f.unlink(missing_ok=True)
        except OSError:
            pass


def clear(db: sqlite3.Connection, backup_dir: Path, upload_dir: Path) -> dict:
    result = {"backup": str(_backup(db, backup_dir)), **preview(db)}
    files = [r[0] for r in db.execute("SELECT path FROM photos")]
    files += [r[0] for r in db.execute("SELECT audio_path FROM daily_updates WHERE audio_path IS NOT NULL")]
    files += [r[0] for r in db.execute(
        "SELECT path FROM attachments WHERE request_id IS NULL OR request_id IN (SELECT id FROM order_requests WHERE kind = 'amendment')")]
    guards = db.execute(f"SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name IN ({','.join('?' * len(_GUARDED))})", _GUARDED).fetchall()
    amend = "(SELECT id FROM order_requests WHERE kind = 'amendment')"
    accepted = "(SELECT id FROM order_requests WHERE kind = 'new_order' AND status = 'accepted')"
    with transaction(db):
        for g in guards:
            db.execute(f"DROP TRIGGER {g['name']}")
        for sql in (
            "DELETE FROM approval_events", "DELETE FROM approvals", "DELETE FROM photos", "DELETE FROM issue_reasons",
            "DELETE FROM daily_updates", "DELETE FROM warnings", "DELETE FROM date_changes", "DELETE FROM milestones",
            "DELETE FROM order_sizes", "DELETE FROM order_materials", "DELETE FROM order_messages",
            "DELETE FROM thread_reads WHERE kind = 'order'",
            f"DELETE FROM request_sizes WHERE request_id IN {amend}",
            f"DELETE FROM request_messages WHERE request_id IN {amend}",
            f"DELETE FROM thread_reads WHERE kind = 'request' AND ref_id IN {amend}",
            f"DELETE FROM attachments WHERE request_id IN {amend}",
            "DELETE FROM attachments WHERE request_id IS NULL",
            "UPDATE attachments SET order_id = NULL WHERE order_id IS NOT NULL",
            f"DELETE FROM request_messages WHERE event = 'accepted' AND request_id IN {accepted}",
            "DELETE FROM order_requests WHERE kind = 'amendment'",
            "UPDATE order_requests SET status = 'submitted', order_id = NULL, decided_by = NULL, decided_at = NULL, updated_at = datetime('now') "
            "WHERE status = 'accepted'",
            "UPDATE order_requests SET order_id = NULL",
            "DELETE FROM outbox_messages", "DELETE FROM feed_reads", "DELETE FROM orders",
        ):
            db.execute(sql)
        for g in guards:
            db.execute(g["sql"])
        problems = db.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise HttpError(500, "The reset was stopped because it would leave broken links. Nothing was changed.")
    _remove_files(files, upload_dir)
    return result
