"""Production complete, shipped on a date, and the reports that measure the brief's goals."""

from test_api import TODAY, _new_order, env, post_update, stage_id  # noqa: F401

STAGES = ["CUT", "STITCH", "FINISH", "PACK"]


def _outbox(env, oid, event):
    return env["db"].execute("SELECT audience, channel, subject, body FROM outbox_messages WHERE order_id = ? AND event = ?", (oid, event)).fetchall()


def _finish_production(env, oid, qty, tag):
    for i, code in enumerate(STAGES):
        r = post_update(env, "sup1", f"{tag}-{i}", stage_id(env["db"], oid, code), qty)
        assert r.status_code == 201, (code, r.text)


def test_the_office_is_told_once_when_production_is_complete(env):
    oid = _new_order(env, "SHIP-1", 1, exFactory="2026-12-20", sizes=[{"size": "M", "qty": 40}], overCapacityOk=True).json()["id"]
    _finish_production(env, oid, 30, "ship1a")
    assert _outbox(env, oid, "production_complete") == []            # not every piece yet
    _finish_production(env, oid, 10, "ship1b")
    done = _outbox(env, oid, "production_complete")
    assert done and {(m["audience"], m["channel"]) for m in done} == {("office", "email")}
    env["client"].get("/api/m/board", headers=env["merch"])          # looking again does not tell them again
    assert len(_outbox(env, oid, "production_complete")) == len(done)
    assert env["db"].execute("SELECT production_complete_at FROM orders WHERE id = ?", (oid,)).fetchone()[0] == TODAY


def test_marking_an_order_shipped_tells_the_buyer_and_counts_towards_on_time(env):
    c, h, db = env["client"], env["merch"], env["db"]
    late = _new_order(env, "SHIP-2", 1, exFactory="2026-12-01", sizes=[{"size": "M", "qty": 10}], overCapacityOk=True).json()["id"]
    db.execute("UPDATE orders SET ex_factory = '2026-11-03' WHERE id = ?", (late,))   # it was due two days before today
    ontime = _new_order(env, "SHIP-3", 1, exFactory="2026-12-20", sizes=[{"size": "M", "qty": 10}], overCapacityOk=True).json()["id"]
    assert c.post(f"/api/m/orders/{late}/ship", headers=h, json={"shippedDate": "2026-12-30"}).status_code == 400   # not in the future
    shipped = c.post(f"/api/m/orders/{late}/ship", headers=h, json={"shippedDate": TODAY})
    assert shipped.status_code == 200 and shipped.json()["daysLate"] == 2 and shipped.json()["verdict"] == "2 days late"
    assert c.post(f"/api/m/orders/{ontime}/ship", headers=h, json={"shippedDate": TODAY}).json()["daysLate"] < 0
    assert c.post(f"/api/m/orders/{late}/ship", headers=h, json={"shippedDate": TODAY}).status_code == 409           # only once
    assert c.post(f"/api/m/orders/{late}/ship", json={"shippedDate": TODAY}).status_code in (401, 403)
    assert c.post(f"/api/m/orders/{late}/ship", headers=env["sup1"], json={"shippedDate": TODAY}).status_code == 403

    row = db.execute("SELECT state, shipped_date FROM orders WHERE id = ?", (late,)).fetchone()
    assert tuple(row) == ("shipped", TODAY)
    assert db.execute("SELECT actual_date FROM milestones WHERE order_id = ? AND code = 'EXF'", (late,)).fetchone()[0] == TODAY
    told = _outbox(env, late, "order_shipped")
    assert told and all(m["audience"] == "buyer" and "shipped 2 days late" in m["body"] for m in told)
    assert not db.execute("SELECT 1 FROM warnings WHERE order_id = ? AND state IN ('pending', 'confirmed')", (late,)).fetchone()

    # Off the floor and off the live board, still in the buyer's list with its verdict.
    assert not any(s["order_id"] == late for s in c.get("/api/s/orders", headers=env["sup1"]).json()["stages"])
    assert late not in [o["id"] for o in c.get("/api/m/board", headers=h).json()["orders"]]
    assert post_update(env, "sup1", "ship2-xxxxxxxx", stage_id(db, late, "CUT"), 1).status_code == 409
    mine = {o["id"]: o for o in c.get("/api/b/me", headers=env["buyerB"]).json()["orders"]} if "buyerB" in env else {}
    assert mine == {} or mine[late]["shippedVerdict"] == "2 days late"

    r = c.get("/api/m/reports", headers=h).json()["delivery"]
    assert r["shipped"] >= 2 and r["late"] >= 1 and r["onTime"] >= 1 and r["targetPct"] == 5 and r["baselinePct"] == 8
    assert {o["poNo"]: o["daysLate"] for o in r["orders"]}["SHIP-2"] == 2


def test_the_reports_show_warning_lead_time_floor_adoption_and_buyer_views(env):
    c, h = env["client"], env["merch"]
    oid = _new_order(env, "REP-1", 1, exFactory="2026-11-12", sizes=[{"size": "M", "qty": 1000}], overCapacityOk=True).json()["id"]
    first = post_update(env, "sup1", "rep1-aaaaaaaa", stage_id(env["db"], oid, "CUT"), 10)
    assert first.status_code == 201, first.text
    rep = c.get("/api/m/reports", headers=h).json()
    w = next(o for o in rep["warnings"]["orders"] if o["poNo"] == "REP-1")
    assert w["warnedOn"] == TODAY and w["leadDays"] == 7 and w["level"] in ("amber", "red")   # 5 Nov to 12 Nov
    assert rep["warnings"]["targetDays"] == 14 and rep["warnings"]["earlyEnough"] < rep["warnings"]["warned"]

    sent = [p for p in rep["floor"]["supervisors"] if p["updatesToday"] >= 1]
    assert sent and sent[0]["lastUpdate"] == TODAY and sent[0]["daysThisWeek"] >= 1 and rep["floor"]["sentToday"] == len(sent) <= rep["floor"]["total"]

    before = rep["buyers"]["week"]
    c.get(f"/api/b/{env['tokenB']}")
    c.get(f"/api/b/{env['tokenB']}")
    after = c.get("/api/m/reports", headers=h).json()["buyers"]
    assert after["week"] == before + 2
    assert next(b for b in after["buyers"] if b["lastSeen"])["lastSeen"] == TODAY
    assert c.get("/api/m/reports").status_code in (401, 403) and c.get("/api/m/reports", headers=env["sup1"]).status_code == 403
