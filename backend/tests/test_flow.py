"""What passes between the buyer and the merchandiser: the inbox and read marks, approvals, delay-notice
receipts, the order timeline, the buyer's documents and view-only accounts."""

import io
import sqlite3

import pytest

from test_api import TODAY, _new_login, _new_order, _sign_in, env, fake_classify  # noqa: F401


def _msg(env, who, oid, text, token=None):
    c = env["client"]
    if who == "buyer":
        return c.post(f"/api/b/{token or env['tokenB']}/orders/{oid}/messages", json={"message": text})
    return c.post(f"/api/m/orders/{oid}/messages", headers=env["merch"], json={"message": text})


def _inbox(env, who, token=None):
    c = env["client"]
    if who == "buyer":
        return c.get(f"/api/b/{token or env['tokenB']}/inbox").json()["conversations"]
    return c.get("/api/m/inbox", headers=env["merch"]).json()["conversations"]


def _mine(env, who, kind, ref, token=None):
    return next((i for i in _inbox(env, who, token) if (i["kind"], i["id"]) == (kind, ref)), None)


# --- the inbox and who has read what ---------------------------------------------------------------------


def test_the_inbox_lists_every_conversation_and_clears_when_it_is_read(env):
    c = env["client"]
    oid = _new_order(env, "INB-1", 1).json()["id"]
    assert _mine(env, "office", "order", oid) is None                                      # nothing said yet, nothing to show

    _msg(env, "buyer", oid, "Can we move the packing date?")
    row = _mine(env, "office", "order", oid)
    assert (row["turn"], row["unread"], row["title"], row["last"]["author"]) == ("you", True, "INB-1", "buyer")
    assert c.get("/api/m/meta", headers=env["merch"]).json()["unreadMessages"] >= 1
    assert _mine(env, "buyer", "order", oid)["unread"] is False                              # their own message is not "new" to them

    assert c.post(f"/api/m/orders/{oid}/messages/read", headers=env["merch"]).status_code == 200
    row = _mine(env, "office", "order", oid)
    assert (row["unread"], row["turn"]) == (False, "you")                                    # read, but still waiting for an answer

    # The buyer's side sees the same thing once the office answers, and the office's reply is "seen" only after they open it.
    reply = _msg(env, "office", oid, "Yes, Friday is fine.").json()["id"]
    assert _mine(env, "buyer", "order", oid)["unread"] is True
    assert c.get(f"/api/m/orders/{oid}/messages", headers=env["merch"]).json()["readUpTo"] < reply
    assert c.post(f"/api/b/{env['tokenB']}/orders/{oid}/messages/read").status_code == 200
    assert _mine(env, "buyer", "order", oid)["unread"] is False
    assert c.get(f"/api/m/orders/{oid}/messages", headers=env["merch"]).json()["readUpTo"] >= reply     # the office now sees "seen"


def test_the_buyer_badges_count_what_waits_on_them(env):
    c = env["client"]
    oid = _new_order(env, "INB-2", 1).json()["id"]
    before = c.get(f"/api/b/{env['tokenB']}/badges").json()
    _msg(env, "office", oid, "Samples shipped today.")
    after = c.get(f"/api/b/{env['tokenB']}/badges").json()
    assert after["messages"] == before["messages"] + 1
    assert set(after) == {"requests", "messages", "notifications", "approvals"}


def test_inbox_and_read_marks_are_private_to_each_buyer(env):
    c = env["client"]
    oid = _new_order(env, "INB-3", 1).json()["id"]
    _msg(env, "buyer", oid, "hello")
    assert _mine(env, "buyer", "order", oid, token=env["tokenC"]) is None                    # another buyer's inbox never lists it
    assert c.post(f"/api/b/{env['tokenC']}/orders/{oid}/messages/read").status_code == 404
    assert c.get(f"/api/b/{env['tokenC']}/orders/{oid}/read-state").status_code == 404
    assert c.post(f"/api/b/{env['tokenB']}/orders/999999/messages/read").status_code == 404
    c.cookies.clear()
    assert c.get("/api/m/inbox").status_code == 401
    assert c.post(f"/api/m/orders/{oid}/messages/read").status_code == 401


