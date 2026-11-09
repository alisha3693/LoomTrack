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
from ..domain.tna import Template, TemplateItem, plan_from_template
from ..util import HttpError


STITCHING = "stitching"
VERBS = {"cutting": "cut", "stitching": "stitch", "finishing": "finish", "packing": "pack", "embroidery": "embroider"}
SEVERITY = {"unknown": 0, "fits": 1, "tight": 2, "over": 3, "no_window": 4}


def subcontract_processes(db: sqlite3.Connection) -> set[str]:
    """Processes done at job-work units (printing, washing). Those stages are not ours to count."""
    return {r["process"] for r in db.execute("SELECT DISTINCT process FROM units WHERE kind = 'subcontract' AND process IS NOT NULL")}


def own_stages(db: sqlite3.Connection, t: Template) -> list[TemplateItem]:
    """The plan's production stages done in our own units: no milestones, no job work."""
    job_work = subcontract_processes(db)
    return [i for i in t.items if i.kind == "stage" and i.start_offset is not None and i.process and i.process not in job_work]


def own_processes(db: sqlite3.Connection) -> list[str]:
    """Every process an own unit can be given a daily capacity for, in the order a garment goes through them."""
    from .templates import STANDARD_PROCESSES

    job_work = subcontract_processes(db)
    found = {r["process"] for r in db.execute("SELECT DISTINCT process FROM plan_steps WHERE kind = 'stage' AND process IS NOT NULL")}
    every = (found | set(STANDARD_PROCESSES)) - job_work
    first = [p for p in ("cutting", "embroidery", STITCHING, "finishing", "packing") if p in every]
    return first + sorted(every - set(first))


def capacities(db: sqlite3.Connection) -> dict[tuple[int, str], int]:
    """Pieces a day each own unit can do, by (unit, process). Stitching is kept on the unit itself."""
    out: dict[tuple[int, str], int] = {}
    for r in db.execute("SELECT id, daily_capacity FROM units WHERE kind = 'own' AND daily_capacity IS NOT NULL"):
        out[(r["id"], STITCHING)] = r["daily_capacity"]
    for r in db.execute("SELECT unit_id, process, daily_capacity FROM unit_capacity"):
        out[(r["unit_id"], r["process"])] = r["daily_capacity"]
    return out


def set_capacity(db: sqlite3.Connection, unit_id: int, process: str, value: int | None) -> None:
    if process == STITCHING:
        db.execute("UPDATE units SET daily_capacity = ? WHERE id = ?", (value, unit_id))
    elif value is None:
        db.execute("DELETE FROM unit_capacity WHERE unit_id = ? AND process = ?", (unit_id, process))
    else:
        db.execute(
            "INSERT INTO unit_capacity (unit_id, process, daily_capacity) VALUES (?,?,?) "
            "ON CONFLICT(unit_id, process) DO UPDATE SET daily_capacity = excluded.daily_capacity",
            (unit_id, process, value),
        )


def stitching_item(t: Template) -> TemplateItem | None:
    """The first stitching stage of the plan."""
    return next((i for i in t.items if i.kind == "stage" and i.process == STITCHING), None)


def bookings(db: sqlite3.Connection, exclude_order_id: int | None = None, process: str = STITCHING) -> dict[int, list[cap.Booking]]:
    """What is still to do on active orders for one process, by the unit doing it (the stage's unit, not the order's)."""
    out: dict[int, list[cap.Booking]] = {}
    for r in db.execute(
        """SELECT m.unit_id, m.planned_start, m.planned_date, o.id AS order_id, o.order_no, o.po_no, o.qty_total,
             COALESCE((SELECT SUM(d.qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS made
           FROM milestones m JOIN plan_steps s ON s.code = m.code JOIN orders o ON o.id = m.order_id
           WHERE o.state = 'active' AND s.kind = 'stage' AND s.process = ? AND m.unit_id IS NOT NULL""",
        (process,),
    ):
        if r["order_id"] == exclude_order_id:
            continue
        left = r["qty_total"] - r["made"]
        if left > 0:
            out.setdefault(r["unit_id"], []).append(
                cap.Booking(r["order_no"], r["po_no"], left, r["planned_start"] or r["planned_date"], r["planned_date"])
            )
    return out


