"""Capacity check: the units' real bookings against what a new order would need.

The rules and the maths are in domain/capacity.py. This reads what is booked, runs the check for each
of our own units and, when asked, refuses an order that would put a unit over unless the merchandiser
has said they want it anyway.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from ..config import CALENDAR
from ..domain import capacity as cap
from ..domain.calendar import add_days, to_date
from ..domain.runrate import pretty_date
from ..domain.tna import Template, TemplateItem
from ..util import HttpError


def stitching_item(t: Template) -> TemplateItem | None:
    """The step capacity is measured on: the first stitching stage of the plan."""
    return next((i for i in t.items if i.kind == "stage" and i.process == "stitching"), None)


def bookings(db: sqlite3.Connection, exclude_order_id: int | None = None) -> dict[int, list[cap.Booking]]:
    """Stitching still to do on active orders, by the unit doing it (the stage's unit, not the order's)."""
    out: dict[int, list[cap.Booking]] = {}
    for r in db.execute(
        """SELECT m.unit_id, m.planned_start, m.planned_date, o.id AS order_id, o.order_no, o.po_no, o.qty_total,
             COALESCE((SELECT SUM(d.qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS made
           FROM milestones m JOIN plan_steps s ON s.code = m.code JOIN orders o ON o.id = m.order_id
           WHERE o.state = 'active' AND s.kind = 'stage' AND s.process = 'stitching' AND m.unit_id IS NOT NULL"""
    ):
        if r["order_id"] == exclude_order_id:
            continue
        left = r["qty_total"] - r["made"]
        if left > 0:
            out.setdefault(r["unit_id"], []).append(
                cap.Booking(r["order_no"], r["po_no"], left, r["planned_start"] or r["planned_date"], r["planned_date"])
            )
    return out


def _summary(name: str, f: cap.Fit, qty: int) -> str:
    if f.verdict == "unknown":
        return "No daily capacity is set for this unit, so it cannot be checked. Set it on the Units page."
    if f.verdict == "no_window":
        return f"The stitching step would have to finish before today, so {name} cannot make this date."
    pct = round((f.utilisation or 0) * 100)
    return (
        f"Would be {pct}% booked across {len(f.days)} working days ({pretty_date(f.days[0])} to {pretty_date(f.days[-1])}): "
        f"{round(f.existing):,} pcs already booked, {qty:,} more needed, {round(f.capacity_total):,} possible."
    )


def check(db: sqlite3.Connection, qty: int, ex_factory: str, t: Template, today: str, exclude_order_id: int | None = None) -> dict:
    item = stitching_item(t)
    if item is None or item.start_offset is None:
        return {"stitching": None, "units": []}
    by_unit = bookings(db, exclude_order_id)
    days = cap.new_order_days(CALENDAR, ex_factory, item.start_offset, item.end_offset, today)
    units = []
    for u in db.execute("SELECT id, name, daily_capacity FROM units WHERE kind = 'own' ORDER BY name"):
        existing = by_unit.get(u["id"], [])
        load = cap.daily_load(existing, CALENDAR, today)
        f = cap.fit(u["daily_capacity"], load, days, qty)
        earliest = None
        if f.verdict in ("over", "no_window"):
            e = cap.earliest_fit(u["daily_capacity"], load, qty, item.start_offset, item.end_offset, ex_factory, CALENDAR, today)
            earliest = {"exFactory": e[0], "utilisation": round(e[1], 2)} if e else None
        mine = set(days)
        overlapping = sorted(
            (
                {"orderNo": b.order_no, "poNo": b.po_no, "qtyLeft": b.qty_left}
                for b in existing
                if mine & set(cap.window(CALENDAR, b.start, b.end, today, overdue_spread=True))
            ),
            key=lambda o: -o["qtyLeft"],
        )[:5]
        units.append({
            "unitId": u["id"], "name": u["name"], "capacity": u["daily_capacity"], "verdict": f.verdict,
            "utilisation": None if f.utilisation is None else round(f.utilisation, 2),
            "needed": qty, "booked": round(f.existing), "possible": round(f.capacity_total),
            "workingDays": len(f.days), "windowStart": f.days[0] if f.days else None, "windowEnd": f.days[-1] if f.days else None,
            "requiredPerDay": round(qty / len(f.days)) if f.days else None,
            "earliest": earliest, "overlapping": overlapping, "summary": _summary(u["name"], f, qty),
        })
    return {
        "stitching": {"name": item.name_en, "startOffset": item.start_offset, "endOffset": item.end_offset},
        "units": units,
    }


def guard(db: sqlite3.Connection, unit_id: int, qty: int, ex_factory: str, t: Template, today: str, allowed: bool) -> None:
    """Refuse an order that would put its unit over capacity, unless the merchandiser has said to go ahead.
    A unit with no capacity set, or a plan with no stitching step, is not checked."""
    if allowed:
        return
    for u in check(db, qty, ex_factory, t, today)["units"]:
        if u["unitId"] == unit_id and u["verdict"] in ("over", "no_window"):
            raise HttpError(409, f"{u['name']}: {u['summary']} Pick another unit or date, or confirm that you want to go ahead anyway.")


def units_with_load(db: sqlite3.Connection, today: str, weeks: int = 4) -> list[dict]:
    """Our units with their capacity and how booked each of the coming weeks is (Monday to Saturday)."""
    by_unit = bookings(db)
    monday = (to_date(today) - timedelta(days=to_date(today).weekday())).isoformat()
    out = []
    for u in db.execute("SELECT id, name, kind, process, daily_capacity FROM units ORDER BY kind, name"):
        row = {"id": u["id"], "name": u["name"], "kind": u["kind"], "process": u["process"], "dailyCapacity": u["daily_capacity"], "weeks": []}
        if u["kind"] == "own":
            load = cap.daily_load(by_unit.get(u["id"], []), CALENDAR, today)
            for w in range(weeks):
                start = add_days(monday, 7 * w)
                days = [d for d in (add_days(start, i) for i in range(7)) if CALENDAR.is_working_day(d)]
                total = (u["daily_capacity"] or 0) * len(days)
                booked = sum(load.get(d, 0.0) for d in days)
                row["weeks"].append({"from": start, "booked": round(booked), "possible": total, "utilisation": round(booked / total, 2) if total else None})
        out.append(row)
    return out
