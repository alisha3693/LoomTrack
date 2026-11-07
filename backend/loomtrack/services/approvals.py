"""Buyer approvals: samples, lab dips and packaging the buyer has to sign off before work goes on.

The office asks, the buyer approves or asks for changes (with a reason), the office answers and asks again.
Every step is kept in approval_events and cannot be edited. Approving a fit or pre-production sample also
marks the matching plan step done, and that goes into the date history like any other change.
"""

from __future__ import annotations

import sqlite3

from ..db import transaction
from ..util import HttpError
from . import notify

KIND_LABEL = {
    "fit_sample": "Fit sample", "pp_sample": "Pre-production sample", "lab_dip": "Lab dip / colour",
    "packaging": "Packaging", "other": "Something else",
}
DEFAULT_STEP = {"fit_sample": "FIT", "pp_sample": "PP"}
ACTION_TEXT = {
    "requested": "Approval requested", "resubmitted": "Sent again", "approved": "Approved",
    "changes": "Changes requested", "withdrawn": "Withdrawn",
}


def _text(value: str | None, *, required: bool, what: str, low: int = 1, limit: int = 2000) -> str | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise HttpError(400, f"Write {what}")
        return None
    if len(text) < low:
        raise HttpError(400, f"Write a little more for {what}")
    if len(text) > limit:
        raise HttpError(400, f"Keep {what} under {limit} characters")
    return text


def _row(db: sqlite3.Connection, approval_id: int, buyer_id: int | None = None) -> sqlite3.Row:
    r = db.execute(
        """SELECT a.*, o.po_no, o.style, o.buyer_id, o.state, b.name AS buyer FROM approvals a
           JOIN orders o ON o.id = a.order_id JOIN buyers b ON b.id = o.buyer_id WHERE a.id = ?""",
        (approval_id,),
    ).fetchone()
    if r is None or (buyer_id is not None and (r["buyer_id"] != buyer_id or r["state"] == "cancelled")):
        raise HttpError(404, "Approval not found")
    return r


def _event(db: sqlite3.Connection, approval_id: int, actor: str, user_id: int | None, action: str, note: str | None) -> None:
    db.execute("INSERT INTO approval_events (approval_id, actor, user_id, action, note) VALUES (?,?,?,?,?)", (approval_id, actor, user_id, action, note))


def _show(db: sqlite3.Connection, r: sqlite3.Row, audience: str) -> dict:
    events = [
        {"actor": e["actor"], "action": e["action"], "text": ACTION_TEXT[e["action"]], "note": e["note"], "at": e["created_at"]}
        for e in db.execute("SELECT actor, action, note, created_at FROM approval_events WHERE approval_id = ? ORDER BY id", (r["id"],))
    ]
    step = db.execute("SELECT name_en FROM plan_steps WHERE code = ?", (r["milestone_code"],)).fetchone() if r["milestone_code"] else None
    out = {
        "id": r["id"], "orderId": r["order_id"], "poNo": r["po_no"], "style": r["style"], "kind": r["kind"], "kindLabel": KIND_LABEL[r["kind"]],
        "title": r["title"], "note": r["note"], "status": r["status"], "requestedAt": r["requested_at"], "decidedAt": r["decided_at"],
        "completesStep": step["name_en"] if step else None, "events": events,
    }
    if audience == "office":
        out["buyer"] = r["buyer"]
        out["buyerSeenAt"] = r["buyer_seen_at"]
    return out


def request_approval(db: sqlite3.Connection, order_id: int, user_id: int, kind: str, title: str, note: str | None) -> int:
    if kind not in KIND_LABEL:
        raise HttpError(400, "Choose what needs approving")
    o = db.execute("SELECT id, buyer_id, po_no, state FROM orders WHERE id = ?", (order_id,)).fetchone()
    if o is None:
        raise HttpError(404, "Order not found")
    if o["state"] != "active":
        raise HttpError(409, "This order is no longer in production")
    title = _text(title, required=True, what="what the buyer is approving", limit=120)
    note = _text(note, required=False, what="the note")
    if db.execute("SELECT 1 FROM approvals WHERE order_id = ? AND kind = ? AND status IN ('requested','changes')", (order_id, kind)).fetchone():
        raise HttpError(409, f"There is already an open approval for this {KIND_LABEL[kind].lower()}")
    code = DEFAULT_STEP.get(kind)
    if code and not db.execute("SELECT 1 FROM milestones WHERE order_id = ? AND code = ?", (order_id, code)).fetchone():
        code = None
    with transaction(db):
        aid = db.execute("INSERT INTO approvals (order_id, kind, title, note, milestone_code) VALUES (?,?,?,?,?)", (order_id, kind, title, note, code)).lastrowid
        _event(db, aid, "merchandiser", user_id, "requested", note)
        notify.send(db, "approval_requested", o["buyer_id"], order_id, title=title, po=o["po_no"], text=note or "")
    return aid


def resubmit(db: sqlite3.Connection, approval_id: int, user_id: int, note: str | None) -> None:
    r = _row(db, approval_id)
    if r["status"] != "changes":
        raise HttpError(409, "Only an approval the buyer asked changes on can be sent again")
    note = _text(note, required=True, what="what you changed")
    with transaction(db):
        db.execute("UPDATE approvals SET status = 'requested', decided_at = NULL, buyer_seen_at = NULL WHERE id = ?", (approval_id,))
        _event(db, approval_id, "merchandiser", user_id, "resubmitted", note)
        notify.send(db, "approval_resubmitted", r["buyer_id"], r["order_id"], title=r["title"], po=r["po_no"], text=note)


