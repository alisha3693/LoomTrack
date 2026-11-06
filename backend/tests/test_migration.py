"""v0 -> v1: step names move to plan_steps, order_id copies leave daily_updates and photos."""

import sqlite3

import pytest

from loomtrack.db import SCHEMA_VERSION, open_db

V0_TABLES = """
CREATE TABLE buyers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT, link_token TEXT NOT NULL UNIQUE, link_active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE units (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, process TEXT);
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, login TEXT NOT NULL UNIQUE, secret_hash TEXT NOT NULL, unit_id INTEGER REFERENCES units(id), lang TEXT NOT NULL DEFAULT 'en');
CREATE TABLE orders (id INTEGER PRIMARY KEY, po_no TEXT NOT NULL UNIQUE, buyer_id INTEGER NOT NULL REFERENCES buyers(id), style TEXT NOT NULL, colour TEXT NOT NULL,
  qty_total INTEGER NOT NULL, ex_factory TEXT NOT NULL, unit_id INTEGER NOT NULL REFERENCES units(id), template_key TEXT NOT NULL, merchandiser_id INTEGER REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'active', status TEXT, projected_ex_factory TEXT, status_computed_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE milestones (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE, seq INTEGER NOT NULL, code TEXT NOT NULL,
  name_en TEXT NOT NULL, name_ta TEXT NOT NULL, kind TEXT NOT NULL, process TEXT, planned_start TEXT, planned_date TEXT NOT NULL, actual_date TEXT,
  unit_id INTEGER REFERENCES units(id), UNIQUE (order_id, code));
CREATE TABLE daily_updates (id TEXT PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), milestone_id INTEGER NOT NULL REFERENCES milestones(id),
  user_id INTEGER NOT NULL REFERENCES users(id), work_date TEXT NOT NULL, qty INTEGER NOT NULL, note_text TEXT, note_source TEXT, audio_path TEXT,
  created_at_client TEXT, received_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX ix_updates_ms ON daily_updates (milestone_id, work_date);
CREATE TABLE photos (id INTEGER PRIMARY KEY, update_id TEXT REFERENCES daily_updates(id), order_id INTEGER NOT NULL REFERENCES orders(id), path TEXT NOT NULL,
  mime TEXT NOT NULL, buyer_visible INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE issue_reasons (update_id TEXT PRIMARY KEY REFERENCES daily_updates(id), ai_category TEXT, final_category TEXT);

INSERT INTO buyers VALUES (1, 'B', 'UK', 'tok', 1);
INSERT INTO units VALUES (1, 'Unit 1', 'own', NULL);
INSERT INTO users VALUES (1, 'S', 'supervisor', '9000000001', 'x', 1, 'ta');
INSERT INTO orders (id, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1, 'PO-1', 1, 'Tee', 'Navy', 1000, '2026-11-20', 1, 'basic');
INSERT INTO orders (id, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (2, 'PO-2', 1, 'Polo', 'White', 500, '2026-11-12', 1, 'basic');
INSERT INTO milestones VALUES (10, 1, 1, 'CUT', 'Cutting', 'x', 'stage', 'cutting', '2026-10-30', '2026-11-05', NULL, 1);
INSERT INTO milestones VALUES (11, 2, 1, 'CUT', 'Cutting', 'x', 'stage', 'cutting', '2026-10-25', '2026-11-01', NULL, 1);
INSERT INTO daily_updates (id, order_id, milestone_id, user_id, work_date, qty, note_text) VALUES ('u1', 1, 10, 1, '2026-11-02', 300, 'machine broke');
INSERT INTO daily_updates (id, order_id, milestone_id, user_id, work_date, qty) VALUES ('u2', 2, 11, 1, '2026-11-02', 120);
INSERT INTO photos (id, update_id, order_id, path, mime) VALUES (5, 'u1', 1, 'a.jpg', 'image/jpeg');
INSERT INTO issue_reasons VALUES ('u1', 'MACHINE_BREAKDOWN', 'MACHINE_BREAKDOWN');
"""


@pytest.fixture
def v0_file(tmp_path):
    f = tmp_path / "old.db"
    con = sqlite3.connect(f)
    con.executescript(V0_TABLES)
    con.commit()
    con.close()
    return f


