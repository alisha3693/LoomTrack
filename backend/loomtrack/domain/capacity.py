"""Does a unit have room for an order?

Pure and deterministic, like the delay engine. The question is asked about stitching, the stage
that decides how many pieces a unit can turn out in a day. Each unit has a daily capacity (pieces
a day). Every order already stitching there is spread evenly over the working days it has left,
and a new order is spread over the stitching window its template would give it. The check is the
total of the two against what the unit can do in those days.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import Calendar, add_days

# Up to this share of the unit's capacity there is room to spare; up to 100% it is tight; above, over.
COMFORTABLE = 0.85
# A stitching window that has already passed still has pieces to make. Assume they take this many working days from today.
OVERDUE_SPREAD_DAYS = 5
# How far ahead to look for the first date a unit could take an order.
HORIZON_DAYS = 120


@dataclass(frozen=True)
class Booking:
    """Stitching an order still has to do at a unit."""

    order_no: str
    po_no: str
    qty_left: int
    start: str
    end: str


def window(cal: Calendar, start: str, end: str, today: str, *, overdue_spread: bool) -> list[str]:
    """The working days a stage can still use: from today (or its start, if later) to its end.

    A booking whose window has passed is spread over the next few working days (overdue_spread);
    a new order whose window has passed has no days at all, because it cannot be done in time.
    """
    first = max(start, today)
    days, d = [], first
    while d <= end:
        if cal.is_working_day(d):
            days.append(d)
        d = add_days(d, 1)
    if days or not overdue_spread:
        return days
    d = today
    while len(days) < OVERDUE_SPREAD_DAYS:
        if cal.is_working_day(d):
            days.append(d)
        d = add_days(d, 1)
    return days


def daily_load(bookings: list[Booking], cal: Calendar, today: str) -> dict[str, float]:
    """Pieces a day the existing bookings already take, by date."""
    load: dict[str, float] = {}
    for b in bookings:
        if b.qty_left <= 0:
            continue
        days = window(cal, b.start, b.end, today, overdue_spread=True)
        for d in days:
            load[d] = load.get(d, 0.0) + b.qty_left / len(days)
    return load


@dataclass(frozen=True)
class Fit:
    verdict: str  # 'fits' | 'tight' | 'over' | 'no_window' | 'unknown'
    days: list[str]
    existing: float
    capacity_total: float
    utilisation: float | None  # 1.0 = every piece of capacity in the window is used


def fit(capacity: int | None, load: dict[str, float], days: list[str], qty: int) -> Fit:
    if capacity is None:
        return Fit("unknown", days, sum(load.get(d, 0.0) for d in days), 0.0, None)
    existing = sum(load.get(d, 0.0) for d in days)
    if not days:
        return Fit("no_window", days, existing, 0.0, None)
    total = float(capacity * len(days))
    util = (existing + qty) / total
    verdict = "fits" if util <= COMFORTABLE else "tight" if util <= 1.0 else "over"
    return Fit(verdict, days, existing, total, util)


def new_order_days(cal: Calendar, ex_factory: str, start_offset: int, end_offset: int, today: str) -> list[str]:
    """The stitching window a plan would give an order shipping on ex_factory, in the plan's own way:
    offsets are calendar days before ex-factory and each end snaps back to a working day."""
    start = cal.snap_back(add_days(ex_factory, -start_offset))
    end = cal.snap_back(add_days(ex_factory, -end_offset))
    return window(cal, start, end, today, overdue_spread=False)
