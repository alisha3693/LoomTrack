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
