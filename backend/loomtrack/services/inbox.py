"""One inbox per side: every conversation in one list, and who has read what.

A conversation is the talk about an order (order_messages) or about a request that has not become an order
yet (request_messages). `thread_reads` remembers how far each side has read, which gives both the "unread"
marker for the reader and the "seen" mark the other side sees.
"""

from __future__ import annotations

import sqlite3

from ..util import HttpError

OPEN_REQUEST = ("submitted", "query", "countered")
_TABLE = {"order": ("order_messages", "order_id"), "request": ("request_messages", "request_id")}
_EVENT_TEXT = {
    "submitted": "Request submitted", "agreed": "Agreed to the proposed date", "accepted": "Request accepted",
    "declined": "Request declined", "withdrawn": "Request withdrawn",
}


def _top(db: sqlite3.Connection, kind: str, ref_id: int) -> int:
    table, col = _TABLE[kind]
    return db.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table} WHERE {col} = ?", (ref_id,)).fetchone()[0]  # names are the constants above


def seen_by(db: sqlite3.Connection, kind: str, ref_id: int, reader: str) -> int:
    row = db.execute("SELECT last_id FROM thread_reads WHERE kind = ? AND ref_id = ? AND reader = ?", (kind, ref_id, reader)).fetchone()
    return row["last_id"] if row else 0


def mark_read(db: sqlite3.Connection, kind: str, ref_id: int, reader: str) -> None:
    """The reader has opened the conversation up to its newest message."""
    if kind not in _TABLE or reader not in ("buyer", "merchandiser"):
        raise HttpError(400, "Unknown conversation")
    db.execute(
        """INSERT INTO thread_reads (kind, ref_id, reader, last_id) VALUES (?,?,?,?)
           ON CONFLICT(kind, ref_id, reader) DO UPDATE SET last_id = MAX(last_id, excluded.last_id), read_at = datetime('now')""",
        (kind, ref_id, reader, _top(db, kind, ref_id)),
    )


def other_read_up_to(db: sqlite3.Connection, kind: str, ref_id: int, reader: str) -> int:
    """How far the *other* side has read, so the reader can see which of their messages were seen."""
    return seen_by(db, kind, ref_id, "merchandiser" if reader == "buyer" else "buyer")


def _snippet(text: str | None, limit: int = 110) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def conversations(db: sqlite3.Connection, reader: str, buyer_id: int | None = None) -> list[dict]:
    """Every conversation that has something in it, the ones waiting on the reader first."""
    other = "merchandiser" if reader == "buyer" else "buyer"
    scope, args = ("AND o.buyer_id = ?", [buyer_id]) if buyer_id is not None else ("", [])
    items: list[dict] = []

    for r in db.execute(
        f"""SELECT m.id, m.order_id, m.author, m.body, m.created_at, o.po_no, o.style, b.name AS buyer,
              (SELECT COUNT(*) FROM order_messages x WHERE x.order_id = m.order_id) AS n
            FROM order_messages m JOIN orders o ON o.id = m.order_id JOIN buyers b ON b.id = o.buyer_id
            WHERE m.id IN (SELECT MAX(id) FROM order_messages GROUP BY order_id) AND o.state != 'cancelled' {scope}""",
        args,
    ):
        waiting = r["author"] == other
        items.append({
            "kind": "order", "id": r["order_id"], "title": r["po_no"], "subtitle": r["style"], "party": r["buyer"], "count": r["n"],
            "last": {"author": r["author"], "text": _snippet(r["body"]), "at": r["created_at"]},
            "turn": "you" if waiting else "them", "unread": waiting and r["id"] > seen_by(db, "order", r["order_id"], reader),
        })

    # A request that is still open has its own conversation; once it is an order its talk joins the order's.
    qscope, qargs = ("AND q.buyer_id = ?", [buyer_id]) if buyer_id is not None else ("", [])
    for r in db.execute(
        f"""SELECT m.id, m.request_id, m.author, m.event, m.body, m.proposed_ex_factory, m.created_at, q.po_no, q.style, q.status, q.request_no, b.name AS buyer,
              (SELECT COUNT(*) FROM request_messages x WHERE x.request_id = m.request_id) AS n
            FROM request_messages m JOIN order_requests q ON q.id = m.request_id JOIN buyers b ON b.id = q.buyer_id
            WHERE m.id IN (SELECT MAX(id) FROM request_messages GROUP BY request_id) AND q.status IN ('submitted','query','countered') {qscope}""",
        qargs,
    ):
        yours = r["status"] == "submitted" if reader == "merchandiser" else r["status"] in ("query", "countered")
        text = r["body"] or _EVENT_TEXT.get(r["event"]) or (f"Proposed {r['proposed_ex_factory']}" if r["event"] == "counter" else r["event"])
        waiting = r["author"] == other
        items.append({
            "kind": "request", "id": r["request_id"], "title": r["po_no"], "subtitle": f"{r['style']} · request {r['request_no']}", "party": r["buyer"], "count": r["n"],
            "last": {"author": r["author"], "text": _snippet(text), "at": r["created_at"]},
            "turn": "you" if yours else "them", "unread": waiting and r["id"] > seen_by(db, "request", r["request_id"], reader),
        })

    items.sort(key=lambda i: (not i["unread"], i["turn"] != "you", _neg(i["last"]["at"])))
    return items


def _neg(text: str) -> str:
    """Sort key that puts the newest first inside a tuple sort."""
    return "".join(chr(0x10FFFF - ord(c)) for c in text)


def unread_count(db: sqlite3.Connection, reader: str, buyer_id: int | None = None) -> int:
    return sum(1 for i in conversations(db, reader, buyer_id) if i["unread"])
