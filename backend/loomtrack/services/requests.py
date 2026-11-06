"""Order requests: a buyer asks for an order; the merchandiser asks a question, counters, accepts or declines.

The status says whose turn it is: `submitted` is the merchandiser's, `query` and `countered` are the
buyer's. Every step is also a row in request_messages (append-only), which both sides see as the history.
What the buyer asked for or agreed to is exactly what the accepted order gets: a different date goes
through a counter-proposal the buyer agrees to, never a silent change.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from ..db import transaction
from ..util import HttpError
from .orders import insert_order, validate_new_order

OPEN = ("submitted", "query", "countered")
MAX_OPEN_PER_BUYER = 25
FILTERS = {
    "mine": ("submitted",),
    "waiting": ("query", "countered"),
    "closed": ("accepted", "declined", "withdrawn"),
    "all": ("submitted", "query", "countered", "accepted", "declined", "withdrawn"),
}


def next_request_no(db: sqlite3.Connection, today: str) -> str:
    prefix = f"RQ-{today[:4]}-"
    n = db.execute(
        "SELECT MAX(CAST(substr(request_no, ?) AS INTEGER)) FROM order_requests WHERE request_no LIKE ?", (len(prefix) + 1, prefix + "%")
    ).fetchone()[0]
    return f"{prefix}{(n or 0) + 1:04d}"


def _row(db: sqlite3.Connection, rid: int, buyer_id: int | None = None) -> sqlite3.Row:
    """A request by id. With buyer_id, only that buyer's: another buyer's request is simply not found."""
    sql, args = "SELECT * FROM order_requests WHERE id = ?", [rid]
    if buyer_id is not None:
        sql, args = sql + " AND buyer_id = ?", [rid, buyer_id]
    r = db.execute(sql, args).fetchone()
    if r is None:
        raise HttpError(404, "Request not found")
    return r


def _require_open(r: sqlite3.Row) -> None:
    if r["status"] not in OPEN:
        raise HttpError(409, f"This request is already {r['status']}")


def _text(value: str | None, *, required: bool, what: str, limit: int = 2000) -> str | None:
    value = (value or "").strip()
    if required and not value:
        raise HttpError(400, f"Write {what}")
    if len(value) > limit:
        raise HttpError(400, f"Keep {what} under {limit} characters")
    return value or None


def _log(db: sqlite3.Connection, rid: int, author: str, user_id: int | None, event: str, body: str | None = None, proposed: str | None = None) -> None:
    db.execute(
        "INSERT INTO request_messages (request_id, author, user_id, event, body, proposed_ex_factory) VALUES (?,?,?,?,?,?)",
        (rid, author, user_id, event, body, proposed),
    )
    db.execute("UPDATE order_requests SET updated_at = datetime('now') WHERE id = ?", (rid,))


def _set_status(db: sqlite3.Connection, rid: int, status: str, decided_by: int | None = None) -> None:
    db.execute(
        "UPDATE order_requests SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, rid)
    )
    if decided_by is not None:
        db.execute("UPDATE order_requests SET decided_by = ?, decided_at = datetime('now') WHERE id = ?", (decided_by, rid))


def _email(db: sqlite3.Connection, r: sqlite3.Row, subject: str, body: str, order_id: int | None = None) -> None:
    """Mock email to the buyer (the outbox is shown in the office, like warnings)."""
    db.execute(
        "INSERT INTO outbox_messages (buyer_id, order_id, channel, subject, body) VALUES (?,?,?,?,?)",
        (r["buyer_id"], order_id, "email", f"{subject} ({r['request_no']})", body),
    )


# --- Reading -------------------------------------------------------------------------


def list_requests(db: sqlite3.Connection, buyer_id: int | None = None, flt: str = "all") -> list[dict]:
    statuses = FILTERS.get(flt)
    if statuses is None:
        raise HttpError(400, "Unknown filter")
    where, args = [f"r.status IN ({','.join('?' * len(statuses))})"], list(statuses)
    if buyer_id is not None:
        where.append("r.buyer_id = ?")
        args.append(buyer_id)
    rows = db.execute(
        f"""SELECT r.*, b.name AS buyer_name,
              (SELECT COALESCE(SUM(qty), 0) FROM request_sizes s WHERE s.request_id = r.id) AS total_qty
            FROM order_requests r JOIN buyers b ON b.id = r.buyer_id
            WHERE {' AND '.join(where)} ORDER BY r.updated_at DESC, r.id DESC""",
        args,
    ).fetchall()
    return [
        {
            "id": r["id"], "requestNo": r["request_no"], "kind": r["kind"], "buyer": r["buyer_name"], "poNo": r["po_no"],
            "style": r["style"], "colour": r["colour"], "colourHex": r["colour_hex"], "exFactory": r["ex_factory"],
            "totalQty": r["total_qty"], "status": r["status"], "updatedAt": r["updated_at"], "createdAt": r["created_at"],
        }
        for r in rows
    ]


def request_detail(db: sqlite3.Connection, rid: int, buyer_id: int | None = None) -> dict:
    """buyer_id given = the buyer's view (their own request only, no internal names or ids)."""
    r = _row(db, rid, buyer_id)
    sizes = [dict(s) for s in db.execute("SELECT size, qty FROM request_sizes WHERE request_id = ? ORDER BY seq", (rid,))]
    messages = [
        {"author": m["author"], "event": m["event"], "body": m["body"], "proposedExFactory": m["proposed_ex_factory"], "at": m["created_at"]}
        for m in db.execute(
            "SELECT author, event, body, proposed_ex_factory, created_at FROM request_messages WHERE request_id = ? ORDER BY id", (rid,)
        )
    ]
    order = db.execute("SELECT order_no FROM orders WHERE id = ?", (r["order_id"],)).fetchone() if r["order_id"] else None
    out = {
        "id": r["id"], "requestNo": r["request_no"], "kind": r["kind"], "poNo": r["po_no"], "style": r["style"],
        "description": r["description"], "colour": r["colour"], "colourHex": r["colour_hex"], "colourPantone": r["colour_pantone"],
        "exFactory": r["ex_factory"], "status": r["status"], "sizes": sizes, "totalQty": sum(s["qty"] for s in sizes),
        "createdAt": r["created_at"], "updatedAt": r["updated_at"], "messages": messages,
        "orderNo": order["order_no"] if order else None,
    }
    if buyer_id is None:
        out["buyer"] = db.execute("SELECT name FROM buyers WHERE id = ?", (r["buyer_id"],)).fetchone()["name"]
        out["orderId"] = r["order_id"]
    else:
        out["canReply"] = r["status"] in OPEN
        out["canAgree"] = r["status"] == "countered"
        out["canWithdraw"] = r["status"] in OPEN
    return out


