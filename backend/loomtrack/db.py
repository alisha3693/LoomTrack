"""SQLite schema and connection. One connection, used from the event loop thread."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS buyers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT,
  link_token TEXT NOT NULL UNIQUE,
  link_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS units (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('own', 'subcontract')),
  process TEXT                      -- for subcontractors: 'printing' | 'washing'
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('merchandiser', 'supervisor')),
  login TEXT NOT NULL UNIQUE,       -- email for office, phone for supervisors
  secret_hash TEXT NOT NULL,
  unit_id INTEGER REFERENCES units(id),
  lang TEXT NOT NULL DEFAULT 'en'
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  po_no TEXT NOT NULL UNIQUE,
  buyer_id INTEGER NOT NULL REFERENCES buyers(id),
  style TEXT NOT NULL,
  colour TEXT NOT NULL,
  qty_total INTEGER NOT NULL CHECK (qty_total > 0),
  ex_factory TEXT NOT NULL,
  unit_id INTEGER NOT NULL REFERENCES units(id),
  template_key TEXT NOT NULL,
  merchandiser_id INTEGER REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'shipped', 'cancelled')),
  status TEXT,                      -- cached: green | amber | red
  projected_ex_factory TEXT,        -- cached
  status_computed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_sizes (
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  size TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (order_id, size)
);

-- TNA plan: non-production milestones and production stages in one table.
CREATE TABLE IF NOT EXISTS milestones (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  code TEXT NOT NULL,
  name_en TEXT NOT NULL,
  name_ta TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('milestone', 'stage')),
  process TEXT,
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
  order_id INTEGER NOT NULL REFERENCES orders(id),
  milestone_id INTEGER NOT NULL REFERENCES milestones(id),
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
  update_id TEXT REFERENCES daily_updates(id),
  order_id INTEGER NOT NULL REFERENCES orders(id),
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
  ai_source TEXT,                   -- 'ollama' | 'keywords'
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
  decided_at TEXT
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

-- Mock outbound messages (email / WhatsApp to buyers).
CREATE TABLE IF NOT EXISTS outbox_messages (
  id INTEGER PRIMARY KEY,
  buyer_id INTEGER NOT NULL REFERENCES buyers(id),
  order_id INTEGER REFERENCES orders(id),
  channel TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def open_db(file: str) -> sqlite3.Connection:
    if file != ":memory:":
        Path(file).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI handlers here are async and run on one thread; check_same_thread
    # is off only so test clients and startup code may share the connection.
    db = sqlite3.connect(file, check_same_thread=False, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
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