def plan_check(t: Template, ex_factory: str, today: str) -> dict:
    """The plan this ex-factory date would give, and the steps already past due on the day the order is made.
    Those are the steps the early warning would flag the moment the order exists, so they are shown before."""
    steps = [p for p in plan_from_template(CALENDAR, t, ex_factory) if p.item.code != "EXF" and p.planned_date < today]
    late = [
        {"name": p.item.name_en, "due": p.planned_date, "workingDaysLate": CALENDAR.working_day_diff(p.planned_date, today)}
        for p in steps
    ]
    worst = max((s["workingDaysLate"] for s in late), default=0)
    last = max((p.planned_date for p in plan_from_template(CALENDAR, t, ex_factory) if p.item.code != "EXF"), default=None)
    earliest = None
    if late:
        # the smallest shift that puts every step on or after today: the earliest step's offset counted from today
        biggest = max(max(i.end_offset, i.start_offset or 0) for i in t.items if i.code != "EXF")
        earliest = CALENDAR.next_working_day(add_days(today, biggest))
    return {"lateSteps": late, "worstDaysLate": worst, "lastStepDue": last, "earliestCleanExFactory": earliest}


def _summary(name: str, f: cap.Fit, qty: int, process: str = STITCHING) -> str:
    what = "" if process == STITCHING else f"{process.capitalize()}: "
    if f.verdict == "unknown":
        return f"{what}No daily capacity is set for {name}, so it cannot be checked. Set it on the Units page."
    if f.verdict == "no_window":
        return f"{what}The {process} step would have to finish before today, so {name} cannot make this date."
    pct = round((f.utilisation or 0) * 100)
    return (
        f"{what}Would be {pct}% booked across {len(f.days)} working days ({pretty_date(f.days[0])} to {pretty_date(f.days[-1])}): "
        f"{round(f.existing):,} pcs already booked, {qty:,} more needed, {round(f.capacity_total):,} possible."
    )


def _stage_fit(item: TemplateItem, unit: sqlite3.Row, capacity: int | None, existing: list[cap.Booking], qty: int, ex_factory: str, today: str) -> dict:
    days = cap.new_order_days(CALENDAR, ex_factory, item.start_offset, item.end_offset, today)
    load = cap.daily_load(existing, CALENDAR, today)
    f = cap.fit(capacity, load, days, qty)
    mine = set(days)
    overlapping = sorted(
        (
            {"orderNo": b.order_no, "poNo": b.po_no, "qtyLeft": b.qty_left}
            for b in existing
            if mine & set(cap.window(CALENDAR, b.start, b.end, today, overdue_spread=True))
        ),
        key=lambda o: -o["qtyLeft"],
    )[:5]
    process = item.process
    return {
        "process": process, "stage": item.name_en, "verb": VERBS.get(process, "do"), "capacity": capacity, "verdict": f.verdict,
        "utilisation": None if f.utilisation is None else round(f.utilisation, 2),
        "needed": qty, "booked": round(f.existing), "possible": round(f.capacity_total),
        "workingDays": len(f.days), "windowStart": f.days[0] if f.days else None, "windowEnd": f.days[-1] if f.days else None,
        "requiredPerDay": round(qty / len(f.days)) if f.days else None,
        "overlapping": overlapping, "summary": _summary(unit["name"], f, qty, process),
        "_load": load,
    }


def _earliest(stages: list[tuple[TemplateItem, int, dict]], qty: int, after: str, today: str) -> dict | None:
    """The first working day after `after` on which every checked stage of the unit would fit."""
    for k in range(1, cap.HORIZON_DAYS + 1):
        ex = add_days(after, k)
        if not CALENDAR.is_working_day(ex):
            continue
        fits = [cap.fit(c, load, cap.new_order_days(CALENDAR, ex, i.start_offset, i.end_offset, today), qty) for i, c, load in stages]
        if all(f.verdict in ("fits", "tight") for f in fits):
            return {"exFactory": ex, "utilisation": round(max(f.utilisation or 0 for f in fits), 2)}
    return None