def test_an_open_request_is_in_the_inbox_until_it_becomes_an_order_and_then_its_talk_joins_the_order(env):
    c = env["client"]
    rid = c.post(f"/api/b/{env['tokenB']}/requests", json={"poNo": "INB-REQ", "style": "Tee", "colour": "Navy", "exFactory": "2026-12-30",
                                                           "sizes": [{"size": "M", "qty": 100}]}).json()["id"]
    row = _mine(env, "office", "request", rid)
    assert (row["turn"], row["unread"]) == ("you", True)
    assert _mine(env, "buyer", "request", rid)["turn"] == "them"

    c.post(f"/api/m/requests/{rid}/query", headers=env["merch"], json={"message": "Which GSM do you want?"})
    assert _mine(env, "buyer", "request", rid)["turn"] == "you"

    oid = c.post(f"/api/m/requests/{rid}/accept", headers=env["merch"], json={"unitId": 1, "templateKey": "basic"}).json()["orderId"]
    assert _mine(env, "office", "request", rid) is None                                      # closed requests leave the inbox...
    thread = c.get(f"/api/b/{env['tokenB']}/orders/{oid}/messages").json()["messages"]
    assert [m["source"] for m in thread][:2] == ["request", "request"]                       # ...and their history opens the order's conversation
    assert [m["event"] for m in thread if m["source"] == "request"] == ["submitted", "query", "accepted"]
    assert thread[0]["requestNo"].startswith("RQ-")


# --- approvals ---------------------------------------------------------------------------------------------


def _ask(env, oid, kind="fit_sample", title="Fit sample, size M", note="On the fit model.", **kw):
    return env["client"].post(f"/api/m/orders/{oid}/approvals", headers=env["merch"], json={"kind": kind, "title": title, "note": note}, **kw)


def test_the_buyer_approves_a_sample_and_the_plan_step_is_marked_done_with_a_trail(env):
    c = env["client"]
    oid = _new_order(env, "APR-1", 1).json()["id"]
    aid = _ask(env, oid, "pp_sample", "PP sample, navy").json()["id"]

    mail = env["db"].execute("SELECT subject FROM outbox_messages WHERE order_id = ?", (oid,)).fetchall()
    assert [m["subject"] for m in mail] == ["Approval needed: PP sample, navy (APR-1)"]
    mine = c.get(f"/api/b/{env['tokenB']}/approvals").json()["approvals"]
    assert [(a["id"], a["status"], a["completesStep"]) for a in mine] == [(aid, "requested", "PP sample approval")]
    assert c.get(f"/api/b/{env['tokenB']}/badges").json()["approvals"] == 1
    assert c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["approvals"][0]["buyerSeenAt"]      # opening the page counts as seen

    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/approve", json={"note": "Looks good."}).status_code == 200
    step = env["db"].execute("SELECT actual_date FROM milestones WHERE order_id = ? AND code = 'PP'", (oid,)).fetchone()
    assert step["actual_date"] == TODAY                                                       # approving completes the plan step...
    trail = env["db"].execute("SELECT reason, changed_by FROM date_changes WHERE order_id = ? AND field = 'actual_date'", (oid,)).fetchone()
    assert "approved by the buyer" in trail["reason"] and trail["changed_by"] is None        # ...and the date history says who
    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/approve", json={}).status_code == 409   # it cannot be decided twice
    assert [e["action"] for e in c.get(f"/api/m/approvals", headers=env["merch"]).json()["approvals"][0]["events"]] == ["requested", "approved"]


