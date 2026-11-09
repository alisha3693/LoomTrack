"""The weekly status email: once a week, each buyer's people get where their orders stand, with the Excel file attached.

A loop wakes every few minutes. From the chosen day and hour (`config.weekly_schedule`, Monday 08:00 unless changed)
it queues one email per buyer for that week, then stays quiet until next week. The record of what was queued is the
outbox itself, so a restart on the same morning does not send it twice. Only the buyer's own orders appear, and only
what a buyer is allowed to know: never the internal green, amber or red.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime

from .. import config
from ..domain.runrate import pretty_date
from ..util import iso_week
from . import buyer_view, clock, notify

EVENT = "weekly_status"


def _status_line(o: dict) -> str:
    if o["state"] == "shipped":
        status = f"shipped {pretty_date(o['shippedDate'])}" if o["shippedDate"] else "shipped"
    elif o["notice"]:
        status = f"delay notice, now expected {pretty_date(o['notice']['expectedExFactory'])}"
    elif o["overallPct"] >= 100:
        status = "packed, ready to ship"
    elif o["overallPct"] > 0:
        status = f"in production, {o['overallPct']}% packed"
    else:
        status = "planned"
    return f"- {o['poNo']} ({o['style']}, {o['colour'].lower()}): {status}. Ex-factory {pretty_date(o['exFactory'])}."


def _already_sent_this_week(db: sqlite3.Connection, buyer_id: int) -> bool:
    """True when a weekly email for this buyer was queued since this week's Monday, by the server's calendar."""
    return db.execute(
        "SELECT 1 FROM outbox_messages WHERE buyer_id = ? AND event = ? AND created_at >= date('now', 'localtime', 'weekday 0', '-6 days') LIMIT 1",
        (buyer_id, EVENT),
    ).fetchone() is not None


def is_due(now: datetime) -> bool:
    schedule = config.weekly_schedule()
    return schedule is not None and now.weekday() == schedule[0] and now.hour >= schedule[1]


def queue_weekly(db: sqlite3.Connection, now: datetime, today: str) -> int:
    """Queue this week's email for every buyer who has orders and has not had it yet. Returns how many buyers."""
    if not is_due(now):
        return 0
    sent = 0
    for b in db.execute("SELECT id FROM buyers ORDER BY id").fetchall():
        if _already_sent_this_week(db, b["id"]):
            continue
        orders = [o for o in buyer_view.buyer_orders(db, b["id"], today) if o["state"] in ("active", "shipped")]
        if not orders:
            continue
        notify.send(db, EVENT, b["id"], None, week=iso_week(today), text="\n".join(_status_line(o) for o in orders))
        sent += 1
    return sent


async def run_forever(db: sqlite3.Connection, every: float = 300.0) -> None:
    while True:
        try:
            queue_weekly(db, datetime.now(), clock.today(db))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # keep the loop alive; the next round tries again
            print(f"weekly status loop: {type(e).__name__}: {e}")
        await asyncio.sleep(every)
