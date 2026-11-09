"""What passes between the buyer and the merchandiser: delay-notice receipts, the order timeline and view-only accounts."""

from test_api import _new_order, _sign_in, env, fake_classify  # noqa: F401


# --- delay notices -----------------------------------------------------------------------------------------


def _confirmed_notice(env, oid):
    env["db"].execute(
        "INSERT INTO warnings (order_id, level, projected_ex_factory, slack_days, summary, buyer_message, state, decided_at) VALUES (?, 'red', '2026-12-10', -5, 'x', 'Now 10 Dec.', 'confirmed', datetime('now'))",
        (oid,),
    )


def test_a_delay_notice_is_seen_then_acknowledged_and_the_office_can_tell(env):
    c = env["client"]
    oid = _new_order(env, "NTC-1", 1).json()["id"]
    assert c.post(f"/api/b/{env['tokenB']}/orders/{oid}/notice/seen").status_code == 404      # no confirmed notice, nothing to open
    _confirmed_notice(env, oid)
    board = lambda: next(o for o in c.get("/api/m/board", headers=env["merch"]).json()["orders"] if o["id"] == oid)
    assert board()["noticeUnacknowledged"] is True
    assert next(o for o in c.get(f"/api/b/{env['tokenB']}").json()["orders"] if o["id"] == oid)["notice"]["acknowledgedAt"] is None

    assert c.post(f"/api/b/{env['tokenB']}/orders/{oid}/notice/seen").status_code == 200
    w = c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["warnings"][0]
    assert w["buyer_seen_at"] and w["buyer_ack_at"] is None                                   # opened, not yet answered

    assert c.post(f"/api/b/{env['tokenC']}/orders/{oid}/notice/acknowledge", json={}).status_code == 404   # only its own buyer
    assert c.post(f"/api/b/{env['tokenB']}/orders/{oid}/notice/acknowledge", json={"note": "Please ship by air for the last 500."}).status_code == 200
    assert board()["noticeUnacknowledged"] is False
    done = c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["warnings"][0]
    assert done["buyer_ack_at"] and "ship by air" in done["buyer_ack_note"]                    # the note stays on the notice


# --- timeline and view-only accounts -----------------------------------------------------------------------


def test_the_timeline_tells_both_sides_what_happened_and_hides_what_is_internal(env):
    c = env["client"]
    oid = _new_order(env, "ACT-1", 1).json()["id"]
    _confirmed_notice(env, oid)
    c.post(f"/api/b/{env['tokenB']}/orders/{oid}/notice/seen")
    c.post(f"/api/b/{env['tokenB']}/orders/{oid}/notice/acknowledge", json={"note": "Thank you, noted."})

    office = c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["activity"]
    buyer = c.get(f"/api/b/{env['tokenB']}/orders/{oid}/activity").json()["activity"]
    assert any(i["kind"] == "notice" and "Delay notice" in i["title"] for i in buyer)
    assert any(i["kind"] == "notice" and "acknowledged" in i["title"] and i["detail"] == "Thank you, noted." for i in buyer)
    assert any("opened" in i["title"] for i in office) and not any("opened" in i["title"] for i in buyer)   # who looked is for the office only
    assert [i["at"] for i in office] == sorted((i["at"] for i in office), reverse=True)        # newest first
    assert c.get(f"/api/b/{env['tokenC']}/orders/{oid}/activity").status_code == 404


def test_a_view_only_account_can_look_but_not_send_or_change(env):
    c = env["client"]
    oid = _new_order(env, "VIEW-1", 1).json()["id"]
    _confirmed_notice(env, oid)
    made = c.post("/api/m/buyers/1/logins", headers=env["merch"], json={"name": "Maya", "email": "maya@buyerb.example", "canWrite": False}).json()
    h = _sign_in(env, made["login"], made["password"])
    assert c.post("/api/auth/password", headers=h, json={"current": made["password"], "new": "a-new-password-1"}).status_code == 200
    h = _sign_in(env, made["login"], "a-new-password-1")
    assert c.get("/api/auth/me", headers=h).json()["user"]["can_write"] == 0

    assert c.get("/api/b/me", headers=h).status_code == 200                                   # can look at everything
    assert c.get("/api/b/me/feed", headers=h).status_code == 200
    denied = [
        c.post(f"/api/b/me/orders/{oid}/notice/acknowledge", headers=h, json={"note": "ok"}),
        c.post("/api/b/me/requests", headers=h, json={"poNo": "VIEW-REQ", "style": "Tee", "colour": "Navy", "exFactory": "2026-12-30", "sizes": [{"size": "M", "qty": 10}]}),
        c.post(f"/api/b/me/orders/{oid}/amendments", headers=h, json={"reason": "later", "exFactory": "2026-12-20"}),
    ]
    assert [r.status_code for r in denied] == [403] * 3
    assert "view" in denied[0].json()["error"].lower()
    assert env["db"].execute("SELECT buyer_ack_at FROM warnings WHERE order_id = ?", (oid,)).fetchone()[0] is None   # nothing changed

    # The office can give the account full access, and it works on the account's very next request.
    uid = env["db"].execute("SELECT id FROM users WHERE login = ?", (made["login"],)).fetchone()[0]
    assert c.patch(f"/api/m/buyer-logins/{uid}", headers=env["merch"], json={"canWrite": True}).status_code == 200
    assert c.post(f"/api/b/me/orders/{oid}/notice/acknowledge", headers=h, json={"note": "ok"}).status_code == 200
    assert c.patch(f"/api/m/buyer-logins/{uid}", json={"canWrite": False}).status_code in (401, 403)
    assert c.patch("/api/m/buyer-logins/1", headers=env["merch"], json={"canWrite": False}).status_code == 404       # staff are not buyer logins