def test_v0_database_is_migrated_without_losing_data(v0_file):
    db = open_db(str(v0_file))
    cols = lambda t: {r["name"] for r in db.execute(f"PRAGMA table_info({t})")}
    assert not cols("milestones") & {"name_en", "name_ta", "kind", "process"}
    assert "order_id" not in cols("daily_updates") and "order_id" not in cols("photos")
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    # Each update still belongs to the same order, now reached through its milestone.
    owner = {r["id"]: r["order_id"] for r in db.execute("SELECT d.id, m.order_id FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id")}
    assert owner == {"u1": 1, "u2": 2}
    assert db.execute("SELECT update_id FROM photos").fetchone()["update_id"] == "u1"
    assert db.execute("SELECT final_category FROM issue_reasons").fetchone()[0] == "MACHINE_BREAKDOWN"

    # The name now lives once in plan_steps, taken from the templates.
    step = db.execute("SELECT name_en, kind, process FROM plan_steps WHERE code = 'CUT'").fetchone()
    assert (step["name_en"], step["kind"], step["process"]) == ("Cutting", "stage", "cutting")
    assert (v0_file.parent / "old.db.v0.bak").exists()
    # The same open carried it on to v2: every order got our own number.
    nos = [r[0] for r in db.execute("SELECT order_no FROM orders ORDER BY id")]
    assert len(set(nos)) == 2 and all(n.startswith("LT-") and n.endswith(("-0001", "-0002")) for n in nos)


def test_migration_runs_once_and_new_databases_start_at_v1(v0_file, tmp_path):
    open_db(str(v0_file)).close()
    again = open_db(str(v0_file))  # second open must not touch anything
    assert again.execute("SELECT COUNT(*) FROM daily_updates").fetchone()[0] == 2

    fresh = open_db(str(tmp_path / "fresh.db"))
    assert fresh.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert not (tmp_path / "fresh.db.v0.bak").exists()


def test_plan_step_labels_follow_the_templates(tmp_path):
    db = open_db(str(tmp_path / "labels.db"))
    db.execute("UPDATE plan_steps SET name_ta = 'typo' WHERE code = 'CUT'")
    open_db(str(tmp_path / "labels.db"))  # startup sync restores the template's label
    assert db.execute("SELECT name_ta FROM plan_steps WHERE code = 'CUT'").fetchone()[0] != "typo"


def test_milestone_needs_a_known_step(tmp_path):
    db = open_db(str(tmp_path / "fk.db"))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    db.execute("INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1,'LT-1','P',1,'s','c',10,'2026-11-20',1,'basic')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO milestones (order_id, seq, code, planned_date) VALUES (1, 1, 'NOPE', '2026-11-01')")


V1_TABLES = """
CREATE TABLE buyers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT, link_token TEXT NOT NULL UNIQUE, link_active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE units (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, process TEXT);
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, login TEXT NOT NULL UNIQUE, secret_hash TEXT NOT NULL, unit_id INTEGER REFERENCES units(id), lang TEXT NOT NULL DEFAULT 'en');
CREATE TABLE orders (id INTEGER PRIMARY KEY, po_no TEXT NOT NULL UNIQUE, buyer_id INTEGER NOT NULL REFERENCES buyers(id), style TEXT NOT NULL, colour TEXT NOT NULL,
  qty_total INTEGER NOT NULL, ex_factory TEXT NOT NULL, unit_id INTEGER NOT NULL REFERENCES units(id), template_key TEXT NOT NULL, merchandiser_id INTEGER REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'active', status TEXT, projected_ex_factory TEXT, status_computed_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
PRAGMA user_version = 1;
INSERT INTO buyers VALUES (1, 'B', 'UK', 'tok', 1);
INSERT INTO units VALUES (1, 'Unit 1', 'own', NULL);
INSERT INTO orders (id, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key, created_at) VALUES (1, 'PO-A', 1, 'Tee', 'Navy', 10, '2026-11-20', 1, 'basic', '2025-12-30 10:00:00');
INSERT INTO orders (id, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key, created_at) VALUES (2, 'PO-B', 1, 'Polo', 'White', 10, '2026-11-12', 1, 'basic', '2026-01-05 10:00:00');
INSERT INTO orders (id, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key, created_at) VALUES (3, 'PO-C', 1, 'Vest', 'Black', 10, '2026-11-25', 1, 'basic', '2026-02-05 10:00:00');
"""


