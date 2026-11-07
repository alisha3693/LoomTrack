"""The conversation about an existing order, and the office search box."""

import sqlite3

import pytest

from test_api import TODAY, _new_order, env, fake_classify  # noqa: F401


def _board_row(env, oid):
    return next(o for o in env["client"].get("/api/m/board", headers=env["merch"]).json()["orders"] if o["id"] == oid)


def _say(env, who, oid, text, token=None):
    c = env["client"]
    if who == "buyer":
        return c.post(f"/api/b/{token or env['tokenB']}/orders/{oid}/messages", json={"message": text})
    return c.post(f"/api/m/orders/{oid}/messages", headers=env["merch"], json={"message": text})


def _thread(env, who, oid, token=None):
    c = env["client"]
    if who == "buyer":
        return c.get(f"/api/b/{token or env['tokenB']}/orders/{oid}/messages")
    return c.get(f"/api/m/orders/{oid}/messages", headers=env["merch"])


def test_buyer_and_merchandiser_talk_about_an_order_and_it_shows_whose_turn_it_is(env):
    oid = _new_order(env, "MSG-1", 1).json()["id"]
    assert _board_row(env, oid)["awaitingReply"] is False

    assert _say(env, "buyer", oid, "  Can you send photos of the finished sample?  ").status_code == 201
    assert _board_row(env, oid)["awaitingReply"] is True                                   # the office owes an answer
    sent = env["client"].get(f"/api/b/{env['tokenB']}").json()["orders"]
    mine = next(o for o in sent if o["poNo"] == "MSG-1")
    assert mine["lastMessage"]["author"] == "buyer" and mine["lastMessage"]["count"] == 1

    assert _say(env, "office", oid, "Yes, photos are on the way.").status_code == 201
    assert _board_row(env, oid)["awaitingReply"] is False                                  # answered
    assert [(m["author"], m["body"]) for m in _thread(env, "buyer", oid).json()["messages"]] == [
        ("buyer", "Can you send photos of the finished sample?"), ("merchandiser", "Yes, photos are on the way.")]
    assert _thread(env, "office", oid).json() == _thread(env, "buyer", oid).json()

    # Each side is told outside the app as well: the buyer's question goes to the office, the reply to the buyer.
    sent = env["db"].execute("SELECT event, audience, subject, body FROM outbox_messages WHERE order_id = ? ORDER BY id", (oid,)).fetchall()
    assert [(m["event"], m["audience"]) for m in sent] == [("order_message_in", "office"), ("order_message", "buyer")]
    assert "Yes, photos are on the way." in sent[1]["body"]


def test_messages_are_checked(env):
    oid = _new_order(env, "MSG-2", 1).json()["id"]
    for text in ("", "   ", "x" * 2001):
        assert _say(env, "buyer", oid, text).status_code == 400, text
        assert _say(env, "office", oid, text).status_code == 400, text
    assert _say(env, "buyer", oid, "x" * 2000).status_code == 201
    env["db"].executemany("INSERT INTO order_messages (order_id, author, body) VALUES (?, 'buyer', 'filler')", [(oid,)] * 499)
    assert _say(env, "buyer", oid, "one too many").status_code == 409                       # the conversation is capped


def test_a_buyer_cannot_read_or_write_another_buyers_order(env):
    mine = _new_order(env, "MSG-3", 1).json()["id"]
    theirs = env["orderC"]
    assert _say(env, "buyer", mine, "hello").status_code == 201
    assert _say(env, "buyer", theirs, "I want to see your order").status_code == 404
    assert _thread(env, "buyer", theirs).status_code == 404
    assert _say(env, "buyer", 999999, "nobody home").status_code == 404
    assert _thread(env, "buyer", mine, token=env["tokenC"]).status_code == 404               # nor can Company C read Company B's thread
    assert _say(env, "buyer", mine, "sneaky", token=env["tokenC"]).status_code == 404
    assert env["db"].execute("SELECT COUNT(*) FROM order_messages WHERE order_id = ?", (theirs,)).fetchone()[0] == 0

    env["db"].execute("UPDATE orders SET state = 'cancelled' WHERE id = ?", (mine,))
    assert _say(env, "buyer", mine, "still there?").status_code == 404                      # a cancelled order is gone for the buyer


def test_only_the_merchandiser_reaches_the_office_side(env):
    c = env["client"]
    oid = _new_order(env, "MSG-4", 1).json()["id"]
    c.cookies.clear()
    assert c.get(f"/api/m/orders/{oid}/messages").status_code == 401
    assert c.post(f"/api/m/orders/{oid}/messages", json={"message": "hi"}).status_code == 401
    assert c.get(f"/api/m/orders/{oid}/messages", headers=env["sup1"]).status_code == 403
    assert c.post(f"/api/m/orders/{oid}/messages", headers=env["sup1"], json={"message": "hi"}).status_code == 403
    assert c.post("/api/m/orders/999999/messages", headers=env["merch"], json={"message": "hi"}).status_code == 404


