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
from . import capacity, notify
from .orders import fabric_fields, insert_order, set_ex_factory, validate_new_order

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


def find_request(db: sqlite3.Connection, rid: int, buyer_id: int | None = None) -> sqlite3.Row:
    """A request by id; with buyer_id, only that buyer's (anyone else's is 'not found')."""
    return _row(db, rid, buyer_id)


def require_open(r: sqlite3.Row) -> None:
    _require_open(r)


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


def _po(db: sqlite3.Connection, r: sqlite3.Row) -> str:
    """The PO number a request is about (a change request has its order's)."""
    if r["order_id"]:
        return db.execute("SELECT po_no FROM orders WHERE id = ?", (r["order_id"],)).fetchone()["po_no"]
    return r["po_no"]


def _tell_buyer(db: sqlite3.Connection, r: sqlite3.Row, event: str, order_id: int | None = None, **values) -> None:
    """Email (and WhatsApp) to the buyer's people; see services/notify.py."""
    notify.send(db, event, r["buyer_id"], order_id, request_no=r["request_no"], po=_po(db, r), **values)


def _tell_office(db: sqlite3.Connection, r: sqlite3.Row, event: str, **values) -> None:
    notify.send(db, event, r["buyer_id"], r["order_id"], request_no=r["request_no"], po=_po(db, r), **values)


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
        f"""SELECT r.*, b.name AS buyer_name, o.order_no,
              (SELECT COALESCE(SUM(qty), 0) FROM request_sizes s WHERE s.request_id = r.id) AS total_qty
            FROM order_requests r JOIN buyers b ON b.id = r.buyer_id LEFT JOIN orders o ON o.id = r.order_id
            WHERE {' AND '.join(where)} ORDER BY r.updated_at DESC, r.id DESC""",
        args,
    ).fetchall()
    return [
        {
            "id": r["id"], "requestNo": r["request_no"], "kind": r["kind"], "orderNo": r["order_no"], "buyer": r["buyer_name"], "poNo": r["po_no"],
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
        "fabric": {"type": r["fabric_type"], "composition": r["fabric_composition"], "gsm": r["fabric_gsm"], "note": r["fabric_note"]},
        "createdAt": r["created_at"], "updatedAt": r["updated_at"], "messages": messages,
        "orderNo": order["order_no"] if order else None,
    }
    if r["kind"] == "amendment" and r["status"] in OPEN:
        out["change"] = _change_summary(db, r, sizes)
    if buyer_id is None:
        out["buyer"] = db.execute("SELECT name FROM buyers WHERE id = ?", (r["buyer_id"],)).fetchone()["name"]
        out["buyerId"] = r["buyer_id"]
        out["orderId"] = r["order_id"]
    else:
        if r["order_id"]:
            out["orderId"] = r["order_id"]  # their own order, so the page can link to it once the request has become one
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
    fabric = fabric_fields(body)

    with transaction(db):
        rid = db.execute(
            """INSERT INTO order_requests (request_no, buyer_id, po_no, style, description, colour, colour_pantone, colour_hex, ex_factory,
                                           fabric_type, fabric_composition, fabric_gsm, fabric_note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (next_request_no(db, today), buyer_id, po, body.style.strip(), description, body.colour.strip(),
             (body.colourPantone or "").strip() or None, body.colourHex.upper() if body.colourHex else None, body.exFactory,
             fabric["type"], fabric["composition"], fabric["gsm"], fabric["note"]),
        ).lastrowid
        for n, (size, qty) in enumerate(sizes, start=1):
            db.execute("INSERT INTO request_sizes (request_id, seq, size, qty) VALUES (?,?,?,?)", (rid, n, size, qty))
        _log(db, rid, "buyer", None, "submitted", description)
        r = _row(db, rid)
        _tell_buyer(db, r, "request_received")
        _tell_office(db, r, "request_submitted", what="order request", text=description or f"Style {body.style.strip()}, {body.colour.strip()}, ex-factory {body.exFactory}.")
    return rid


def buyer_reply(db: sqlite3.Connection, buyer_id: int, rid: int, message: str) -> None:
    r = _row(db, rid, buyer_id)
    _require_open(r)
    text = _text(message, required=True, what="a message")
    with transaction(db):
        _log(db, rid, "buyer", None, "message", text)
        if r["status"] in ("query", "countered"):
            _set_status(db, rid, "submitted")  # answered: back to the merchandiser
        _tell_office(db, r, "buyer_reply", text=text)


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
        _tell_office(db, r, "buyer_reply", text=f"Agreed to the ex-factory date {proposed}.")


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
        _tell_buyer(db, r, "request_question", text=text)


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
        _tell_buyer(db, r, "request_counter", date=ex_factory, text=text)


def office_decline(db: sqlite3.Connection, user_id: int, rid: int, message: str) -> None:
    r = _row(db, rid)
    _require_open(r)
    text = _text(message, required=True, what="a reason")
    with transaction(db):
        _log(db, rid, "merchandiser", user_id, "declined", text)
        _set_status(db, rid, "declined", decided_by=user_id)
        _tell_buyer(db, r, "request_declined", text=text)


def office_accept(db: sqlite3.Connection, user_id: int, rid: int, unit_id: int | None, template_key: str | None, message: str | None, today: str,
                  over_capacity_ok: bool = False) -> tuple[int, str]:
    """Turn a new-order request into an order, planned from the chosen template and unit."""
    r = _row(db, rid)
    _require_open(r)
    note = _text(message, required=False, what="the note")
    if r["kind"] == "amendment":
        with transaction(db):
            summary = _apply_change(db, r, user_id, today)
            text = note or f"Accepted. {summary}."
            _log(db, rid, "merchandiser", user_id, "accepted", text)
            _set_status(db, rid, "accepted", decided_by=user_id)
            _tell_buyer(db, r, "change_accepted", r["order_id"], text=text)
        return r["order_id"], db.execute("SELECT order_no FROM orders WHERE id = ?", (r["order_id"],)).fetchone()["order_no"]
    if unit_id is None or not template_key:
        raise HttpError(400, "Pick the production unit and the plan template")
    body = SimpleNamespace(
        poNo=r["po_no"], buyerId=r["buyer_id"], style=r["style"], colour=r["colour"], colourHex=r["colour_hex"],
        colourPantone=r["colour_pantone"], exFactory=r["ex_factory"], unitId=unit_id, templateKey=template_key, milestones=None,
        fabricType=r["fabric_type"], fabricComposition=r["fabric_composition"], fabricGsm=r["fabric_gsm"], fabricNote=r["fabric_note"],
        sizes=[SimpleNamespace(size=s["size"], qty=s["qty"]) for s in db.execute("SELECT size, qty FROM request_sizes WHERE request_id = ? ORDER BY seq", (rid,))],
    )
    t = validate_new_order(db, body, today)
    capacity.guard(db, unit_id, sum(s.qty for s in body.sizes), r["ex_factory"], t, today, over_capacity_ok)
    with transaction(db):
        order_id, order_no = insert_order(db, body, t, user_id, today)
        db.execute("UPDATE order_requests SET order_id = ? WHERE id = ?", (order_id, rid))
        db.execute("UPDATE attachments SET order_id = ? WHERE request_id = ?", (order_id, rid))  # the files follow it onto the order
        text = note or f"Accepted. Your order with us is {order_no}, for ex-factory {r['ex_factory']}."
        _log(db, rid, "merchandiser", user_id, "accepted", text)
        _set_status(db, rid, "accepted", decided_by=user_id)
        _tell_buyer(db, r, "request_accepted", order_id, order_no=order_no, text=text)
    return order_id, order_no


# --- Changes to an order that already exists (amendments) -------------------------------------


def _order_open_for_change(db: sqlite3.Connection, order_id: int, buyer_id: int | None = None) -> sqlite3.Row:
    sql, args = "SELECT * FROM orders WHERE id = ?", [order_id]
    if buyer_id is not None:
        sql, args = sql + " AND buyer_id = ?", [order_id, buyer_id]
    o = db.execute(sql, args).fetchone()
    if o is None:
        raise HttpError(404, "Order not found")
    if o["state"] != "active":
        raise HttpError(409, "This order is no longer open for changes")
    return o


def _order_sizes(db: sqlite3.Connection, order_id: int) -> list[tuple[str, int]]:
    return [(r["size"], r["qty"]) for r in db.execute("SELECT size, qty FROM order_sizes WHERE order_id = ? ORDER BY seq", (order_id,))]


def _clean_sizes(sizes) -> list[tuple[str, int]]:
    out = [(s.size.strip().upper(), s.qty) for s in sizes if s.size.strip() and s.qty > 0]
    if not out:
        raise HttpError(400, "The quantities add up to zero")
    if len({s for s, _ in out}) != len(out):
        raise HttpError(400, "A size is listed twice")
    return out


def _change_summary(db: sqlite3.Connection, r: sqlite3.Row, requested: list[dict]) -> dict:
    o = db.execute("SELECT order_no, ex_factory FROM orders WHERE id = ?", (r["order_id"],)).fetchone()
    current = [{"size": s, "qty": q} for s, q in _order_sizes(db, r["order_id"])]
    return {
        "orderNo": o["order_no"],
        "current": {"exFactory": o["ex_factory"], "sizes": current, "totalQty": sum(s["qty"] for s in current)},
        "dateChanged": r["ex_factory"] != o["ex_factory"],
        "qtyChanged": [(s["size"], s["qty"]) for s in requested] != [(s["size"], s["qty"]) for s in current],
    }


def _create_amendment(db: sqlite3.Connection, o: sqlite3.Row, ex_factory: str | None, sizes, reason: str, author: str, user_id: int | None, today: str) -> int:
    """Insert the amendment request. Call inside a transaction. Only the changed parts differ from the order."""
    new_date = ex_factory or o["ex_factory"]
    cur = _order_sizes(db, o["id"])
    new_sizes = _clean_sizes(sizes) if sizes is not None else cur
    if new_date == o["ex_factory"] and new_sizes == cur:
        raise HttpError(400, "That is what the order already says. Change the date or a quantity.")
    if new_date != o["ex_factory"] and new_date <= today:
        raise HttpError(400, "The new date must be in the future")
    if db.execute("SELECT 1 FROM order_requests WHERE order_id = ? AND kind = 'amendment' AND status IN ('submitted','query','countered')", (o["id"],)).fetchone():
        raise HttpError(409, "There is already an open change request for this order")
    rid = db.execute(
        """INSERT INTO order_requests (request_no, kind, buyer_id, order_id, po_no, style, description, colour, colour_pantone, colour_hex, ex_factory)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (next_request_no(db, today), "amendment", o["buyer_id"], o["id"], o["po_no"], o["style"], reason, o["colour"],
         o["colour_pantone"], o["colour_hex"], new_date),
    ).lastrowid
    for n, (size, qty) in enumerate(new_sizes, start=1):
        db.execute("INSERT INTO request_sizes (request_id, seq, size, qty) VALUES (?,?,?,?)", (rid, n, size, qty))
    _log(db, rid, author, user_id, "submitted", reason)
    return rid


def submit_amendment(db: sqlite3.Connection, buyer_id: int, order_id: int, body, today: str) -> int:
    o = _order_open_for_change(db, order_id, buyer_id)
    reason = _text(body.reason, required=True, what="the reason for the change", limit=1000)
    if db.execute("SELECT COUNT(*) FROM order_requests WHERE buyer_id = ? AND status IN ('submitted','query','countered')", (buyer_id,)).fetchone()[0] >= MAX_OPEN_PER_BUYER:
        raise HttpError(429, "You have too many open requests. Wait for some to be answered.")
    with transaction(db):
        rid = _create_amendment(db, o, body.exFactory, body.sizes, reason, "buyer", None, today)
        _tell_office(db, _row(db, rid), "request_submitted", what="change request", text=reason)
        return rid


def _apply_change(db: sqlite3.Connection, r: sqlite3.Row, user_id: int, today: str) -> str:
    """Put an amendment's date and quantities on the order. Call inside a transaction; returns what changed."""
    o = _order_open_for_change(db, r["order_id"])
    parts = []
    if r["ex_factory"] != o["ex_factory"]:
        if r["ex_factory"] <= today:
            raise HttpError(409, "That date has passed. Ask the buyer for a new one.")
        set_ex_factory(db, o["id"], r["ex_factory"], f"Change {r['request_no']}: {r['description'] or 'agreed with the buyer'}", user_id)
        parts.append(f"ex-factory {o['ex_factory']} to {r['ex_factory']}")
    new_sizes = [(s["size"], s["qty"]) for s in db.execute("SELECT size, qty FROM request_sizes WHERE request_id = ? ORDER BY seq", (r["id"],))]
    old_sizes = _order_sizes(db, o["id"])
    if new_sizes != old_sizes:
        total = sum(q for _, q in new_sizes)
        made = db.execute(
            """SELECT COALESCE(MAX(t), 0) FROM (SELECT SUM(d.qty) AS t FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id
               WHERE m.order_id = ? GROUP BY m.id)""", (o["id"],)).fetchone()[0]
        if total < made:
            raise HttpError(409, f"{made:,} pieces are already made at the furthest stage, so the quantity cannot go below that")
        db.execute("DELETE FROM order_sizes WHERE order_id = ?", (o["id"],))
        for n, (size, qty) in enumerate(new_sizes, start=1):
            db.execute("INSERT INTO order_sizes (order_id, seq, size, qty) VALUES (?,?,?,?)", (o["id"], n, size, qty))
        db.execute("UPDATE orders SET qty_total = ? WHERE id = ?", (total, o["id"]))
        parts.append(f"quantity {o['qty_total']:,} to {total:,}")
    return " and ".join(parts).capitalize() if parts else "Nothing needed changing"


def office_record_change(db: sqlite3.Connection, user_id: int, order_id: int, ex_factory: str | None, sizes, reason: str, today: str) -> int:
    """The buyer asked outside the app (email, phone): record the change and apply it in one step,
    with the same trail as a request. The buyer sees it under their requests."""
    o = _order_open_for_change(db, order_id)
    text = _text(reason, required=True, what="what the buyer asked for", limit=1000)
    with transaction(db):
        rid = _create_amendment(db, o, ex_factory, sizes, text, "merchandiser", user_id, today)
        r = _row(db, rid)
        summary = _apply_change(db, r, user_id, today)
        _log(db, rid, "merchandiser", user_id, "accepted", f"Recorded and applied. {summary}.")
        _set_status(db, rid, "accepted", decided_by=user_id)
        _tell_buyer(db, r, "change_recorded", order_id, summary=f"{summary}.", text=text)
    return rid
