"""What a buyer is allowed to see.

Built field by field from an allow-list: no unit or subcontractor names, no
internal status colour, no raw supervisor notes, and only warnings a
merchandiser has confirmed. Every query is scoped by the buyer_id resolved
from the link token.
"""

from __future__ import annotations

import sqlite3

from .orders import compute_projection, get_milestones


def buyer_by_token(db: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    if not token or len(token) < 20:
        return None
    return db.execute("SELECT id, name, country FROM buyers WHERE link_token = ? AND link_active = 1", (token,)).fetchone()


def buyer_orders(db: sqlite3.Connection, buyer_id: int, today: str) -> list[dict]:
    orders = db.execute("SELECT * FROM orders WHERE buyer_id = ? AND state != 'cancelled' ORDER BY ex_factory", (buyer_id,)).fetchall()
    result = []
    for o in orders:
        p = compute_projection(db, o, today).p
        stage_by_code = {s.code: s for s in p.stages}

        milestones = []
        for m in get_milestones(db, o["id"]):
            s = stage_by_code.get(m["code"])
            actual = m["actual_date"] or (s.projected_finish if s and s.remaining == 0 else None)
            milestones.append(
                {
                    "code": m["code"],
                    "name": m["name_en"],
                    "kind": m["kind"],
                    "plannedDate": m["planned_date"],
                    "actualDate": actual,
                    "pct": s.pct if s else (100 if m["actual_date"] else 0),
                    "done": s.done if s else None,
                }
            )

        warning = db.execute(
            "SELECT buyer_message, projected_ex_factory, decided_at, state FROM warnings WHERE order_id = ? AND state IN ('confirmed','resolved') ORDER BY id DESC LIMIT 1",
            (o["id"],),
        ).fetchone()

        photos = db.execute(
            """SELECT p.id, u.work_date, m.name_en AS stage FROM photos p
               JOIN daily_updates u ON u.id = p.update_id JOIN milestones m ON m.id = u.milestone_id
               WHERE p.order_id = ? AND p.buyer_visible = 1 ORDER BY p.id DESC LIMIT 12""",
            (o["id"],),
        ).fetchall()

        date_changes = db.execute(
            """SELECT d.field, d.old_value, d.new_value, d.reason, d.changed_at, m.name_en AS milestone
               FROM date_changes d LEFT JOIN milestones m ON m.id = d.milestone_id
               WHERE d.order_id = ? ORDER BY d.id DESC""",
            (o["id"],),
        ).fetchall()

        sizes = db.execute("SELECT size, qty FROM order_sizes WHERE order_id = ? ORDER BY seq", (o["id"],)).fetchall()
        last = p.stages[-1] if p.stages else None

        result.append(
            {
                "id": o["id"],
                "poNo": o["po_no"],
                "style": o["style"],
                "colour": o["colour"],
                "qty": o["qty_total"],
                "sizes": [dict(s) for s in sizes],
                "exFactory": o["ex_factory"],
                "state": o["state"],
                # Buyers see a delay only once a merchandiser has confirmed it.
                "notice": (
                    {"message": warning["buyer_message"], "expectedExFactory": warning["projected_ex_factory"], "at": warning["decided_at"]}
                    if warning and warning["state"] == "confirmed"
                    else None
                ),
                "overallPct": last.pct if last else 0,
                "milestones": milestones,
                "photos": [{"id": ph["id"], "date": ph["work_date"], "stage": ph["stage"]} for ph in photos],
                "dateChanges": [
                    {"field": d["field"], "oldValue": d["old_value"], "newValue": d["new_value"], "reason": d["reason"], "changedAt": d["changed_at"], "milestone": d["milestone"]}
                    for d in date_changes
                ],
            }
        )
    return result
