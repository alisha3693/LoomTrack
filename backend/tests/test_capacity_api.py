"""The capacity check and unit capacity, through the API.

`env` is the same fixture test_api.py uses; importing it gives this module its own fresh database.
"""

import uuid

from test_api import TODAY, _new_order, _save_template, env, fake_classify  # noqa: F401

SHIP = "2026-12-30"  # far enough out that the plan's early steps are still ahead of 5 Nov


def _order(env, po, buyer=1, ex=SHIP, **extra):
    r = _new_order(env, po, buyer, exFactory=ex, **extra)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _detail(env, oid):
    return env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()


def _ms(env, oid, code):
    return next(m for m in _detail(env, oid)["milestones"] if m["code"] == code)


# --- capacity --------------------------------------------------------------------------------------


def _unit(env, uid, name, kind="own", cap=None, process=None):
    env["db"].execute("INSERT OR IGNORE INTO units (id, name, kind, process, daily_capacity) VALUES (?,?,?,?,?)", (uid, name, kind, process, cap))


def _set_cap(env, uid, value):
    return env["client"].patch(f"/api/m/units/{uid}", headers=env["merch"], json={"dailyCapacity": value})


def _check(env, qty, ex=SHIP, template="basic"):
    r = env["client"].post("/api/m/capacity/check", headers=env["merch"], json={"qty": qty, "exFactory": ex, "templateKey": template})
    assert r.status_code == 200, r.text
    return {u["unitId"]: u for u in r.json()["units"]}


def test_unit_capacity_is_set_cleared_and_checked(env):
    c = env["client"]
    _unit(env, 3, "Unit 3")
    _unit(env, 4, "Printer", kind="subcontract", process="printing")
    assert _set_cap(env, 3, 1000).status_code == 200
    listed = {u["id"]: u for u in c.get("/api/m/units", headers=env["merch"]).json()["units"]}
    assert listed[3]["dailyCapacity"] == 1000 and len(listed[3]["weeks"]) == 4 and listed[4]["weeks"] == []
    assert _set_cap(env, 3, 0).status_code == 400
    assert c.patch("/api/m/units/3", headers=env["merch"], json={}).status_code == 400
    assert _set_cap(env, 4, 500).status_code == 404                                      # job work units have no capacity here
    assert _set_cap(env, 999, 500).status_code == 404
    c.cookies.clear()
    assert c.get("/api/m/units").status_code == 401
    assert c.patch("/api/m/units/3", headers=env["sup1"], json={"dailyCapacity": 5}).status_code == 403
    assert c.post("/api/m/capacity/check", headers=env["sup1"], json={"qty": 1, "exFactory": SHIP, "templateKey": "basic"}).status_code == 403
    assert _set_cap(env, 3, None).status_code == 200
    assert next(u for u in c.get("/api/m/units", headers=env["merch"]).json()["units"] if u["id"] == 3)["dailyCapacity"] is None
    assert _check(env, 100)[3]["verdict"] == "unknown"


def test_the_check_reports_each_own_unit_and_explains_itself(env):
    _set_cap(env, 3, 1000)
    env["db"].execute("UPDATE units SET daily_capacity = 1000 WHERE id = 3")
    ok = _check(env, 1000)
    assert ok[3]["verdict"] == "fits" and ok[1]["verdict"] == "unknown" and 4 not in ok
    assert ok[3]["workingDays"] == 16 and ok[3]["possible"] == 16000 and ok[3]["requiredPerDay"] == 62   # 5 Dec to 23 Dec, Sundays out
    assert ok[3]["booked"] == 0 and "Would be 6% booked across 16 working days" in ok[3]["summary"]

    over = _check(env, 30000)
    assert over[3]["verdict"] == "over" and over[3]["utilisation"] == 1.88 and over[3]["earliest"] is None   # no date lengthens the window

    bad = env["client"].post("/api/m/capacity/check", headers=env["merch"], json={"qty": 10, "exFactory": SHIP, "templateKey": "nope"})
    assert bad.status_code == 400
    assert env["client"].post("/api/m/capacity/check", headers=env["merch"], json={"qty": 0, "exFactory": SHIP, "templateKey": "basic"}).status_code == 400


