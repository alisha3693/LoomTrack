from loomtrack.domain.calendar import Calendar
from loomtrack.domain.runrate import DailyQty, StageInput, project_order

cal = Calendar(frozenset({"2026-11-08"}))
TODAY = "2026-11-05"  # Thursday


def days(end: str, n: int, qty: int) -> list[DailyQty]:
    """n working days of `qty` ending on `end`."""
    out, d = [], end
    for _ in range(n):
        out.insert(0, DailyQty(d, qty))
        d = cal.prev_working_day(d)
    return out


def stage(code, start, end, daily=None):
    return StageInput(code, code, start, end, daily or [])


def project(ex_factory, qty, stages):
    return project_order(today=TODAY, ex_factory=ex_factory, order_qty=qty, stages=stages, calendar=cal)


def test_calendar_skips_sundays_and_holidays():
    assert cal.count_working_days("2026-11-02", "2026-11-08") == 6
    assert cal.add_working_days("2026-11-07", 1) == "2026-11-09"
    assert cal.working_day_diff("2026-11-13", "2026-11-09") == -4


def test_green_when_rate_finishes_inside_plan():
    p = project("2026-11-20", 1000, [stage("STITCH", "2026-10-26", "2026-11-13", days(TODAY, 8, 100))])
    # 800 done, 200 left at 100/day → 2 working days → Sat 7 Nov, well before 13 Nov.
    assert p.stages[0].projected_finish == "2026-11-07"
    assert p.status == "green"


def test_shows_required_vs_actual():
    p = project("2026-11-20", 12000, [stage("STITCH", "2026-10-27", "2026-11-13", days(TODAY, 10, 680))])
    s = p.stages[0]
    assert s.done == 6800
    assert s.working_days_left == 7  # 6,7,9,10,11,12,13 Nov
    assert abs(s.required_per_day - 5200 / 7) < 1e-9
    assert s.run_rate == 680
    assert s.rate_window_days == 7
    assert "need 743 pcs/day for 7 days, making 680 pcs/day" in " ".join(p.reasons)


def test_today_not_counted_until_todays_number_is_in():
    p = project("2026-11-20", 1000, [stage("STITCH", "2026-10-26", "2026-11-13", days("2026-11-04", 5, 100))])
    assert p.stages[0].run_rate == 100
    assert p.stages[0].rate_window_days == 5


def test_red_when_projected_ex_factory_passes_plan():
    p = project("2026-11-12", 8000, [
        stage("FINISH", "2026-10-29", "2026-11-07", days(TODAY, 8, 650)),
        stage("PACK", "2026-11-04", "2026-11-09"),
    ])
    assert p.status == "red"
    assert p.slack_days < 0
    assert p.key_stage == "FINISH"


def test_amber_when_stage_slips_but_buffer_covers():
    p = project("2026-11-20", 12000, [
        stage("STITCH", "2026-10-27", "2026-11-13", days(TODAY, 10, 680)),
        stage("FINISH", "2026-11-06", "2026-11-16"),
        stage("PACK", "2026-11-12", "2026-11-17"),
    ])
    assert p.stages[0].slip_days == 1
    assert p.status == "amber"


def test_downstream_cannot_finish_before_upstream():
    p = project("2026-11-28", 10000, [
        stage("PRINT", "2026-11-02", "2026-11-14", days(TODAY, 4, 500)),
        stage("STITCH", "2026-11-04", "2026-11-21", days(TODAY, 2, 600)),
    ])
    printing, stitching = p.stages
    assert stitching.projected_finish > printing.projected_finish
    assert stitching.constrained_by_upstream


def test_starved_stage_gets_planned_capacity_but_queued_stage_keeps_its_pace():
    upstream = stage("STITCH", "2026-10-20", "2026-11-13", days(TODAY, 12, 400))  # 4800 done
    starved = project("2026-11-20", 10000, [upstream, stage("FINISH", "2026-10-26", "2026-11-16", days(TODAY, 10, 450))])  # 300 waiting
    assert starved.stages[1].run_rate > 450
    queued = project("2026-11-20", 10000, [upstream, stage("FINISH", "2026-10-26", "2026-11-16", days(TODAY, 4, 200))])  # 4000 waiting
    assert queued.stages[1].run_rate == 200


def test_planned_end_passed():
    p = project("2026-11-10", 1000, [stage("PACK", "2026-10-26", "2026-11-03", days(TODAY, 3, 100))])
    assert p.stages[0].required_per_day is None
    assert p.status == "red"


def test_not_started_stage_uses_planned_rate_from_planned_start():
    p = project("2026-12-15", 15000, [stage("CUT", "2026-11-14", "2026-11-25")])
    assert p.stages[0].rate_basis == "planned"
    assert p.stages[0].projected_finish == "2026-11-25"
    assert p.status == "green"


def test_stalled_stage_does_not_hang():
    # Planned end passed and rate 0 would otherwise mean "never finishes".
    p = project("2026-11-20", 1000, [stage("CUT", "2026-10-01", "2026-10-10", [DailyQty("2026-10-01", 100)])])
    assert p.status == "red"
