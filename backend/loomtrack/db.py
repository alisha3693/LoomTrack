"""SQLite schema and connection. One connection, used from the event loop thread."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .domain.tna import BUILTIN_TEMPLATES

SCHEMA = """
CREATE TABLE IF NOT EXISTS buyers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT,
  link_token TEXT NOT NULL UNIQUE,
  link_active INTEGER NOT NULL DEFAULT 1,
  notify_email INTEGER NOT NULL DEFAULT 1,       -- send the buyer's people email about their orders
  whatsapp_number TEXT,                          -- E.164, digits with a leading +
  whatsapp_opt_in INTEGER NOT NULL DEFAULT 0,    -- 1 only once the buyer agreed to WhatsApp messages
  whatsapp_opt_in_at TEXT,
  whatsapp_opt_in_by INTEGER REFERENCES users(id)  -- who recorded the consent (NULL = the buyer, by message)
);

CREATE TABLE IF NOT EXISTS units (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('own', 'subcontract')),
  process TEXT,                     -- for subcontractors: 'printing' | 'washing'
  daily_capacity INTEGER CHECK (daily_capacity IS NULL OR daily_capacity > 0)  -- pieces a day it can stitch; own units
);

CREATE TABLE IF NOT EXISTS unit_capacity (  -- pieces a day an own unit can do in a stage other than stitching (stitching is units.daily_capacity)
  unit_id INTEGER NOT NULL REFERENCES units(id),
  process TEXT NOT NULL,
  daily_capacity INTEGER NOT NULL CHECK (daily_capacity > 0),
  PRIMARY KEY (unit_id, process)
);

CREATE TABLE IF NOT EXISTS app_clock (  -- one row: a date a tester has set by hand (test machines only; see services/clock.py)
  id INTEGER PRIMARY KEY CHECK (id = 1),
  test_date TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('merchandiser', 'supervisor', 'buyer')),
  login TEXT NOT NULL UNIQUE,       -- email for office and buyers, phone for supervisors
  secret_hash TEXT NOT NULL,
  unit_id INTEGER REFERENCES units(id),
  lang TEXT NOT NULL DEFAULT 'en',
  buyer_id INTEGER REFERENCES buyers(id),          -- set for buyer accounts, and only for them
  must_change_secret INTEGER NOT NULL DEFAULT 0,   -- 1 while the password is one the office chose
  can_write INTEGER NOT NULL DEFAULT 1,            -- 0 = a buyer account that can look but not send, approve or change
  CHECK ((role = 'buyer') = (buyer_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  order_no TEXT NOT NULL UNIQUE,    -- our own number, LT-2026-0001; the PO number below is the buyer's
  po_no TEXT NOT NULL,
  buyer_id INTEGER NOT NULL REFERENCES buyers(id),
  style TEXT NOT NULL,
  colour TEXT NOT NULL,             -- colour name as the buyer calls it
  colour_pantone TEXT,              -- e.g. 19-4024 TCX; the real colour reference
  colour_hex TEXT CHECK (colour_hex IS NULL OR colour_hex GLOB '#[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]'),
  fabric_type TEXT,                 -- e.g. single jersey, rib 1x1, fleece
  fabric_composition TEXT,          -- e.g. 95% cotton, 5% elastane
  fabric_gsm INTEGER CHECK (fabric_gsm IS NULL OR fabric_gsm BETWEEN 50 AND 800),
  fabric_note TEXT,                 -- mill, buyer's fabric code, finish
  qty_total INTEGER NOT NULL CHECK (qty_total > 0),
  ex_factory TEXT NOT NULL,
  unit_id INTEGER NOT NULL REFERENCES units(id),
  template_key TEXT NOT NULL,
  merchandiser_id INTEGER REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'shipped', 'cancelled')),
  status TEXT,                      -- cached: green | amber | red
  projected_ex_factory TEXT,        -- cached
  status_computed_at TEXT,
  cancel_reason TEXT,               -- why the merchandiser cancelled the order; the buyer is shown it
  cancelled_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (buyer_id, po_no)          -- two buyers may use the same PO number
);

CREATE TABLE IF NOT EXISTS order_sizes (
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  size TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (order_id, size)
);

