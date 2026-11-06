"""The two pure calculations: is a material going to be there in time, and does a unit have room."""

import pytest

from loomtrack.domain import capacity as cap
from loomtrack.domain import materials as mat
from loomtrack.domain.calendar import Calendar

TODAY = "2026-11-05"  # a Thursday
CAL = Calendar(frozenset({"2026-11-08"}))  # 8 Nov is a Sunday and a holiday


def risk(status="ordered", expected=None, received=None, needed="2026-11-20", today=TODAY):
    return mat.material_risk(status=status, expected=expected, received=received, needed_by=needed, needed_label="Cutting starts", today=today)


# --- materials ------------------------------------------------------------------------------------


def test_received_is_received_and_says_when_it_came_late():
    assert risk("received", received="2026-11-10")["state"] == "received"
    assert "after it was needed" not in risk("received", received="2026-11-10")["message"]
    assert "2 days after it was needed" in risk("received", received="2026-11-22")["message"]


def test_an_arrival_date_after_the_need_date_is_late_and_says_by_how_much():
    r = risk(expected="2026-11-23")
    assert r["state"] == "late" and "3 days after it is needed" in r["message"]


def test_an_arrival_date_that_has_passed_without_arrival_is_late():
    r = risk(expected="2026-11-04")
    assert r["state"] == "late" and "has not arrived" in r["message"]


def test_arriving_before_it_is_needed_is_on_track():
    assert risk(expected="2026-11-18")["state"] == "on_track"
    assert risk(expected="2026-11-20")["state"] == "on_track"       # the day it is needed is still in time
    assert risk(expected=TODAY, needed=TODAY)["state"] == "on_track"


def test_no_arrival_date():
    assert risk("ordered", needed="2026-11-05")["state"] == "late"                   # needed today, nothing recorded
    assert risk("not_ordered", needed="2026-11-19")["state"] == "at_risk"            # 14 days: not ordered yet
    assert risk("not_ordered", needed="2026-11-20")["state"] == "on_track"           # 15 days: still time
    assert risk("ordered", needed="2026-11-12")["state"] == "at_risk"                # 7 days: ordered, no date
    assert risk("ordered", needed="2026-11-13")["state"] == "on_track"


def test_worst_state_of_an_order():
    assert mat.worst(["on_track", "late", "at_risk"]) == "late"
    assert mat.worst(["on_track", "at_risk"]) == "at_risk"
    assert mat.worst([]) is None


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
    assert f.existing == 1400 and f.utilisation == pytest.approx(0.95) and f.verdict == "tight" and f.free == 600


def test_unknown_when_no_capacity_and_no_window_when_there_are_no_days():
    assert cap.fit(None, {}, ["2026-11-09"], 100).verdict == "unknown"
    assert cap.fit(1000, {}, [], 100).verdict == "no_window"


def test_new_order_window_follows_the_plan_offsets():
    # Stitching from 24 to 7 days before 30 Nov: 6 Nov to 23 Nov, from today. Sundays and the 8 Nov holiday are out.
    days = cap.new_order_days(CAL, "2026-11-30", 24, 7, TODAY)
    assert days[0] == "2026-11-06" and days[-1] == "2026-11-23"
    assert "2026-11-08" not in days and "2026-11-15" not in days and "2026-11-22" not in days
    assert cap.new_order_days(CAL, "2026-11-10", 24, 7, TODAY) == []     # the stitching would have ended on 3 Nov, before today


def test_earliest_date_is_the_first_one_that_is_not_over():
    load = {d: 900.0 for d in cap.window(CAL, "2026-11-06", "2026-12-10", TODAY, overdue_spread=False)}   # a unit busy until 10 Dec
    found = cap.earliest_fit(1000, load, 6000, 24, 7, "2026-11-30", CAL, TODAY)
    assert found is not None
    date, util = found
    assert date > "2026-11-30" and util <= 1.0
    ok = lambda ex: cap.fit(1000, load, cap.new_order_days(CAL, ex, 24, 7, TODAY), 6000).verdict in ("fits", "tight")
    assert ok(date)
    d = cap.add_days("2026-11-30", 1)
    while d < date:                                                  # no earlier working day would have done
        if CAL.is_working_day(d):
            assert not ok(d)
        d = cap.add_days(d, 1)


def test_no_date_helps_when_the_window_is_simply_too_short():
    # 20,000 pieces in a 15-day window at 1,000 a day: moving the ship date never lengthens the window.
    assert cap.earliest_fit(1000, {}, 20000, 24, 7, "2026-11-30", CAL, TODAY) is None
    assert cap.earliest_fit(None, {}, 100, 24, 7, "2026-11-30", CAL, TODAY) is None
