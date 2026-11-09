"""The floor is part of the pipeline: what the supervisor sees and may enter follows the plan, the stage before, and the order's state."""

from test_api import _new_order, env, post_update, release, stage_id  # noqa: F401

EX = "2026-12-10"  # cutting started 23 Oct and stitching on 3 Nov, so both are due to be worked on the demo date


def _mine(env, oid):
    stages = env["client"].get("/api/s/orders", headers=env["sup1"]).json()["stages"]
    return {s["code"]: s for s in stages if s["order_id"] == oid}


def test_the_supervisor_sees_a_daily_target_and_what_the_stage_before_has_handed_over(env):
    oid = _new_order(env, "SUP-PIPE-1", 1, exFactory=EX, sizes=[{"size": "M", "qty": 1000}], overCapacityOk=True).json()["id"]
    cut = stage_id(env["db"], oid, "CUT")
    release(env["db"], cut)
    got = _mine(env, oid)
    assert set(got) == {"CUT"}  # stitching has nothing to work on until cutting hands pieces over, so it is not shown
    assert got["CUT"]["ready"] is None and got["CUT"]["upstream_name_en"] is None  # nothing comes before cutting
    assert got["CUT"]["target_per_day"] >= 1  # what is left over the working days left
    target = got["CUT"]["target_per_day"]
    assert post_update(env, "sup1", "pipe-cut-000001", cut, 400).status_code == 201
    after = _mine(env, oid)
    assert after["CUT"]["target_per_day"] == target  # today's target does not move as pieces are entered
    assert after["STITCH"]["ready"] == 400 and after["STITCH"]["upstream_name_en"] == "Cutting"


def test_a_stage_cannot_make_more_than_the_stage_before_has_finished(env):
    oid = _new_order(env, "SUP-PIPE-2", 1, exFactory=EX, sizes=[{"size": "M", "qty": 1000}], overCapacityOk=True).json()["id"]
    stitch = stage_id(env["db"], oid, "STITCH")
    blocked = post_update(env, "sup1", "pipe-st-0000001", stitch, 10)
    assert blocked.status_code == 422 and "Cutting" in blocked.text
    assert post_update(env, "sup1", "pipe-cut-000002", stage_id(env["db"], oid, "CUT"), 300).status_code == 201
    assert post_update(env, "sup1", "pipe-st-0000002", stitch, 300).status_code == 201
    assert post_update(env, "sup1", "pipe-st-0000003", stitch, 1).status_code == 422  # all 300 cut pieces are stitched
    assert post_update(env, "sup1", "pipe-cut-000003", stage_id(env["db"], oid, "CUT"), 100).status_code == 201
    assert post_update(env, "sup1", "pipe-st-0000004", stitch, 100).status_code == 201


def test_a_cancelled_order_leaves_the_floor_and_takes_no_more_output(env):
    oid = _new_order(env, "SUP-PIPE-3", 1, exFactory=EX, sizes=[{"size": "M", "qty": 500}], overCapacityOk=True).json()["id"]
    cut = stage_id(env["db"], oid, "CUT")
    release(env["db"], cut)
    assert _mine(env, oid)
    assert env["client"].post(f"/api/m/orders/{oid}/cancel", headers=env["merch"], json={"reason": "Buyer withdrew the PO"}).status_code == 200
    assert _mine(env, oid) == {}
    assert post_update(env, "sup1", "pipe-cut-000009", cut, 10).status_code == 409


def _open_steps(env, oid):
    return [r["code"] for r in env["db"].execute(
        "SELECT m.code FROM milestones m JOIN plan_steps s ON s.code = m.code WHERE m.order_id = ? AND s.kind = 'milestone' AND m.actual_date IS NULL", (oid,))]


def test_a_stage_is_hidden_until_the_office_marks_the_checkpoints_before_it_done(env):
    oid = _new_order(env, "SUP-GATE-1", 1, exFactory=EX, sizes=[{"size": "M", "qty": 500}], overCapacityOk=True).json()["id"]
    cut = stage_id(env["db"], oid, "CUT")
    assert _mine(env, oid) == {}  # not unlocked: the supervisor does not see it at all
    refused = post_update(env, "sup1", "gate-cut-0000001", cut, 10, released=False)
    assert refused.status_code == 409 and "Fabric in-house" in refused.text  # and the server refuses it too
    for code in ("FIT", "LAB", "PP", "FAB", "FABQC", "TRIMS"):
        assert _mine(env, oid) == {}
        mid = stage_id(env["db"], oid, code)
        assert env["client"].patch(f"/api/m/milestones/{mid}", headers=env["merch"], json={"actualDate": "2026-11-04"}).status_code == 200
    assert "CUT" in _mine(env, oid)  # the last one is marked done: it appears
    assert post_update(env, "sup1", "gate-cut-0000002", cut, 10, released=False).status_code == 201
    # unmarking a step later does not hide a stage that has already started
    mid = stage_id(env["db"], oid, "FAB")
    assert env["client"].patch(f"/api/m/milestones/{mid}", headers=env["merch"], json={"clearActual": True}).status_code == 200
    assert "CUT" in _mine(env, oid)
    assert post_update(env, "sup1", "gate-cut-0000003", cut, 10, released=False).status_code == 201


