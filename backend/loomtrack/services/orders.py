"""Load an order, project it, cache its status and keep warnings in step."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..config import CALENDAR
from ..db import transaction
from ..domain.calendar import add_days
from ..domain.reasons import REASON_LABEL_EN
from ..domain.tna import Template, plan_from_template
from ..domain.runrate import DailyQty, OrderProjection, StageInput, pretty_date, project_order
from ..util import HttpError
from . import notify, shipping
from .templates import load_template


@dataclass
class FullProjection:
    p: OrderProjection
    overdue_milestones: list[dict] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.p.status

    def to_json(self) -> dict:
        return {**self.p.to_json(), "overdueMilestones": self.overdue_milestones}


def next_order_no(db: sqlite3.Connection, today: str) -> str:
    """Our own order number, LT-<year>-<n>. Call inside the transaction that inserts the order,
    so two orders can't take the same number (and orders.order_no is UNIQUE as a backstop)."""
    prefix = f"LT-{today[:4]}-"
    n = db.execute(
        "SELECT MAX(CAST(substr(order_no, ?) AS INTEGER)) FROM orders WHERE order_no LIKE ?", (len(prefix) + 1, prefix + "%")
    ).fetchone()[0]
    return f"{prefix}{(n or 0) + 1:04d}"


def fabric_fields(body) -> dict:
    """The fabric on a new order or request, cleaned. Anything left out is None."""
    def text(v):
        return (v or "").strip() or None

    return {"type": text(getattr(body, "fabricType", None)), "composition": text(getattr(body, "fabricComposition", None)),
            "gsm": getattr(body, "fabricGsm", None), "note": text(getattr(body, "fabricNote", None))}


