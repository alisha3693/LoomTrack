"""Messages between a buyer and the merchandiser about an order that already exists.

A request has its own conversation (services/requests.py). Once it is an order, a question that is not
a change of date or quantity had nowhere to go; this is that place. Append-only, like the other trails.
"""

from __future__ import annotations

import sqlite3

from ..util import HttpError
from . import notify

MAX_LENGTH = 2000
MAX_PER_ORDER = 500


def _clean(body: str) -> str:
    text = (body or "").strip()
    if not text:
        raise HttpError(400, "Write a message first")
    if len(text) > MAX_LENGTH:
        raise HttpError(400, f"Keep a message under {MAX_LENGTH} characters")
    return text


def _order(db: sqlite3.Connection, order_id: int, buyer_id: int | None) -> sqlite3.Row:
    """The order, or a plain 'not found' when it is not this buyer's (never revealing that it exists)."""
    o = db.execute("SELECT id, buyer_id, po_no, order_no, state FROM orders WHERE id = ?", (order_id,)).fetchone()
    if o is None or (buyer_id is not None and (o["buyer_id"] != buyer_id or o["state"] == "cancelled")):
        raise HttpError(404, "Order not found")
    return o


def thread(db: sqlite3.Connection, order_id: int, buyer_id: int | None = None) -> list[dict]:
    """The whole conversation about an order: what was said while it was still a request, then the messages
    since. Request items come first (they happened first) and carry `source: "request"` and their event."""
    _order(db, order_id, buyer_id)
    out: list[dict] = [
        {"key": f"r{m['id']}", "source": "request", "id": None, "event": m["event"], "author": m["author"], "body": m["body"],
         "proposedExFactory": m["proposed_ex_factory"], "requestNo": m["request_no"], "at": m["created_at"]}
        for m in db.execute(
            """SELECT m.id, m.event, m.author, m.body, m.proposed_ex_factory, m.created_at, q.request_no
               FROM request_messages m JOIN order_requests q ON q.id = m.request_id WHERE q.order_id = ? ORDER BY m.id""",
            (order_id,),
        )
    ]
    out += [
        {"key": f"o{m['id']}", "source": "order", "id": m["id"], "author": m["author"], "body": m["body"], "at": m["created_at"]}
        for m in db.execute("SELECT id, author, body, created_at FROM order_messages WHERE order_id = ? ORDER BY id", (order_id,))
    ]
    return out


def post(db: sqlite3.Connection, order_id: int, author: str, body: str, *, buyer_id: int | None = None, user_id: int | None = None) -> int:
    text = _clean(body)
    o = _order(db, order_id, buyer_id)
    if db.execute("SELECT COUNT(*) FROM order_messages WHERE order_id = ?", (order_id,)).fetchone()[0] >= MAX_PER_ORDER:
        raise HttpError(409, "This conversation is full. Please call or email instead.")
    mid = db.execute("INSERT INTO order_messages (order_id, author, user_id, body) VALUES (?,?,?,?)", (order_id, author, user_id, text)).lastrowid
    # The other side hears of it outside the app too (email, and WhatsApp for a buyer who agreed to it).
    notify.send(db, "order_message" if author == "merchandiser" else "order_message_in", o["buyer_id"], order_id, po=o["po_no"], text=text)
    return mid


def last_by_order(db: sqlite3.Connection, order_ids: list[int]) -> dict[int, dict]:
    """The latest message of each order that has any: who wrote it and when."""
    if not order_ids:
        return {}
    marks = ",".join("?" * len(order_ids))
    rows = db.execute(
        f"""SELECT m.id AS mid, m.order_id, m.author, m.created_at, (SELECT COUNT(*) FROM order_messages x WHERE x.order_id = m.order_id) AS n
            FROM order_messages m WHERE m.id IN (SELECT MAX(id) FROM order_messages WHERE order_id IN ({marks}) GROUP BY order_id)""",
        order_ids,
    )
    return {r["order_id"]: {"id": r["mid"], "author": r["author"], "at": r["created_at"], "count": r["n"]} for r in rows}
