# How LoomTrack works

A walkthrough of what happens from a supervisor's tap to a buyer's screen. For *why* each technology was chosen, see [TECH_STACK.md](TECH_STACK.md). For the delay maths, see [RUN_RATE.md](RUN_RATE.md).

## The big picture

```
 Supervisor phone            Office browser             Buyer browser
 (Tamil, offline-capable)    (merchandiser)             (read-only link)
        |                          |                          |
        |  /api/s/*                |  /api/m/*                |  /api/b/<token>/*
        +--------------+-----------+--------------------------+
                       v
              FastAPI backend  (Python, one process, one SQLite file)
              ├─ routes/        thin HTTP layer: checks who you are, validates input
              ├─ services/      loads data, runs the engine, keeps warnings in step
              ├─ domain/        pure logic: calendar, run-rate engine, TNA templates
              └─ ai/            note → English translation + reason category
                       |
              SQLite file + uploads folder (photos, voice)
                       |
              Ollama on the same machine (Llama 3 8B), optional
```

Three kinds of user hit three separate sets of endpoints, and each set is guarded differently:

| Who | URL prefix | How they're identified |
|---|---|---|
| Merchandiser | `/api/m/` | Signs in with email + password → session token (sent as a Bearer header by the app; also set as a cookie) |
| Supervisor | `/api/s/` | Signs in with phone + PIN → session token, tied to one unit |
| Buyer | `/api/b/<token>/` | The random token in the link *is* the credential |

## The main loop: one supervisor update

1. **On the phone** the supervisor enters pieces, optionally a photo and a note (typed, or spoken). The photo is shrunk to ≤1280 px first.
2. **The update is saved to the phone's own storage (IndexedDB) before anything is sent.** It gets an ID generated on the phone. This is the offline queue.
3. **The app tries to send it** to `POST /api/s/updates`. If there's no network, it stays queued and retries when the phone reconnects, when the app comes to the foreground, and every 30 seconds.
4. **The server checks it:** the stage must belong to this supervisor's unit, the order must be active, the date can't be in the future or older than 7 days, and the running total can't exceed the order quantity by more than 5%.
5. **If the ID has been seen before, the server says "already have it" and does nothing.** That's what stops a retry from double-counting pieces.
6. **It's stored:** one row in `daily_updates`, one in `photos` if there's a photo, and one empty row in `issue_reasons` if there's a note or voice.
7. **The order is re-projected right away** (next section), so the board is current.
8. **If there's a note, the phone doesn't wait for the AI.** The server answers "sent" and classifies the note in the background (a few seconds on the local model). When it finishes, it saves the translation and category and re-projects the order once more, because the reason feeds the suggested buyer message.

## Re-projecting an order (`services/orders.py`)

Every time numbers change, and every time the board loads, the server recomputes each active order:

1. Load the order's stages and each stage's daily totals.
2. Run the pure run-rate engine (`domain/runrate.py`). It returns a status (green / amber / red), the projected ex-factory date, and every number it used.
3. Add overdue milestones (e.g. a sample approval nobody marked done). An otherwise-green order with one becomes amber.
4. **Cache the result** on the order row (`status`, `projected_ex_factory`).
5. **Keep warnings in step** with the new status:

| Situation | What happens |
|---|---|
| Order turns amber/red, no warning yet | A **pending** warning is created with a suggested buyer message |
| Pending warning exists | It's updated to the latest numbers; the draft message is rewritten |
| Buyer was already told, and it's no worse | Nothing new (the buyer isn't spammed) |
| Order recovers to green | Pending warning → *superseded*; confirmed warning → *resolved* |

## Warnings and the confirm-before-buyer rule

```
 engine says "late"  →  PENDING  →  merchandiser edits + confirms  →  CONFIRMED  →  buyer sees it
                            |
                            └→ merchandiser dismisses → DISMISSED  (buyer never sees it)
```

A warning is invisible to buyers until a merchandiser confirms it. Confirming also writes a (mock) email to `outbox_messages`, shown under **Buyers & exports**. This is deliberate: the AI or the engine can be wrong, and a delay notice to a UK buyer is a business decision.

## The AI step (`ai/classifier.py`)

- The note goes to the local Llama 3 model through Ollama, with a fixed list of 11 reason categories, plain-language definitions of each, and a short Tamil factory glossary. Ollama forces the answer into a JSON shape: English translation + one category + confidence.
- **Both the AI's answer and the human's answer are stored, in separate columns** (`ai_category` and `final_category`). When a merchandiser changes the category, the AI's original guess stays visible ("AI said …").
- A later AI run never overwrites a category a person set by hand.
- If Ollama is down, slow or returns junk, a keyword matcher gives a first guess instead. The record says which one produced it (`ai_source`) and keeps any error. The top bar shows **AI · llama3** or **AI off · keywords**.

