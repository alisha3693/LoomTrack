"""The built-in plans read like a time-and-action calendar: complete, in due order, and with stages that run forwards."""
import pytest

from loomtrack.domain.tna import BUILTIN_TEMPLATES


@pytest.mark.parametrize("t", BUILTIN_TEMPLATES.values(), ids=lambda t: t.key)
def test_a_built_in_plan_is_in_due_order_and_ends_at_ex_factory(t):
    ends = [i.end_offset for i in t.items]
    assert ends == sorted(ends, reverse=True), "earliest first"
    assert t.items[-1].code == "EXF" and t.items[-1].end_offset == 0
    assert len({i.code for i in t.items}) == len(t.items)


@pytest.mark.parametrize("t", BUILTIN_TEMPLATES.values(), ids=lambda t: t.key)
def test_a_built_in_plan_has_the_usual_buyer_checkpoints(t):
    codes = {i.code for i in t.items}
    assert {"FIT", "LAB", "PP", "FAB", "FABQC", "TRIMS", "INLINE", "FINAL", "EXF"} <= codes


@pytest.mark.parametrize("t", BUILTIN_TEMPLATES.values(), ids=lambda t: t.key)
def test_materials_are_checked_before_cutting_starts_and_trims_before_stitching(t):
    by = {i.code: i for i in t.items}
    assert by["FAB"].end_offset > by["FABQC"].end_offset > by["CUT"].start_offset
    assert by["TRIMS"].end_offset > by["STITCH"].start_offset
    assert all(i.start_offset > i.end_offset for i in t.items if i.kind == "stage")


@pytest.mark.parametrize("t", BUILTIN_TEMPLATES.values(), ids=lambda t: t.key)
def test_each_built_in_stage_starts_the_day_after_the_one_before_it_ends(t):
    by = {i.code: i for i in t.items}
    stages = [i for i in t.items if i.kind == "stage"]
    assert stages[0].after is None
    for before, stage in zip(stages, stages[1:]):
        assert stage.after == before.code
        assert stage.start_offset == before.end_offset - 1, f"{stage.code} should start the day after {before.code} ends"
    assert by["STITCH"].start_offset < by["CUT"].end_offset


# --- "starts after", through the editor's API --------------------------------------------------------------------

from test_api import env  # noqa: E402,F401


def _step(**kw):
    return {"kind": "stage", "endOffset": 10, **kw}


def _save(env, steps, name="After test"):
    return env["client"].post("/api/m/templates", headers=env["merch"], json={"name": name, "steps": steps})


def test_a_stage_that_starts_after_another_follows_its_end(env):
    steps = [
        _step(nameEn="Embroidery Z", process="embroidery", startOffset=30, endOffset=20),
        _step(nameEn="Sewing Z", process="stitching", after="Embroidery Z", endOffset=8),
    ]
    r = _save(env, steps, "After A")
    assert r.status_code == 201, r.text
    t = next(t for t in env["client"].get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == r.json()["id"])
    sew = next(s for s in t["steps"] if s["nameEn"] == "Sewing Z")
    emb = next(s for s in t["steps"] if s["nameEn"] == "Embroidery Z")
    assert (sew["startOffset"], sew["after"]) == (19, emb["code"])      # the day after Embroidery's 20
    assert emb["after"] is None
    # change the first stage's due day and save again: the second stage follows
    steps[0]["endOffset"], steps[0]["startOffset"] = 24, 34
    assert env["client"].put(f"/api/m/templates/{r.json()['id']}", headers=env["merch"], json={"name": "After A", "steps": steps}).status_code == 200
    t = next(t for t in env["client"].get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == r.json()["id"])
    assert next(s for s in t["steps"] if s["nameEn"] == "Sewing Z")["startOffset"] == 23


def test_the_preview_uses_the_followed_start(env):
    steps = [
        _step(nameEn="Embroidery Y", process="embroidery", startOffset=30, endOffset=20),
        _step(nameEn="Sewing Y", process="stitching", after="Embroidery Y", endOffset=8),
    ]
    r = env["client"].post("/api/m/templates/preview", headers=env["merch"], json={"exFactory": "2027-03-01", "steps": steps})
    assert r.status_code == 200, r.text
    sew = next(i for i in r.json()["items"] if i["nameEn"] == "Sewing Y")
    emb = next(i for i in r.json()["items"] if i["nameEn"] == "Embroidery Y")
    assert sew["plannedStart"] > emb["plannedDate"] or sew["plannedStart"] == emb["plannedDate"]