-- The steps a plan is made of. A step's name, kind and process belong to the step,
-- not to any one order, so they live here once (synced from domain/tna.py at startup).
CREATE TABLE IF NOT EXISTS plan_steps (
  code TEXT PRIMARY KEY,
  name_en TEXT NOT NULL,
  name_ta TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('milestone', 'stage')),
  process TEXT,                     -- stages only
  builtin INTEGER NOT NULL DEFAULT 0   -- 1 = defined in domain/tna.py, labels not editable in the app
);

-- A saved plan layout a merchandiser picks when creating an order. An order copies the
-- dates at creation, so editing or retiring a template never changes an existing order.
CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,         -- stored on orders.template_key
  name TEXT NOT NULL,
  builtin INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_templates_name ON templates (lower(name)) WHERE active = 1;

CREATE TABLE IF NOT EXISTS template_steps (
  template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  code TEXT NOT NULL REFERENCES plan_steps(code),
  end_offset INTEGER NOT NULL CHECK (end_offset BETWEEN 0 AND 365),   -- calendar days before ex-factory
  start_offset INTEGER CHECK (start_offset IS NULL OR start_offset BETWEEN 0 AND 365),  -- stages only
  after_code TEXT REFERENCES plan_steps(code),   -- stages only: starts the day after this step ends; start_offset follows it
  PRIMARY KEY (template_id, code),
  UNIQUE (template_id, seq)
);

-- One order's TNA plan: dated milestones and production stages, each pointing at a step.
CREATE TABLE IF NOT EXISTS milestones (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  code TEXT NOT NULL REFERENCES plan_steps(code),
  planned_start TEXT,
  planned_date TEXT NOT NULL,
  actual_date TEXT,
  unit_id INTEGER REFERENCES units(id),
  UNIQUE (order_id, code)
);

