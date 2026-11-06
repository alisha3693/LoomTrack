"""Is something an order needs going to be there when the plan needs it?

Pure and deterministic, like the delay engine: dates in, a state and a sentence out. This does not
feed the delay projection. It sits beside it, so a late roll of fabric is visible before the day the
"Fabric in-house" milestone goes overdue.
"""

from __future__ import annotations

from .calendar import to_date
from .runrate import pretty_date

# Not ordered, and needed within this many days: worth a look even though nothing is late yet.
NOT_ORDERED_DAYS = 14
# Ordered but nobody has recorded when it arrives, and needed within this many days.
NO_DATE_DAYS = 7

# Worst first, for sorting and for the one-word summary on the board.
RANK = {"late": 0, "at_risk": 1, "on_track": 2, "received": 3}


def _days(a: str, b: str) -> int:
    """Calendar days from b to a (positive when a is later)."""
    return (to_date(a) - to_date(b)).days


def _n(n: int, unit: str = "day") -> str:
    return f"{n} {unit}{'' if n == 1 else 's'}"


def material_risk(
    *, status: str, expected: str | None, received: str | None, needed_by: str, needed_label: str, today: str
) -> dict:
    """`needed_label` says what the date is, for example "Cutting starts" or "Fabric in-house is due"."""
    need = f"{needed_label} {pretty_date(needed_by)}"
    if status == "received":
        gap = _days(received, needed_by) if received else 0
        late = f", {_n(gap)} after it was needed" if gap > 0 else ""
        return {"state": "received", "message": f"Received {pretty_date(received)}{late}" if received else "Received"}

    if expected:
        if expected > needed_by:
            return {"state": "late", "message": f"Arrives {pretty_date(expected)}, {_n(_days(expected, needed_by))} after it is needed ({need})"}
        if today > expected:
            return {"state": "late", "message": f"Was expected {pretty_date(expected)} and has not arrived ({need})"}
        return {"state": "on_track", "message": f"Expected {pretty_date(expected)}, {_n(_days(needed_by, expected))} before it is needed ({need})"}

    left = _days(needed_by, today)
    if left <= 0:
        return {"state": "late", "message": f"Needed now ({need}) and no arrival date is recorded"}
    if status == "not_ordered" and left <= NOT_ORDERED_DAYS:
        return {"state": "at_risk", "message": f"Not ordered yet and needed in {_n(left)} ({need})"}
    if status == "ordered" and left <= NO_DATE_DAYS:
        return {"state": "at_risk", "message": f"Ordered but no arrival date, and needed in {_n(left)} ({need})"}
    return {"state": "on_track", "message": "Not ordered yet" if status == "not_ordered" else "Ordered, no arrival date yet"}


def worst(states: list[str]) -> str | None:
    """The state to show for a whole order: the worst of its open materials, else received, else None."""
    return min(states, key=RANK.__getitem__) if states else None