def test_v1_orders_get_numbers_by_year_and_keep_their_ids(tmp_path):
    f = tmp_path / "v1.db"
    con = sqlite3.connect(f)
    con.executescript(V1_TABLES)
    con.commit()
    con.close()
    db = open_db(str(f))
    got = {r["id"]: r["order_no"] for r in db.execute("SELECT id, order_no FROM orders")}
    assert got == {1: "LT-2025-0001", 2: "LT-2026-0001", 3: "LT-2026-0002"}
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (tmp_path / "v1.db.v1.bak").exists()
    # The PO number is now unique per buyer, not globally.
    db.execute("INSERT INTO buyers VALUES (2, 'C', 'DE', 'tok2', 1)")
    cols = "(order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key)"
    db.execute(f"INSERT INTO orders {cols} VALUES ('LT-2026-0003', 'PO-A', 2, 's', 'c', 1, '2026-11-20', 1, 'basic')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(f"INSERT INTO orders {cols} VALUES ('LT-2026-0004', 'PO-A', 1, 's', 'c', 1, '2026-11-20', 1, 'basic')")


def test_colour_hex_must_be_a_six_digit_hex_code(tmp_path):
    db = open_db(str(tmp_path / "hex.db"))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    cols = "(order_no, po_no, buyer_id, style, colour, colour_hex, qty_total, ex_factory, unit_id, template_key)"
    db.execute(f"INSERT INTO orders {cols} VALUES ('LT-1', 'P1', 1, 's', 'c', '#1F2A44', 1, '2026-11-20', 1, 'basic')")
    for bad in ("1F2A44", "#1f2a44", "#12345", "navy"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"INSERT INTO orders {cols} VALUES ('LT-2', 'P2', 1, 's', 'c', ?, 1, '2026-11-20', 1, 'basic')", (bad,))


def test_v2_database_gets_the_template_tables_and_keeps_its_orders(tmp_path):
    """A v2 database has no templates tables and no plan_steps.builtin column."""
    f = tmp_path / "v2.db"
    db = open_db(str(f))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    db.execute("INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1,'LT-2026-0001','P',1,'s','c',10,'2026-11-20',1,'basic')")
    db.execute("DROP TABLE template_steps")
    db.execute("DROP TABLE templates")
    db.execute("ALTER TABLE plan_steps DROP COLUMN builtin")
    db.execute("PRAGMA user_version = 2")
    db.close()

    db = open_db(str(f))
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert {r["key"] for r in db.execute("SELECT key FROM templates")} == {"basic", "printed", "washed"}
    assert db.execute("SELECT builtin FROM plan_steps WHERE code = 'CUT'").fetchone()[0] == 1
    assert db.execute("SELECT po_no FROM orders").fetchone()[0] == "P"  # the order is untouched


def test_v5_database_gets_buyer_accounts_and_keeps_its_users_and_sessions(tmp_path):
    """Before buyer accounts the users table had no buyer role, buyer_id or must_change_secret."""
    f = tmp_path / "v5.db"
    db = open_db(str(f))
    db.execute("PRAGMA foreign_keys = OFF")
    db.executescript(
        "DROP TABLE users;"
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('merchandiser', 'supervisor')),"
        " login TEXT NOT NULL UNIQUE, secret_hash TEXT NOT NULL, unit_id INTEGER REFERENCES units(id), lang TEXT NOT NULL DEFAULT 'en');"
        "INSERT INTO users VALUES (1, 'Priya', 'merchandiser', 'p@x.in', 'h', NULL, 'en');"
        "INSERT INTO sessions VALUES ('tok', 1, '2999-01-01T00:00:00+00:00');"
        "PRAGMA user_version = 5;"
    )
    db.close()

    db = open_db(str(f))
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert tuple(db.execute("SELECT name, buyer_id, must_change_secret FROM users").fetchone()) == ("Priya", None, 0)
    assert db.execute("SELECT user_id FROM sessions WHERE token = 'tok'").fetchone()[0] == 1
    assert (tmp_path / "v5.db.v5.bak").exists()
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO users (name, role, login, secret_hash, buyer_id) VALUES ('Hannah', 'buyer', 'h@b.example', 'h', 1)")  # the new role is accepted