def withdraw(db: sqlite3.Connection, approval_id: int, user_id: int) -> None:
    r = _row(db, approval_id)
    if r["status"] not in ("requested", "changes"):
        raise HttpError(409, "This approval is already closed")
    with transaction(db):
        db.execute("UPDATE approvals SET status = 'withdrawn', decided_at = datetime('now') WHERE id = ?", (approval_id,))
        _event(db, approval_id, "merchandiser", user_id, "withdrawn", None)


def decide(db: sqlite3.Connection, buyer_id: int, approval_id: int, approve: bool, comment: str | None, today: str) -> None:
    r = _row(db, approval_id, buyer_id)
    if r["status"] != "requested":
        raise HttpError(409, "This approval is not waiting for you")
    note = _text(comment, required=not approve, what="what needs to change", low=3)
    with transaction(db):
        db.execute("UPDATE approvals SET status = ?, decided_at = datetime('now') WHERE id = ?", ("approved" if approve else "changes", approval_id))
        _event(db, approval_id, "buyer", None, "approved" if approve else "changes", note)
        notify.send(db, "approval_decided", buyer_id, r["order_id"], title=r["title"], po=r["po_no"],
                    outcome="approved" if approve else "asked for changes", text=note or "")
        if approve and r["milestone_code"]:
            m = db.execute("SELECT id, actual_date FROM milestones WHERE order_id = ? AND code = ?", (r["order_id"], r["milestone_code"])).fetchone()
            if m and m["actual_date"] is None:
                db.execute("UPDATE milestones SET actual_date = ? WHERE id = ?", (today, m["id"]))
                db.execute(
                    "INSERT INTO date_changes (order_id, milestone_id, field, old_value, new_value, reason, changed_by) VALUES (?,?,?,?,?,?,NULL)",
                    (r["order_id"], m["id"], "actual_date", None, today, f"Marked done: approved by the buyer ({r['title']})"),
                )


def mark_seen(db: sqlite3.Connection, buyer_id: int) -> None:
    """The buyer has opened their approvals page: everything waiting for them there counts as seen."""
    db.execute(
        """UPDATE approvals SET buyer_seen_at = datetime('now') WHERE status = 'requested' AND buyer_seen_at IS NULL
           AND order_id IN (SELECT id FROM orders WHERE buyer_id = ?)""",
        (buyer_id,),
    )


_ORDER = "CASE a.status WHEN 'changes' THEN 0 WHEN 'requested' THEN 1 ELSE 2 END, a.id DESC"


def for_order(db: sqlite3.Connection, order_id: int, audience: str = "office") -> list[dict]:
    rows = db.execute(
        f"""SELECT a.*, o.po_no, o.style, o.buyer_id, o.state, b.name AS buyer FROM approvals a
            JOIN orders o ON o.id = a.order_id JOIN buyers b ON b.id = o.buyer_id WHERE a.order_id = ? ORDER BY {_ORDER}""",
        (order_id,),
    ).fetchall()
    return [_show(db, r, audience) for r in rows]


def for_buyer(db: sqlite3.Connection, buyer_id: int) -> list[dict]:
    rows = db.execute(
        f"""SELECT a.*, o.po_no, o.style, o.buyer_id, o.state, b.name AS buyer FROM approvals a
            JOIN orders o ON o.id = a.order_id JOIN buyers b ON b.id = o.buyer_id
            WHERE o.buyer_id = ? AND o.state != 'cancelled' ORDER BY CASE a.status WHEN 'requested' THEN 0 WHEN 'changes' THEN 1 ELSE 2 END, a.id DESC""",
        (buyer_id,),
    ).fetchall()
    return [_show(db, r, "buyer") for r in rows]


def for_office(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        f"""SELECT a.*, o.po_no, o.style, o.buyer_id, o.state, b.name AS buyer FROM approvals a
            JOIN orders o ON o.id = a.order_id JOIN buyers b ON b.id = o.buyer_id WHERE o.state != 'cancelled' ORDER BY {_ORDER}""",
    ).fetchall()
    return [_show(db, r, "office") for r in rows]


def to_answer(db: sqlite3.Connection) -> int:
    """Approvals where the buyer asked for changes: the office has to answer."""
    return db.execute(
        "SELECT COUNT(*) FROM approvals a JOIN orders o ON o.id = a.order_id WHERE a.status = 'changes' AND o.state = 'active'"
    ).fetchone()[0]


def to_decide(db: sqlite3.Connection, buyer_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM approvals a JOIN orders o ON o.id = a.order_id WHERE a.status = 'requested' AND o.buyer_id = ? AND o.state != 'cancelled'",
        (buyer_id,),
    ).fetchone()[0]


def open_by_order(db: sqlite3.Connection) -> dict[int, dict]:
    """For the board: per order, how many approvals wait on the buyer and how many the buyer sent back."""
    out: dict[int, dict] = {}
    for r in db.execute("SELECT order_id, status, COUNT(*) AS n FROM approvals WHERE status IN ('requested','changes') GROUP BY order_id, status"):
        out.setdefault(r["order_id"], {"waiting": 0, "sentBack": 0})["waiting" if r["status"] == "requested" else "sentBack"] = r["n"]
    return out
