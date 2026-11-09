"""The numbers behind the brief's success measures, worked out from what the app already records.

- On-time shipping: shipped orders against their ex-factory date (the goal: late shipments from 8% to 5%).
- Early warning: how many days before the ex-factory date the first delay warning was raised (the goal: two weeks).
- Floor adoption: did each supervisor send updates today and this week.
- Buyer page views: how often buyers look for themselves instead of emailing.
"""

from __future__ import annotations

import sqlite3

from ..domain.calendar import add_days, to_date
from .shipping import days_late, verdict

TARGET_LATE_PCT = 5   # the goal in the brief
BASELINE_LATE_PCT = 8  # where the client is today
WARNING_LEAD_DAYS = 14  # "two weeks early, not two days"


def on_time(db: sqlite3.Connection) -> dict:
    rows = db.execute(
        """SELECT o.id, o.po_no, o.style, o.ex_factory, o.shipped_date, b.name AS buyer
           FROM orders o JOIN buyers b ON b.id = o.buyer_id WHERE o.state = 'shipped' AND o.shipped_date IS NOT NULL
           ORDER BY o.shipped_date DESC, o.id DESC"""
    ).fetchall()
    orders = [
        {"id": r["id"], "poNo": r["po_no"], "style": r["style"], "buyer": r["buyer"], "exFactory": r["ex_factory"], "shippedDate": r["shipped_date"],
         "daysLate": days_late(r["shipped_date"], r["ex_factory"]), "verdict": verdict(r["shipped_date"], r["ex_factory"])}
        for r in rows
    ]
    late = [o for o in orders if o["daysLate"] > 0]
    return {
        "shipped": len(orders), "late": len(late), "onTime": len(orders) - len(late),
        "latePct": round(100 * len(late) / len(orders), 1) if orders else None,
        "averageDaysLate": round(sum(o["daysLate"] for o in late) / len(late), 1) if late else 0,
        "targetPct": TARGET_LATE_PCT, "baselinePct": BASELINE_LATE_PCT,
        "orders": orders,
    }


def early_warning(db: sqlite3.Connection) -> dict:
    """The first warning on each order: how far ahead of the ex-factory date it was raised."""
    rows = db.execute(
        """SELECT o.id, o.po_no, o.ex_factory, o.state, o.shipped_date, b.name AS buyer, w.level,
             COALESCE(w.warned_on, substr(w.created_at, 1, 10)) AS warned_on
           FROM warnings w JOIN orders o ON o.id = w.order_id JOIN buyers b ON b.id = o.buyer_id
           WHERE w.id = (SELECT MIN(w2.id) FROM warnings w2 WHERE w2.order_id = o.id) AND o.state != 'cancelled'
           ORDER BY o.ex_factory"""
    ).fetchall()
    orders = [
        {"id": r["id"], "poNo": r["po_no"], "buyer": r["buyer"], "level": r["level"], "warnedOn": r["warned_on"], "exFactory": r["ex_factory"],
         "leadDays": (to_date(r["ex_factory"]) - to_date(r["warned_on"])).days, "state": r["state"]}
        for r in rows
    ]
    early = [o for o in orders if o["leadDays"] >= WARNING_LEAD_DAYS]
    return {
        "warned": len(orders), "earlyEnough": len(early),
        "averageLeadDays": round(sum(o["leadDays"] for o in orders) / len(orders), 1) if orders else None,
        "targetDays": WARNING_LEAD_DAYS, "orders": orders,
    }


def floor(db: sqlite3.Connection, today: str) -> dict:
    week_start = add_days(today, -6)
    people = db.execute(
        """SELECT u.id, u.name, un.name AS unit,
             (SELECT COUNT(*) FROM daily_updates d WHERE d.user_id = u.id AND d.work_date = ?) AS today_updates,
             (SELECT COUNT(DISTINCT d.work_date) FROM daily_updates d WHERE d.user_id = u.id AND d.work_date BETWEEN ? AND ?) AS days_this_week,
             (SELECT MAX(d.work_date) FROM daily_updates d WHERE d.user_id = u.id) AS last_update
           FROM users u LEFT JOIN units un ON un.id = u.unit_id WHERE u.role = 'supervisor' ORDER BY un.name, u.name""",
        (today, week_start, today),
    ).fetchall()
    out = [{"name": r["name"], "unit": r["unit"], "updatesToday": r["today_updates"], "daysThisWeek": r["days_this_week"], "lastUpdate": r["last_update"]} for r in people]
    return {"today": today, "supervisors": out, "sentToday": sum(1 for p in out if p["updatesToday"]), "total": len(out)}


def buyer_views(db: sqlite3.Connection, today: str) -> dict:
    d7, d30 = add_days(today, -6), add_days(today, -29)
    rows = db.execute(
        """SELECT b.id, b.name,
             COALESCE((SELECT SUM(n) FROM buyer_visits v WHERE v.buyer_id = b.id AND v.day BETWEEN ? AND ?), 0) AS week,
             COALESCE((SELECT SUM(n) FROM buyer_visits v WHERE v.buyer_id = b.id AND v.day BETWEEN ? AND ?), 0) AS month,
             (SELECT MAX(day) FROM buyer_visits v WHERE v.buyer_id = b.id) AS last_seen
           FROM buyers b ORDER BY b.name""",
        (d7, today, d30, today),
    ).fetchall()
    out = [{"buyer": r["name"], "week": r["week"], "month": r["month"], "lastSeen": r["last_seen"]} for r in rows]
    return {"buyers": out, "week": sum(b["week"] for b in out), "month": sum(b["month"] for b in out)}


def all_reports(db: sqlite3.Connection, today: str) -> dict:
    return {"today": today, "delivery": on_time(db), "warnings": early_warning(db), "floor": floor(db, today), "buyers": buyer_views(db, today)}


def count_buyer_visit(db: sqlite3.Connection, buyer_id: int, today: str, via: str) -> None:
    db.execute(
        "INSERT INTO buyer_visits (buyer_id, day, via, n) VALUES (?,?,?,1) ON CONFLICT (buyer_id, day, via) DO UPDATE SET n = n + 1",
        (buyer_id, today, via),
    )