def test_a_date_that_is_too_soon_is_over_and_suggests_the_first_date_that_works(env):
    _unit(env, 5, "Unit 5", cap=1000)
    env["db"].execute("UPDATE units SET daily_capacity = 1000 WHERE id = 5")
    # 11,000 pieces already booked in the 13 working days from now to 19 Nov (stitching ends 20 days before ex-factory); ask for 8,000 more in the same days.
    busy = _order(env, "CAP-BUSY", unitId=5, ex="2026-12-09", sizes=[{"size": "M", "qty": 11000}])
    busy_no = _detail(env, busy)["order"]["order_no"]
    soon = _check(env, 8000, ex="2026-12-09")[5]
    assert soon["verdict"] == "over" and soon["booked"] == 11000 and soon["workingDays"] == 13
    assert [o["orderNo"] for o in soon["overlapping"]] == [busy_no]

    assert soon["earliest"] is not None
    assert soon["earliest"]["exFactory"] > "2026-12-09" and soon["earliest"]["utilisation"] <= 1.0
    again = _check(env, 8000, ex=soon["earliest"]["exFactory"])[5]
    assert again["verdict"] in ("fits", "tight")                                         # the suggested date really works
    assert _check(env, 8000, ex="2027-01-30")[5]["verdict"] == "fits"                    # and a date well clear of the booking fits with room


def test_an_order_that_would_put_a_unit_over_is_refused_unless_confirmed(env):
    _unit(env, 6, "Unit 6", cap=500)
    env["db"].execute("UPDATE units SET daily_capacity = 500 WHERE id = 6")
    assert _new_order(env, "CAP-OK", 1, exFactory=SHIP, unitId=6, sizes=[{"size": "M", "qty": 1000}]).status_code == 201
    refused = _new_order(env, "CAP-BIG", 1, exFactory=SHIP, unitId=6, sizes=[{"size": "M", "qty": 20000}])
    assert refused.status_code == 409 and "Unit 6" in refused.json()["error"] and "booked" in refused.json()["error"]
    assert env["db"].execute("SELECT COUNT(*) FROM orders WHERE po_no = 'CAP-BIG'").fetchone()[0] == 0
    forced = _new_order(env, "CAP-BIG", 1, exFactory=SHIP, unitId=6, sizes=[{"size": "M", "qty": 20000}], overCapacityOk=True)
    assert forced.status_code == 201
    # A unit with no capacity set, and units we have not looked at, are never refused.
    assert _new_order(env, "CAP-FREE", 1, exFactory=SHIP, unitId=2, sizes=[{"size": "M", "qty": 900000}]).status_code == 201


def test_accepting_a_request_runs_the_same_check(env):
    c = env["client"]
    _unit(env, 7, "Unit 7", cap=500)
    env["db"].execute("UPDATE units SET daily_capacity = 500 WHERE id = 7")
    rid = c.post(f"/api/b/{env['tokenB']}/requests", json={"poNo": "CAP-RQ", "style": "Tee", "colour": "Navy", "exFactory": SHIP,
                                                           "sizes": [{"size": "M", "qty": 30000}]}).json()["id"]
    refused = c.post(f"/api/m/requests/{rid}/accept", headers=env["merch"], json={"unitId": 7, "templateKey": "basic"})
    assert refused.status_code == 409 and "booked" in refused.json()["error"]
    assert c.get(f"/api/m/requests/{rid}", headers=env["merch"]).json()["status"] == "submitted"      # nothing half-done
    ok = c.post(f"/api/m/requests/{rid}/accept", headers=env["merch"], json={"unitId": 7, "templateKey": "basic", "overCapacityOk": True})
    assert ok.status_code == 200 and c.get(f"/api/m/requests/{rid}", headers=env["merch"]).json()["status"] == "accepted"


def test_what_is_already_booked_counts_less_as_pieces_are_made_and_not_at_all_once_closed(env):
    _unit(env, 8, "Unit 8", cap=1000)
    env["db"].execute("UPDATE units SET daily_capacity = 1000 WHERE id = 8")
    oid = _order(env, "CAP-LOAD", unitId=8, sizes=[{"size": "M", "qty": 6000}])
    first = _check(env, 1000)[8]
    assert first["booked"] == 6000 and first["overlapping"][0]["qtyLeft"] == 6000

    stitch = _ms(env, oid, "STITCH")
    user = env["db"].execute("SELECT id FROM users LIMIT 1").fetchone()[0]
    env["db"].execute("INSERT INTO daily_updates (id, milestone_id, user_id, work_date, qty) VALUES (?,?,?,?,?)", (str(uuid.uuid4()), stitch["id"], user, TODAY, 2000))
    assert _check(env, 1000)[8]["booked"] == 4000                                       # only what is left is still to come

    env["db"].execute("UPDATE orders SET state = 'cancelled' WHERE id = ?", (oid,))
    assert _check(env, 1000)[8]["booked"] == 0