def test_a_checkpoint_before_a_stage_in_the_plan_locks_it_even_when_it_is_planned_the_same_day(env):
    oid = _new_order(env, "SUP-GATE-3", 1, exFactory=EX, sizes=[{"size": "M", "qty": 500}], overCapacityOk=True).json()["id"]
    db = env["db"]
    stitch = stage_id(db, oid, "STITCH")
    # the inspection sits between cutting and stitching in the template, and is planned for the day stitching starts
    start = db.execute("SELECT planned_start FROM milestones WHERE id = ?", (stitch,)).fetchone()[0]
    db.execute("UPDATE milestones SET actual_date = '2026-10-01' WHERE order_id = ? AND code <> 'INLINE' AND seq < (SELECT seq FROM milestones WHERE id = ?)", (oid, stitch))
    db.execute("UPDATE milestones SET planned_date = ?, actual_date = NULL WHERE order_id = ? AND code = 'INLINE'", (start, oid))
    assert post_update(env, "sup1", "gate-st-0000020", stage_id(db, oid, "CUT"), 500, released=False).status_code == 201
    assert "STITCH" not in _mine(env, oid)
    blocked = post_update(env, "sup1", "gate-st-0000021", stitch, 10, released=False)
    assert blocked.status_code == 409
    inline = stage_id(db, oid, "INLINE")
    assert env["client"].patch(f"/api/m/milestones/{inline}", headers=env["merch"], json={"actualDate": "2026-11-04"}).status_code == 200
    assert "STITCH" in _mine(env, oid)


def test_a_job_work_step_must_be_marked_done_before_the_next_stage_starts(env):
    env["db"].execute("INSERT OR IGNORE INTO units (id, name, kind, process) VALUES (40, 'Print job work', 'subcontract', 'printing')")
    oid = _new_order(env, "SUP-GATE-2", 1, exFactory="2027-01-20", templateKey="printed", sizes=[{"size": "M", "qty": 500}]).json()["id"]
    stitch = stage_id(env["db"], oid, "STITCH")
    print_step = stage_id(env["db"], oid, "PRINT")
    env["db"].execute("UPDATE milestones SET actual_date = '2026-10-01' WHERE order_id = ? AND code IN (SELECT code FROM plan_steps WHERE kind = 'milestone')", (oid,))
    cut_done = post_update(env, "sup1", "gate-cut-0000010", stage_id(env["db"], oid, "CUT"), 500, released=False)
    assert cut_done.status_code == 201
    waiting = post_update(env, "sup1", "gate-st-0000010", stitch, 10, released=False)
    assert waiting.status_code == 409 and "Print" in waiting.text
    assert env["client"].patch(f"/api/m/milestones/{print_step}", headers=env["merch"], json={"actualDate": "2026-11-04"}).status_code == 200
    assert post_update(env, "sup1", "gate-st-0000011", stitch, 10, released=False).status_code == 201


def test_a_tester_can_set_the_date_on_the_supervisors_side(env, monkeypatch):
    c = env["client"]
    monkeypatch.setenv("LOOMTRACK_ALLOW_RESET", "")
    assert c.get("/api/s/clock", headers=env["sup1"]).json()["allowed"] is False
    assert c.put("/api/s/clock", headers=env["sup1"], json={"date": "2026-11-10"}).status_code == 404  # not on a live site
    monkeypatch.setenv("LOOMTRACK_ALLOW_RESET", "1")
    from loomtrack.services import clock
    try:
        got = c.put("/api/s/clock", headers=env["sup1"], json={"date": "2026-11-10"})
        assert got.status_code == 200 and got.json()["testDate"] == "2026-11-10"
        assert clock.today(env["db"]) == "2026-11-10"  # the whole app reads the same date
        assert c.put("/api/s/clock", headers=env["sup1"], json={"date": "not-a-date"}).status_code == 400
        assert c.put("/api/s/clock", headers=env["sup1"], json={"date": "2031-01-01"}).status_code == 400
        assert c.put("/api/m/../s/clock", headers=env["merch"], json={"date": None}).status_code in (403, 404)
    finally:
        clock.set_test_date(env["db"], None)
    assert clock.today(env["db"]) != "2026-11-10"


def test_a_stage_that_is_not_due_yet_is_not_shown(env):
    oid = _new_order(env, "SUP-FUTURE", 1, exFactory="2027-03-15", sizes=[{"size": "M", "qty": 500}]).json()["id"]
    release(env["db"], stage_id(env["db"], oid, "CUT"))
    assert _mine(env, oid) == {}  # unlocked, but its start is months away: nothing to do today