def get_order(db: sqlite3.Connection, order_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_milestones(db: sqlite3.Connection, order_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT m.*, s.name_en, s.name_ta, s.kind, s.process FROM milestones m
           JOIN plan_steps s ON s.code = m.code WHERE m.order_id = ? ORDER BY m.seq""",
        (order_id,),
    ).fetchall()


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

    # Missed TNA milestones (sample approvals, inspections) also need attention.
    overdue = [
        {"code": m["code"], "name": m["name_en"], "plannedDate": m["planned_date"]}
        for m in ms
        if m["kind"] == "milestone" and m["code"] != "EXF" and not m["actual_date"] and m["planned_date"] < today
    ]
    if overdue and p.status == "green":
        p.status = "amber"
    p.reasons.extend(f"{m['name']} was due {pretty_date(m['plannedDate'])} and is not marked done." for m in overdue)
    return FullProjection(p, overdue)


def cancel_order(db: sqlite3.Connection, order_id: int, reason: str) -> None:
    """Cancel an order that is still in production, with the reason the buyer will read. One step, no back and forth."""
    text = " ".join(reason.split())
    if len(text) < 3:
        raise HttpError(400, "Give the buyer a reason for cancelling")
    order = get_order(db, order_id)
    if order is None:
        raise HttpError(404, "Order not found")
    if order["state"] != "active":
        raise HttpError(409, "Only an order that is still in production can be cancelled")
    with transaction(db):
        db.execute("UPDATE orders SET state = 'cancelled', cancel_reason = ?, cancelled_at = datetime('now') WHERE id = ?", (text, order_id))
        db.execute("UPDATE warnings SET state = 'superseded' WHERE order_id = ? AND state IN ('pending','confirmed')", (order_id,))
        notify.send(db, "order_cancelled", order["buyer_id"], order_id, po=order["po_no"], text=text)


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
        shipping.check_production_complete(db, order, today)
    return fp


def refresh_all_active(db: sqlite3.Connection, today: str) -> None:
    for (oid,) in db.execute("SELECT id FROM orders WHERE state = 'active'").fetchall():
        refresh_order(db, oid, today)


_LEVEL_RANK = {"amber": 1, "red": 2}


def _sync_warnings(db: sqlite3.Connection, order: sqlite3.Row, fp: FullProjection, today: str) -> None:
    p = fp.p
    open_rows = db.execute(
        "SELECT id, level, projected_ex_factory, state, reason_category FROM warnings WHERE order_id = ? AND state IN ('pending','confirmed') ORDER BY id DESC",
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

    reason = recent_reason(db, order["id"], today)
    reason_cat = reason[0] if reason else None

    # A confirmed warning that still describes the situation needs nothing new, unless the supervisor has since
    # given a different reason than the one the buyer was told.
    if confirmed and _LEVEL_RANK[confirmed["level"]] >= _LEVEL_RANK[level] and confirmed["projected_ex_factory"] >= p.projected_ex_factory:
        if not _new_reason_since(db, order["id"], confirmed, reason_cat):
            if pending:
                db.execute("UPDATE warnings SET state = 'superseded' WHERE id = ?", (pending["id"],))
            return

    if pending:
        # Still a draft, so the suggested buyer message follows the latest numbers.
        db.execute(
            "UPDATE warnings SET level = ?, projected_ex_factory = ?, slack_days = ?, summary = ?, buyer_message = ?, reason_category = ? WHERE id = ?",
            (level, p.projected_ex_factory, p.slack_days, summary, message, reason_cat, pending["id"]),
        )
    else:
        db.execute(
            "INSERT INTO warnings (order_id, level, projected_ex_factory, slack_days, summary, buyer_message, reason_category, warned_on) VALUES (?,?,?,?,?,?,?,?)",
            (order["id"], level, p.projected_ex_factory, p.slack_days, summary, message, reason_cat, today),
        )
        # A new warning is the moment the office should hear of it; later updates to the same draft are quiet.
        notify.send(db, "delay_detected", order["buyer_id"], order["id"], po=order["po_no"], level="at risk" if level == "amber" else "late",
                    date=pretty_date(p.projected_ex_factory), text=summary)


def _new_reason_since(db: sqlite3.Connection, order_id: int, confirmed: sqlite3.Row, reason_cat: str | None) -> bool:
    """True when the supervisor has reported a reason, after the buyer was told, that differs from the one the buyer was told.
    A notice the office dismissed for the same reason is not offered again."""
    if reason_cat is None or reason_cat == confirmed["reason_category"]:
        return False
    since = db.execute("SELECT decided_at FROM warnings WHERE id = ?", (confirmed["id"],)).fetchone()["decided_at"] or ""
    reported = db.execute(
        """SELECT 1 FROM daily_updates u JOIN issue_reasons r ON r.update_id = u.id JOIN milestones m ON m.id = u.milestone_id
           WHERE m.order_id = ? AND r.final_category = ? AND u.received_at >= ? LIMIT 1""",
        (order_id, reason_cat, since),
    ).fetchone()
    if reported is None:
        return False
    waved_off = db.execute(
        "SELECT 1 FROM warnings WHERE order_id = ? AND state = 'dismissed' AND reason_category = ? AND decided_at >= ? LIMIT 1",
        (order_id, reason_cat, since),
    ).fetchone()
    return waved_off is None


def recent_reason(db: sqlite3.Connection, order_id: int, today: str) -> tuple[str, str | None] | None:
    """The supervisor's latest reason on this order (category, English translation of his words), or None when his
    latest note says there is no issue. The latest one wins: the situation on the floor is what he said last."""
    row = db.execute(
        """SELECT r.final_category AS cat, r.ai_translation AS tr FROM issue_reasons r
           JOIN daily_updates u ON u.id = r.update_id JOIN milestones m ON m.id = u.milestone_id
           WHERE m.order_id = ? AND u.work_date >= ? AND r.final_category IS NOT NULL
           ORDER BY u.work_date DESC, u.rowid DESC LIMIT 1""",
        (order_id, add_days(today, -14)),
    ).fetchone()
    if not row or row["cat"] == "NO_ISSUE":
        return None
    return row["cat"], (" ".join(row["tr"].split())[:160] if row["tr"] else None)


def _default_buyer_message(db: sqlite3.Connection, order: sqlite3.Row, fp: FullProjection, today: str) -> str:
    p = fp.p
    reason = recent_reason(db, order["id"], today)
    because = ""
    if reason:
        cat, said = reason
        because = f" The main cause is {REASON_LABEL_EN[cat].lower()}" + (f" (our supervisor reports: “{said}”)." if said else ".")
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


def validate_new_order(db: sqlite3.Connection, body, today: str) -> Template:
    """Checks shared by 'create order' and 'accept a buyer's request'. Returns the template to plan from."""
    t = load_template(db, body.templateKey, active_only=True)
    if not t:
        raise HttpError(400, "Unknown template")
    qty = sum(s.qty for s in body.sizes)
    if qty <= 0:
        raise HttpError(400, "Size quantities add up to zero")
    if len({s.size.strip().upper() for s in body.sizes}) != len(body.sizes):
        raise HttpError(400, "Duplicate size")
    if body.exFactory <= today:
        raise HttpError(400, "Ex-factory date must be in the future")
    if db.execute("SELECT 1 FROM orders WHERE po_no = ? AND buyer_id = ?", (body.poNo.strip(), body.buyerId)).fetchone():
        raise HttpError(409, f"This buyer already has a PO {body.poNo.strip()}")
    unit = db.execute("SELECT kind FROM units WHERE id = ?", (body.unitId,)).fetchone()
    if not unit or unit["kind"] != "own":
        raise HttpError(400, "Pick one of our own units")
    if not db.execute("SELECT 1 FROM buyers WHERE id = ?", (body.buyerId,)).fetchone():
        raise HttpError(400, "Unknown buyer")
    return t


def insert_order(db: sqlite3.Connection, body, t: Template, user_id: int, today: str) -> tuple[int, str]:
    """Insert the order, its sizes and its dated plan. Call inside a transaction; returns (id, order_no)."""
    overrides = {m.code: m for m in body.milestones or []}
    subcontractor = {r["process"]: r["id"] for r in db.execute("SELECT id, process FROM units WHERE kind = 'subcontract'")}
    order_no = next_order_no(db, today)
    fabric = fabric_fields(body)
    order_id = db.execute(
        """INSERT INTO orders (order_no, po_no, buyer_id, style, colour, colour_hex, colour_pantone, qty_total, ex_factory, unit_id, template_key, merchandiser_id,
                               fabric_type, fabric_composition, fabric_gsm, fabric_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order_no, body.poNo.strip(), body.buyerId, body.style.strip(), body.colour.strip(),
         body.colourHex.upper() if body.colourHex else None, (body.colourPantone or "").strip() or None,
         sum(s.qty for s in body.sizes), body.exFactory, body.unitId, t.key, user_id,
         fabric["type"], fabric["composition"], fabric["gsm"], fabric["note"]),
    ).lastrowid
    for n, s in enumerate(body.sizes, start=1):
        db.execute("INSERT INTO order_sizes (order_id, seq, size, qty) VALUES (?,?,?,?)", (order_id, n, s.size.strip().upper(), s.qty))
    for p in plan_from_template(CALENDAR, t, body.exFactory):
        it, o = p.item, overrides.get(p.item.code)
        unit_id = None
        if it.kind == "stage":
            # A step goes to the subcontractor for its process if there is one, else to the order's own unit.
            unit_id = (o.unitId if o and o.unitId else None) or subcontractor.get(it.process, body.unitId)
        db.execute(
            "INSERT INTO milestones (order_id, seq, code, planned_start, planned_date, unit_id) VALUES (?,?,?,?,?,?)",
            (order_id, p.seq, it.code, (o.plannedStart if o else None) or p.planned_start, o.plannedDate if o else p.planned_date, unit_id),
        )
    return order_id, order_no


def set_ex_factory(db: sqlite3.Connection, order_id: int, new_date: str, reason: str, user_id: int) -> None:
    """Change the ex-factory date and record who, why and what it was. Call inside a transaction.
    Planned dates of the stages are not moved: the merchandiser reviews them (each edit is audited too)."""
    old = db.execute("SELECT ex_factory FROM orders WHERE id = ?", (order_id,)).fetchone()["ex_factory"]
    db.execute("UPDATE orders SET ex_factory = ? WHERE id = ?", (new_date, order_id))
    db.execute("UPDATE milestones SET planned_date = ? WHERE order_id = ? AND code = 'EXF'", (new_date, order_id))
    db.execute(
        "INSERT INTO date_changes (order_id, field, old_value, new_value, reason, changed_by) VALUES (?,?,?,?,?,?)",
        (order_id, "ex_factory", old, new_date, reason, user_id),
    )
