"""Load an order, project it, cache its status and keep warnings in step."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..config import CALENDAR
from ..db import transaction
from ..domain.calendar import add_days
from ..domain.reasons import REASON_LABEL_EN
from ..domain.runrate import DailyQty, OrderProjection, StageInput, pretty_date, project_order


@dataclass
class FullProjection:
    p: OrderProjection
    overdue_milestones: list[dict] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.p.status

    def to_json(self) -> dict:
        return {**self.p.to_json(), "overdueMilestones": self.overdue_milestones}


def get_order(db: sqlite3.Connection, order_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_milestones(db: sqlite3.Connection, order_id: int) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM milestones WHERE order_id = ? ORDER BY seq", (order_id,)).fetchall()


def compute_projection(db: sqlite3.Connection, order: sqlite3.Row, today: str) -> FullProjection:
    ms = get_milestones(db, order["id"])
    stages = [
        StageInput(
            code=m["code"],
            name=m["name_en"],
            planned_start=m["planned_start"] or m["planned_date"],
            planned_end=m["planned_date"],
            daily=[
                DailyQty(r["date"], r["qty"])
                for r in db.execute(
                    "SELECT work_date AS date, SUM(qty) AS qty FROM daily_updates WHERE milestone_id = ? GROUP BY work_date ORDER BY work_date",
                    (m["id"],),
                )
            ],
        )
        for m in ms
        if m["kind"] == "stage"
    ]
    p = project_order(today=today, ex_factory=order["ex_factory"], order_qty=order["qty_total"], stages=stages, calendar=CALENDAR)

    # Missed TNA milestones (approvals, inspections) also need attention.
    overdue = [
        {"code": m["code"], "name": m["name_en"], "plannedDate": m["planned_date"]}
        for m in ms
        if m["kind"] == "milestone" and m["code"] != "EXF" and not m["actual_date"] and m["planned_date"] < today
    ]
    if overdue and p.status == "green":
        p.status = "amber"
    p.reasons.extend(f"{m['name']} was due {pretty_date(m['plannedDate'])} and is not marked done." for m in overdue)
    return FullProjection(p, overdue)


def refresh_order(db: sqlite3.Connection, order_id: int, today: str) -> FullProjection | None:
    """Recompute an order's status, cache it on the row, and keep warnings in step."""
    order = get_order(db, order_id)
    if order is None or order["state"] != "active":
        return None
    fp = compute_projection(db, order, today)
    with transaction(db):
        db.execute(
            "UPDATE orders SET status = ?, projected_ex_factory = ?, status_computed_at = datetime('now') WHERE id = ?",
            (fp.status, fp.p.projected_ex_factory, order_id),
        )
        _sync_warnings(db, order, fp, today)
    return fp


def refresh_all_active(db: sqlite3.Connection, today: str) -> None:
    for (oid,) in db.execute("SELECT id FROM orders WHERE state = 'active'").fetchall():
        refresh_order(db, oid, today)


_LEVEL_RANK = {"amber": 1, "red": 2}


def _sync_warnings(db: sqlite3.Connection, order: sqlite3.Row, fp: FullProjection, today: str) -> None:
    p = fp.p
    open_rows = db.execute(
        "SELECT id, level, projected_ex_factory, state FROM warnings WHERE order_id = ? AND state IN ('pending','confirmed') ORDER BY id DESC",
        (order["id"],),
    ).fetchall()
    pending = next((w for w in open_rows if w["state"] == "pending"), None)
    confirmed = next((w for w in open_rows if w["state"] == "confirmed"), None)

    if fp.status == "green":
        db.execute("UPDATE warnings SET state = 'superseded' WHERE order_id = ? AND state = 'pending'", (order["id"],))
        db.execute("UPDATE warnings SET state = 'resolved', decided_at = datetime('now') WHERE order_id = ? AND state = 'confirmed'", (order["id"],))
        return

    level = fp.status
    summary = " ".join(p.reasons)
    message = _default_buyer_message(db, order, fp, today)

    # A confirmed warning that still describes the situation needs nothing new.
    if confirmed and _LEVEL_RANK[confirmed["level"]] >= _LEVEL_RANK[level] and confirmed["projected_ex_factory"] >= p.projected_ex_factory:
        if pending:
            db.execute("UPDATE warnings SET state = 'superseded' WHERE id = ?", (pending["id"],))
        return

    if pending:
        # Still a draft, so the suggested buyer message follows the latest numbers.
        db.execute(
            "UPDATE warnings SET level = ?, projected_ex_factory = ?, slack_days = ?, summary = ?, buyer_message = ? WHERE id = ?",
            (level, p.projected_ex_factory, p.slack_days, summary, message, pending["id"]),
        )
    else:
        db.execute(
            "INSERT INTO warnings (order_id, level, projected_ex_factory, slack_days, summary, buyer_message) VALUES (?,?,?,?,?,?)",
            (order["id"], level, p.projected_ex_factory, p.slack_days, summary, message),
        )


def recent_reason(db: sqlite3.Connection, order_id: int, today: str) -> str | None:
    """The most common recent reason category on this order, ignoring 'no issue'."""
    row = db.execute(
        """SELECT r.final_category AS cat, COUNT(*) AS n FROM issue_reasons r
           JOIN daily_updates u ON u.id = r.update_id
           WHERE u.order_id = ? AND u.work_date >= ? AND r.final_category IS NOT NULL AND r.final_category != 'NO_ISSUE'
           GROUP BY r.final_category ORDER BY n DESC, MAX(u.work_date) DESC LIMIT 1""",
        (order_id, add_days(today, -14)),
    ).fetchone()
    return row["cat"] if row else None


def _default_buyer_message(db: sqlite3.Connection, order: sqlite3.Row, fp: FullProjection, today: str) -> str:
    p = fp.p
    cat = recent_reason(db, order["id"], today)
    because = f" The main cause is {REASON_LABEL_EN[cat].lower()}." if cat else ""
    stage = next((s for s in p.stages if s.code == p.key_stage), None)
    head = f"{order['po_no']} ({order['style']})"
    if fp.status == "red":
        where = f" in {stage.name.lower()}" if stage else ""
        return (
            f"{head}: at the current output we expect ex-factory on {pretty_date(p.projected_ex_factory)} instead of {pretty_date(order['ex_factory'])}."
            f"{because} We are adding capacity{where} and will update you on recovery."
        )
    what = stage.name.lower() if stage else "production"
    return f"{head}: {what} is running behind plan.{because} Ex-factory {pretty_date(order['ex_factory'])} is still achievable and we are watching it daily."
