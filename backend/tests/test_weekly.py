"""The weekly status email: when it goes, to whom, what it says, and that the buyer's own Excel file is attached."""

import asyncio
import io
from datetime import datetime

from openpyxl import load_workbook

from loomtrack.services import delivery, weekly
from test_api import TODAY, env, _new_login  # noqa: F401

MONDAY = datetime(2026, 11, 9, 9, 0)  # a Monday


def _rows(env):
    return env["db"].execute("SELECT buyer_id, audience, channel, recipient, status, subject, body FROM outbox_messages WHERE event = 'weekly_status' ORDER BY id").fetchall()


def test_the_weekly_status_goes_once_a_week_on_the_chosen_day_and_hour(env, monkeypatch):
    db = env["db"]
    monkeypatch.setenv("LOOMTRACK_SMTP_HOST", "smtp.test.example")
    monkeypatch.setenv("LOOMTRACK_SMTP_FROM", "LoomTrack <office@test.example>")
    monkeypatch.setenv("LOOMTRACK_WEEKLY_DAY", "mon")
    monkeypatch.setenv("LOOMTRACK_WEEKLY_HOUR", "8")
    made = _new_login(env, 1, "weekly@buyerb.example", "Weekly Person")

    assert weekly.queue_weekly(db, datetime(2026, 11, 10, 9, 0), TODAY) == 0      # Tuesday
    assert weekly.queue_weekly(db, datetime(2026, 11, 9, 7, 59), TODAY) == 0      # Monday, before 8:00
    assert _rows(env) == []
    first = weekly.queue_weekly(db, MONDAY, TODAY)
    assert first >= 1
    assert weekly.queue_weekly(db, MONDAY, TODAY) == 0                            # a restart that morning sends nothing more
    assert weekly.queue_weekly(db, datetime(2026, 11, 9, 15, 0), TODAY) == 0

    mine = [r for r in _rows(env) if r["recipient"] == made["login"]]
    assert len(mine) == 1 and mine[0]["audience"] == "buyer" and mine[0]["channel"] == "email" and mine[0]["status"] == "queued"
    assert mine[0]["subject"].startswith("Weekly order status: 2026-W")
    assert "PO-B-1" in mine[0]["body"] and "Hello Weekly Person" in mine[0]["body"] and "attached" in mine[0]["body"]
    # What a buyer may know: never the internal colour of the order, and never another buyer's orders.
    assert not any(w in mine[0]["body"].lower() for w in ("amber", "green status", "red status", "run rate"))
    other_pos = [r[0] for r in db.execute("SELECT po_no FROM orders WHERE buyer_id != 1")]
    assert other_pos and not any(po in mine[0]["body"] for po in other_pos)


def test_the_weekly_email_carries_that_buyers_excel_file_only(env, monkeypatch):
    db = env["db"]
    monkeypatch.setenv("LOOMTRACK_SMTP_HOST", "smtp.test.example")
    monkeypatch.setenv("LOOMTRACK_SMTP_FROM", "LoomTrack <office@test.example>")
    sent = []

    def fake_smtp(cfg, to, subject, body, **kw):
        sent.append((to, subject, kw.get("attachment")))

    asyncio.run(delivery.deliver_pending(db, smtp=fake_smtp, whatsapp=None))
    mail = [m for m in sent if m[1].startswith("Weekly order status")]
    assert mail, sent
    name, data, mime = mail[0][2]
    assert name.startswith("order-status-") and name.endswith(".xlsx") and data[:2] == b"PK" and "spreadsheetml" in mime
    cells = " ".join(str(c.value) for ws in load_workbook(io.BytesIO(data)) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "PO-B-1" in cells
    assert not any(po in cells for po in [r[0] for r in db.execute("SELECT po_no FROM orders WHERE buyer_id != 1")])
    # Ordinary messages are sent without an attachment.
    assert all(m[2] is None for m in sent if not m[1].startswith("Weekly order status"))


def test_the_weekly_email_can_be_switched_off_or_moved(env, monkeypatch):
    from loomtrack import config
    monkeypatch.setenv("LOOMTRACK_WEEKLY", "off")
    assert config.weekly_schedule() is None and not weekly.is_due(MONDAY)
    monkeypatch.delenv("LOOMTRACK_WEEKLY")
    monkeypatch.setenv("LOOMTRACK_WEEKLY_DAY", "Fri")
    monkeypatch.setenv("LOOMTRACK_WEEKLY_HOUR", "17")
    assert config.weekly_schedule() == (4, 17) and weekly.is_due(datetime(2026, 11, 13, 17, 30)) and not weekly.is_due(MONDAY)