def test_asking_for_changes_needs_a_reason_and_the_office_sends_it_again(env):
    c = env["client"]
    oid = _new_order(env, "APR-2", 1).json()["id"]
    aid = _ask(env, oid).json()["id"]
    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/changes", json={}).status_code == 400
    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/changes", json={"note": "no"}).status_code == 400
    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/changes", json={"note": "The neck is too wide."}).status_code == 200
    assert env["db"].execute("SELECT actual_date FROM milestones WHERE order_id = ? AND code = 'FIT'", (oid,)).fetchone()[0] is None   # nothing is marked done
    assert c.get("/api/m/meta", headers=env["merch"]).json()["approvalsToAnswer"] >= 1
    board = next(o for o in c.get("/api/m/board", headers=env["merch"]).json()["orders"] if o["id"] == oid)
    assert board["approvals"] == {"waiting": 0, "sentBack": 1}

    assert c.post(f"/api/m/approvals/{aid}/resubmit", headers=env["merch"], json={}).status_code == 400     # say what changed
    assert c.post(f"/api/m/approvals/{aid}/resubmit", headers=env["merch"], json={"note": "Neck narrowed by 5 mm."}).status_code == 200
    assert c.get(f"/api/b/{env['tokenB']}/badges").json()["approvals"] >= 1
    events = c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["approvals"][0]["events"]
    assert [e["action"] for e in events] == ["requested", "changes", "resubmitted"]
    assert c.post(f"/api/m/approvals/{aid}/resubmit", headers=env["merch"], json={"note": "again"}).status_code == 409   # only after a "changes"


def test_approvals_are_checked_scoped_and_audited(env):
    c = env["client"]
    oid = _new_order(env, "APR-3", 1).json()["id"]
    assert _ask(env, oid, kind="nonsense").status_code == 400
    assert _ask(env, oid, title="   ").status_code == 422 or _ask(env, oid, title="   ").status_code == 400
    assert _ask(env, 999999).status_code == 404
    aid = _ask(env, oid).json()["id"]
    assert _ask(env, oid).status_code == 409                                                  # one open approval per kind

    # Another buyer cannot see or decide it; a stranger cannot ask.
    assert c.get(f"/api/b/{env['tokenC']}/approvals").json()["approvals"] == []
    assert c.post(f"/api/b/{env['tokenC']}/approvals/{aid}/approve", json={}).status_code == 404
    c.cookies.clear()
    assert c.post(f"/api/m/orders/{oid}/approvals", json={"kind": "other", "title": "x"}).status_code == 401
    assert c.post(f"/api/m/orders/{oid}/approvals", headers=env["sup1"], json={"kind": "other", "title": "x"}).status_code == 403

    # Withdrawing closes it; the trail cannot be edited.
    assert c.post(f"/api/m/approvals/{aid}/withdraw", headers=env["merch"]).status_code == 200
    assert c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/approve", json={}).status_code == 409
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("UPDATE approval_events SET note = 'edited'")
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM approval_events")
    # A cancelled order's approvals disappear for the buyer.
    other = _new_order(env, "APR-4", 1).json()["id"]
    _ask(env, other, "lab_dip", "Lab dip, olive")
    env["db"].execute("UPDATE orders SET state = 'cancelled' WHERE id = ?", (other,))
    assert all(a["poNo"] != "APR-4" for a in c.get(f"/api/b/{env['tokenB']}/approvals").json()["approvals"])


# --- delay-notice receipts ----------------------------------------------------------------------------------


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
    assert c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["warnings"][0]["buyer_ack_at"]
    talk = c.get(f"/api/m/orders/{oid}/messages", headers=env["merch"]).json()["messages"]
    assert talk[-1]["author"] == "buyer" and "ship by air" in talk[-1]["body"]               # the note joined the conversation


# --- timeline, documents and view-only accounts -----------------------------------------------------------


def test_the_timeline_tells_both_sides_what_happened_and_hides_what_is_internal(env):
    c = env["client"]
    oid = _new_order(env, "ACT-1", 1).json()["id"]
    _msg(env, "buyer", oid, "Any news?")
    aid = _ask(env, oid, "pp_sample", "PP sample").json()["id"]
    c.post(f"/api/b/{env['tokenB']}/approvals/{aid}/approve", json={})
    env["db"].execute("INSERT INTO order_materials (order_id, kind, name, status, received_date, needed_by) VALUES (?, 'trim', 'Main label', 'received', ?, ?)", (oid, TODAY, TODAY))

    office = c.get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["activity"]
    buyer = c.get(f"/api/b/{env['tokenB']}/orders/{oid}/activity").json()["activity"]
    assert any(i["kind"] == "message" and i["actor"] == "buyer" for i in buyer)
    assert any(i["kind"] == "approval" and "Approved" in i["title"] for i in buyer)
    assert any(i["kind"] == "step" and "PP sample approval" in i["title"] for i in buyer)
    assert any(i["kind"] == "material" for i in office) and not any(i["kind"] == "material" for i in buyer)
    assert [i["at"] for i in office] == sorted((i["at"] for i in office), reverse=True)        # newest first
    assert c.get(f"/api/b/{env['tokenC']}/orders/{oid}/activity").status_code == 404


