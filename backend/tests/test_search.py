"""The office search box, and the link to what the buyer sees."""

import sqlite3

import pytest

from test_api import TODAY, _new_order, env, fake_classify  # noqa: F401


def test_order_detail_for_the_office_carries_the_buyers_view_link(env):
    oid = _new_order(env, "MSG-6", 1).json()["id"]
    d = env["client"].get(f"/api/m/orders/{oid}", headers=env["merch"]).json()
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
