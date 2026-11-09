"""Office API: board, order setup, order detail, dates, reasons, warnings, buyers, exports."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from .. import config
from ..ai.classifier import ai_status
from ..db import transaction
from ..deps import AppContext, User, ctx, merchandiser
from ..domain.reasons import REASON_CATEGORIES, REASON_CODES
from ..security import new_token, sign_path
from ..services import clock, reports, shipping, accounts, activity, capacity, feed, reset, notices, notify, search as search_service
from ..services.export import weekly_workbook
from ..services.attachments import for_office
from ..services.requests import open_count
from ..services.templates import load_template, plan_json
from ..services.orders import (cancel_order, compute_projection, get_milestones, get_order, insert_order, refresh_all_active, refresh_order,
                               set_ex_factory, validate_new_order)
from ..util import HttpError, iso_week

router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])

IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


@router.get("/search")
async def search(q: str = "", c: AppContext = Depends(ctx)):
    return search_service.search(c.db, q)


@router.get("/meta")
async def meta(user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    db = c.db
    return {
        "buyers": rows(db.execute("SELECT id, name, country FROM buyers ORDER BY name")),
        "units": rows(db.execute("SELECT id, name, kind, process FROM units ORDER BY kind, name")),
        "templates": rows(db.execute("SELECT key, name FROM templates WHERE active = 1 ORDER BY builtin DESC, lower(name)")),
        "reasons": REASON_CATEGORIES,
        "today": c.today(),
        "openRequests": open_count(db),
        "canReset": config.allow_reset(),
        "testDate": clock.test_date(db),
        "unreadNotifications": feed.unread_count(db, "merchandiser", user.id, "office"),
        "ai": await ai_status(),
    }


# --- Order board ------------------------------------------------------------------

_RANK = {"red": 0, "amber": 1, "green": 2}


@router.get("/board")
async def board(buyer: int | None = None, unit: int | None = None, week: str | None = None, c: AppContext = Depends(ctx)):
    db, today = c.db, c.today()
    refresh_all_active(db, today)
    where, args = ["o.state = 'active'"], []
    if buyer:
        where.append("o.buyer_id = ?")
        args.append(buyer)
    if unit:
        where.append("o.unit_id = ?")
        args.append(unit)
    found = db.execute(
        f"""SELECT o.*, b.name AS buyer_name, u.name AS unit_name,
              (SELECT COUNT(*) FROM warnings w WHERE w.order_id = o.id AND w.state = 'pending') AS pending_warnings,
              (SELECT MAX(d.received_at) FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id WHERE m.order_id = o.id) AS last_update
            FROM orders o JOIN buyers b ON b.id = o.buyer_id JOIN units u ON u.id = o.unit_id
            WHERE {' AND '.join(where)}""",
        args,
    ).fetchall()

    unacked = set(notices.unacknowledged(db))
    orders = []
    for o in found:
        if week and iso_week(o["ex_factory"]) != week:
            continue
        p = compute_projection(db, o, today).p
        key = next((s for s in p.stages if s.code == p.key_stage), None)
        orders.append(
            {
                "id": o["id"], "orderNo": o["order_no"], "poNo": o["po_no"], "buyer": o["buyer_name"], "unit": o["unit_name"],
                "style": o["style"], "colour": o["colour"], "colourHex": o["colour_hex"], "qty": o["qty_total"],
                "exFactory": o["ex_factory"], "shipWeek": iso_week(o["ex_factory"]),
                "status": p.status, "projectedExFactory": p.projected_ex_factory, "slackDays": p.slack_days,
                "keyStage": key and {
                    "name": key.name, "pct": key.pct, "done": key.done, "requiredPerDay": key.required_per_day,
                    "runRate": key.run_rate, "rateBasis": key.rate_basis, "workingDaysLeft": key.working_days_left,
                },
                "stages": [{"code": s.code, "name": s.name, "pct": s.pct, "state": s.state} for s in p.stages],
                "headline": p.reasons[0] if p.reasons else None,
                "pendingWarnings": o["pending_warnings"],
                "lastUpdate": o["last_update"],
                "noticeUnacknowledged": o["id"] in unacked,
            }
        )
    orders.sort(key=lambda o: (_RANK[o["status"]], o["slackDays"], o["exFactory"]))
    weeks = sorted({iso_week(o["ex_factory"]) for o in found})
    return {"today": today, "orders": orders, "weeks": weeks}


# --- Order setup ------------------------------------------------------------------


class PlanPreviewIn(BaseModel):
    templateKey: str
    exFactory: IsoDate


@router.post("/plan-preview")
async def plan_preview(body: PlanPreviewIn, c: AppContext = Depends(ctx)):
    t = load_template(c.db, body.templateKey, active_only=True)
    if not t:
        raise HttpError(400, "Unknown template")
    return {"items": plan_json(c.db, t, body.exFactory)}


class SizeIn(BaseModel):
    size: str = Field(min_length=1, max_length=10)
    qty: int = Field(ge=0)


class MilestoneOverride(BaseModel):
    code: str
    plannedStart: IsoDate | None = None
    plannedDate: IsoDate
    unitId: int | None = None


class OrderIn(BaseModel):
    poNo: str = Field(min_length=3, max_length=40)  # the buyer's PO number, as on their document
    buyerId: int
    style: str = Field(min_length=2, max_length=120)
    colour: str = Field(min_length=1, max_length=60)
    colourHex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    colourPantone: str | None = Field(default=None, max_length=30)
    exFactory: IsoDate
    unitId: int
    templateKey: str
    fabricType: str | None = Field(default=None, max_length=60)
    fabricComposition: str | None = Field(default=None, max_length=120)
    fabricGsm: int | None = Field(default=None, ge=50, le=800)
    fabricNote: str | None = Field(default=None, max_length=200)
    sizes: list[SizeIn] = Field(min_length=1)
    milestones: list[MilestoneOverride] | None = None
    overCapacityOk: bool = False  # see AcceptIn in routes/requests.py


@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    db, today = c.db, c.today()
    t = validate_new_order(db, body, today)
    capacity.guard(db, body.unitId, sum(s.qty for s in body.sizes), body.exFactory, t, today, body.overCapacityOk)
    with transaction(db):
        order_id, order_no = insert_order(db, body, t, user.id, today)
    refresh_order(db, order_id, today)
    return {"id": order_id, "orderNo": order_no}


# --- Order detail -------------------------------------------------------------------


@router.get("/orders/{order_id}")
async def order_detail(order_id: int, c: AppContext = Depends(ctx)):
    db, today = c.db, c.today()
    fp = refresh_order(db, order_id, today)
    order = db.execute(
        """SELECT o.*, b.name AS buyer_name, u.name AS unit_name FROM orders o
           JOIN buyers b ON b.id = o.buyer_id JOIN units u ON u.id = o.unit_id WHERE o.id = ?""",
        (order_id,),
    ).fetchone()
    if not order:
        raise HttpError(404, "Order not found")

    units = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM units")}
    unit_kinds = {r["id"]: r["kind"] for r in db.execute("SELECT id, kind FROM units")}
    milestones = [{**dict(m), "unit_name": units.get(m["unit_id"]), "unit_kind": unit_kinds.get(m["unit_id"])} for m in get_milestones(db, order_id)]

    updates = []
    for u in db.execute(
        """SELECT d.*, s.name_en AS stage, m.code AS stage_code, us.name AS supervisor,
             r.ai_category, r.ai_translation, r.ai_confidence, r.ai_source, r.ai_error, r.final_category, r.changed_at, r.classified_at,
             (r.update_id IS NOT NULL) AS has_reason
           FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id JOIN plan_steps s ON s.code = m.code
           JOIN users us ON us.id = d.user_id LEFT JOIN issue_reasons r ON r.update_id = d.id
           WHERE m.order_id = ? ORDER BY d.work_date DESC, d.received_at DESC LIMIT 60""",
        (order_id,),
    ).fetchall():
        item = dict(u)
        item.pop("audio_path")
        item["audio_url"] = sign_path(f"/api/media/audio/{u['id']}") if u["audio_path"] else None
        item["photos"] = [
            {"id": p["id"], "buyerVisible": bool(p["buyer_visible"]), "url": sign_path(f"/api/media/photos/{p['id']}")}
            for p in db.execute("SELECT id, buyer_visible FROM photos WHERE update_id = ?", (u["id"],))
        ]
        updates.append(item)

    return {
        "today": today,
        "order": dict(order),
        "sizes": rows(db.execute("SELECT size, qty FROM order_sizes WHERE order_id = ? ORDER BY seq", (order_id,))),
        "milestones": milestones,
        "projection": (fp or compute_projection(db, order, today)).to_json(),
        "updates": updates,
        "warnings": rows(db.execute("SELECT * FROM warnings WHERE order_id = ? ORDER BY id DESC", (order_id,))),
        "changeRequests": rows(db.execute(
            "SELECT id, request_no AS requestNo, kind, status, ex_factory AS exFactory, updated_at AS updatedAt FROM order_requests WHERE order_id = ? ORDER BY id DESC",
            (order_id,),
        )),
        "attachments": [{**a, "url": sign_path(f"/api/media/attachments/{a['id']}")} for a in for_office(db, order_id=order_id)],
        "activity": activity.for_order(db, order_id, "office"),
        "buyerPath": (lambda t: f"/b/{t['link_token']}/orders/{order_id}" if t and t["link_active"] else None)(
            db.execute("SELECT link_token, link_active FROM buyers WHERE id = ?", (order["buyer_id"],)).fetchone()),
        "dateChanges": rows(
            db.execute(
                """SELECT d.*, s.name_en AS milestone, u.name AS changed_by_name FROM date_changes d
                   LEFT JOIN milestones m ON m.id = d.milestone_id LEFT JOIN plan_steps s ON s.code = m.code
                   LEFT JOIN users u ON u.id = d.changed_by
                   WHERE d.order_id = ? ORDER BY d.id DESC""",
                (order_id,),
            )
        ),
    }


# --- Date changes (always audited) --------------------------------------------------


class ExFactoryIn(BaseModel):
    date: IsoDate
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/orders/{order_id}/ex-factory")
async def change_ex_factory(order_id: int, body: ExFactoryIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    db = c.db
    order = get_order(db, order_id)
    if not order:
        raise HttpError(404, "Order not found")
    if order["ex_factory"] != body.date:
        with transaction(db):
            set_ex_factory(db, order_id, body.date, body.reason.strip(), user.id)
        refresh_order(db, order_id, c.today())
    return {"ok": True}


class ResetIn(BaseModel):
    confirm: str


@router.get("/reset")
async def reset_preview(c: AppContext = Depends(ctx)):
    if not config.allow_reset():
        raise HttpError(404, "Not found")
    return reset.preview(c.db)


@router.post("/reset")
async def reset_test_data(body: ResetIn, c: AppContext = Depends(ctx)):
    if not config.allow_reset():
        raise HttpError(404, "Not found")
    if body.confirm.strip() != "RESET":
        raise HttpError(400, "Type RESET to confirm")
    return reset.clear(c.db, Path(config.DB_FILE).parent / "backups", c.upload_dir)


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/orders/{order_id}/cancel")
async def cancel(order_id: int, body: CancelIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    cancel_order(c.db, order_id, body.reason)
    return {"ok": True}


class MilestoneIn(BaseModel):
    plannedStart: IsoDate | None = None
    plannedDate: IsoDate | None = None
    actualDate: IsoDate | None = None
    clearActual: bool = False
    reason: str | None = Field(default=None, min_length=3, max_length=300)


@router.patch("/milestones/{milestone_id}")
async def change_milestone(milestone_id: int, body: MilestoneIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    db = c.db
    m = db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
    if not m:
        raise HttpError(404, "Milestone not found")
    if m["code"] == "EXF" and body.plannedDate:
        raise HttpError(400, "Change ex-factory on the order itself")

    changes: list[tuple[str, str | None, str | None]] = []
    if body.plannedStart and body.plannedStart != m["planned_start"]:
        changes.append(("planned_start", m["planned_start"], body.plannedStart))
    if body.plannedDate and body.plannedDate != m["planned_date"]:
        changes.append(("planned_date", m["planned_date"], body.plannedDate))
    new_actual = None if body.clearActual else body.actualDate
    if (body.clearActual or body.actualDate) and new_actual != m["actual_date"]:
        changes.append(("actual_date", m["actual_date"], new_actual))
    if any(f != "actual_date" for f, _, _ in changes) and not body.reason:
        raise HttpError(400, "Give a reason for changing a planned date")

    with transaction(db):
        for field, old, new in changes:
            db.execute(f"UPDATE milestones SET {field} = ? WHERE id = ?", (new, milestone_id))  # field is from a fixed set
            db.execute(
                "INSERT INTO date_changes (order_id, milestone_id, field, old_value, new_value, reason, changed_by) VALUES (?,?,?,?,?,?,?)",
                (m["order_id"], milestone_id, field, old, new, body.reason or ("Marked done" if new else "Unmarked done"), user.id),
            )
    refresh_order(db, m["order_id"], c.today())
    return {"ok": True}


# --- AI reason override -----------------------------------------------------------


class ReasonIn(BaseModel):
    category: Literal[tuple(REASON_CODES)]  # type: ignore[valid-type]


@router.patch("/reasons/{update_id}")
async def override_reason(update_id: str, body: ReasonIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    cur = c.db.execute(
        "UPDATE issue_reasons SET final_category = ?, changed_by = ?, changed_at = datetime('now') WHERE update_id = ?",
        (body.category, user.id, update_id),
    )
    if not cur.rowcount:
        raise HttpError(404, "No reason recorded for that update")
    return {"ok": True}


# --- Shipping and the success-measure reports ---------------------------------------------


class ShipIn(BaseModel):
    shippedDate: IsoDate


@router.post("/orders/{order_id}/ship")
async def ship_order(order_id: int, body: ShipIn, c: AppContext = Depends(ctx)):
    """The order left the factory on this date. The buyer is told, and the date counts towards on-time shipping."""
    return shipping.mark_shipped(c.db, order_id, body.shippedDate, c.today())


@router.get("/reports")
async def reports_page(c: AppContext = Depends(ctx)):
    refresh_all_active(c.db, c.today())
    return reports.all_reports(c.db, c.today())


# --- Warnings: nothing reaches a buyer until a merchandiser confirms --------------


class ConfirmIn(BaseModel):
    message: str = Field(min_length=10, max_length=1000)


@router.post("/warnings/{warning_id}/confirm")
async def confirm_warning(warning_id: int, body: ConfirmIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    db = c.db
    w = db.execute(
        "SELECT w.*, o.buyer_id, o.po_no FROM warnings w JOIN orders o ON o.id = w.order_id WHERE w.id = ?", (warning_id,)
    ).fetchone()
    if not w:
        raise HttpError(404, "Warning not found")
    if w["state"] != "pending":
        raise HttpError(409, f"Warning is already {w['state']}")
    message = body.message.strip()
    with transaction(db):
        # A newer confirmed warning replaces the one the buyer saw before.
        db.execute("UPDATE warnings SET state = 'superseded' WHERE order_id = ? AND state = 'confirmed'", (w["order_id"],))
        db.execute(
            "UPDATE warnings SET state = 'confirmed', buyer_message = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?",
            (message, user.id, warning_id),
        )
        notify.send(db, "delay_notice", w["buyer_id"], w["order_id"], po=w["po_no"], text=message)
    return {"ok": True}


@router.post("/warnings/{warning_id}/dismiss")
async def dismiss_warning(warning_id: int, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    cur = c.db.execute(
        "UPDATE warnings SET state = 'dismissed', decided_by = ?, decided_at = datetime('now') WHERE id = ? AND state = 'pending'",
        (user.id, warning_id),
    )
    if not cur.rowcount:
        raise HttpError(409, "Only a pending warning can be dismissed")
    return {"ok": True}


class PhotoIn(BaseModel):
    buyerVisible: bool


@router.patch("/photos/{photo_id}")
async def photo_visibility(photo_id: int, body: PhotoIn, c: AppContext = Depends(ctx)):
    c.db.execute("UPDATE photos SET buyer_visible = ? WHERE id = ?", (int(body.buyerVisible), photo_id))
    return {"ok": True}


# --- Buyer links, exports, mock outbox ----------------------------------------------


@router.get("/buyers")
async def buyers(c: AppContext = Depends(ctx)):
    result = rows(
        c.db.execute(
            """SELECT b.id, b.name, b.country, b.link_token, b.link_active, b.notify_email AS notifyEmail,
                 b.whatsapp_number AS whatsappNumber, b.whatsapp_opt_in AS whatsappOptIn, b.whatsapp_opt_in_at AS whatsappOptInAt,
                 (SELECT COUNT(*) FROM orders o WHERE o.buyer_id = b.id AND o.state = 'active') AS active_orders
               FROM buyers b ORDER BY b.name"""
        )
    )
    for b in result:
        b["logins"] = accounts.list_logins(c.db, b["id"])
    return result


@router.post("/buyers/{buyer_id}/rotate-link")
async def rotate_link(buyer_id: int, c: AppContext = Depends(ctx)):
    token = new_token()
    c.db.execute("UPDATE buyers SET link_token = ?, link_active = 1 WHERE id = ?", (token, buyer_id))
    return {"token": token}


@router.get("/exports/weekly")
async def export_weekly(buyerId: int, audience: Literal["buyer", "internal"] = Query("internal"), c: AppContext = Depends(ctx)):
    today = c.today()
    try:
        data = weekly_workbook(c.db, buyerId, today, audience)
    except LookupError:
        raise HttpError(404, "Unknown buyer")
    name = f"status-{buyerId}-{iso_week(today)}{'-buyer' if audience == 'buyer' else ''}.xlsx"
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/outbox")
async def outbox(c: AppContext = Depends(ctx)):
    return rows(c.db.execute("SELECT m.*, b.name AS buyer FROM outbox_messages m JOIN buyers b ON b.id = m.buyer_id ORDER BY m.id DESC LIMIT 50"))
