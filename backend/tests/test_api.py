"""End-to-end API tests on an in-memory database: buyer isolation, the
supervisor update path (idempotency, unit scoping), the AI override, warning
confirmation and the date-change audit trail."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from loomtrack.ai.classifier import classify_by_keywords
from loomtrack.db import open_db
from loomtrack.main import create_app
from loomtrack.security import hash_secret, new_token

TODAY = "2026-11-05"


async def fake_classify(note: str):
    return classify_by_keywords(note)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    db = open_db(":memory:")
    app = create_app(db, today=lambda: TODAY, classify=fake_classify, upload_dir=tmp_path_factory.mktemp("uploads"))
    client = TestClient(app)

    e = {"db": db, "client": client, "tokenB": new_token(), "tokenC": new_token()}
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'Buyer B', ?), (2, 'Buyer C', ?)", (e["tokenB"], e["tokenC"]))
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'Unit 1', 'own'), (2, 'Unit 2', 'own')")
    for name, role, login, secret, unit in [("M", "merchandiser", "m@x.in", "pass1234", None), ("S1", "supervisor", "9000000001", "1111", 1), ("S2", "supervisor", "9000000002", "2222", 2)]:
        db.execute("INSERT INTO users (name, role, login, secret_hash, unit_id) VALUES (?,?,?,?,?)", (name, role, login, hash_secret(secret), unit))

    def login(who, secret):
        r = client.post("/api/auth/login", json={"login": who, "secret": secret})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    e["merch"], e["sup1"], e["sup2"] = login("m@x.in", "pass1234"), login("9000000001", "1111"), login("9000000002", "2222")

    def make(po, buyer_id):
        r = client.post(
            "/api/m/orders",
            headers=e["merch"],
            json={"poNo": po, "buyerId": buyer_id, "style": f"Style {po}", "colour": "Navy", "exFactory": "2026-11-30", "unitId": 1, "templateKey": "basic", "sizes": [{"size": "M", "qty": 1000}]},
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    e["orderB"], e["orderC"] = make("PO-B-1", 1), make("PO-C-1", 2)
    return e


def stage_id(db: sqlite3.Connection, order_id: int, code: str) -> int:
    return db.execute("SELECT id FROM milestones WHERE order_id = ? AND code = ?", (order_id, code)).fetchone()["id"]


def post_update(env, who, update_id, milestone, qty, **extra):
    files = extra.pop("files", None)
    data = {"id": update_id, "milestoneId": str(milestone), "workDate": TODAY, "qty": str(qty), **extra}
    return env["client"].post("/api/s/updates", headers=env[who], data=data, files=files)


# --- buyer isolation ------------------------------------------------------------------


def test_buyer_sees_only_own_orders(env):
    r = env["client"].get(f"/api/b/{env['tokenB']}")
    assert r.status_code == 200
    assert [o["poNo"] for o in r.json()["orders"]] == ["PO-B-1"]
    assert "PO-C-1" not in r.text


def test_buyer_view_has_no_internal_fields(env):
    body = env["client"].get(f"/api/b/{env['tokenB']}").text
    for field in ["unit", "status", "slack", "supervisor", "note_text", "merchandiser"]:
        assert f'"{field}' not in body


def test_buyer_cannot_fetch_another_buyers_photo(env):
    r = post_update(env, "sup1", "photo-update-0001", stage_id(env["db"], env["orderC"], "CUT"), 100,
                    files={"photo": ("p.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")})
    assert r.status_code == 201, r.text
    photo = env["db"].execute(
        "SELECT p.id FROM photos p JOIN daily_updates u ON u.id = p.update_id JOIN milestones m ON m.id = u.milestone_id WHERE m.order_id = ?",
        (env["orderC"],),
    ).fetchone()["id"]
    assert env["client"].get(f"/api/b/{env['tokenB']}/photos/{photo}").status_code == 404
    assert env["client"].get(f"/api/b/{env['tokenC']}/photos/{photo}").status_code == 200


def test_unknown_and_revoked_links(env):
    db, c = env["db"], env["client"]
    assert c.get(f"/api/b/{new_token()}").status_code == 404
    db.execute("UPDATE buyers SET link_active = 0 WHERE id = 2")
    assert c.get(f"/api/b/{env['tokenC']}").status_code == 404
    db.execute("UPDATE buyers SET link_active = 1 WHERE id = 2")


def test_buyer_token_is_not_a_staff_session(env):
    c = env["client"]
    c.cookies.clear()  # the shared client keeps the cookie from earlier logins, like a browser
    assert c.get("/api/m/board").status_code == 401
    assert c.get("/api/m/board", headers={"Authorization": f"Bearer {env['tokenB']}"}).status_code == 401
    c.cookies.set("loomtrack_session", env["tokenB"])
    assert c.get("/api/m/board").status_code == 401
    c.cookies.clear()


def test_board_and_order_detail_load(env):
    c = env["client"]
    board = c.get("/api/m/board", headers=env["merch"])
    assert board.status_code == 200
    assert {o["id"] for o in board.json()["orders"]} >= {env["orderB"], env["orderC"]}

    detail = c.get(f"/api/m/orders/{env['orderB']}", headers=env["merch"])
    assert detail.status_code == 200
    d = detail.json()
    # Names and kinds come from plan_steps through the milestone's code.
    assert all(m["name_en"] and m["name_ta"] and m["kind"] in ("stage", "milestone") for m in d["milestones"])
    assert all(u["stage"] for u in d["updates"])


def test_login_cookie_works_without_header(env):
    c = env["client"]
    c.cookies.clear()
    r = c.post("/api/auth/login", json={"login": "m@x.in", "secret": "pass1234"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert c.get("/api/m/meta").status_code == 200  # cookie only, no Authorization header
    c.post("/api/auth/logout")
    assert c.get("/api/m/meta").status_code == 401
    c.cookies.clear()


def test_supervisor_cannot_use_office_api(env):
    assert env["client"].get("/api/m/board", headers=env["sup1"]).status_code == 403


# --- supervisor update ---------------------------------------------------------------


def test_update_is_idempotent(env):
    ms = stage_id(env["db"], env["orderB"], "CUT")
    assert post_update(env, "sup1", "dup-update-0001", ms, 250).status_code == 201
    again = post_update(env, "sup1", "dup-update-0001", ms, 250)
    assert again.status_code == 200 and again.json()["duplicate"] is True
    total = env["db"].execute("SELECT SUM(qty) FROM daily_updates WHERE milestone_id = ?", (ms,)).fetchone()[0]
    assert total == 250


def test_update_only_for_own_unit(env):
    assert post_update(env, "sup2", "wrong-unit-0001", stage_id(env["db"], env["orderB"], "CUT"), 10).status_code == 403


def test_update_rejects_over_quantity(env):
    assert post_update(env, "sup1", "too-many-0001", stage_id(env["db"], env["orderB"], "CUT"), 900).status_code == 422


def test_tamil_note_is_classified_and_can_be_overridden(env):
    db, c = env["db"], env["client"]
    r = post_update(env, "sup1", "note-update-0001", stage_id(db, env["orderB"], "CUT"), 50, noteText="கரண்ட் இல்லை, மூன்று மணி நேரம் வேலை நின்றது")
    assert r.status_code == 201
    row = db.execute("SELECT * FROM issue_reasons WHERE update_id = 'note-update-0001'").fetchone()
    assert row["ai_category"] == "POWER_CUT"  # background task has run by the time TestClient returns
    assert c.patch("/api/m/reasons/note-update-0001", headers=env["merch"], json={"category": "MACHINE_BREAKDOWN"}).status_code == 200
    row = db.execute("SELECT * FROM issue_reasons WHERE update_id = 'note-update-0001'").fetchone()
    assert row["ai_category"] == "POWER_CUT"  # the AI's guess is kept beside the human decision
    assert row["final_category"] == "MACHINE_BREAKDOWN"


def test_classifier_failure_falls_back_to_keywords(env):
    db = env["db"]
    async def broken(_):
        raise ConnectionError("ollama down")
    env["client"].app.state.ctx.classify = broken
    try:
        post_update(env, "sup1", "fallback-0001", stage_id(db, env["orderB"], "CUT"), 10, noteText="மெஷின் பழுது")
    finally:
        env["client"].app.state.ctx.classify = fake_classify
    row = db.execute("SELECT * FROM issue_reasons WHERE update_id = 'fallback-0001'").fetchone()
    assert row["ai_source"] == "keywords" and row["ai_category"] == "MACHINE_BREAKDOWN"
    assert "ollama down" in row["ai_error"]


# --- warnings and audit --------------------------------------------------------------


def test_buyer_sees_warning_only_after_confirmation(env):
    db, c = env["db"], env["client"]
    # Pull ex-factory in so the order is certainly late.
    r = c.patch(f"/api/m/orders/{env['orderB']}/ex-factory", headers=env["merch"], json={"date": "2026-11-07", "reason": "Test: buyer asked for earlier"})
    assert r.status_code == 200
    assert c.get(f"/api/b/{env['tokenB']}").json()["orders"][0]["notice"] is None

    w = db.execute("SELECT id FROM warnings WHERE order_id = ? AND state = 'pending'", (env["orderB"],)).fetchone()
    assert w is not None
    assert c.post(f"/api/m/warnings/{w['id']}/confirm", headers=env["merch"], json={"message": "We expect a delay of two weeks."}).status_code == 200
    assert c.get(f"/api/b/{env['tokenB']}").json()["orders"][0]["notice"]["message"] == "We expect a delay of two weeks."


def test_date_changes_are_recorded_and_append_only(env):
    db = env["db"]
    rows = db.execute("SELECT * FROM date_changes WHERE order_id = ?", (env["orderB"],)).fetchall()
    assert len(rows) == 1
    assert (rows[0]["old_value"], rows[0]["new_value"]) == ("2026-11-30", "2026-11-07")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE date_changes SET reason = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM date_changes")


def test_moving_a_planned_date_needs_a_reason(env):
    ms = stage_id(env["db"], env["orderB"], "STITCH")
    r = env["client"].patch(f"/api/m/milestones/{ms}", headers=env["merch"], json={"plannedDate": "2026-11-20"})
    assert r.status_code == 400
    assert "reason" in r.json()["error"].lower()


def test_validation_errors_use_the_common_shape(env):
    r = env["client"].post("/api/m/orders", headers=env["merch"], json={"poNo": "X"})
    assert r.status_code == 400
    assert "error" in r.json()


def test_weekly_export_is_an_xlsx(env):
    r = env["client"].get(f"/api/b/{env['tokenB']}/weekly.xlsx")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx is a zip


def _new_order(env, po, buyer_id, **extra):
    body = {"poNo": po, "buyerId": buyer_id, "style": "Style X", "colour": "Navy", "exFactory": "2026-11-30", "unitId": 1,
            "templateKey": "basic", "sizes": [{"size": "M", "qty": 100}], **extra}
    return env["client"].post("/api/m/orders", headers=env["merch"], json=body)


def test_orders_get_our_own_number_and_keep_the_buyers_po(env):
    first = _new_order(env, "PO-NUM-1", 1).json()
    second = _new_order(env, "PO-NUM-2", 1).json()
    year = TODAY[:4]
    assert first["orderNo"].startswith(f"LT-{year}-") and second["orderNo"].startswith(f"LT-{year}-")
    assert int(second["orderNo"][-4:]) == int(first["orderNo"][-4:]) + 1
    detail = env["client"].get(f"/api/m/orders/{second['id']}", headers=env["merch"]).json()["order"]
    assert detail["order_no"] == second["orderNo"] and detail["po_no"] == "PO-NUM-2"


def test_po_number_is_unique_per_buyer_not_globally(env):
    assert _new_order(env, "PO-SHARED", 1).status_code == 201
    assert _new_order(env, "PO-SHARED", 2).status_code == 201  # another buyer may use the same number
    again = _new_order(env, "PO-SHARED", 1)
    assert again.status_code == 409 and "already has" in again.json()["error"]


def test_colour_hex_and_pantone_are_saved_and_checked(env):
    ok = _new_order(env, "PO-COL-1", 2, colourHex="#1f2a44", colourPantone=" 19-4024 TCX ")
    assert ok.status_code == 201
    o = env["client"].get(f"/api/m/orders/{ok.json()['id']}", headers=env["merch"]).json()["order"]
    assert (o["colour_hex"], o["colour_pantone"]) == ("#1F2A44", "19-4024 TCX")
    for bad in ("1F2A44", "#12345", "navy", "#GGGGGG"):
        assert _new_order(env, "PO-COL-2", 2, colourHex=bad).status_code == 400

    # The buyer sees their own swatch, but never our internal order number.
    view = env["client"].get(f"/api/b/{env['tokenC']}").json()["orders"]
    mine = next(x for x in view if x["poNo"] == "PO-COL-1")
    assert mine["colourHex"] == "#1F2A44" and mine["colourPantone"] == "19-4024 TCX"
    assert not any("orderNo" in x or "order_no" in x for x in view)


# --- Custom plan templates ------------------------------------------------------------

EMBROIDERY = [
    # endOffset / startOffset are calendar days before ex-factory; a stage starts earlier (a bigger number) than it ends.
    {"code": "CUT", "endOffset": 20, "startOffset": 30},
    {"nameEn": "Embroidery", "nameTa": "எம்பிராய்டரி", "kind": "stage", "process": "Embroidery", "endOffset": 16, "startOffset": 26},
    {"code": "STITCH", "endOffset": 7, "startOffset": 24},
    {"code": "PACK", "endOffset": 3, "startOffset": 8},
    {"code": "FINAL", "endOffset": 2},
]


def _save_template(env, name, steps, method="post", tid=None):
    url = "/api/m/templates" + (f"/{tid}" if tid else "")
    return getattr(env["client"], method)(url, headers=env["merch"], json={"name": name, "steps": steps})


def test_merchandiser_builds_a_template_and_orders_use_it(env):
    c = env["client"]
    listing = c.get("/api/m/templates", headers=env["merch"]).json()
    assert {t["key"] for t in listing["templates"] if t["builtin"]} == {"basic", "printed", "washed"}

    made = _save_template(env, "Embroidered polo", EMBROIDERY)
    assert made.status_code == 201, made.text
    saved = next(t for t in c.get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == made.json()["id"])
    codes = [s["code"] for s in saved["steps"]]
    assert codes[0] == "CUT" and codes[-1] == "EXF" and "EMBROIDERY" in codes     # new step created, EXF added last
    assert codes.index("EMBROIDERY") < codes.index("STITCH")                      # ordered by end offset, earliest first

    meta = c.get("/api/m/meta", headers=env["merch"]).json()["templates"]
    key = next(t["key"] for t in meta if t["name"] == "Embroidered polo")
    r = _new_order(env, "PO-TPL-1", 1, templateKey=key)
    assert r.status_code == 201, r.text
    ms = c.get(f"/api/m/orders/{r.json()['id']}", headers=env["merch"]).json()["milestones"]
    emb = next(m for m in ms if m["code"] == "EMBROIDERY")
    assert emb["kind"] == "stage" and emb["name_en"] == "Embroidery" and emb["unit_id"] == 1   # no subcontractor: own unit
    assert emb["planned_date"] < next(m for m in ms if m["code"] == "STITCH")["planned_date"]


def test_template_checks(env):
    bad = {
        "no stage": [{"code": "FINAL", "endOffset": 2}],
        "stage starts after it ends": [{"code": "CUT", "endOffset": 20, "startOffset": 10}],
        "stage without a start": [{"code": "CUT", "endOffset": 20}],
        "duplicate step": [{"code": "CUT", "endOffset": 20, "startOffset": 30}, {"code": "CUT", "endOffset": 10, "startOffset": 18}],
        "unknown step": [{"code": "NOPE", "endOffset": 20, "startOffset": 25}],
        "new stage without a process": [{"nameEn": "Dye", "kind": "stage", "endOffset": 20, "startOffset": 25}],
        "new step without a kind": [{"nameEn": "Dye", "endOffset": 20}],
    }
    for label, steps in bad.items():
        assert _save_template(env, "Bad", steps).status_code == 400, label
    ok = [{"code": "CUT", "endOffset": 20, "startOffset": 30}]
    assert _save_template(env, "X", ok).status_code == 400  # name too short
    assert _save_template(env, "Cutting only", ok).status_code == 201
    assert _save_template(env, "cutting ONLY", ok).status_code == 409                 # names are unique, ignoring case


def test_builtin_templates_are_read_only_and_retired_ones_leave_the_dropdown(env):
    c = env["client"]
    basic = next(t for t in c.get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["key"] == "basic")
    assert _save_template(env, "Renamed", EMBROIDERY, "put", basic["id"]).status_code == 403
    assert c.post(f"/api/m/templates/{basic['id']}/retire", headers=env["merch"]).status_code == 403
    assert c.patch("/api/m/steps/CUT", headers=env["merch"], json={"nameEn": "Cut", "nameTa": "x"}).status_code == 403

    mine = _save_template(env, "Short-run", EMBROIDERY).json()["id"]
    key = next(t["key"] for t in c.get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == mine)
    assert c.post(f"/api/m/templates/{mine}/retire", headers=env["merch"]).status_code == 200
    assert key not in {t["key"] for t in c.get("/api/m/meta", headers=env["merch"]).json()["templates"]}
    assert _new_order(env, "PO-TPL-RET", 1, templateKey=key).status_code == 400      # can't start a new order on a retired template
    assert c.post(f"/api/m/templates/{mine}/restore", headers=env["merch"]).status_code == 200
    assert _new_order(env, "PO-TPL-RET", 1, templateKey=key).status_code == 201


def test_editing_a_template_never_changes_existing_orders(env):
    c = env["client"]
    tid = _save_template(env, "Editable", EMBROIDERY).json()["id"]
    key = next(t["key"] for t in c.get("/api/m/templates", headers=env["merch"]).json()["templates"] if t["id"] == tid)
    oid = _new_order(env, "PO-TPL-EDIT", 1, templateKey=key).json()["id"]
    before = [(m["code"], m["planned_date"]) for m in c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["milestones"]]

    shorter = [{"code": "CUT", "endOffset": 28, "startOffset": 34}, {"code": "PACK", "endOffset": 6, "startOffset": 9}]
    assert _save_template(env, "Editable", shorter, "put", tid).status_code == 200
    after = [(m["code"], m["planned_date"]) for m in c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["milestones"]]
    assert before == after


def test_template_preview_and_step_rename(env):
    c = env["client"]
    r = c.post("/api/m/templates/preview", headers=env["merch"], json={"exFactory": "2026-12-18", "steps": EMBROIDERY})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[-1]["code"] == "EXF" and items[-1]["plannedDate"] == "2026-12-18"
    assert all(a["plannedDate"] <= b["plannedDate"] for a, b in zip(items, items[1:]))
    assert next(i for i in items if i["code"] == "EMBROIDERY")["nameEn"] == "Embroidery"
    # Previewing saves nothing: the library only has the steps already saved by the tests above.
    codes = {s["code"] for s in c.get("/api/m/templates", headers=env["merch"]).json()["library"]}
    n_before = len(codes)
    c.post("/api/m/templates/preview", headers=env["merch"], json={"exFactory": "2026-12-18", "steps": [
        {"nameEn": "Brand new", "kind": "stage", "process": "dyeing", "endOffset": 20, "startOffset": 25}]})
    assert len(c.get("/api/m/templates", headers=env["merch"]).json()["library"]) == n_before

    assert c.patch("/api/m/steps/EMBROIDERY", headers=env["merch"], json={"nameEn": "Machine embroidery", "nameTa": "எம்பிராய்டரி"}).status_code == 200
    assert next(s for s in c.get("/api/m/templates", headers=env["merch"]).json()["library"] if s["code"] == "EMBROIDERY")["nameEn"] == "Machine embroidery"


def test_only_a_merchandiser_can_manage_templates(env):
    c = env["client"]
    assert c.get("/api/m/templates", headers=env["sup1"]).status_code == 403
    assert c.post("/api/m/templates", headers=env["sup1"], json={"name": "Nope", "steps": EMBROIDERY}).status_code == 403
    assert c.get(f"/api/b/{env['tokenB']}/templates").status_code in (401, 404)


def test_typing_an_existing_step_name_reuses_it_instead_of_duplicating(env):
    c = env["client"]
    inline = {"nameEn": "  machine EMBROIDERY ", "kind": "stage", "process": "embroidery", "endOffset": 15, "startOffset": 25}
    n = len(c.get("/api/m/templates", headers=env["merch"]).json()["library"])
    assert _save_template(env, "Reuses embroidery", [{"code": "CUT", "endOffset": 20, "startOffset": 30}, inline]).status_code == 201
    assert len(c.get("/api/m/templates", headers=env["merch"]).json()["library"]) == n
    # Ex-factory is added automatically, so it can't be typed in as a new step.
    exf = {"nameEn": "Ex-factory", "kind": "milestone", "endOffset": 0}
    assert _save_template(env, "Bad exf", [{"code": "CUT", "endOffset": 20, "startOffset": 30}, exf]).status_code == 400


# --- Order requests ---------------------------------------------------------------------

def _req(env, token, po, **extra):
    body = {"poNo": po, "style": "Men's raglan tee", "colour": "Charcoal", "exFactory": "2026-12-20",
            "sizes": [{"size": "M", "qty": 600}, {"size": "L", "qty": 400}], **extra}
    return env["client"].post(f"/api/b/{token}/requests", json=body)


def _office(env, path, method="get", **json):
    return getattr(env["client"], method)(f"/api/m/requests{path}", headers=env["merch"], **({"json": json} if json else {}))


def _buyer(env, token, path, method="get", **json):
    return getattr(env["client"], method)(f"/api/b/{token}/requests{path}", **({"json": json} if json else {}))


def test_a_buyer_sees_only_their_own_requests(env):
    mine = _req(env, env["tokenB"], "RQ-ISO-1", colourHex="#36454f", colourPantone="19-3906 TCX").json()["id"]
    assert [r["id"] for r in _buyer(env, env["tokenB"], "").json()["requests"] if r["id"] == mine] == [mine]
    assert all(r["id"] != mine for r in _buyer(env, env["tokenC"], "").json()["requests"])
    for path, method, body in ((f"/{mine}", "get", {}), (f"/{mine}/reply", "post", {"message": "hi"}),
                               (f"/{mine}/agree", "post", {}), (f"/{mine}/withdraw", "post", {})):
        assert _buyer(env, env["tokenC"], path, method, **body).status_code == 404, path
    detail = _buyer(env, env["tokenB"], f"/{mine}").json()
    assert detail["colourHex"] == "#36454F" and detail["status"] == "submitted" and detail["totalQty"] == 1000
    assert not any(k in detail for k in ("buyer", "orderId", "decided_by")) and all("user_id" not in m for m in detail["messages"])
    office = _office(env, f"/{mine}").json()
    assert office["buyer"] == "Buyer B" and office["status"] == "submitted"
    assert env["client"].get("/api/m/requests", headers=env["sup1"]).status_code == 403
    env["client"].cookies.clear()
    assert env["client"].get(f"/api/m/requests/{mine}").status_code == 401
    assert env["client"].get(f"/api/m/requests/{mine}", headers={"Authorization": f"Bearer {env['tokenB']}"}).status_code == 401


def test_request_checks(env):
    t = env["tokenB"]
    assert _req(env, t, "RQ-CHK-1", exFactory="2026-11-01").status_code == 400                       # in the past
    assert _req(env, t, "RQ-CHK-1", sizes=[{"size": "M", "qty": 0}]).status_code == 400            # nothing ordered
    assert _req(env, t, "RQ-CHK-1", sizes=[{"size": "M", "qty": 5}, {"size": "m", "qty": 5}]).status_code == 400
    assert _req(env, t, "RQ-CHK-1", colourHex="navy").status_code == 400
    assert _req(env, t, "PO-B-1").status_code == 409                                                # already an order
    assert _req(env, t, "RQ-CHK-2").status_code == 201
    assert _req(env, t, "RQ-CHK-2").status_code == 409                                              # already an open request
    assert _req(env, env["tokenC"], "RQ-CHK-2").status_code == 201                                  # other buyer: fine
    assert _req(env, "not-a-token", "RQ-CHK-3").status_code == 404


def test_the_whole_conversation_ends_in_an_order(env):
    db, t = env["db"], env["tokenB"]
    rid = _req(env, t, "RQ-FLOW-1", colourHex="#36454F", colourPantone="19-3906 TCX", description="Raglan, contrast sleeve").json()["id"]
    before = _office(env, "").json()["openCount"]
    assert any(r["id"] == rid for r in _office(env, "?filter=mine").json()["requests"])
    assert env["client"].get("/api/m/meta", headers=env["merch"]).json()["openRequests"] == before

    assert _office(env, f"/{rid}/query", "post", message="").status_code == 400                    # needs words
    assert _office(env, f"/{rid}/query", "post", message="Is the sleeve colour Pantone 18-1664?").status_code == 200
    assert _buyer(env, t, f"/{rid}").json()["status"] == "query"
    assert not any(r["id"] == rid for r in _office(env, "?filter=mine").json()["requests"])        # now on the buyer
    assert any(r["id"] == rid for r in _office(env, "?filter=waiting").json()["requests"])

    assert _buyer(env, t, f"/{rid}/reply", "post", message="Yes, 18-1664 TCX.").status_code == 200
    assert _buyer(env, t, f"/{rid}").json()["status"] == "submitted"                               # back to us

    assert _office(env, f"/{rid}/counter", "post", exFactory="2026-12-20", message="same").status_code == 400
    assert _office(env, f"/{rid}/counter", "post", exFactory="2026-11-01", message="past").status_code == 400
    assert _office(env, f"/{rid}/counter", "post", exFactory="2026-12-27", message="Fabric lead time").status_code == 200
    d = _buyer(env, t, f"/{rid}").json()
    assert d["status"] == "countered" and d["canAgree"] and d["exFactory"] == "2026-12-20"          # not changed until they agree

    assert _buyer(env, t, f"/{rid}/agree", "post").status_code == 200
    d = _buyer(env, t, f"/{rid}").json()
    assert d["status"] == "submitted" and d["exFactory"] == "2026-12-27"
    assert _buyer(env, t, f"/{rid}/agree", "post").status_code == 409                               # nothing left to agree to

    assert _office(env, f"/{rid}/accept", "post", unitId=1, templateKey="basic").status_code == 200
    accepted = _office(env, f"/{rid}").json()
    assert accepted["status"] == "accepted" and accepted["orderNo"].startswith("LT-")
    order = env["client"].get(f"/api/m/orders/{accepted['orderId']}", headers=env["merch"]).json()
    o = order["order"]
    assert (o["po_no"], o["ex_factory"], o["qty_total"], o["colour"], o["colour_hex"], o["colour_pantone"]) == (
        "RQ-FLOW-1", "2026-12-27", 1000, "Charcoal", "#36454F", "19-3906 TCX")
    assert [(s["size"], s["qty"]) for s in order["sizes"]] == [("M", 600), ("L", 400)]
    assert _buyer(env, t, f"/{rid}").json()["orderNo"] == o["order_no"]

    events = [m["event"] for m in _buyer(env, t, f"/{rid}").json()["messages"]]
    assert events == ["submitted", "query", "message", "counter", "agreed", "accepted"]
    assert _buyer(env, t, f"/{rid}/reply", "post", message="thanks").status_code == 409            # closed
    mails = [m["subject"] for m in env["client"].get("/api/m/outbox", headers=env["merch"]).json() if "RQ-" in m["subject"]]
    assert len(mails) >= 3
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE request_messages SET body = 'edited' WHERE request_id = ?", (rid,))
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("DELETE FROM request_messages WHERE request_id = ?", (rid,))


def test_decline_withdraw_and_failed_accept_leave_things_consistent(env):
    t = env["tokenC"]
    a = _req(env, t, "RQ-END-1").json()["id"]
    assert _office(env, f"/{a}/decline", "post", message="").status_code == 400                      # a reason is required
    assert _office(env, f"/{a}/decline", "post", message="No capacity for that window").status_code == 200
    assert _buyer(env, t, f"/{a}").json()["status"] == "declined"
    assert _office(env, f"/{a}/accept", "post", unitId=1, templateKey="basic").status_code == 409   # already closed
    assert _buyer(env, t, f"/{a}/withdraw", "post").status_code == 409

    b = _req(env, t, "RQ-END-2").json()["id"]
    assert _buyer(env, t, f"/{b}/withdraw", "post").status_code == 200
    assert _buyer(env, t, f"/{b}").json()["status"] == "withdrawn"

    c = _req(env, t, "RQ-END-3").json()["id"]
    n_orders = env["db"].execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert _office(env, f"/{c}/accept", "post", unitId=999, templateKey="basic").status_code == 400      # not a unit
    assert _office(env, f"/{c}/accept", "post", unitId=1, templateKey="no-such").status_code == 400
    assert env["db"].execute("SELECT COUNT(*) FROM orders").fetchone()[0] == n_orders                    # nothing half-created
    assert _office(env, f"/{c}").json()["status"] == "submitted"
    # The same PO turning up as an order in the meantime blocks the accept.
    _new_order(env, "RQ-END-3", 2)
    assert _office(env, f"/{c}/accept", "post", unitId=1, templateKey="basic").status_code == 409
    assert _office(env, "?filter=bogus").status_code == 400


def test_a_buyer_cannot_have_more_than_25_open_requests(env):
    env["db"].execute("INSERT INTO buyers (id, name, link_token) VALUES (9, 'Busy buyer', ?)", ("busy-" + new_token(),))
    token = env["db"].execute("SELECT link_token FROM buyers WHERE id = 9").fetchone()[0]
    codes = [_req(env, token, f"RQ-BUSY-{i}").status_code for i in range(27)]
    assert codes.count(201) == 25 and codes[25:] == [429, 429]


# --- Attachments ---------------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n%fake but starts like a PDF\n"
ZIP = b"PK\x03\x04" + b"\x00" * 30
DXF = b"  0\nSECTION\n  2\nHEADER\n"


def _upload(env, where, data, name="design.png", kind="design", claimed="image/png", token=None, **extra):
    """where: ('buyer', request_id) or ('office-request', id) or ('office-order', id)."""
    who, target = where
    files = {"file": (name, data, claimed)}
    if who == "buyer":
        return env["client"].post(f"/api/b/{token}/requests/{target}/attachments", data={"kind": kind}, files=files)
    path = f"/api/m/requests/{target}/attachments" if who == "office-request" else f"/api/m/orders/{target}/attachments"
    return env["client"].post(path, headers=env["merch"], data={"kind": kind, **{k: str(v).lower() for k, v in extra.items()}}, files=files)


def _files_seen_by_buyer(env, token, rid):
    return {a["id"]: a for a in _buyer(env, token, f"/{rid}").json()["attachments"]}


def test_files_are_judged_by_their_bytes_not_their_names(env):
    t = env["tokenB"]
    rid = _req(env, t, "ATT-1").json()["id"]
    assert _upload(env, ("buyer", rid), b"<html><script>alert(1)</script></html>", "logo.png", token=t).status_code == 400
    assert _upload(env, ("buyer", rid), b"MZ\x90\x00" + b"\x00" * 50, "design.pdf", claimed="application/pdf", token=t).status_code == 400
    assert _upload(env, ("buyer", rid), b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "art.svg", claimed="image/svg+xml", token=t).status_code == 400
    assert _upload(env, ("buyer", rid), b"", "empty.png", token=t).status_code == 400
    assert _upload(env, ("buyer", rid), PNG, "x.png", kind="selfie", token=t).status_code == 400

    # A real PNG, sent with a hostile name and a lying content type, is stored as what it is.
    ok = _upload(env, ("buyer", rid), PNG, "../../evil.php", claimed="text/html", token=t)
    assert ok.status_code == 201
    row = env["db"].execute("SELECT * FROM attachments WHERE id = ?", (ok.json()["id"],)).fetchone()
    assert row["mime"] == "image/png" and row["filename"] == "evil.png" and "evil" not in row["path"] and row["path"].endswith(".png")

    got = env["client"].get(f"/api/b/{t}/attachments/{ok.json()['id']}")
    assert got.status_code == 200 and got.headers["content-type"] == "image/png" and got.headers["x-content-type-options"] == "nosniff"
    assert got.content == PNG and got.headers["content-disposition"].startswith("inline")

    pdf = _upload(env, ("buyer", rid), PDF, "techpack.pdf", kind="pattern", claimed="application/octet-stream", token=t)
    assert pdf.status_code == 201
    assert env["client"].get(f"/api/b/{t}/attachments/{pdf.json()['id']}").headers["content-type"] == "application/pdf"
    zipped = _upload(env, ("buyer", rid), ZIP, "bundle.zip", kind="other", token=t)
    assert env["client"].get(f"/api/b/{t}/attachments/{zipped.json()['id']}").headers["content-disposition"].startswith("attachment")
    assert _upload(env, ("buyer", rid), DXF, "pattern.dxf", kind="pattern", token=t).status_code == 201


def test_file_size_and_count_limits(env):
    t = env["tokenB"]
    rid = _req(env, t, "ATT-2").json()["id"]
    too_big = b"\xff\xd8\xff" + b"0" * (15 * 1024 * 1024)
    assert _upload(env, ("buyer", rid), too_big, "huge.jpg", claimed="image/jpeg", token=t).status_code == 413
    codes = [_upload(env, ("buyer", rid), PNG, f"f{i}.png", token=t).status_code for i in range(12)]
    assert codes.count(201) == 10 and codes[10:] == [409, 409]


def test_only_the_owning_buyer_can_touch_a_requests_files(env):
    t, other = env["tokenB"], env["tokenC"]
    rid = _req(env, t, "ATT-3").json()["id"]
    aid = _upload(env, ("buyer", rid), PNG, token=t).json()["id"]
    assert _upload(env, ("buyer", rid), PNG, token=other).status_code == 404
    assert env["client"].get(f"/api/b/{other}/attachments/{aid}").status_code == 404
    assert env["client"].delete(f"/api/b/{other}/requests/{rid}/attachments/{aid}").status_code == 404
    assert env["client"].get(f"/api/b/{t}/attachments/{aid}").status_code == 200
    assert env["client"].get(f"/api/b/{t}/attachments/999999").status_code == 404
    env["client"].cookies.clear()
    assert env["client"].get(f"/api/m/requests/{rid}").status_code == 401                       # the office listing needs a login

    # Office downloads use a short-lived signed link, and a tampered one is refused.
    url = next(a["url"] for a in _office(env, f"/{rid}").json()["attachments"] if a["id"] == aid)
    assert env["client"].get(url).status_code == 200
    assert env["client"].get(url.replace("sig=", "sig=0")).status_code == 403
    assert env["client"].get(f"/api/media/attachments/{aid}").status_code == 403


def test_what_the_buyer_and_the_floor_can_see_is_the_merchandisers_call(env):
    t = env["tokenB"]
    rid = _req(env, t, "ATT-4").json()["id"]
    mine = _upload(env, ("buyer", rid), PNG, "mine.png", token=t).json()["id"]
    internal = _upload(env, ("office-request", rid), PDF, "our-pattern.pdf", kind="pattern", claimed="application/pdf").json()["id"]

    assert set(_files_seen_by_buyer(env, t, rid)) == {mine}                                       # our file is private by default
    assert env["client"].get(f"/api/b/{t}/attachments/{internal}").status_code == 404
    assert env["client"].patch(f"/api/m/attachments/{internal}", headers=env["merch"], json={"buyerVisible": True}).status_code == 200
    seen = _files_seen_by_buyer(env, t, rid)
    assert set(seen) == {mine, internal} and seen[mine]["uploadedBy"] == "you" and seen[internal]["uploadedBy"] == "merchandiser"
    assert env["client"].get(f"/api/b/{t}/attachments/{internal}").status_code == 200

    assert env["client"].patch(f"/api/m/attachments/{mine}", headers=env["merch"], json={"buyerVisible": False}).status_code == 409
    assert env["client"].delete(f"/api/m/attachments/{mine}", headers=env["merch"]).status_code == 403   # the buyer's file is theirs
    assert env["client"].delete(f"/api/m/attachments/{internal}", headers=env["merch"]).status_code == 200
    assert set(_files_seen_by_buyer(env, t, rid)) == {mine}
    assert env["client"].patch(f"/api/m/attachments/{mine}", headers=env["merch"], json={"kind": "nonsense"}).status_code == 400
    assert env["client"].delete(f"/api/b/{t}/requests/{rid}/attachments/{mine}").status_code == 200   # the buyer removes their own


def test_files_follow_a_request_onto_its_order_and_the_floor_sees_only_what_is_shared(env):
    t = env["tokenC"]
    rid = _req(env, t, "ATT-5").json()["id"]
    art = _upload(env, ("buyer", rid), PNG, "print-artwork.png", kind="print", token=t).json()["id"]
    assert _office(env, f"/{rid}/accept", "post", unitId=1, templateKey="basic").status_code == 200
    oid = _office(env, f"/{rid}").json()["orderId"]

    detail = env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()
    assert [(a["id"], a["kind"]) for a in detail["attachments"]] == [(art, "print")]
    buyer_orders = env["client"].get(f"/api/b/{t}").json()["orders"]
    mine = next(o for o in buyer_orders if o["id"] == oid)
    assert [a["id"] for a in mine["attachments"]] == [art]                                       # the buyer sees it on their order
    assert all(a["id"] != art for o in env["client"].get(f"/api/b/{env['tokenB']}").json()["orders"] for a in o["attachments"])

    assert env["client"].get(f"/api/s/orders/{oid}/attachments", headers=env["sup1"]).json()["files"] == []    # not shared with the floor yet
    assert env["client"].patch(f"/api/m/attachments/{art}", headers=env["merch"], json={"supervisorVisible": True}).status_code == 200
    floor = env["client"].get(f"/api/s/orders/{oid}/attachments", headers=env["sup1"]).json()["files"]
    assert [f["id"] for f in floor] == [art] and env["client"].get(floor[0]["url"]).status_code == 200
    assert env["client"].get(f"/api/s/orders/{oid}/attachments", headers=env["sup2"]).json()["files"] == []   # unit 2 has no stage on it

    extra = _upload(env, ("office-order", oid), PDF, "spec.pdf", kind="pattern", claimed="application/pdf", supervisorVisible=True)
    assert extra.status_code == 201
    assert len(env["client"].get(f"/api/s/orders/{oid}/attachments", headers=env["sup1"]).json()["files"]) == 2
    assert env["client"].post(f"/api/m/orders/999999/attachments", headers=env["merch"], data={"kind": "design"}, files={"file": ("a.png", PNG, "image/png")}).status_code == 404
    assert env["client"].get(f"/api/m/requests", headers=env["sup1"]).status_code == 403


def test_a_closed_request_takes_no_more_files(env):
    t = env["tokenC"]
    rid = _req(env, t, "ATT-6").json()["id"]
    assert _buyer(env, t, f"/{rid}/withdraw", "post").status_code == 200
    assert _upload(env, ("buyer", rid), PNG, token=t).status_code == 409


# --- Changes to an existing order (amendments) -----------------------------------------------

def _fresh_order(env, po, buyer_id=1, qty=1000):
    r = env["client"].post("/api/m/orders", headers=env["merch"], json={
        "poNo": po, "buyerId": buyer_id, "style": "Style A", "colour": "Navy", "exFactory": "2026-12-15", "unitId": 1,
        "templateKey": "basic", "sizes": [{"size": "M", "qty": qty // 2}, {"size": "L", "qty": qty - qty // 2}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _amend(env, token, order_id, **body):
    return env["client"].post(f"/api/b/{token}/orders/{order_id}/amendments", json={"reason": "Buyer revised the order", **body})


def _order(env, oid):
    return env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()


def test_buyer_asks_for_a_change_and_accepting_applies_it_with_a_trail(env):
    oid = _fresh_order(env, "AMD-1")
    t = env["tokenB"]
    before = _order(env, oid)
    sized = [{"size": "M", "qty": 700}, {"size": "L", "qty": 500}, {"size": "XL", "qty": 200}]
    made = _amend(env, t, oid, exFactory="2026-12-22", sizes=sized, reason="Retail promotion moved")
    assert made.status_code == 201, made.text
    rid = made.json()["id"]

    # While open the order is untouched, and both sides can see exactly what would change.
    assert _order(env, oid)["order"]["qty_total"] == 1000
    detail = _office(env, f"/{rid}").json()
    assert detail["kind"] == "amendment" and detail["change"]["dateChanged"] and detail["change"]["qtyChanged"]
    assert detail["change"]["current"]["totalQty"] == 1000 and detail["totalQty"] == 1400
    assert _buyer(env, t, f"/{rid}").json()["change"]["current"]["exFactory"] == "2026-12-15"

    assert _office(env, f"/{rid}/accept", "post").status_code == 200       # no unit or template needed for a change
    after = _order(env, oid)
    assert after["order"]["ex_factory"] == "2026-12-22" and after["order"]["qty_total"] == 1400
    assert [(s["size"], s["qty"]) for s in after["sizes"]] == [("M", 700), ("L", 500), ("XL", 200)]
    assert next(m for m in after["milestones"] if m["code"] == "EXF")["planned_date"] == "2026-12-22"
    trail = [d for d in after["dateChanges"] if d["field"] == "ex_factory"]
    assert len(trail) == 1 and trail[0]["old_value"] == "2026-12-15" and trail[0]["new_value"] == "2026-12-22"
    assert "Retail promotion moved" in trail[0]["reason"] and "RQ-" in trail[0]["reason"]
    assert before["order"]["order_no"] == after["order"]["order_no"]

    closed = _buyer(env, t, f"/{rid}").json()
    assert closed["status"] == "accepted" and "change" not in closed
    assert "1,400" in closed["messages"][-1]["body"]
    assert [m["event"] for m in closed["messages"]] == ["submitted", "accepted"]
    assert any(c["id"] == rid for c in after["changeRequests"])


def test_a_quantity_only_change_leaves_the_date_trail_alone(env):
    oid = _fresh_order(env, "AMD-2")
    rid = _amend(env, env["tokenB"], oid, sizes=[{"size": "M", "qty": 600}, {"size": "L", "qty": 600}]).json()["id"]
    assert _office(env, f"/{rid}/accept", "post").status_code == 200
    o = _order(env, oid)
    assert o["order"]["qty_total"] == 1200 and o["order"]["ex_factory"] == "2026-12-15"
    assert [d for d in o["dateChanges"] if d["field"] == "ex_factory"] == []


def test_a_change_cannot_go_below_what_is_already_made(env):
    oid = _fresh_order(env, "AMD-3")
    assert post_update(env, "sup1", "amd3-cut-0001", stage_id(env["db"], oid, "CUT"), 400).status_code == 201
    rid = _amend(env, env["tokenB"], oid, sizes=[{"size": "M", "qty": 150}, {"size": "L", "qty": 150}]).json()["id"]
    refused = _office(env, f"/{rid}/accept", "post")
    assert refused.status_code == 409 and "already made" in refused.json()["error"]
    assert _order(env, oid)["order"]["qty_total"] == 1000                      # nothing half-applied
    assert _office(env, f"/{rid}").json()["status"] == "submitted"
    assert _office(env, f"/{rid}/decline", "post", message="Cutting is already past that quantity").status_code == 200


def test_a_countered_date_is_applied_once_the_buyer_agrees(env):
    oid = _fresh_order(env, "AMD-4")
    t = env["tokenB"]
    rid = _amend(env, t, oid, exFactory="2026-12-10", reason="Need it sooner").json()["id"]
    assert _office(env, f"/{rid}/counter", "post", exFactory="2026-12-12", message="Earliest we can do").status_code == 200
    assert _order(env, oid)["order"]["ex_factory"] == "2026-12-15"
    assert _buyer(env, t, f"/{rid}/agree", "post").status_code == 200
    assert _office(env, f"/{rid}/accept", "post").status_code == 200
    assert _order(env, oid)["order"]["ex_factory"] == "2026-12-12"


def test_amendment_checks(env):
    oid = _fresh_order(env, "AMD-5")
    t = env["tokenB"]
    assert _amend(env, t, oid).status_code == 400                                              # nothing changes
    assert _amend(env, t, oid, exFactory="2026-12-15").status_code == 400                      # same date
    assert _amend(env, t, oid, exFactory="2026-11-01").status_code == 400                      # in the past
    assert _amend(env, t, oid, sizes=[{"size": "M", "qty": 0}]).status_code == 400             # nothing ordered
    assert _amend(env, t, oid, sizes=[{"size": "M", "qty": 5}, {"size": "m", "qty": 5}]).status_code == 400
    assert env["client"].post(f"/api/b/{t}/orders/{oid}/amendments", json={"exFactory": "2026-12-20", "reason": ""}).status_code == 400
    assert _amend(env, env["tokenC"], oid, exFactory="2026-12-20").status_code == 404          # not their order
    assert _amend(env, t, 999999, exFactory="2026-12-20").status_code == 404
    first = _amend(env, t, oid, exFactory="2026-12-20")
    assert first.status_code == 201
    assert _amend(env, t, oid, exFactory="2026-12-21").status_code == 409                      # one open change at a time
    assert _buyer(env, t, f"/{first.json()['id']}/withdraw", "post").status_code == 200       # clear it, so the next check stands alone

    env["db"].execute("UPDATE orders SET state = 'cancelled' WHERE id = ?", (oid,))
    assert _amend(env, t, oid, exFactory="2026-12-23").status_code == 409                      # closed orders take no changes
    env["db"].execute("UPDATE orders SET state = 'active' WHERE id = ?", (oid,))


def test_the_merchandiser_can_record_a_change_the_buyer_sent_by_email(env):
    oid = _fresh_order(env, "AMD-6")
    t = env["tokenB"]
    body = {"exFactory": "2026-12-18", "sizes": [{"size": "M", "qty": 800}, {"size": "L", "qty": 700}], "reason": "Buyer emailed: more units, a few days later"}
    assert env["client"].post(f"/api/m/orders/{oid}/amend", headers=env["sup1"], json=body).status_code == 403
    r = env["client"].post(f"/api/m/orders/{oid}/amend", headers=env["merch"], json=body)
    assert r.status_code == 201, r.text
    o = _order(env, oid)
    assert o["order"]["qty_total"] == 1500 and o["order"]["ex_factory"] == "2026-12-18"
    assert any(d["field"] == "ex_factory" and "emailed" in d["reason"] for d in o["dateChanges"])

    mine = next(x for x in _buyer(env, t, "").json()["requests"] if x["id"] == r.json()["id"])
    assert mine["status"] == "accepted" and mine["kind"] == "amendment"                          # the buyer sees what was recorded
    events = [m for m in _buyer(env, t, f"/{r.json()['id']}").json()["messages"]]
    assert [(m["author"], m["event"]) for m in events] == [("merchandiser", "submitted"), ("merchandiser", "accepted")]
    assert env["client"].post(f"/api/m/orders/{oid}/amend", headers=env["merch"], json={"reason": "again", "exFactory": "2026-12-18"}).status_code == 400