def test_documents_lists_only_what_the_buyer_may_see(env):
    c = env["client"]
    oid = _new_order(env, "DOC-1", 1).json()["id"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    up = lambda vis: c.post(f"/api/m/orders/{oid}/attachments", headers=env["merch"], data={"kind": "design", "buyerVisible": str(vis).lower()}, files={"file": (f"art{vis}.png", io.BytesIO(png), "image/png")})
    assert up(True).status_code == 201 and up(False).status_code == 201
    docs = c.get(f"/api/b/{env['tokenB']}/documents").json()["documents"]
    mine = [d for d in docs if d["orderPo"] == "DOC-1"]
    assert [d["filename"] for d in mine] == ["artTrue.png"]                                  # the private one is not listed
    assert c.get(mine[0]["url"]).status_code == 200                                           # and the link opens
    assert all(d["orderPo"] != "DOC-1" for d in c.get(f"/api/b/{env['tokenC']}/documents").json()["documents"])


def test_a_view_only_account_can_look_but_not_send_approve_or_change(env):
    c = env["client"]
    oid = _new_order(env, "VIEW-1", 1).json()["id"]
    aid = _ask(env, oid).json()["id"]
    made = c.post("/api/m/buyers/1/logins", headers=env["merch"], json={"name": "Maya", "email": "maya@buyerb.example", "canWrite": False}).json()
    h = _sign_in(env, made["login"], made["password"])
    assert c.post("/api/auth/password", headers=h, json={"current": made["password"], "new": "a-new-password-1"}).status_code == 200
    h = _sign_in(env, made["login"], "a-new-password-1")
    assert c.get("/api/auth/me", headers=h).json()["user"]["can_write"] == 0

    assert c.get("/api/b/me", headers=h).status_code == 200                                   # can look at everything
    assert c.get("/api/b/me/approvals", headers=h).status_code == 200
    assert c.get("/api/b/me/inbox", headers=h).status_code == 200
    denied = [
        c.post(f"/api/b/me/orders/{oid}/messages", headers=h, json={"message": "hi"}),
        c.post(f"/api/b/me/approvals/{aid}/approve", headers=h, json={}),
        c.post(f"/api/b/me/approvals/{aid}/changes", headers=h, json={"note": "no good"}),
        c.post("/api/b/me/requests", headers=h, json={"poNo": "VIEW-REQ", "style": "Tee", "colour": "Navy", "exFactory": "2026-12-30", "sizes": [{"size": "M", "qty": 10}]}),
        c.post(f"/api/b/me/orders/{oid}/amendments", headers=h, json={"reason": "later", "exFactory": "2026-12-20"}),
    ]
    assert [r.status_code for r in denied] == [403] * 5
    assert "view" in denied[0].json()["error"].lower()
    assert env["db"].execute("SELECT status FROM approvals WHERE id = ?", (aid,)).fetchone()[0] == "requested"   # nothing changed

    # The office can give the account full access, and it works on the account's very next request.
    uid = env["db"].execute("SELECT id FROM users WHERE login = ?", (made["login"],)).fetchone()[0]
    assert c.patch(f"/api/m/buyer-logins/{uid}", headers=env["merch"], json={"canWrite": True}).status_code == 200
    assert c.post(f"/api/b/me/approvals/{aid}/approve", headers=h, json={}).status_code == 200
    assert c.patch(f"/api/m/buyer-logins/{uid}", json={"canWrite": False}).status_code in (401, 403)
    assert c.patch("/api/m/buyer-logins/1", headers=env["merch"], json={"canWrite": False}).status_code == 404       # staff are not buyer logins
