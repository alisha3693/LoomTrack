"""The "Reset test data" button: off by default, and it keeps the requests while clearing the orders."""

import pytest

from test_api import _new_order, _office, _req, env, fake_classify  # noqa: F401


def test_reset_is_off_unless_switched_on(env, monkeypatch):
    monkeypatch.delenv("LOOMTRACK_ALLOW_RESET", raising=False)
    c, h = env["client"], env["merch"]
    assert c.get("/api/m/reset", headers=h).status_code == 404
    assert c.post("/api/m/reset", headers=h, json={"confirm": "RESET"}).status_code == 404
    assert c.get("/api/m/meta", headers=h).json()["canReset"] is False


def test_reset_clears_orders_but_keeps_requests_and_reopens_accepted_ones(env, monkeypatch, tmp_path):
    monkeypatch.setenv("LOOMTRACK_ALLOW_RESET", "1")
    monkeypatch.setattr("loomtrack.config.DB_FILE", str(tmp_path / "x.db"))
    c, h = env["client"], env["merch"]
    _new_order(env, "RST-1", 1)
    rid = _req(env, env["tokenB"], "RST-REQ").json()["id"]
    assert _office(env, f"/{rid}/accept", "post", unitId=1, templateKey="basic").status_code == 200
    waiting = _req(env, env["tokenB"], "RST-WAIT").json()["id"]
    assert c.get("/api/m/meta", headers=h).json()["canReset"] is True
    assert c.get("/api/m/reset", headers=h).json()["removes"]["orders"] >= 2

    assert c.post("/api/m/reset", headers=h, json={"confirm": "reset please"}).status_code == 400
    r = c.post("/api/m/reset", headers=h, json={"confirm": "RESET"})
    assert r.status_code == 200, r.text
    assert (tmp_path / "backups").exists() and list((tmp_path / "backups").glob("before-reset-*.db"))

    db = env["db"]
    for table in ("orders", "milestones", "outbox_messages", "approvals", "order_materials"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    assert db.execute("SELECT COUNT(*) FROM buyers").fetchone()[0] >= 1 and db.execute("SELECT COUNT(*) FROM templates").fetchone()[0] >= 3
    assert _office(env, f"/{waiting}").json()["status"] == "submitted"
    reopened = _office(env, f"/{rid}").json()
    assert reopened["status"] == "submitted" and not reopened.get("orderNo")
    assert _office(env, f"/{rid}/accept", "post", unitId=1, templateKey="basic").status_code == 200   # can be accepted again
