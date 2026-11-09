"""A per-order timeline of what happened and who did it, assembled from the trails the app already keeps.

Nothing is stored for it: it reads date changes, messages, request steps, approvals and delay notices.
The buyer's version leaves out what is internal (dismissed warnings, materials, who changed what).
"""

from __future__ import annotations

import sqlite3

from .approvals import ACTION_TEXT

LIMIT = 80
_FIELD = {"ex_factory": "Ex-factory date", "planned_date": "Due date", "planned_start": "Start date", "actual_date": "Done date"}
_REQUEST = {
    "submitted": "Request submitted", "message": "Message on the request", "query": "Question about the request", "counter": "A different date was proposed",
    "agreed": "The proposed date was agreed", "accepted": "Request accepted into an order", "declined": "Request declined", "withdrawn": "Request cancelled",
}


def _item(at: str, kind: str, actor: str, title: str, detail: str | None = None) -> dict:
    return {"at": at, "kind": kind, "actor": actor, "title": title, "detail": detail}


def for_order(db: sqlite3.Connection, order_id: int, audience: str) -> list[dict]:
    office = audience == "office"
    out: list[dict] = []

    for d in db.execute(
        """SELECT d.field, d.old_value, d.new_value, d.reason, d.changed_at, d.changed_by, s.name_en AS milestone, u.name AS who
           FROM date_changes d LEFT JOIN milestones m ON m.id = d.milestone_id LEFT JOIN plan_steps s ON s.code = m.code
           LEFT JOIN users u ON u.id = d.changed_by WHERE d.order_id = ?""",
        (order_id,),
    ):
        what = f"{d['milestone'] or 'Order'}: {_FIELD.get(d['field'], d['field']).lower()}"
        if d["field"] == "actual_date" and d["new_value"]:
            title, kind = f"{d['milestone'] or 'Step'} marked done", "step"
        elif d["field"] == "actual_date":
            title, kind = f"{d['milestone'] or 'Step'} marked not done", "step"
        else:
            title, kind = f"{what} moved to {d['new_value']}", "date"
        out.append(_item(d["changed_at"], kind, d["who"] if office and d["who"] else "merchandiser", title, d["reason"]))

    for m in db.execute("SELECT author, body, created_at FROM order_messages WHERE order_id = ?", (order_id,)):
        out.append(_item(m["created_at"], "message", m["author"], "Message from the buyer" if m["author"] == "buyer" else "Message from the merchandiser", m["body"]))

    for m in db.execute(
        """SELECT m.author, m.event, m.body, m.created_at FROM request_messages m JOIN order_requests q ON q.id = m.request_id WHERE q.order_id = ?""",
        (order_id,),
    ):
        out.append(_item(m["created_at"], "request", m["author"], _REQUEST.get(m["event"], m["event"]), m["body"]))

    for a in db.execute("SELECT id, title FROM approvals WHERE order_id = ?", (order_id,)).fetchall():
        for e in db.execute("SELECT actor, action, note, created_at FROM approval_events WHERE approval_id = ?", (a["id"],)):
            out.append(_item(e["created_at"], "approval", e["actor"], f"{ACTION_TEXT[e['action']]}: {a['title']}", e["note"]))

    for w in db.execute("SELECT state, buyer_message, decided_at, buyer_seen_at, buyer_ack_at, projected_ex_factory FROM warnings WHERE order_id = ?", (order_id,)):
        if w["state"] in ("confirmed", "resolved") and w["decided_at"]:
            out.append(_item(w["decided_at"], "notice", "merchandiser", f"Delay notice: now expected {w['projected_ex_factory']}", w["buyer_message"]))
            if w["buyer_seen_at"] and office:
                out.append(_item(w["buyer_seen_at"], "notice", "buyer", "The buyer opened the delay notice"))
            if w["buyer_ack_at"]:
                out.append(_item(w["buyer_ack_at"], "notice", "buyer", "The buyer acknowledged the delay notice"))

    if office:
        for m in db.execute("SELECT name, received_date, updated_at FROM order_materials WHERE order_id = ? AND status = 'received'", (order_id,)):
            out.append(_item(f"{m['received_date']} 00:00:00", "material", "merchandiser", f"{m['name']} received"))

    out.sort(key=lambda i: i["at"], reverse=True)
    return out[:LIMIT]