def test_messages_cannot_be_changed_or_removed(env):
    oid = _new_order(env, "MSG-5", 1).json()["id"]
    _say(env, "buyer", oid, "original")
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("UPDATE order_messages SET body = 'edited' WHERE order_id = ?", (oid,))
    with pytest.raises(sqlite3.IntegrityError):
        env["db"].execute("DELETE FROM order_messages WHERE order_id = ?", (oid,))


def test_order_detail_for_the_office_carries_the_thread_and_the_buyers_view_link(env):
    oid = _new_order(env, "MSG-6", 1).json()["id"]
    _say(env, "buyer", oid, "Hello")
    d = env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()
    assert [m["body"] for m in d["messages"]] == ["Hello"]
    assert d["buyerPath"] == f"/b/{env['tokenB']}/orders/{oid}"
    env["db"].execute("UPDATE buyers SET link_active = 0 WHERE id = 1")
    assert env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()["buyerPath"] is None     # a switched-off link is not offered
    env["db"].execute("UPDATE buyers SET link_active = 1 WHERE id = 1")


# --- search ------------------------------------------------------------------------------------


def _find(env, q):
    r = env["client"].get("/api/m/search", headers=env["merch"], params={"q": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_search_finds_orders_requests_and_buyers_by_what_people_type(env):
    oid = _new_order(env, "SRCH-4471", 1, style="Raglan hoodie", colour="Burgundy").json()["id"]
    rid = env["client"].post(f"/api/b/{env['tokenC']}/requests", json={"poNo": "SRCH-REQ-9", "style": "Pique polo", "colour": "White", "exFactory": "2026-12-30",
                                                                      "sizes": [{"size": "M", "qty": 10}]}).json()["id"]
    by_po = _find(env, "srch-4471")["orders"]
    assert [o["id"] for o in by_po] == [oid] and by_po[0]["buyer"] == "Buyer B" and by_po[0]["state"] == "active"
    order_no = by_po[0]["orderNo"]
    assert [o["id"] for o in _find(env, order_no)["orders"]] == [oid]
    assert any(o["id"] == oid for o in _find(env, "raglan")["orders"])
    assert any(o["id"] == oid for o in _find(env, "burgundy")["orders"])
    by_buyer = _find(env, "Buyer B")
    assert by_buyer["orders"] and {o["buyer"] for o in by_buyer["orders"]} == {"Buyer B"} and by_buyer["buyers"][0]["name"] == "Buyer B"
    hit = _find(env, "SRCH-REQ")["requests"]
    assert [r["id"] for r in hit] == [rid] and hit[0]["buyer"] == "Buyer C"
    assert any(r["id"] == rid for r in _find(env, "RQ-")["requests"])


def test_search_is_literal_short_limited_and_private(env):
    for n in range(8):
        _new_order(env, f"LIM-{n}", 1)
    assert len(_find(env, "LIM-")["orders"]) == 6                                           # at most six of each kind
    assert _find(env, "a") == {"orders": [], "requests": [], "buyers": []}                  # too short to mean anything
    assert _find(env, "") == {"orders": [], "requests": [], "buyers": []}
    assert _find(env, "%%") == {"orders": [], "requests": [], "buyers": []}                 # a wildcard is just text, not "everything"
    assert _find(env, "_") == {"orders": [], "requests": [], "buyers": []}
    assert _find(env, "zz-no-such-thing") == {"orders": [], "requests": [], "buyers": []}
    c = env["client"]
    c.cookies.clear()
    assert c.get("/api/m/search", params={"q": "LIM-"}).status_code == 401
    assert c.get("/api/m/search", headers=env["sup1"], params={"q": "LIM-"}).status_code == 403
    assert c.get(f"/api/b/{env['tokenB']}/search", params={"q": "LIM-"}).status_code == 404   # there is no buyer-side search of the office's data


def test_an_accepted_request_tells_the_buyer_which_order_it_became(env):
    c = env["client"]
    rid = c.post(f"/api/b/{env['tokenB']}/requests", json={"poNo": "LINK-1", "style": "Tee", "colour": "Navy", "exFactory": "2026-12-30",
                                                           "sizes": [{"size": "M", "qty": 100}]}).json()["id"]
    assert "orderId" not in c.get(f"/api/b/{env['tokenB']}/requests/{rid}").json()                # nothing to link to yet
    oid = c.post(f"/api/m/requests/{rid}/accept", headers=env["merch"], json={"unitId": 1, "templateKey": "basic"}).json()["orderId"]
    assert c.get(f"/api/b/{env['tokenB']}/requests/{rid}").json()["orderId"] == oid
    assert c.get(f"/api/b/{env['tokenC']}/requests/{rid}").status_code == 404                     # still only the owner