-- One row per supervisor submission. id is generated on the phone so a
-- retried upload from the offline queue is idempotent.
CREATE TABLE IF NOT EXISTS daily_updates (
  id TEXT PRIMARY KEY,
  milestone_id INTEGER NOT NULL REFERENCES milestones(id),   -- the order is milestones.order_id
  user_id INTEGER NOT NULL REFERENCES users(id),
  work_date TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  note_text TEXT,
  note_source TEXT CHECK (note_source IN ('text', 'voice')),
  audio_path TEXT,
  created_at_client TEXT,
  received_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_updates_ms ON daily_updates (milestone_id, work_date);

CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY,
  update_id TEXT NOT NULL REFERENCES daily_updates(id),
  path TEXT NOT NULL,
  mime TEXT NOT NULL,
  buyer_visible INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- AI output and the human decision are kept apart so a wrong guess is visible.
CREATE TABLE IF NOT EXISTS issue_reasons (
  update_id TEXT PRIMARY KEY REFERENCES daily_updates(id),
  ai_category TEXT,
  ai_translation TEXT,
  ai_confidence REAL,
  ai_source TEXT,                   -- 'indictrans2' | 'keywords'
  ai_error TEXT,
  final_category TEXT,
  changed_by INTEGER REFERENCES users(id),
  changed_at TEXT,
  classified_at TEXT
);

CREATE TABLE IF NOT EXISTS warnings (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  level TEXT NOT NULL CHECK (level IN ('amber', 'red')),
  projected_ex_factory TEXT NOT NULL,
  slack_days INTEGER NOT NULL,
  summary TEXT NOT NULL,            -- internal maths
  buyer_message TEXT,               -- what the buyer sees once confirmed
  state TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending', 'confirmed', 'dismissed', 'superseded', 'resolved')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  decided_by INTEGER REFERENCES users(id),
  decided_at TEXT,
  buyer_seen_at TEXT,               -- when the buyer first opened the notice
  buyer_ack_at TEXT                 -- when the buyer acknowledged it
);

-- Compliance trail: every planned-date change, append-only.
CREATE TABLE IF NOT EXISTS date_changes (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  milestone_id INTEGER REFERENCES milestones(id),
  field TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  reason TEXT NOT NULL,
  changed_by INTEGER REFERENCES users(id),
  changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS date_changes_no_update BEFORE UPDATE ON date_changes
BEGIN SELECT RAISE(ABORT, 'date_changes is append-only'); END;
CREATE TRIGGER IF NOT EXISTS date_changes_no_delete BEFORE DELETE ON date_changes
BEGIN SELECT RAISE(ABORT, 'date_changes is append-only'); END;

-- A buyer's request: a new order they want us to make, or (later) a change to an order. It is
-- a conversation: whose turn it is is the status. submitted = ours, query/countered = the buyer's.
CREATE TABLE IF NOT EXISTS order_requests (
  id INTEGER PRIMARY KEY,
  request_no TEXT NOT NULL UNIQUE,                 -- RQ-2026-0001
  kind TEXT NOT NULL DEFAULT 'new_order' CHECK (kind IN ('new_order', 'amendment')),
  buyer_id INTEGER NOT NULL REFERENCES buyers(id),
  order_id INTEGER REFERENCES orders(id),          -- amendment: the order; new order: set when accepted
  po_no TEXT NOT NULL,                             -- the buyer's PO number
  style TEXT NOT NULL,
  description TEXT,
  colour TEXT NOT NULL,
  colour_pantone TEXT,
  colour_hex TEXT CHECK (colour_hex IS NULL OR colour_hex GLOB '#[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]'),
  fabric_type TEXT,                 -- e.g. single jersey, rib 1x1, fleece
  fabric_composition TEXT,          -- e.g. 95% cotton, 5% elastane
  fabric_gsm INTEGER CHECK (fabric_gsm IS NULL OR fabric_gsm BETWEEN 50 AND 800),
  fabric_note TEXT,                 -- mill, buyer's fabric code, finish
  ex_factory TEXT NOT NULL,                        -- the date the buyer wants, or has agreed to
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted', 'query', 'countered', 'accepted', 'declined', 'withdrawn')),
  decided_by INTEGER REFERENCES users(id),
  decided_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_requests_buyer ON order_requests (buyer_id, status);

CREATE TABLE IF NOT EXISTS request_sizes (
  request_id INTEGER NOT NULL REFERENCES order_requests(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  size TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (request_id, size)
);

-- The conversation and every status change, append-only like date_changes.
CREATE TABLE IF NOT EXISTS request_messages (
  id INTEGER PRIMARY KEY,
  request_id INTEGER NOT NULL REFERENCES order_requests(id),
  author TEXT NOT NULL CHECK (author IN ('buyer', 'merchandiser')),
  user_id INTEGER REFERENCES users(id),
  event TEXT NOT NULL CHECK (event IN ('submitted', 'message', 'query', 'counter', 'agreed', 'accepted', 'declined', 'withdrawn')),
  body TEXT,
  proposed_ex_factory TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_request_messages ON request_messages (request_id, id);
CREATE TRIGGER IF NOT EXISTS request_messages_no_update BEFORE UPDATE ON request_messages
BEGIN SELECT RAISE(ABORT, 'request_messages is append-only'); END;
CREATE TRIGGER IF NOT EXISTS request_messages_no_delete BEFORE DELETE ON request_messages
BEGIN SELECT RAISE(ABORT, 'request_messages is append-only'); END;

-- Designs, patterns, print artwork and fabric references. A file belongs to a request, to an order,
-- or to both (a request's files follow it onto the order it becomes). The buyer's own uploads are
-- always visible to that buyer; ours are private unless buyer_visible is set. supervisor_visible
-- decides what the floor can open.
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY,
  request_id INTEGER REFERENCES order_requests(id),
  order_id INTEGER REFERENCES orders(id),
  kind TEXT NOT NULL CHECK (kind IN ('design', 'pattern', 'print', 'fabric', 'other')),
  filename TEXT NOT NULL,            -- for display only, never used as a path
  mime TEXT NOT NULL,                -- from the file's own bytes, not from the browser
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  path TEXT NOT NULL,
  uploaded_by TEXT NOT NULL CHECK (uploaded_by IN ('buyer', 'merchandiser')),
  user_id INTEGER REFERENCES users(id),
  buyer_visible INTEGER NOT NULL DEFAULT 0,
  supervisor_visible INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (request_id IS NOT NULL OR order_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_attachments_request ON attachments (request_id);
CREATE INDEX IF NOT EXISTS ix_attachments_order ON attachments (order_id);

-- What an order needs before it can be made: fabric, trims, packing. When it is needed comes from
-- the plan step that uses it (needed_for), so it follows the plan if a date moves; needed_by is only
-- for something that belongs to no step. Nothing here changes the delay projection.
CREATE TABLE IF NOT EXISTS order_materials (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  kind TEXT NOT NULL CHECK (kind IN ('fabric', 'trim', 'packing')),
  name TEXT NOT NULL,
  supplier TEXT,
  supplied_by TEXT NOT NULL DEFAULT 'us' CHECK (supplied_by IN ('us', 'buyer')),
  qty REAL CHECK (qty IS NULL OR qty > 0),
  unit TEXT,                                     -- kg, m, pcs, rolls ...
  status TEXT NOT NULL DEFAULT 'not_ordered' CHECK (status IN ('not_ordered', 'ordered', 'received')),
  ordered_date TEXT,
  expected_date TEXT,
  received_date TEXT,
  needed_for TEXT REFERENCES plan_steps(code),
  needed_by TEXT,
  note TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_by INTEGER REFERENCES users(id),
  CHECK (status != 'received' OR received_date IS NOT NULL),
  CHECK (needed_for IS NOT NULL OR needed_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_materials_order ON order_materials (order_id);

-- Messages between the buyer and the merchandiser about an order that exists (a request has its own
-- conversation in request_messages). Append-only.
CREATE TABLE IF NOT EXISTS order_messages (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  author TEXT NOT NULL CHECK (author IN ('buyer', 'merchandiser')),
  user_id INTEGER REFERENCES users(id),
  body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_order_messages ON order_messages (order_id, id);
CREATE TRIGGER IF NOT EXISTS order_messages_no_update BEFORE UPDATE ON order_messages
BEGIN SELECT RAISE(ABORT, 'order_messages is append-only'); END;
CREATE TRIGGER IF NOT EXISTS order_messages_no_delete BEFORE DELETE ON order_messages
BEGIN SELECT RAISE(ABORT, 'order_messages is append-only'); END;

-- How far each side has read a conversation, so both can tell "seen" from "not seen". last_id is the
-- newest message id of that conversation the reader has opened.
CREATE TABLE IF NOT EXISTS thread_reads (
  kind TEXT NOT NULL CHECK (kind IN ('order', 'request')),
  ref_id INTEGER NOT NULL,
  reader TEXT NOT NULL CHECK (reader IN ('buyer', 'merchandiser')),
  last_id INTEGER NOT NULL DEFAULT 0,
  read_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (kind, ref_id, reader)
);

-- Something the buyer has to approve before work goes on: a fit or pre-production sample, a lab dip,
-- packaging. The decision is the buyer's; every step is in approval_events and cannot be edited.
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  kind TEXT NOT NULL CHECK (kind IN ('fit_sample', 'pp_sample', 'lab_dip', 'packaging', 'other')),
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
  note TEXT,
  milestone_code TEXT REFERENCES plan_steps(code),   -- the plan step this approval completes
  status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'approved', 'changes', 'withdrawn')),
  requested_at TEXT NOT NULL DEFAULT (datetime('now')),
  decided_at TEXT,
  buyer_seen_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_approvals_order ON approvals (order_id);
CREATE TABLE IF NOT EXISTS approval_events (
  id INTEGER PRIMARY KEY,
  approval_id INTEGER NOT NULL REFERENCES approvals(id),
  actor TEXT NOT NULL CHECK (actor IN ('buyer', 'merchandiser')),
  user_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL CHECK (action IN ('requested', 'resubmitted', 'approved', 'changes', 'withdrawn')),
  note TEXT CHECK (note IS NULL OR length(note) <= 2000),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_approval_events ON approval_events (approval_id, id);
CREATE TRIGGER IF NOT EXISTS approval_events_no_update BEFORE UPDATE ON approval_events
BEGIN SELECT RAISE(ABORT, 'approval_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS approval_events_no_delete BEFORE DELETE ON approval_events
BEGIN SELECT RAISE(ABORT, 'approval_events is append-only'); END;

-- Every email and WhatsApp message the app sends or would send: one row per recipient. 'logged' = no provider is
-- set up for the channel, so it is only recorded (the old mock behaviour); 'queued' waits for the sender.
-- How far each reader has looked down the notifications page (the newest outbox id they have seen).
CREATE TABLE IF NOT EXISTS feed_reads (
  reader TEXT NOT NULL CHECK (reader IN ('buyer', 'merchandiser')),
  ref_id INTEGER NOT NULL,         -- the buyer's id, or the merchandiser's user id
  last_id INTEGER NOT NULL DEFAULT 0,
  read_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (reader, ref_id)
);

CREATE TABLE IF NOT EXISTS outbox_messages (
  id INTEGER PRIMARY KEY,
  buyer_id INTEGER NOT NULL REFERENCES buyers(id),
  order_id INTEGER REFERENCES orders(id),
  channel TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  event TEXT,                                    -- see services/notify.py
  audience TEXT NOT NULL DEFAULT 'buyer' CHECK (audience IN ('buyer', 'office')),
  recipient TEXT,                                -- email address or WhatsApp number
  status TEXT NOT NULL DEFAULT 'logged' CHECK (status IN ('logged', 'queued', 'sent', 'delivered', 'read', 'failed', 'skipped')),
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  not_before TEXT,                               -- do not retry before this time (UTC)
  provider_id TEXT,                              -- WhatsApp message id, to match delivery reports
  template TEXT,                                 -- WhatsApp template name
  params TEXT,                                   -- WhatsApp template values, JSON list
  sent_at TEXT
);
"""


SCHEMA_VERSION = 15  # PRAGMA user_version; 0 = before plan_steps, 1 = before order_no/colour, 2 = before templates, 3 = before order requests, 4 = before attachments, 5 = before buyer accounts, 6 = before fabric, materials and unit capacity, 7 = before order messages, 8 = before approvals, read tracking and view-only accounts, 9 = before email/WhatsApp delivery, 10 = before a stage can start after another step, 11 = before an order can be cancelled with a reason, 12 = before the notifications page, 13 = before capacity for every own stage, 14 = before the test date


def _is_v0(db: sqlite3.Connection) -> bool:
    return "name_en" in {r["name"] for r in db.execute("PRAGMA table_info(milestones)")}


def _migrate_v0(db: sqlite3.Connection, file: str) -> None:
    """Normalise a v0 database in place: step names move to plan_steps, and the
    order_id copies on daily_updates and photos go (the order is reached through the milestone).

    Tables are renamed aside, recreated from SCHEMA, refilled, then the old ones dropped, all in
    one transaction. legacy_alter_table keeps the renames from rewriting other tables' foreign keys.
    """
    if db.execute("SELECT 1 FROM photos WHERE update_id IS NULL").fetchone():
        raise RuntimeError("Cannot migrate: some photos are not attached to an update")
    if file != ":memory:":
        backup = sqlite3.connect(f"{file}.v0.bak")
        db.backup(backup)
        backup.close()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    try:
        db.executescript(
            f"""BEGIN;
            DROP INDEX IF EXISTS ix_updates_ms;
            ALTER TABLE photos RENAME TO photos_old;
            ALTER TABLE daily_updates RENAME TO daily_updates_old;
            ALTER TABLE milestones RENAME TO milestones_old;
            {SCHEMA}
            INSERT INTO plan_steps (code, name_en, name_ta, kind, process)
              SELECT code, name_en, name_ta, kind, process FROM milestones_old GROUP BY code;
            INSERT INTO milestones (id, order_id, seq, code, planned_start, planned_date, actual_date, unit_id)
              SELECT id, order_id, seq, code, planned_start, planned_date, actual_date, unit_id FROM milestones_old;
            INSERT INTO daily_updates (id, milestone_id, user_id, work_date, qty, note_text, note_source, audio_path, created_at_client, received_at)
              SELECT id, milestone_id, user_id, work_date, qty, note_text, note_source, audio_path, created_at_client, received_at FROM daily_updates_old;
            INSERT INTO photos (id, update_id, path, mime, buyer_visible, created_at)
              SELECT id, update_id, path, mime, buyer_visible, created_at FROM photos_old;
            DROP TABLE photos_old;
            DROP TABLE daily_updates_old;
            DROP TABLE milestones_old;
            PRAGMA user_version = 1;
            COMMIT;"""
        )
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.execute("PRAGMA legacy_alter_table = OFF")
        db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError(f"Migration left broken references; the pre-migration copy is {file}.v0.bak")


def _is_v1(db: sqlite3.Connection) -> bool:
    cols = {r["name"] for r in db.execute("PRAGMA table_info(orders)")}
    return bool(cols) and "order_no" not in cols


def _migrate_v1(db: sqlite3.Connection, file: str) -> None:
    """Add orders.order_no (backfilled LT-<year>-<n> in creation order), the colour fields, and
    make the PO number unique per buyer instead of globally. Same rename-aside approach as v0."""
    if file != ":memory:":
        backup = sqlite3.connect(f"{file}.v1.bak")
        db.backup(backup)
        backup.close()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    try:
        db.executescript(
            f"""BEGIN;
            ALTER TABLE orders RENAME TO orders_old;
            {SCHEMA}
            INSERT INTO orders (id, order_no, po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key,
                                merchandiser_id, state, status, projected_ex_factory, status_computed_at, created_at)
              SELECT id,
                     'LT-' || strftime('%Y', created_at) || '-' ||
                       printf('%04d', ROW_NUMBER() OVER (PARTITION BY strftime('%Y', created_at) ORDER BY id)),
                     po_no, buyer_id, style, colour, qty_total, ex_factory, unit_id, template_key,
                     merchandiser_id, state, status, projected_ex_factory, status_computed_at, created_at
              FROM orders_old;
            DROP TABLE orders_old;
            PRAGMA user_version = 2;
            COMMIT;"""
        )
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.execute("PRAGMA legacy_alter_table = OFF")
        db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError(f"Migration left broken references; the pre-migration copy is {file}.v1.bak")


def _is_v5(db: sqlite3.Connection) -> bool:
    cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
    return bool(cols) and "buyer_id" not in cols


def _migrate_v5(db: sqlite3.Connection, file: str) -> None:
    """Buyer accounts: users gets a 'buyer' role, buyer_id and must_change_secret. SQLite cannot
    change a CHECK in place, so users is renamed aside, recreated from SCHEMA and refilled."""
    if file != ":memory:":
        backup = sqlite3.connect(f"{file}.v5.bak")
        db.backup(backup)
        backup.close()
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("PRAGMA legacy_alter_table = ON")
    try:
        db.executescript(
            f"""BEGIN;
            ALTER TABLE users RENAME TO users_old;
            {SCHEMA}
            INSERT INTO users (id, name, role, login, secret_hash, unit_id, lang)
              SELECT id, name, role, login, secret_hash, unit_id, lang FROM users_old;
            DROP TABLE users_old;
            COMMIT;"""
        )
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.execute("PRAGMA legacy_alter_table = OFF")
        db.execute("PRAGMA foreign_keys = ON")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError(f"Migration left broken references; the pre-migration copy is {file}.v5.bak")


# v6 -> v7: columns added to tables that already exist (the new table comes from SCHEMA).
_V7_COLUMNS = {
    "orders": {
        "fabric_type": "TEXT", "fabric_composition": "TEXT", "fabric_note": "TEXT",
        "fabric_gsm": "INTEGER CHECK (fabric_gsm IS NULL OR fabric_gsm BETWEEN 50 AND 800)",
    },
    "order_requests": {
        "fabric_type": "TEXT", "fabric_composition": "TEXT", "fabric_note": "TEXT",
        "fabric_gsm": "INTEGER CHECK (fabric_gsm IS NULL OR fabric_gsm BETWEEN 50 AND 800)",
    },
    "units": {"daily_capacity": "INTEGER CHECK (daily_capacity IS NULL OR daily_capacity > 0)"},
}


def _add_v7_columns(db: sqlite3.Connection) -> None:
    for table, columns in _V7_COLUMNS.items():
        have = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():  # names and declarations are the constants above
            if name not in have:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


# v8 -> v9: columns added to tables that already exist (the new tables come from SCHEMA).
_V9_COLUMNS = {
    "users": {"can_write": "INTEGER NOT NULL DEFAULT 1"},
    "warnings": {"buyer_seen_at": "TEXT", "buyer_ack_at": "TEXT"},
}


def _add_columns(db: sqlite3.Connection, spec: dict[str, dict[str, str]]) -> None:
    for table, columns in spec.items():
        have = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():  # names and declarations are constants in this file
            if name not in have:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _add_v9_columns(db: sqlite3.Connection) -> None:
    _add_columns(db, _V9_COLUMNS)


# v9 -> v10: delivery of email and WhatsApp (the outbox grows from a log into a queue) and the buyer's consent.
_V10_COLUMNS = {
    "buyers": {
        "notify_email": "INTEGER NOT NULL DEFAULT 1",
        "whatsapp_number": "TEXT",
        "whatsapp_opt_in": "INTEGER NOT NULL DEFAULT 0",
        "whatsapp_opt_in_at": "TEXT",
        "whatsapp_opt_in_by": "INTEGER REFERENCES users(id)",
    },
    "outbox_messages": {
        "event": "TEXT",
        "audience": "TEXT NOT NULL DEFAULT 'buyer' CHECK (audience IN ('buyer', 'office'))",
        "recipient": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'logged' CHECK (status IN ('logged', 'queued', 'sent', 'delivered', 'read', 'failed', 'skipped'))",
        "error": "TEXT",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "not_before": "TEXT",
        "provider_id": "TEXT",
        "template": "TEXT",
        "params": "TEXT",
        "sent_at": "TEXT",
    },
}


_V11_COLUMNS = {"template_steps": {"after_code": "TEXT REFERENCES plan_steps(code)"}}


def _add_v11_columns(db: sqlite3.Connection) -> None:
    _add_columns(db, _V11_COLUMNS)


_V12_COLUMNS = {"orders": {"cancel_reason": "TEXT", "cancelled_at": "TEXT"}}


def _add_v12_columns(db: sqlite3.Connection) -> None:
    _add_columns(db, _V12_COLUMNS)


def _add_v10_columns(db: sqlite3.Connection) -> None:
    _add_columns(db, _V10_COLUMNS)
    db.execute("CREATE INDEX IF NOT EXISTS ix_outbox_queue ON outbox_messages (status, id)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_outbox_provider ON outbox_messages (provider_id)")


def _add_builtin_column(db: sqlite3.Connection) -> None:
    """v2 -> v3: plan_steps.builtin (the new tables come from SCHEMA)."""
    if "builtin" not in {r["name"] for r in db.execute("PRAGMA table_info(plan_steps)")}:
        db.execute("ALTER TABLE plan_steps ADD COLUMN builtin INTEGER NOT NULL DEFAULT 0")


def sync_plan_steps(db: sqlite3.Connection) -> None:
    """Make the built-in steps match domain/tna.py. Custom steps (builtin = 0) are left alone."""
    steps = {i.code: i for t in BUILTIN_TEMPLATES.values() for i in t.items}
    db.executemany(
        """INSERT INTO plan_steps (code, name_en, name_ta, kind, process, builtin) VALUES (?,?,?,?,?,1)
           ON CONFLICT(code) DO UPDATE SET name_en = excluded.name_en, name_ta = excluded.name_ta,
             kind = excluded.kind, process = excluded.process, builtin = 1""",
        [(i.code, i.name_en, i.name_ta, i.kind, i.process) for i in steps.values()],
    )


def sync_builtin_templates(db: sqlite3.Connection) -> None:
    """Keep the built-in templates in step with domain/tna.py. Merchandisers' own templates are never touched."""
    for t in BUILTIN_TEMPLATES.values():
        db.execute(
            """INSERT INTO templates (key, name, builtin) VALUES (?,?,1)
               ON CONFLICT(key) DO UPDATE SET name = excluded.name, builtin = 1""",
            (t.key, t.name),
        )
        tid = db.execute("SELECT id FROM templates WHERE key = ?", (t.key,)).fetchone()["id"]
        db.execute("DELETE FROM template_steps WHERE template_id = ?", (tid,))
        db.executemany(
            "INSERT INTO template_steps (template_id, seq, code, end_offset, start_offset, after_code) VALUES (?,?,?,?,?,?)",
            [(tid, n, i.code, i.end_offset, i.start_offset, i.after) for n, i in enumerate(t.items, start=1)],
        )


def open_db(file: str) -> sqlite3.Connection:
    if file != ":memory:":
        Path(file).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI handlers here are async and run on one thread; check_same_thread
    # is off only so test clients and startup code may share the connection.
    db = sqlite3.connect(file, check_same_thread=False, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA foreign_keys = ON")
    if _is_v0(db):
        _migrate_v0(db, file)
    if _is_v1(db):
        _migrate_v1(db, file)
    if _is_v5(db):
        _migrate_v5(db, file)
    db.executescript(SCHEMA)
    _add_builtin_column(db)
    _add_v7_columns(db)
    _add_v9_columns(db)
    _add_v10_columns(db)
    _add_v11_columns(db)
    _add_v12_columns(db)
    sync_plan_steps(db)
    sync_builtin_templates(db)
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return db


class transaction:
    """`with transaction(db):` — BEGIN/COMMIT, ROLLBACK on error."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def __enter__(self):
        self.db.execute("BEGIN")
        return self.db

    def __exit__(self, exc_type, *_):
        self.db.execute("ROLLBACK" if exc_type else "COMMIT")
        return False
