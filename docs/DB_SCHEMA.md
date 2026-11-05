# LoomTrack database schema

SQLite, 12 tables, defined in [backend/loomtrack/db.py](../backend/loomtrack/db.py). The diagram below is a Mermaid ER diagram: it renders on GitHub, and in VS Code with the "Markdown Preview Mermaid Support" extension.

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
    orders ||--o{ daily_updates : "receives"
    milestones ||--o{ daily_updates : "progress on"
    daily_updates ||--o{ photos : "has"
    daily_updates ||--o| issue_reasons : "classified as"
    orders ||--o{ photos : "has"
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
        TEXT po_no UK
        INTEGER buyer_id FK
        TEXT style
        TEXT colour
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
    milestones {
        INTEGER id PK
        INTEGER order_id FK
        TEXT code UK "unique per order"
        INTEGER seq
        TEXT name_en
        TEXT name_ta
        TEXT kind "milestone or stage"
        TEXT process
        TEXT planned_start
        TEXT planned_date
        TEXT actual_date "null until done"
        INTEGER unit_id FK
    }
    daily_updates {
        TEXT id PK "made on the phone"
        INTEGER order_id FK
        INTEGER milestone_id FK
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
        TEXT update_id FK
        INTEGER order_id FK
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
| The plan | `orders`, `order_sizes`, `milestones` | `milestones` holds both production stages (`kind = 'stage'`) and dated checkpoints (`kind = 'milestone'`). |
| Floor data | `daily_updates`, `photos`, `issue_reasons` | `daily_updates.id` is created on the phone, so a retried offline upload hits the same key and is ignored. |
| Warnings | `warnings`, `outbox_messages` | Buyers see only `confirmed` warnings. Confirming writes a mock email to the outbox. |
| Compliance | `date_changes` | Triggers abort every UPDATE and DELETE, so the table is append-only. |

## Rules enforced by the database

- `orders.qty_total > 0`, `order_sizes.qty >= 0`, `daily_updates.qty >= 0`.
- Allowed values are checked for `units.kind`, `users.role`, `orders.state`, `milestones.kind`, `daily_updates.note_source`, `warnings.level` and `warnings.state`.
- `milestones` is unique on `(order_id, code)`, and `order_sizes` is keyed on `(order_id, size)`.
- Foreign keys are on. `order_sizes` and `milestones` are deleted with their order.
- Index: `ix_updates_ms` on `daily_updates (milestone_id, work_date)`, used by the run-rate engine.
- Dates are ISO text (`2026-11-20`), which sorts correctly.