@pytest.mark.parametrize("steps,words", [
    ([_step(nameEn="Alpha Q", process="x", after="Nothing here", endOffset=5)], "not in this plan"),
    ([_step(nameEn="Beta Q", process="x", after="Beta Q", endOffset=5)], "after itself"),
    ([_step(nameEn="Gamma Q", process="x", startOffset=30, endOffset=20), _step(nameEn="Delta Q", process="x", after="Gamma Q", endOffset=19)], "not before it is due"),
    ([_step(nameEn="Epsilon Q", process="x", startOffset=30, endOffset=20), {"kind": "milestone", "nameEn": "Zeta Q", "endOffset": 5, "after": "Epsilon Q"}], "only a production stage"),
])
def test_a_starts_after_that_makes_no_sense_is_refused_with_the_reason(env, steps, words):
    r = _save(env, steps, "Bad " + steps[0]["nameEn"])
    assert r.status_code == 400 and words in r.json()["error"]


def test_the_process_list_has_the_standard_work_and_what_is_already_in_use(env):
    got = env["client"].get("/api/m/templates", headers=env["merch"]).json()["processes"]
    assert {"cutting", "stitching", "printing", "washing", "finishing", "packing", "embroidery"} <= set(got) and got == sorted(got)


@pytest.mark.parametrize("typo", ["stiching", "Stitchin", "packng", "cuting"])
def test_a_process_that_is_a_typo_of_a_known_one_is_refused_and_names_the_right_one(env, typo):
    r = _save(env, [_step(nameEn="Typo " + typo, process=typo, startOffset=30, endOffset=20)], "Typo " + typo)
    assert r.status_code == 400 and "looks like" in r.json()["error"], r.text


def test_a_genuinely_new_process_is_accepted_and_then_offered_in_the_list(env):
    r = _save(env, [_step(nameEn="Heat press N", process="heat press", startOffset=30, endOffset=20)], "New process")
    assert r.status_code == 201, r.text
    assert "heat press" in env["client"].get("/api/m/templates", headers=env["merch"]).json()["processes"]


def test_a_template_of_your_own_can_be_deleted_unless_orders_used_it(env):
    from test_api import EMBROIDERY, _new_order, _save_template
    c, h = env["client"], env["merch"]
    builtin = next(t for t in c.get("/api/m/templates", headers=h).json()["templates"] if t["builtin"])
    assert c.delete(f"/api/m/templates/{builtin['id']}", headers=h).status_code == 403
    spare = _save_template(env, "Spare plan", EMBROIDERY).json()["id"]
    assert c.delete(f"/api/m/templates/{spare}", headers=h).status_code == 200
    assert all(t["id"] != spare for t in c.get("/api/m/templates?retired=true", headers=h).json()["templates"])
    used = _save_template(env, "Used plan", EMBROIDERY).json()
    key = next(t["key"] for t in c.get("/api/m/templates", headers=h).json()["templates"] if t["id"] == used["id"])
    assert _new_order(env, "DEL-TPL-1", 1, templateKey=key).status_code == 201
    assert c.delete(f"/api/m/templates/{used['id']}", headers=h).status_code == 409
    assert c.delete("/api/m/templates/99999", headers=h).status_code == 404


def test_plan_check_lists_steps_already_past_due():
    from loomtrack.domain.tna import BUILTIN_TEMPLATES
    from loomtrack.services import capacity

    near = capacity.plan_check(BUILTIN_TEMPLATES["basic"], "2026-11-30", "2026-11-05")
    assert near["lateSteps"] and near["worstDaysLate"] > 0
    assert any(s["name"] == "Fit sample approval" for s in near["lateSteps"])
    assert near["earliestCleanExFactory"] > "2026-11-30"
    far = capacity.plan_check(BUILTIN_TEMPLATES["basic"], "2027-03-01", "2026-11-05")
    assert far["lateSteps"] == [] and far["earliestCleanExFactory"] is None
