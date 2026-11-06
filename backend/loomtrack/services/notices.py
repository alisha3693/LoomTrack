"""What a buyer does with a delay notice: opening it is "seen", answering it is "acknowledged".

The office sees both on the order, so a notice that was never opened is told apart from one that was read
and accepted. A note with the acknowledgement lands in the order's conversation as well.
"""

from __future__ import annotations

import sqlite3

from ..db import transaction
from ..util import HttpError
from . import order_messages


def _latest(db: sqlite3.Connection, buyer_id: int, order_id: int) -> sqlite3.Row:
    w = db.execute(
        """SELECT w.* FROM warnings w JOIN orders o ON o.id = w.order_id
           WHERE w.order_id = ? AND o.buyer_id = ? AND o.state != 'cancelled' AND w.state = 'confirmed' ORDER BY w.id DESC LIMIT 1""",
        (order_id, buyer_id),
    ).fetchone()
    if w is None:
        raise HttpError(404, "There is no delay notice on this order")
    return w


def seen(db: sqlite3.Connection, buyer_id: int, order_id: int) -> None:
    w = _latest(db, buyer_id, order_id)
    db.execute("UPDATE warnings SET buyer_seen_at = COALESCE(buyer_seen_at, datetime('now')) WHERE id = ?", (w["id"],))


def acknowledge(db: sqlite3.Connection, buyer_id: int, order_id: int, note: str | None) -> None:
    w = _latest(db, buyer_id, order_id)
    note = (note or "").strip()
    with transaction(db):
        db.execute(
            "UPDATE warnings SET buyer_seen_at = COALESCE(buyer_seen_at, datetime('now')), buyer_ack_at = COALESCE(buyer_ack_at, datetime('now')) WHERE id = ?",
            (w["id"],),
        )
        if note:
            order_messages.post(db, order_id, "buyer", f"About the delay notice: {note}", buyer_id=buyer_id)


def unacknowledged(db: sqlite3.Connection) -> list[int]:
    """Orders whose latest confirmed notice the buyer has not acknowledged."""
    return [
        r["order_id"]
        for r in db.execute(
            """SELECT w.order_id FROM warnings w JOIN orders o ON o.id = w.order_id
               WHERE w.state = 'confirmed' AND w.buyer_ack_at IS NULL AND o.state = 'active'
                 AND w.id = (SELECT MAX(id) FROM warnings x WHERE x.order_id = w.order_id AND x.state = 'confirmed')"""
        )
    ]