## What buyers can see (`services/buyer_view.py`)

The buyer endpoints never reuse the office responses. They build a separate response field by field:

- **Included:** PO, style, colour, sizes, quantities, ex-factory, progress per stage, milestones, photos (unless hidden), date-change history, and *confirmed* notices.
- **Left out on purpose:** unit and subcontractor names, status colour, slack, supervisor names and notes, unconfirmed warnings.
- Every query is filtered by the buyer ID found from the link's token. There's no buyer ID in the URL a buyer could change.
- A buyer's token can't be used as a staff session, and rotating the link kills the old one at once.

## The date-change trail

Changing ex-factory, or any planned date, requires a reason and writes a row to `date_changes` in the same transaction as the change. Database triggers refuse any UPDATE or DELETE on that table, so the history is append-only even if someone edits the database directly. Marking a milestone done or undone is logged too. The same history shows on the buyer link.

## The screens and where their data comes from

| Screen | URL | Main endpoint(s) |
|---|---|---|
| Login | `/login` | `POST /api/auth/login` |
| Order board | `/m` | `GET /api/m/board?buyer=&unit=&week=` |
| New order | `/m/orders/new` | `POST /api/m/plan-preview`, `POST /api/m/orders` |
| Order detail | `/m/orders/:id` | `GET /api/m/orders/:id`, warning confirm/dismiss, date changes, reason override |
| Buyers & exports | `/m/buyers` | `GET /api/m/buyers`, `/exports/weekly`, `/outbox` |
| Supervisor home | `/s` | `GET /api/s/orders` (cached on the phone) |
| Supervisor update | `/s/update/:id` | `POST /api/s/updates` (through the offline queue) |
| Buyer view | `/b/:token` | `GET /api/b/:token` |

Live API docs with every endpoint: http://localhost:4000/api/docs

## Data model (SQLite)

```
buyers ──< orders >── units
             │ ├──< order_sizes
             │ └──< milestones         the TNA plan: milestones and production stages in one table
             │        └──< daily_updates ──< photos
             │                  └── issue_reasons    (AI result + human decision, kept apart)
             ├──< warnings            pending / confirmed / dismissed / superseded / resolved
             └──< date_changes        append-only audit trail
users ──< sessions          outbox_messages (mock buyer emails)
```

A *stage* is a production step with quantities (cutting, printing, stitching, washing, finishing, packing). A *milestone* is a dated checkpoint (sample approval, inspection, ex-factory). Both live in `milestones`, told apart by `kind`.

## Where things are in the code

```
backend/loomtrack/
  main.py              app setup, error format, serves the built web app
  config.py            database path, holidays, AI model, "today" (pinned for the demo)
  db.py                schema + transaction helper
  security.py          password hashing, session tokens, signed media URLs
  deps.py              "who is signed in", role guards
  domain/              no database, no web: calendar, runrate, tna templates, reason list
  services/            orders (projection + warnings), buyer_view, export (Excel)
  routes/              auth, merchandiser, supervisor, buyer
  ai/classifier.py     Ollama call + keyword fallback
  seed.py / explain.py demo data / prints the run-rate maths for every order
backend/tests/         37 tests
web/src/
  App.tsx              routes + role guards
  lib/                 api client, auth, Tamil strings, offline outbox, photo/voice helpers, theme
  pages/merch/         office screens;  pages/sup/  phone screens;  pages/buyer/  buyer view
  styles.css           design tokens (light + dark) and all styling
e2e/                   browser walkthrough + offline test
```

## Offline behaviour in detail

- **Sending:** covered above. Updates are never lost to a dead network; they wait in the phone's storage.
- **Viewing:** the supervisor's stage list is cached on the phone after each successful load, so the app still opens and shows it offline. The numbers shown include anything still queued.
- **App shell:** in production builds, a service worker caches the app itself so it opens without a network. It never caches API data.
- **A refused update** (e.g. over the quantity cap) isn't retried forever. It's kept with the server's message and shown to the supervisor with a Discard button.

## What is mocked or limited today

- Buyer emails are recorded in the app, not sent.
- Voice: the original audio is always kept for the merchandiser. The live transcript uses the phone browser's speech service where available; local Whisper is on the to-do list.
- The run rate is a 7-day average and doesn't model capacity shared between orders on one line (see RUN_RATE.md, "Known limits").
- One SQLite file is right for this size. Postgres is the path if the client wants managed backups.
