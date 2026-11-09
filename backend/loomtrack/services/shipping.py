"""The end of an order's life: production finished, then shipped on a date.

Production is complete when the last production stage has reached the order quantity. The office is told once.
"Shipped" is something a merchandiser records, with the date it left the factory, because only they know that.
The shipped date against the ex-factory date is what shows whether the order was on time.
"""

from __future__ import annotations

import sqlite3

from ..db import transaction
from ..domain.calendar import add_days, to_date
from ..domain.runrate import pretty_date
from ..util import HttpError
from . import notify


def days_late(shipped_date: str, ex_factory: str) -> int:
    """Calendar days after the ex-factory date. Zero or less is on time."""
    return (to_date(shipped_date) - to_date(ex_factory)).days


def verdict(shipped_date: str, ex_factory: str) -> str:
    n = days_late(shipped_date, ex_factory)
    if n <= 0:
        return "on time" if n == 0 else f"{-n} day{'s' if n != -1 else ''} early"
    return f"{n} day{'s' if n != 1 else ''} late"


def check_production_complete(db: sqlite3.Connection, order: sqlite3.Row, today: str) -> None:
    """Tell the office, once, when the last production stage has reached the order quantity."""
    if order["production_complete_at"]:
        return
    last = db.execute(
        """SELECT m.id FROM milestones m JOIN plan_steps s ON s.code = m.code
           WHERE m.order_id = ? AND s.kind = 'stage' ORDER BY m.seq DESC LIMIT 1""",
        (order["id"],),
    ).fetchone()
    if last is None:
        return
    done = db.execute("SELECT COALESCE(SUM(qty), 0) FROM daily_updates WHERE milestone_id = ?", (last["id"],)).fetchone()[0]
    if done < order["qty_total"]:
        return
    db.execute("UPDATE orders SET production_complete_at = ? WHERE id = ?", (today, order["id"]))
    notify.send(db, "production_complete", order["buyer_id"], order["id"], po=order["po_no"])


def mark_shipped(db: sqlite3.Connection, order_id: int, shipped_date: str, today: str) -> dict:
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise HttpError(404, "Order not found")
    if order["state"] != "active":
        raise HttpError(409, "Only an order that is still in production can be marked shipped")
    if shipped_date > today:
        raise HttpError(400, "The ship date cannot be in the future")
    if shipped_date < add_days(order["ex_factory"], -120):
        raise HttpError(400, "That ship date is too far before the ex-factory date")
    result = verdict(shipped_date, order["ex_factory"])
    with transaction(db):
        db.execute("UPDATE orders SET state = 'shipped', shipped_date = ? WHERE id = ?", (shipped_date, order_id))
        # The ex-factory checkpoint of the plan happened the day it shipped.
        db.execute("UPDATE milestones SET actual_date = ? WHERE order_id = ? AND code = 'EXF' AND actual_date IS NULL", (shipped_date, order_id))
        db.execute("UPDATE warnings SET state = 'superseded' WHERE order_id = ? AND state = 'pending'", (order_id,))
        db.execute("UPDATE warnings SET state = 'resolved', decided_at = datetime('now') WHERE order_id = ? AND state = 'confirmed'", (order_id,))
        notify.send(db, "order_shipped", order["buyer_id"], order_id, po=order["po_no"], date=pretty_date(shipped_date),
                    text=f"It was due on {pretty_date(order['ex_factory'])}: shipped {result}." if result != "on time" else "It shipped on the agreed date.")
    return {"shippedDate": shipped_date, "daysLate": days_late(shipped_date, order["ex_factory"]), "verdict": result}