def test_a_plan_with_no_stitching_step_is_not_checked(env):
    steps = [{"code": "CUT", "endOffset": 20, "startOffset": 30}, {"code": "PACK", "endOffset": 3, "startOffset": 8}, {"code": "FINAL", "endOffset": 2}]
    made = _save_template(env, "Cut and pack only", steps)
    assert made.status_code == 201, made.text
    key = next(t["key"] for t in env["client"].get("/api/m/meta", headers=env["merch"]).json()["templates"] if t["name"] == "Cut and pack only")
    r = env["client"].post("/api/m/capacity/check", headers=env["merch"], json={"qty": 100, "exFactory": SHIP, "templateKey": key})
    body = r.json()
    # no stitching step; cutting and packing have no capacity set, so every unit reads "not set", never over
    assert body["stitching"] is None and {u["verdict"] for u in body["units"]} == {"unknown"} and "lateSteps" in body["plan"]
    _unit(env, 9, "Unit 9", cap=1)
    env["db"].execute("UPDATE units SET daily_capacity = 1 WHERE id = 9")
    assert _new_order(env, "CAP-NOSTITCH", 1, exFactory=SHIP, unitId=9, templateKey=key, sizes=[{"size": "M", "qty": 50000}]).status_code == 201


def _set(env, unit_id, process, value):
    return env["client"].patch(f"/api/m/units/{unit_id}", headers=env["merch"], json={"dailyCapacity": value, "process": process})


def _unit_check(env, qty, unit_id=3, key="basic"):
    r = env["client"].post("/api/m/capacity/check", headers=env["merch"], json={"qty": qty, "exFactory": SHIP, "templateKey": key})
    assert r.status_code == 200, r.text
    return next(u for u in r.json()["units"] if u["unitId"] == unit_id)


def test_every_own_stage_is_checked_and_the_tightest_one_decides(env):
    _set_cap(env, 3, 1000)
    assert _set(env, 3, "cutting", 50).status_code == 200  # cutting is the slow stage here
    assert _set(env, 3, "finishing", None).status_code == 200 and _set(env, 3, "packing", None).status_code == 200
    u = _unit_check(env, 1000)
    by = {s["process"]: s for s in u["stages"]}
    assert set(by) == {"cutting", "stitching", "finishing", "packing"}  # production stages only, no milestones
    assert by["stitching"]["verdict"] in ("fits", "tight") and by["cutting"]["verdict"] == "over"
    assert u["verdict"] == "over" and u["limitingProcess"] == "cutting" and u["summary"].startswith("Cutting:")
    assert set(u["notSet"]) == {"Finishing & checking", "Packing"}  # listed, never decisive
    # an order that would put cutting over is refused, and goes through when the merchandiser says so
    refused = _new_order(env, "CAP-CUT", 1, exFactory=SHIP, unitId=3, templateKey="basic", sizes=[{"size": "M", "qty": 1000}])
    assert refused.status_code == 409 and "Cutting" in refused.text
    assert _new_order(env, "CAP-CUT2", 1, exFactory=SHIP, unitId=3, templateKey="basic", sizes=[{"size": "M", "qty": 1000}], overCapacityOk=True).status_code == 201


def test_job_work_stages_are_not_counted(env):
    _set_cap(env, 3, 1000)
    u = _unit_check(env, 1000, key="printed")
    assert "printing" not in {s["process"] for s in u["stages"]}
    assert _set(env, 3, "printing", 100).status_code == 400  # job work has no capacity here
    assert _set(env, 3, "stitching", None).status_code == 200


def test_a_second_order_adds_to_the_load_of_each_stage(env):
    _set_cap(env, 3, 1000)
    assert _set(env, 3, "cutting", 1000).status_code == 200
    before = {s["process"]: s["booked"] for s in _unit_check(env, 500)["stages"]}
    assert _new_order(env, "CAP-TWO", 1, exFactory=SHIP, unitId=3, templateKey="basic", sizes=[{"size": "M", "qty": 600}]).status_code == 201
    after = {s["process"]: s["booked"] for s in _unit_check(env, 500)["stages"]}
    assert after["stitching"] > before["stitching"] and after["cutting"] > before["cutting"]  # the pieces are booked in each stage's own days


def test_units_page_lists_a_capacity_per_stage(env):
    _set_cap(env, 3, 1000)
    _set(env, 3, "packing", 700)
    _set(env, 3, "cutting", None)
    row = next(u for u in env["client"].get("/api/m/units", headers=env["merch"]).json()["units"] if u["id"] == 3)
    by = {p["process"]: p for p in row["processes"]}
    assert by["stitching"]["dailyCapacity"] == 1000 and by["packing"]["dailyCapacity"] == 700 and by["cutting"]["dailyCapacity"] is None
    assert len(by["packing"]["weeks"]) == 4 and "printing" not in by
