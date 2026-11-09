"""The pure calculation: does a unit have room for an order."""

import pytest

from loomtrack.domain import capacity as cap
from loomtrack.domain.calendar import Calendar

TODAY = "2026-11-05"  # a Thursday
CAL = Calendar(frozenset({"2026-11-08"}))  # 8 Nov is a Sunday and a holiday


# --- capacity -------------------------------------------------------------------------------------


def test_window_runs_from_today_to_the_end_and_skips_sundays_and_holidays():
    days = cap.window(CAL, "2026-11-02", "2026-11-14", TODAY, overdue_spread=False)
    assert days[0] == "2026-11-05" and days[-1] == "2026-11-14"
    assert "2026-11-08" not in days and len(days) == 9
    assert cap.window(CAL, "2026-11-10", "2026-11-12", TODAY, overdue_spread=False) == ["2026-11-10", "2026-11-11", "2026-11-12"]   # not started yet: its own days


def test_a_window_that_has_passed():
    assert cap.window(CAL, "2026-10-01", "2026-10-20", TODAY, overdue_spread=False) == []         # a new order cannot be done in time
    spread = cap.window(CAL, "2026-10-01", "2026-10-20", TODAY, overdue_spread=True)              # existing work still has to be done
    assert spread == ["2026-11-05", "2026-11-06", "2026-11-07", "2026-11-09", "2026-11-10"]


def test_existing_work_is_spread_evenly_over_the_days_it_has_left():
    load = cap.daily_load([cap.Booking("LT-1", "P1", 900, "2026-11-05", "2026-11-07"), cap.Booking("LT-2", "P2", 100, "2026-11-06", "2026-11-06")], CAL, TODAY)
    assert load == {"2026-11-05": 300.0, "2026-11-06": 400.0, "2026-11-07": 300.0}
    assert cap.daily_load([cap.Booking("LT-3", "P3", 0, "2026-11-05", "2026-11-07")], CAL, TODAY) == {}          # nothing left to do
    # Half of a window already used: only the days left share the pieces left.
    assert cap.daily_load([cap.Booking("LT-4", "P4", 600, "2026-11-02", "2026-11-06")], CAL, TODAY) == {"2026-11-05": 300.0, "2026-11-06": 300.0}


@pytest.mark.parametrize("qty,verdict", [(8500, "fits"), (8501, "tight"), (10000, "tight"), (10001, "over")])
def test_the_verdict_thresholds(qty, verdict):
    days = [f"2026-11-{d:02d}" for d in range(9, 19)]                # ten working days at 1,000 a day
    f = cap.fit(1000, {}, days, qty)
    assert f.verdict == verdict and f.capacity_total == 10000


def test_existing_load_counts_against_a_new_order():
    days = ["2026-11-09", "2026-11-10"]
    f = cap.fit(1000, {"2026-11-09": 700.0, "2026-11-10": 700.0}, days, 500)
    assert f.existing == 1400 and f.utilisation == pytest.approx(0.95) and f.verdict == "tight"


def test_unknown_when_no_capacity_and_no_window_when_there_are_no_days():
    assert cap.fit(None, {}, ["2026-11-09"], 100).verdict == "unknown"
    assert cap.fit(1000, {}, [], 100).verdict == "no_window"


def test_new_order_window_follows_the_plan_offsets():
    # Stitching from 24 to 7 days before 30 Nov: 6 Nov to 23 Nov, from today. Sundays and the 8 Nov holiday are out.
    days = cap.new_order_days(CAL, "2026-11-30", 24, 7, TODAY)
    assert days[0] == "2026-11-06" and days[-1] == "2026-11-23"
    assert "2026-11-08" not in days and "2026-11-15" not in days and "2026-11-22" not in days
    assert cap.new_order_days(CAL, "2026-11-10", 24, 7, TODAY) == []     # the stitching would have ended on 3 Nov, before today