def test_v6_database_gets_fabric_materials_and_unit_capacity_and_keeps_its_orders(tmp_path):
    """Before this version orders and requests had no fabric columns, units no capacity, and there was no materials table."""
    f = tmp_path / "v6.db"
    db = open_db(str(f))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    db.execute("INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1,'LT-2026-0001','P',1,'s','c',10,'2026-11-20',1,'basic')")
    db.execute("DROP TABLE order_materials")
    for table, cols in (("orders", ("fabric_type", "fabric_composition", "fabric_gsm", "fabric_note")),
                        ("order_requests", ("fabric_type", "fabric_composition", "fabric_gsm", "fabric_note")), ("units", ("daily_capacity",))):
        for col in cols:
            db.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
    db.execute("PRAGMA user_version = 6")
    db.close()

    db = open_db(str(f))
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.execute("SELECT po_no, fabric_type, fabric_gsm FROM orders").fetchone()[:] == ("P", None, None)   # the order is untouched
    assert db.execute("SELECT daily_capacity FROM units").fetchone()[0] is None
    assert db.execute("SELECT COUNT(*) FROM order_materials").fetchone()[0] == 0
    db.execute("UPDATE orders SET fabric_gsm = 180")
    for bad in (49, 801):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE orders SET fabric_gsm = ?", (bad,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE units SET daily_capacity = 0")
    with pytest.raises(sqlite3.IntegrityError):                                    # a line needs a step or a date, and a received one needs its date
        db.execute("INSERT INTO order_materials (order_id, kind, name) VALUES (1, 'trim', 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO order_materials (order_id, kind, name, needed_by, status) VALUES (1, 'trim', 'x', '2026-11-01', 'received')")


def test_v7_database_gets_order_messages_and_keeps_its_orders(tmp_path):
    """Before this version there was no conversation about an existing order."""
    f = tmp_path / "v7.db"
    db = open_db(str(f))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    db.execute("INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1,'LT-2026-0001','P',1,'s','c',10,'2026-11-20',1,'basic')")
    db.execute("DROP TABLE order_messages")
    db.execute("PRAGMA user_version = 7")
    db.close()

    db = open_db(str(f))
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.execute("SELECT po_no FROM orders").fetchone()[0] == "P"                     # the order is untouched
    db.execute("INSERT INTO order_messages (order_id, author, body) VALUES (1, 'buyer', 'hello')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE order_messages SET body = 'edited'")                            # append-only
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM order_messages")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO order_messages (order_id, author, body) VALUES (1, 'stranger', 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO order_messages (order_id, author, body) VALUES (1, 'buyer', '')")


def test_v8_database_gets_approvals_read_marks_and_view_only_accounts_and_keeps_its_data(tmp_path):
    """Before this version there were no approvals, no read marks, and every buyer account could make changes."""
    f = tmp_path / "v8.db"
    db = open_db(str(f))
    db.execute("INSERT INTO buyers (id, name, link_token) VALUES (1, 'B', 't')")
    db.execute("INSERT INTO units (id, name, kind) VALUES (1, 'U', 'own')")
    db.execute("INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key) VALUES (1,'LT-2026-0001','P',1,'s','c',10,'2026-11-20',1,'basic')")
    db.execute("INSERT INTO users (name, role, login, secret_hash, buyer_id) VALUES ('Hannah', 'buyer', 'h@b.example', 'x', 1)")
    db.execute("INSERT INTO warnings (order_id, level, projected_ex_factory, slack_days, summary, state) VALUES (1, 'red', '2026-12-01', -3, 'x', 'confirmed')")
    for table in ("approval_events", "approvals", "thread_reads"):
        db.execute(f"DROP TABLE {table}")
    for table, column in (("users", "can_write"), ("warnings", "buyer_seen_at"), ("warnings", "buyer_ack_at")):
        db.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    db.execute("PRAGMA user_version = 8")
    db.close()

    db = open_db(str(f))
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.execute("SELECT po_no FROM orders").fetchone()[0] == "P"
    assert db.execute("SELECT can_write FROM users").fetchone()[0] == 1                     # existing accounts keep full access
    assert db.execute("SELECT buyer_seen_at, buyer_ack_at FROM warnings").fetchone()[:] == (None, None)
    db.execute("INSERT INTO approvals (order_id, kind, title) VALUES (1, 'fit_sample', 'Fit sample')")
    db.execute("INSERT INTO approval_events (approval_id, actor, action) VALUES (1, 'merchandiser', 'requested')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE approval_events SET note = 'edited'")                            # append-only
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO approvals (order_id, kind, title) VALUES (1, 'nonsense', 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO thread_reads (kind, ref_id, reader) VALUES ('order', 1, 'stranger')")
