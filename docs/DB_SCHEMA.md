# LoomTrack database schema

SQLite, 13 tables, defined in [backend/loomtrack/db.py](../backend/loomtrack/db.py). The schema is normalised (third normal form) apart from two deliberate caches. The diagram below is a Mermaid ER diagram: it renders on GitHub, and in VS Code with the "Markdown Preview Mermaid Support" extension.

`PK` primary key, `FK` foreign key, `UK` unique. `||--o{` means one-to-many.

```mermaid
erDiagram
    buyers ||--o{ orders : "places"
    units ||--o{ orders : "runs"
    units ||--o{ users : "employs supervisors"
    units ||--o{ milestones : "does stage"
    users ||--o{ sessions : "signs in"
    users ||--o{ orders : "merchandises"
    users ||--o{ daily_updates : "submits"
    orders ||--|{ order_sizes : "has sizes"
    orders ||--|{ milestones : "has TNA plan"
    plan_steps ||--o{ milestones : "defines the step"
    orders ||--o{ daily_updates : "receives"
    milestones ||--o{ daily_updates : "progress on"
    daily_updates ||--o{ photos : "has"
    daily_updates ||--o| issue_reasons : "classified as"
    orders ||--o{ warnings : "raises"
    orders ||--o{ date_changes : "audited by"
    milestones ||--o{ date_changes : "date moved"
    buyers ||--o{ outbox_messages : "emailed"
    orders ||--o{ outbox_messages : "about"

    buyers {
        INTEGER id PK
        TEXT name
        TEXT country
        TEXT link_token UK "buyer credential"
        INTEGER link_active "1 = link works"
    }
    units {
        INTEGER id PK
        TEXT name
        TEXT kind "own or subcontract"
        TEXT process "printing or washing"
    }
    users {
        INTEGER id PK
        TEXT name
        TEXT role "merchandiser or supervisor"
        TEXT login UK "email or phone"
        TEXT secret_hash "scrypt"
        INTEGER unit_id FK "supervisors only"
        TEXT lang "en or ta"
    }
    sessions {
        TEXT token PK
        INTEGER user_id FK
        TEXT expires_at
    }
    orders {
        INTEGER id PK
        TEXT order_no UK "our number, LT-2026-0001"
        TEXT po_no "buyer's PO; unique per buyer"
        INTEGER buyer_id FK
        TEXT style
        TEXT colour "name"
        TEXT colour_pantone "optional reference"
        TEXT colour_hex "optional swatch, #RRGGBB"
        INTEGER qty_total "greater than 0"
        TEXT ex_factory
        INTEGER unit_id FK
        TEXT template_key
        INTEGER merchandiser_id FK
        TEXT state "active, shipped, cancelled"
        TEXT status "cached green, amber, red"
        TEXT projected_ex_factory "cached"
        TEXT status_computed_at
        TEXT created_at
    }
    order_sizes {
        INTEGER order_id PK, FK
        TEXT size PK
        INTEGER seq
        INTEGER qty
    }
    plan_steps {
        TEXT code PK
        TEXT name_en
        TEXT name_ta
        TEXT kind "milestone or stage"
        TEXT process "stages only"
    }
    milestones {
        INTEGER id PK
        INTEGER order_id FK
        TEXT code UK, FK "step; unique per order"
        INTEGER seq
        TEXT planned_start
        TEXT planned_date
        TEXT actual_date "null until done"
        INTEGER unit_id FK
    }
    daily_updates {
        TEXT id PK "made on the phone"
        INTEGER milestone_id FK "order is milestones.order_id"
        INTEGER user_id FK
        TEXT work_date
        INTEGER qty
        TEXT note_text
        TEXT note_source "text or voice"
        TEXT audio_path
        TEXT created_at_client
        TEXT received_at
    }
    photos {
        INTEGER id PK
        TEXT update_id FK "required"
        TEXT path
        TEXT mime
        INTEGER buyer_visible
        TEXT created_at
    }
    issue_reasons {
        TEXT update_id PK, FK
        TEXT ai_category
        TEXT ai_translation
        REAL ai_confidence
        TEXT ai_source "ollama or keywords"
        TEXT ai_error
        TEXT final_category "human decision"
        INTEGER changed_by FK
        TEXT changed_at
        TEXT classified_at
    }
    warnings {
        INTEGER id PK
        INTEGER order_id FK
        TEXT level "amber or red"
        TEXT projected_ex_factory
        INTEGER slack_days
        TEXT summary "internal maths"
        TEXT buyer_message
        TEXT state "pending, confirmed, dismissed, superseded, resolved"
        INTEGER decided_by FK
        TEXT decided_at
        TEXT created_at
    }
    date_changes {
        INTEGER id PK
        INTEGER order_id FK
        INTEGER milestone_id FK
        TEXT field
        TEXT old_value
        TEXT new_value
        TEXT reason "required"
        INTEGER changed_by FK
        TEXT changed_at
    }
    outbox_messages {
        INTEGER id PK
        INTEGER buyer_id FK
        INTEGER order_id FK
        TEXT channel
        TEXT subject
        TEXT body
        TEXT created_at
    }
```

