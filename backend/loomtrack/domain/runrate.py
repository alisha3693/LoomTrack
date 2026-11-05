"""Run-rate delay projection.

Pure and deterministic: given the plan and the floor numbers it returns a
status *and* every number it used, so the UI can show the maths
("need 743/day, making 669/day"). See docs/RUN_RATE.md.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal

from .calendar import Calendar, to_date

RateBasis = Literal["actual", "planned", "done"]
StageState = Literal["done", "on_track", "slipping", "not_started"]
OrderStatus = Literal["green", "amber", "red"]

NEVER = "9999-12-31"


@dataclass
class DailyQty:
    date: str
    qty: int


@dataclass
class StageInput:
    code: str
    name: str
    planned_start: str
    planned_end: str
    daily: list[DailyQty] = field(default_factory=list)


@dataclass
class StageProjection:
    code: str
    name: str
    done: int
    remaining: int
    pct: int
    planned_start: str
    planned_end: str
    # Working days from the next working day after `as_of` up to planned_end.
    working_days_left: int
    # Pieces per day needed to finish on plan. None once the planned end has passed.
    required_per_day: float | None
    # Pieces per day used for the projection.
    run_rate: float
    rate_basis: RateBasis
    # Working days averaged into an actual run rate.
    rate_window_days: int
    # True when the stage is waiting on its upstream stage rather than on its own capacity.
    constrained_by_upstream: bool
    projected_finish: str
    # Working days late versus planned_end (negative = early).
    slip_days: int
    state: StageState


@dataclass
class OrderProjection:
    status: OrderStatus
    ex_factory: str
    projected_ex_factory: str
    # Working days between projected and planned ex-factory (negative = late).
    slack_days: int
    # Stage that best explains the status: the most-slipping one, or the current one.
    key_stage: str | None
    stages: list[StageProjection]
    reasons: list[str]

    def to_json(self) -> dict:
        return _camel(asdict(self))


def _camel(obj):
    if isinstance(obj, dict):
        return {_camel_key(k): _camel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_camel(v) for v in obj]
    return obj


def _camel_key(k: str) -> str:
    head, *rest = k.split("_")
    return head + "".join(p.title() for p in rest)


def _fmt(n: float) -> str:
    return f"{round(n):,}"


def pretty_date(iso: str) -> str:
    """'2026-11-17' → 'Tue 17 Nov' (how the office and buyers write dates)."""
    d = to_date(iso)
    return f"{d:%a} {d.day} {d:%b}"


def _days(n: int, unit: str = "working day") -> str:
    return f"{n} {unit}{'' if n == 1 else 's'}"


def project_order(
    *,
    today: str,
    ex_factory: str,
    order_qty: int,
    stages: list[StageInput],
    calendar: Calendar,
    window_days: int = 7,
    lag_days: int = 1,
) -> OrderProjection:
    """Project every stage in process order (cutting → … → packing)."""
    cal = calendar
    out: list[StageProjection] = []
    upstream_finish: str | None = None
    upstream_done = True
    upstream_qty = order_qty

    for s in stages:
        daily = sorted((d for d in s.daily if d.qty > 0 and d.date <= today), key=lambda d: d.date)
        done = sum(d.qty for d in daily)
        remaining = max(0, order_qty - done)
        pct = min(100, round(done / order_qty * 100)) if order_qty > 0 else 0

        # The run-rate window ends today if today's numbers are in, else yesterday:
        # a morning board view shouldn't punish a stage for a day not yet worked.
        has_today = any(d.date == today for d in daily)
        as_of = today if has_today else cal.prev_working_day(today)

        working_days_left = cal.count_working_days(cal.next_working_day(as_of), s.planned_end)
        if remaining == 0:
            required: float | None = 0
        elif working_days_left > 0:
            required = remaining / working_days_left
        else:
            required = None

        planned_days = max(1, cal.count_working_days(s.planned_start, s.planned_end))
        planned_rate = order_qty / planned_days

        run_rate = 0.0
        window = 0
        constrained = False

        if remaining == 0:
            basis: RateBasis = "done"
            own_finish = daily[-1].date if daily else s.planned_end
        else:
            if daily:
                # Average over the last `window_days` working days, but never before
                # the stage's first entry (a stage that started 3 days ago has a 3-day window).
                first = daily[0].date
                window_start = as_of
                for _ in range(1, window_days):
                    prev = cal.prev_working_day(window_start)
                    if prev < first:
                        break
                    window_start = prev
                window_start = max(window_start, first)
                window = max(1, cal.count_working_days(window_start, as_of))
                in_window = sum(d.qty for d in daily if window_start <= d.date <= as_of)
                run_rate = in_window / window
                basis = "actual"
            else:
                run_rate = planned_rate
                basis = "planned"

            # A stage with less than a day's work waiting from an unfinished upstream
            # stage is starved: its measured rate shows the upstream's pace, not its
            # own capacity. Assume planned capacity then; the upstream chain below
            # still bounds it. With a real queue waiting, a slow rate is its own.
            waiting = upstream_qty - done
            starved = not upstream_done and waiting < planned_rate
            if starved and basis == "actual" and run_rate < planned_rate:
                run_rate = planned_rate
                constrained = True

            # Not started and not due yet: it begins at its planned start.
            start_from = cal.prev_working_day(s.planned_start) if not daily and s.planned_start > as_of else as_of
            own_finish = cal.add_working_days(start_from, math.ceil(remaining / run_rate)) if run_rate > 0 else NEVER

        projected = own_finish
        if upstream_finish and remaining > 0:
            chained = cal.add_working_days(upstream_finish, lag_days)
            if chained > projected:
                projected = chained
                constrained = True

        slip = cal.working_day_diff(s.planned_end, projected) if projected != NEVER else 999
        if remaining == 0:
            state: StageState = "done"
        elif not daily:
            state = "not_started"
        else:
            state = "slipping" if slip > 0 else "on_track"

        out.append(
            StageProjection(
                code=s.code, name=s.name, done=done, remaining=remaining, pct=pct,
                planned_start=s.planned_start, planned_end=s.planned_end,
                working_days_left=working_days_left, required_per_day=required,
                run_rate=run_rate, rate_basis=basis, rate_window_days=window,
                constrained_by_upstream=constrained, projected_finish=projected,
                slip_days=slip, state=state,
            )
        )
        upstream_finish = projected
        upstream_done = upstream_done and remaining == 0
        upstream_qty = done

    # Ex-factory keeps the plan's buffer after the last stage (final inspection,
    # loading): shift it by however late or early the last stage is projected.
    shifted = cal.shift_working_days(ex_factory, out[-1].slip_days) if out else ex_factory
    slack = -cal.working_day_diff(ex_factory, shifted)

    # Headline stage: the worst slipping stage that is slow on its own numbers
    # (the root cause, not a stage merely waiting on it); failing that, the
    # worst slipping stage, then the first unfinished one.
    slipping = sorted((s for s in out if s.slip_days > 0 and s.remaining > 0), key=lambda s: -s.slip_days)
    root = [s for s in slipping if not s.constrained_by_upstream]
    key = (root or slipping or [s for s in out if s.remaining > 0] or [None])[0]

    reasons: list[str] = []
    status: OrderStatus = "green"
    if slack < 0:
        status = "red"
        reasons.append(f"Projected ex-factory {pretty_date(shifted)} is {_days(-slack)} after the planned {pretty_date(ex_factory)}.")
    elif slipping and key:
        status = "amber"
        reasons.append(f"{key.name} is {_days(key.slip_days)} behind plan; the buffer still covers ex-factory.")

    if key and key.rate_basis == "actual" and key.required_per_day is not None and key.run_rate < key.required_per_day:
        reasons.append(
            f"{key.name}: need {_fmt(key.required_per_day)} pcs/day for {_days(key.working_days_left, 'day')}, "
            f"making {_fmt(key.run_rate)} pcs/day ({key.rate_window_days}-day average)."
        )
    elif key and key.required_per_day is None and key.remaining > 0:
        reasons.append(f"{key.name}: planned end {pretty_date(key.planned_end)} has passed with {_fmt(key.remaining)} pcs left.")

    return OrderProjection(
        status=status, ex_factory=ex_factory, projected_ex_factory=shifted, slack_days=slack,
        key_stage=key.code if key else None, stages=out, reasons=reasons,
    )