def open_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM order_requests WHERE status = 'submitted'").fetchone()[0]


# --- Buyer actions ------------------------------------------------------------------------


def submit_request(db: sqlite3.Connection, buyer_id: int, body, today: str) -> int:
    po = body.poNo.strip()
    if body.exFactory <= today:
        raise HttpError(400, "The date you need it by must be in the future")
    sizes = [(s.size.strip().upper(), s.qty) for s in body.sizes if s.size.strip() and s.qty > 0]
    if not sizes:
        raise HttpError(400, "Enter at least one size quantity")
    if len({s for s, _ in sizes}) != len(sizes):
        raise HttpError(400, "A size is listed twice")
    if db.execute("SELECT 1 FROM orders WHERE po_no = ? AND buyer_id = ?", (po, buyer_id)).fetchone():
        raise HttpError(409, f"You already have an order with PO number {po}")
    if db.execute(
        "SELECT 1 FROM order_requests WHERE po_no = ? AND buyer_id = ? AND kind = 'new_order' AND status IN ('submitted','query','countered')", (po, buyer_id)
    ).fetchone():
        raise HttpError(409, f"You already have an open request with PO number {po}")
    if db.execute("SELECT COUNT(*) FROM order_requests WHERE buyer_id = ? AND status IN ('submitted','query','countered')", (buyer_id,)).fetchone()[0] >= MAX_OPEN_PER_BUYER:
        raise HttpError(429, "You have too many open requests. Wait for some to be answered.")
    description = _text(body.description, required=False, what="the description", limit=1000)

    with transaction(db):
        rid = db.execute(
            """INSERT INTO order_requests (request_no, buyer_id, po_no, style, description, colour, colour_pantone, colour_hex, ex_factory)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (next_request_no(db, today), buyer_id, po, body.style.strip(), description, body.colour.strip(),
             (body.colourPantone or "").strip() or None, body.colourHex.upper() if body.colourHex else None, body.exFactory),
        ).lastrowid
        for n, (size, qty) in enumerate(sizes, start=1):
            db.execute("INSERT INTO request_sizes (request_id, seq, size, qty) VALUES (?,?,?,?)", (rid, n, size, qty))
        _log(db, rid, "buyer", None, "submitted", description)
    return rid


def buyer_reply(db: sqlite3.Connection, buyer_id: int, rid: int, message: str) -> None:
    r = _row(db, rid, buyer_id)
    _require_open(r)
    text = _text(message, required=True, what="a message")
    with transaction(db):
        _log(db, rid, "buyer", None, "message", text)
        if r["status"] in ("query", "countered"):
            _set_status(db, rid, "submitted")  # answered: back to the merchandiser


def buyer_agree(db: sqlite3.Connection, buyer_id: int, rid: int, today: str) -> None:
    r = _row(db, rid, buyer_id)
    if r["status"] != "countered":
        raise HttpError(409, "There is no proposal to agree to")
    proposed = db.execute(
        "SELECT proposed_ex_factory FROM request_messages WHERE request_id = ? AND event = 'counter' ORDER BY id DESC LIMIT 1", (rid,)
    ).fetchone()["proposed_ex_factory"]
    if proposed <= today:
        raise HttpError(409, "That date has passed. Ask for a new proposal.")
    with transaction(db):
        db.execute("UPDATE order_requests SET ex_factory = ? WHERE id = ?", (proposed, rid))
        _log(db, rid, "buyer", None, "agreed", None, proposed)
        _set_status(db, rid, "submitted")


def buyer_withdraw(db: sqlite3.Connection, buyer_id: int, rid: int) -> None:
    r = _row(db, rid, buyer_id)
    _require_open(r)
    with transaction(db):
        _log(db, rid, "buyer", None, "withdrawn")
        _set_status(db, rid, "withdrawn")


# --- Merchandiser actions -----------------------------------------------------------------


def office_query(db: sqlite3.Connection, user_id: int, rid: int, message: str) -> None:
    r = _row(db, rid)
    _require_open(r)
    text = _text(message, required=True, what="your question")
    with transaction(db):
        _log(db, rid, "merchandiser", user_id, "query", text)
        _set_status(db, rid, "query")
        _email(db, r, "A question about your order request", text)


def office_counter(db: sqlite3.Connection, user_id: int, rid: int, ex_factory: str, message: str, today: str) -> None:
    r = _row(db, rid)
    _require_open(r)
    if ex_factory <= today:
        raise HttpError(400, "Propose a date in the future")
    if ex_factory == r["ex_factory"]:
        raise HttpError(400, "That is the date the buyer already asked for. Accept the request instead.")
    text = _text(message, required=True, what="a reason for the new date")
    with transaction(db):
        _log(db, rid, "merchandiser", user_id, "counter", text, ex_factory)
        _set_status(db, rid, "countered")
        _email(db, r, "A different delivery date is proposed", f"{text}\n\nProposed ex-factory date: {ex_factory}")


def office_decline(db: sqlite3.Connection, user_id: int, rid: int, message: str) -> None:
    r = _row(db, rid)
    _require_open(r)
    text = _text(message, required=True, what="a reason")
    with transaction(db):
        _log(db, rid, "merchandiser", user_id, "declined", text)
        _set_status(db, rid, "declined", decided_by=user_id)
        _email(db, r, "Your order request was declined", text)


def office_accept(db: sqlite3.Connection, user_id: int, rid: int, unit_id: int, template_key: str, message: str | None, today: str) -> tuple[int, str]:
    """Turn a new-order request into an order, planned from the chosen template and unit."""
    r = _row(db, rid)
    _require_open(r)
    if r["kind"] != "new_order":
        raise HttpError(400, "This request changes an existing order")
    note = _text(message, required=False, what="the note")
    body = SimpleNamespace(
        poNo=r["po_no"], buyerId=r["buyer_id"], style=r["style"], colour=r["colour"], colourHex=r["colour_hex"],
        colourPantone=r["colour_pantone"], exFactory=r["ex_factory"], unitId=unit_id, templateKey=template_key, milestones=None,
        sizes=[SimpleNamespace(size=s["size"], qty=s["qty"]) for s in db.execute("SELECT size, qty FROM request_sizes WHERE request_id = ? ORDER BY seq", (rid,))],
    )
    t = validate_new_order(db, body, today)
    with transaction(db):
        order_id, order_no = insert_order(db, body, t, user_id, today)
        db.execute("UPDATE order_requests SET order_id = ? WHERE id = ?", (order_id, rid))
        text = note or f"Accepted. Your order with us is {order_no}, for ex-factory {r['ex_factory']}."
        _log(db, rid, "merchandiser", user_id, "accepted", text)
        _set_status(db, rid, "accepted", decided_by=user_id)
        _email(db, r, "Your order request was accepted", f"{text}\n\nOrder number: {order_no}", order_id)
    return order_id, order_no