## Reading the diagram

| Area | Tables | Note |
|---|---|---|
| People and access | `buyers`, `users`, `sessions`, `units` | A buyer's `link_token` is their credential. A supervisor's `unit_id` limits which stages they see. |
| The plan | `orders`, `order_sizes`, `plan_steps`, `milestones` | `plan_steps` holds each kind of step once (names, stage or milestone). `milestones` is one order's plan: a row per step with that order's dates. |
| Floor data | `daily_updates`, `photos`, `issue_reasons` | `daily_updates.id` is created on the phone, so a retried offline upload hits the same key and is ignored. |
| Warnings | `warnings`, `outbox_messages` | Buyers see only `confirmed` warnings. Confirming writes a mock email to the outbox. |
| Compliance | `date_changes` | Triggers abort every UPDATE and DELETE, so the table is append-only. |

## Rules enforced by the database

- `orders.qty_total > 0`, `order_sizes.qty >= 0`, `daily_updates.qty >= 0`.
- Allowed values are checked for `units.kind`, `users.role`, `orders.state`, `milestones.kind`, `daily_updates.note_source`, `warnings.level` and `warnings.state`.
- `orders.order_no` is unique. `orders.po_no` is unique per buyer (`UNIQUE (buyer_id, po_no)`), because it is the buyer's own number. `colour_hex` must be `#` plus six uppercase hex digits.
- `milestones` is unique on `(order_id, code)`, and `milestones.code` must exist in `plan_steps`. `order_sizes` is keyed on `(order_id, size)`.
- `daily_updates` and `photos` carry no `order_id`: an update's order is its milestone's order, so there is no second copy to disagree. Every photo must belong to an update.
- Foreign keys are on. `order_sizes` and `milestones` are deleted with their order.
- Index: `ix_updates_ms` on `daily_updates (milestone_id, work_date)`, used by the run-rate engine.
- Dates are ISO text (`2026-11-20`), which sorts correctly.

## Normalisation

| What | Where it stands |
|---|---|
| Step names stored once | `plan_steps` (synced from `domain/tna.py` at startup). Fix a Tamil label in one place and every order shows it. |
| No duplicated `order_id` | Removed from `daily_updates` and `photos`. Queries reach the order through `milestones`. |
| Deliberate exceptions | `orders.status` and `projected_ex_factory` are cached results (so the board doesn't rerun the engine per row), and `warnings` keeps a snapshot of the numbers when it was raised (history). |
| `date_changes.order_id` kept | Ex-factory changes have no milestone, so the order must be stored directly. |

## Versions and migration

`PRAGMA user_version` holds the schema version (now 2). Older databases are migrated in place when the app opens them, one version at a time: one transaction, a copy saved as `<db>.v0.bak` or `.v1.bak`, and a foreign-key check afterwards.

| Version | Change |
|---|---|
| 0 to 1 | Step names moved to `plan_steps`; `order_id` removed from `daily_updates` and `photos`. |
| 1 to 2 | `orders.order_no` added and backfilled (`LT-<year>-<n>` in creation order); colour fields added; PO number made unique per buyer. |

Code: `_migrate_v0` and `_migrate_v1` in [db.py](../backend/loomtrack/db.py). Tests: [test_migration.py](../backend/tests/test_migration.py).
