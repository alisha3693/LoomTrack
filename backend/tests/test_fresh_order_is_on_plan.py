"""An order that has just been accepted, with no output yet, must never read as late.

The plan's own dates are the promise; the projection may only call an order late when the floor numbers or the
calendar say so. Plans are built from the starting templates and from random merchandiser-made ones, including
stages that overlap or end on the same day, and every ex-factory date, so a weekend never decides the answer.
"""

import random
from datetime import date, timedelta

from loomtrack.config import CALENDAR
from loomtrack.domain import runrate
from loomtrack.domain.tna import BUILTIN_TEMPLATES, Template, TemplateItem, plan_from_template


def _project(t, ex, today, qty=1000):
    plan = plan_from_template(CALENDAR, t, ex)
    stages = [runrate.StageInput(p.item.code, p.item.name_en, p.planned_start, p.planned_date) for p in plan if p.item.kind == "stage"]
    return runrate.project_order(today=today, ex_factory=ex, order_qty=qty, stages=stages, calendar=CALENDAR)


def _first_start(t, ex):
    plan = plan_from_template(CALENDAR, t, ex)
    return min(p.planned_start for p in plan if p.item.kind == "stage")


def test_builtin_plans_are_on_plan_before_any_work():
    for t in BUILTIN_TEMPLATES.values():
        for n in range(0, 120):
            ex = (date(2026, 11, 30) + timedelta(days=n)).isoformat()
            first = _first_start(t, ex)
            for today in (CALENDAR.prev_working_day(first), CALENDAR.shift_working_days(first, -5)):
                p = _project(t, ex, today)
                assert p.status == "green" and p.slack_days == 0, (t.key, ex, today, p.reasons)


def test_merchandiser_made_plans_with_overlap_are_on_plan_before_any_work():
    rng = random.Random(7)
    for trial in range(300):
        items, end = [], rng.randint(2, 6)
        for k in range(rng.randint(1, 5)):
            runs = rng.randint(0, 9)
            start = end + runs
            items.append(TemplateItem(f"S{k}", f"Stage {k}", f"Stage {k}", "stage", end, start, "stitching" if k == 0 else "finishing"))
            end = start + rng.choice([-2, -1, 0, 1, 2]) if runs else start + 1  # stages may overlap or end together
            end = max(end, 1)
        items.sort(key=lambda i: -i.end_offset)
        items.append(TemplateItem("EXF", "Ex-factory", "Ex-factory", "milestone", 0))
        t = Template("t", "t", tuple(items))
        ex = (date(2026, 12, 1) + timedelta(days=rng.randint(0, 200))).isoformat()
        today = CALENDAR.prev_working_day(_first_start(t, ex))
        p = _project(t, ex, today)
        assert p.status == "green" and p.slack_days == 0, (trial, [(i.code, i.start_offset, i.end_offset) for i in items], ex, p.reasons)