def check(db: sqlite3.Connection, qty: int, ex_factory: str, t: Template, today: str, exclude_order_id: int | None = None) -> dict:
    """Every own production stage of the plan, at each of our units. A unit's verdict is that of its tightest stage."""
    items = own_stages(db, t)
    plan = plan_check(t, ex_factory, today)
    if not items:
        return {"stitching": None, "stages": [], "units": [], "plan": plan}
    caps = capacities(db)
    by_process = {i.process: bookings(db, exclude_order_id, i.process) for i in items}
    stitch = stitching_item(t)
    units = []
    for u in db.execute("SELECT id, name FROM units WHERE kind = 'own' ORDER BY name"):
        rows = [
            (i, _stage_fit(i, u, caps.get((u["id"], i.process)), by_process[i.process].get(u["id"], []), qty, ex_factory, today))
            for i in items
        ]
        # The stage that decides: the worst verdict, then the most booked one. A stage with no capacity set is listed, never decisive.
        _, lead = max(rows, key=lambda r: (SEVERITY[r[1]["verdict"]], r[1]["utilisation"] or 0))
        earliest = None
        if lead["verdict"] in ("over", "no_window"):
            checked = [(i, caps[(u["id"], i.process)], r["_load"]) for i, r in rows if caps.get((u["id"], i.process))]
            earliest = _earliest(checked, qty, ex_factory, today)
        units.append({
            "unitId": u["id"], "name": u["name"], **{k: v for k, v in lead.items() if k not in ("_load", "stage", "verb", "process")},
            "limitingStage": lead["stage"], "limitingProcess": lead["process"], "verb": lead["verb"],
            "notSet": [r["stage"] for _, r in rows if r["verdict"] == "unknown"],
            "earliest": earliest,
            "stages": [{k: v for k, v in r.items() if k != "_load"} for _, r in rows],
        })
    return {
        "stitching": {"name": stitch.name_en, "startOffset": stitch.start_offset, "endOffset": stitch.end_offset} if stitch else None,
        "stages": [{"process": i.process, "name": i.name_en, "startOffset": i.start_offset, "endOffset": i.end_offset} for i in items],
        "units": units,
        "plan": plan,
    }


def guard(db: sqlite3.Connection, unit_id: int, qty: int, ex_factory: str, t: Template, today: str, allowed: bool) -> None:
    """Refuse an order that would put its unit over capacity, unless the merchandiser has said to go ahead.
    A stage with no capacity set is not checked."""
    if allowed:
        return
    for u in check(db, qty, ex_factory, t, today)["units"]:
        if u["unitId"] == unit_id and u["verdict"] in ("over", "no_window"):
            raise HttpError(409, f"{u['name']}: {u['summary']} Pick another unit or date, or confirm that you want to go ahead anyway.")


def units_with_load(db: sqlite3.Connection, today: str, weeks: int = 4) -> list[dict]:
    """Our units with their capacity for each stage and how booked each of the coming weeks is (Monday to Saturday)."""
    caps = capacities(db)
    processes = own_processes(db)
    by_process = {p: bookings(db, None, p) for p in processes}
    monday = (to_date(today) - timedelta(days=to_date(today).weekday())).isoformat()
    out = []
    for u in db.execute("SELECT id, name, kind, process, daily_capacity FROM units ORDER BY kind, name"):
        row = {"id": u["id"], "name": u["name"], "kind": u["kind"], "process": u["process"], "dailyCapacity": u["daily_capacity"], "weeks": [], "processes": []}
        if u["kind"] == "own":
            for p in processes:
                capacity = caps.get((u["id"], p))
                load = cap.daily_load(by_process[p].get(u["id"], []), CALENDAR, today)
                wk = []
                for w in range(weeks):
                    start = add_days(monday, 7 * w)
                    days = [d for d in (add_days(start, i) for i in range(7)) if CALENDAR.is_working_day(d)]
                    total = (capacity or 0) * len(days)
                    booked = sum(load.get(d, 0.0) for d in days)
                    wk.append({"from": start, "booked": round(booked), "possible": total, "utilisation": round(booked / total, 2) if total else None})
                row["processes"].append({"process": p, "dailyCapacity": capacity, "weeks": wk})
            row["weeks"] = next((x["weeks"] for x in row["processes"] if x["process"] == STITCHING), [])
        out.append(row)
    return out
