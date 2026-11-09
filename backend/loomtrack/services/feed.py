"""The notifications page: what the app has told each side, kept in the app as well as sent by email.

Nothing new is stored for it. Every email the app sends is already recorded in `outbox_messages`, so the page
reads that, one entry per event (not one per recipient or channel). Only the "last seen" mark is stored.
"""

from __future__ import annotations

import re
import sqlite3

LIMIT = 100
# Conversations between buyer and merchandiser are gone, so their notices are not shown either.
_HIDDEN = ("order_message", "order_message_in")
_TOPIC = {
    "request_received": "Request", "request_question": "Request", "request_counter": "Request", "request_declined": "Request",
    "request_accepted": "Request", "request_submitted": "Request", "buyer_reply": "Request", "change_accepted": "Change",
    "change_recorded": "Change", "delay_notice": "Delay", "notice_acknowledged": "Delay", "order_cancelled": "Order",
    "supervisor_reported": "Floor", "approval_requested": "Approval", "approval_resubmitted": "Approval", "approval_decided": "Approval",
}


def _plain(body: str) -> str:
    """The message without the email greeting and sign-off."""
    body = re.sub(r"^Hello [^\n]*,\n\n", "", body)
    body = re.sub(r"\n\nOpen LoomTrack: .*$", "", body, flags=re.S)
    return body.strip()


def items(db: sqlite3.Connection, audience: str, buyer_id: int | None = None) -> list[dict]:
    where = f"m.audience = ? AND m.channel = 'email' AND m.event IS NOT NULL AND m.event NOT IN ({','.join('?' * len(_HIDDEN))})"
    args: list = [audience, *_HIDDEN]
    if buyer_id is not None:
        where += " AND m.buyer_id = ?"
        args.append(buyer_id)
    rows = db.execute(
        f"""SELECT MIN(m.id) AS id, m.event, m.order_id, m.subject, m.body, m.created_at, b.id AS buyer_id, b.name AS buyer_name, o.po_no
            FROM outbox_messages m JOIN buyers b ON b.id = m.buyer_id LEFT JOIN orders o ON o.id = m.order_id
            WHERE {where} GROUP BY m.buyer_id, m.event, m.order_id, m.subject, m.created_at ORDER BY id DESC LIMIT {LIMIT}""",
        args,
    ).fetchall()
    return [
        {"id": r["id"], "event": r["event"], "topic": _TOPIC.get(r["event"], "Update"), "title": r["subject"], "text": _plain(r["body"]),
         "at": r["created_at"], "orderId": r["order_id"], "poNo": r["po_no"], "buyerId": r["buyer_id"], "buyerName": r["buyer_name"]}
        for r in rows
    ]


def seen_up_to(db: sqlite3.Connection, reader: str, ref_id: int) -> int:
    row = db.execute("SELECT last_id FROM feed_reads WHERE reader = ? AND ref_id = ?", (reader, ref_id)).fetchone()
    return row["last_id"] if row else 0


def mark_seen(db: sqlite3.Connection, reader: str, ref_id: int, audience: str, buyer_id: int | None = None) -> None:
    newest = max((i["id"] for i in items(db, audience, buyer_id)), default=0)
    db.execute(
        """INSERT INTO feed_reads (reader, ref_id, last_id) VALUES (?,?,?)
           ON CONFLICT(reader, ref_id) DO UPDATE SET last_id = MAX(last_id, excluded.last_id), read_at = datetime('now')""",
        (reader, ref_id, newest),
    )


def unread_count(db: sqlite3.Connection, reader: str, ref_id: int, audience: str, buyer_id: int | None = None) -> int:
    seen = seen_up_to(db, reader, ref_id)
    return sum(1 for i in items(db, audience, buyer_id) if i["id"] > seen)
