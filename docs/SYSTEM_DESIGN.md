# LoomTrack: system design

The whole system on one page tree: what it must do, how it's built, how it runs, how it fails, how it grows, and what is still missing. Companion docs: [HOW_IT_WORKS.md](HOW_IT_WORKS.md) (data flow and code map), [TECH_STACK.md](TECH_STACK.md) (technology choices), [RUN_RATE.md](RUN_RATE.md) (delay maths).

Figures marked **measured** come from this build on the dev laptop. Figures marked **estimate** are reasoned from the brief's numbers and should be re-checked in the pilot.

---

## 1. Purpose and scope

**Problem (from the brief):** a Tiruppur knitwear exporter finds out an order is late "when it is too late to save it". Status lives in Excel and phone calls; buyers email for updates. Cost of the problem: about ₹1.08 crore a year.

**What LoomTrack does:** supervisors enter real numbers daily on their phones (Tamil, offline-tolerant); the system projects every order against its time-and-action (TNA) plan and flags trouble weeks early; merchandisers review and confirm warnings; buyers see their own orders' progress without emailing.

**In scope:** order setup with TNA, supervisor updates, order board, run-rate delay warning, AI reason category from Tamil notes, buyer link, weekly export.
**Out of scope (per brief):** costing, invoicing, export documents, fabric inventory, attendance and payroll.

**Users:**

| Actor | Count (from brief) | Device | Needs |
|---|---|---|---|
| Supervisor | one per unit/line; ~5 units incl. job-work | cheap 2–3 GB Android, patchy network | Numbers, a photo, a send button. Tamil. |
| Merchandiser | 12 | Office desktop | Board, warnings, order setup, buyer comms |
| Buyer sourcing staff | a handful per buyer | Any browser | Read-only progress, photos, date history |
| Managing Director | 1 | Any | Board at a glance, outcome metrics |

---

## 2. Requirements → design

Every constraint in the brief and the design decision that answers it.

| # | Requirement | Design response | Where |
|---|---|---|---|
| R1 | Supervisors on cheap phones, patchy network; updates must queue offline | Installable web app (no store), ~72 KB gzipped JS; update saved to IndexedDB first, sent with a phone-made ID, retried on reconnect | `web/src/lib/outbox.ts` |
| R2 | Tamil interface | Tamil strings for the whole supervisor flow, Noto Sans Tamil, language toggle, Tamil voice/text input | `lib/i18n.ts` |
| R3 | One buyer must never see another's styles or volumes | Buyer identity = link token; every query scoped by that buyer; separate allow-listed response shape; tested | `services/buyer_view.py` |
| R4 | Buyers' compliance wants a history of every date change | Append-only `date_changes` table written in the same transaction as the change; DB triggers block edits | `db.py` |
| R5 | Delay warning from daily output vs remaining qty and days left; show the maths | Pure deterministic engine returning the numbers it used; no AI in the projection | `domain/runrate.py` |
| R6 | Warnings two weeks early | Projection runs on every update and board load from actual run rate, not from "due" dates | `services/orders.py` |
| R7 | AI turns Tamil text/voice into an English reason category; may be wrong | Original shown beside translation; AI and human category stored separately; merchandiser override; buyers see warnings only after confirmation | `ai/classifier.py`, `routes/merchandiser.py` |
| R8 | Green / amber / red board filtered by buyer, unit, ship week | Status cached per order; filters server-side | `GET /api/m/board` |
| R9 | Weekly status export per buyer | Excel, buyer edition (same allow-list as the link) and internal edition | `services/export.py` |
| R10 | Minimal, clean design; supervisor screen = numbers, photo, send | Token-based design system, light and dark; supervisor screen has three inputs and one button | `web/src/styles.css` |
| R11 | ₹7 lakh, 6 weeks; demo must cost nothing to run | One backend language, one database file, free and open-source only, local AI | [TECH_STACK.md](TECH_STACK.md) |

---

## 3. System context

```
                      ┌──────────────────────────────────────────┐
  Supervisors  ──────►│                                          │
  (phones, Tamil)     │                LoomTrack                 │──► Mock outbox
                      │   web app + API + database + local AI    │    (buyer emails
  Merchandisers ─────►│                                          │     recorded, not sent)
  (office browser)    └──────────────┬───────────────────────────┘
                                     │
  Buyers  ───────────────────────────┘  read-only link, own orders only

  Nothing else: no ERP, no payment, no external AI service, no third-party analytics.
```

The only network call leaving the box is the browser loading fonts from Google Fonts (cached afterwards by the service worker). Voice transcription in Chrome sends audio to Google's speech service; that is a browser feature, not ours, and the original audio is always kept regardless.

---

## 4. Logical architecture

```
┌─────────────────────────── Browser (one React app, three experiences) ───────────────────────────┐
│  Office  /m/*      Supervisor  /s/*                Buyer  /b/:token                              │
│                    ├─ IndexedDB outbox (queued updates, photos, voice)                           │
│                    ├─ localStorage (session, cached stage list, language, theme)                 │
│                    └─ Service worker (app shell only, never API data)                            │
└───────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                            │ HTTPS, JSON + multipart
┌───────────────────────────────────────────▼──────────────────────────────────────────────────────┐
│ FastAPI (single process)                                                                         │
│                                                                                                  │
│  routes/        auth · merchandiser · supervisor · buyer                                         │
│                 (auth, input validation, status codes; no business rules)                        │
│       │                                                                                          │
│  services/      orders      load order → project → cache status → sync warnings                 │
│                 buyer_view  the allow-listed buyer response                                      │
│                 export      Excel workbooks                                                      │
│       │                                                                                          │
│  domain/        calendar · runrate · tna · reasons      (pure functions, no I/O, unit-tested)    │
│  ai/            classifier  Ollama call, keyword fallback                                        │
│                                                                                                  │
│  deps.py (who is signed in) · security.py (hashing, tokens, signed URLs) · db.py (schema)        │
└───────────────┬──────────────────────────────────────────────────────┬───────────────────────────┘
                │                                                      │ HTTP, localhost
        ┌───────▼────────┐                                     ┌───────▼────────┐
        │ SQLite (WAL)   │  + uploads/ folder (photos, voice)  │ Ollama         │
        │ one file       │                                     │ Llama 3 8B     │
        └────────────────┘                                     └────────────────┘
```

**Layering rule:** routes call services; services call domain; domain calls nothing. That is why the run-rate engine can be tested with no database and why the buyer view can't accidentally reuse an office query.

---

## 5. Key design decisions

Technology choices and their reasons are in [TECH_STACK.md](TECH_STACK.md). The decisions that shape behaviour:

| Decision | Why | Cost / tradeoff |
|---|---|---|
| **Projection is deterministic arithmetic, AI only labels reasons** | Warnings must be explainable and checkable by a buyer's compliance team | The AI never improves the prediction |
| **Status is computed and cached, not typed in** | The board can't drift from the floor's numbers | Each update triggers a recompute |
| **Warnings are drafts until a merchandiser confirms** | A delay notice to a UK buyer is a business decision; AI and maths can be wrong | One extra click for the office |
| **Client-generated update IDs** | Makes retries from the offline queue safe | Server must keep IDs forever |
| **AI answer and human answer in separate columns** | A wrong guess stays visible and correctable | Two fields to render |
| **Buyer responses built from an allow-list, never from office queries** | Leaks need a deliberate code change, not an oversight | Some duplication |
| **Classify notes in the background** | The phone gets "sent" in milliseconds; a local 8B model takes seconds | Translation appears a few seconds late |
| **SQLite, one process** | Zero ops; transactions make the audit guarantee simple; far above this load | No horizontal scaling without a move to Postgres |

---

## 6. Data design

### Entities

```
buyers ──< orders >── units
             ├──< order_sizes
             ├──< milestones >── plan_steps
             │       └──< daily_updates ──< photos
             │                    └──1 issue_reasons
             ├──< warnings
             └──< date_changes
users ──< sessions            outbox_messages
```

| Table | Holds | Notes |
|---|---|---|
| `orders` | Our order number, the buyer's PO, buyer, style, colour (name, optional Pantone, optional hex swatch), qty, ex-factory, unit, template, cached status | `order_no` (`LT-2026-0001`) is ours and unique; `po_no` is the buyer's and unique per buyer. `status` and `projected_ex_factory` are caches |
| `order_sizes` | Size × quantity grid | Sums to `orders.qty_total` |
| `plan_steps` | The kinds of step a plan is built from (cutting, sample approval, ...): English and Tamil name, `kind`, `process` | Written once per step and synced from `domain/tna.py` at startup, so a label is fixed in one place |
| `attachments` | Design, pattern, print and fabric files on requests and orders | Type from the file's bytes, random stored name, 15 MB cap, limits per request and order. Visibility is per file: buyer, floor |
| `order_requests`, `request_sizes`, `request_messages` | A buyer's order request and its conversation; status = whose turn it is | `request_messages` is append-only. Accepting creates the order |
| `templates`, `template_steps` | Saved plan layouts: an ordered list of steps with start and end offsets (days before ex-factory) | The 3 built-ins come from `domain/tna.py` and are read-only; merchandisers add their own. Retired, never deleted |
| `milestones` | One order's TNA plan: each row points at a `plan_steps` step and holds that order's dates | Stages carry `unit_id` (own or job-work); name and kind come from `plan_steps` |
| `daily_updates` | One row per supervisor submission | `id` is generated on the phone. The order is reached through `milestone_id` (no copy of `order_id`) |
| `photos` | Photo per update | Always belongs to an update. `buyer_visible` lets the office hide one |
| `issue_reasons` | AI result and human decision, side by side | `ai_*` columns vs `final_category` |
| `warnings` | Draft and decided buyer warnings | States below |
| `date_changes` | Every planned-date change with reason and who | Append-only by trigger |
| `outbox_messages` | Mock buyer emails | Replace with real email later |
| `users`, `sessions` | Staff accounts (scrypt hashes), session tokens | Roles: merchandiser, supervisor |

### Invariants the system enforces

1. A supervisor can only write to stages belonging to their own unit.
2. A given update ID is stored once, however many times it is sent.
3. Cumulative output per stage can't exceed order quantity by more than 5%.
4. An update can't be dated in the future or more than 7 days back.
5. Changing a planned date requires a reason, and writes `date_changes` in the same transaction.
6. `date_changes` rows can't be updated or deleted.
7. `request_messages` rows can't be updated or deleted.
8. A buyer can reach only their own requests; another buyer's request is "not found".
9. An accepted request creates an order with exactly the quantities, colour and date the buyer asked for or agreed to. A different date goes through a counter-proposal the buyer agrees to.
   An accepted change to an existing order updates the date (with a `date_changes` entry that names the request and the reason) and the quantities in one transaction, and cannot take the quantity below what has already been made. The order's stage dates are not moved automatically.
10. A milestone must point at a known `plan_steps` step, and an update's order is always its milestone's order (there is no second copy to disagree).

### Normalisation and migrations

The schema is in third normal form apart from two deliberate exceptions: the cached `orders.status` / `projected_ex_factory` (so the board doesn't rerun the engine per row) and the point-in-time numbers on `warnings` (history, not duplication). `PRAGMA user_version` records the schema version. Opening a version-0 database (before `plan_steps`) migrates it in place inside one transaction, keeps a copy as `<db>.v0.bak`, and checks foreign keys afterwards. See `_migrate_v0` in `db.py` and `tests/test_migration.py`.
7. A buyer sees a warning only in state `confirmed` (or its resolved history).
8. A warning is created only for orders that are amber or red.

### Warning lifecycle

```
            engine: amber/red                      merchandiser confirms
 (none) ───────────────────────► PENDING ───────────────────────────────► CONFIRMED ──► (buyer sees)
                                    │   └─ dismiss ─► DISMISSED                │
                                    │                                          │ order back to green
                  order back to green                                          ▼
                                    ▼                                       RESOLVED
                               SUPERSEDED         (a newer confirmation also supersedes the older one)
```

---

## 7. API design

- **REST + JSON**, one prefix per actor: `/api/auth`, `/api/m` (office), `/api/s` (floor), `/api/b/:token` (buyer, read plus the request endpoints), plus signed media at `/api/media/*`. Interactive docs at `/api/docs`.
- **One error shape** everywhere: `{"error": "human-readable message"}`. 400 validation, 401 sign-in, 403 role or unit, 404, 409 conflict, 422 business rule, 429 lockout.
- **Auth:** the session token is accepted from either `Authorization: Bearer <token>` (what the app sends, from localStorage) or the `loomtrack_session` cookie (set at login: `HttpOnly`, `SameSite=Lax`, `Secure` over HTTPS). The cookie lets the API be opened directly in a browser while signed in. The header wins if both are present. A buyer link token is never accepted as either. Buyer accounts use the same session (role `buyer`); the buyer endpoints accept either the link token or the word `me` in its place, and `me` is only honoured for a signed-in buyer whose password is not a temporary one.
- **Idempotency:** `POST /api/s/updates` is idempotent on the client ID (second send returns 200 `duplicate: true`).
- **Dates** are ISO `YYYY-MM-DD` strings everywhere; time zone is never involved in date arithmetic.
- **Media:** photos and voice served by short-lived HMAC-signed URLs (an `<img>` can't send a Bearer header). Buyer photos go through the buyer-scoped endpoint instead.
- **Naming:** computed responses are camelCase; raw database rows on the order-detail endpoint keep their column names. A known inconsistency, cheap to unify before there are outside API consumers.

---

## 8. Core algorithms

- **Run-rate projection:** per stage, required pieces/day vs actual pieces/day (7-working-day average), chained through the production pipeline, ending in a projected ex-factory date and green/amber/red. Full method and a worked example: [RUN_RATE.md](RUN_RATE.md).
- **TNA generation:** templates give each step an offset in days before ex-factory; dates snap back to the nearest working day (Sundays and holidays skipped). Merchandisers build their own templates in the app. A saved template is always ordered by end offset (the delay engine reads stages in order) and ends with ex-factory. A stage must start earlier than it ends. A step typed in with an existing name reuses that step. A step goes to the subcontract unit for its process if one exists, otherwise to the order's own unit.
- **Reason classification:** local LLM with fixed categories, definitions and a Tamil factory glossary, schema-constrained output; keyword matcher as fallback. Detail: [HOW_IT_WORKS.md](HOW_IT_WORKS.md).

---

## 9. Security and privacy

| Threat | Mitigation today | Gap / next step |
|---|---|---|
| Buyer A sees buyer B's data | Scoping by token-derived buyer ID; allow-listed shape; isolation tests | None known |
| Guessing or leaking a buyer link | 32-byte random token; revocable; `no-store` and no-referrer headers | Optional expiry; link view logging |
| Password guessing | scrypt hashing; lockout after 5 tries for 5 minutes | Lockout is per login and in memory (resets on restart; an attacker can lock a real user out). Add per-IP limit |
| Stolen session token | 90-day supervisor / 14-day office expiry; logout deletes the session and clears the cookie; the cookie is `HttpOnly` | **Session tokens are stored in plain text in the database**; hash them. The app still keeps a copy of the token in localStorage (XSS-exposed; the cookie's `HttpOnly` protection doesn't cover that copy); mitigated by React escaping, no third-party scripts, but add a Content-Security-Policy. Moving the app fully to the cookie would remove the localStorage copy |
| Cross-site request forgery (cookie auth) | `SameSite=Lax`: browsers don't send the cookie on cross-site POST/PATCH. Write routes need a JSON body | No CSRF token. Relies on `SameSite` browser support; keep state changes off GET (`GET /board` only refreshes a cached status). Add a token if the API is ever served from a different site |
| Malicious upload (photos and voice) | Size cap (6 MB), top-level type check (image/audio) | Type comes from the client; **verify file signatures** and send `X-Content-Type-Options: nosniff` |
| Malicious upload (design files) | Type decided from the file's own bytes (PDF, JPG, PNG, WebP, GIF, TIFF, PSD, ZIP/Office, DXF only; HTML, SVG and executables are refused); random stored name, display name sanitised; 15 MB cap; 10 files per request, 30 per order; served with `nosniff`, and only images and PDF open inline; ZIPs are never unpacked | No virus scan. ZIP and Office files are opaque downloads. A buyer-link holder can upload (see requests). Add scanning if files will be opened on shared office machines |
| One buyer sees another's design files | Every buyer file lookup joins to the owning request or order and filters on the link's buyer; our own files are private until marked visible; tests remove each check to prove they fail | None known |
| Supervisor writes to someone else's stage | Unit check on every update | None known |
| Tampering with the audit trail | Triggers block UPDATE/DELETE on `date_changes` | A DB admin can still drop the trigger; for compliance-grade proof, ship the log to write-once storage |
| AI prompt injection via a note | AI output is constrained to a fixed enum + free text shown as plain text; it cannot take actions | Free-text translation could be misleading; the original is always shown beside it |
| Data leaving the building | AI is local; no analytics; only Google Fonts and (Chrome-only) speech service | Self-host the fonts for strict privacy |
| Transport | None in demo (HTTP on LAN) | **HTTPS is required in production** (phones also require it for camera and mic) |

Personal data held is small: staff names, phone numbers (as logins), PIN/password hashes. No worker-level records are kept (attendance is out of scope).

---

## 10. Reliability and failure modes

| Failure | What the user sees | Behaviour |
|---|---|---|
| Phone has no network | "Saved. It will send when the network is back." | Update queued in IndexedDB; retried on reconnect, foreground and every 30 s |
| Network drops mid-upload | Same | Server may or may not have stored it; retry is safe (idempotent ID) |
| Server rejects an update (e.g. over quantity) | Red message with the reason and a Discard button | Not retried forever |
| Server restarts | Brief errors, then normal | State is all in SQLite; signed media URLs become invalid until reloaded (key regenerates unless `LOOMTRACK_SIGNING_KEY` is set) |
| Ollama down, slow or cold | Top bar shows "AI off · keywords"; translation missing | Keyword guess used; error stored; app fully usable. Cold start ~20 s (**measured**) |
| AI returns a wrong category | Original note beside translation; dropdown to fix | Human decision stored and never overwritten by a later AI run |
| Two updates for the same stage | Both stored and summed | Cap check prevents runaway totals |
| Phone clock wrong | Update dated by the server's "today" shown on the phone from the last sync | Server rejects future or too-old dates |
| Disk full or corrupted | Server errors | **No backups yet** (see §12) |
| Process crash | Service stops | Needs a process supervisor in production (systemd/NSSM) |

---

## 11. Performance and capacity

**Load (estimate from the brief):** 500 orders a year → roughly 80 active at once (10 a week × ~8 weeks). Each has 1–2 stages running, so about 100–150 supervisor updates a day, ~55,000 a year. Buyer views: a few hundred requests a day.

| Resource | Estimate | Notes |
|---|---|---|
| Database rows | ~55k updates/yr plus ~10k milestone rows | Megabytes; SQLite is far from stressed |
| Photos | ~150 updates/day × ~150–300 KB ≈ 20–45 MB/day ≈ **8–16 GB/yr** | Phone shrinks to ≤1280 px, JPEG 70% (size per photo is an estimate; check in pilot). This is the real storage driver |
| AI | ≤150 notes/day × ~4 s ≈ 10 min of GPU a day | **Measured** ~4 s per note warm, ~20 s cold on an RTX 3050 6 GB. CPU-only is slower (**estimate** 15–30 s), acceptable because it runs in the background |
| Board load | **Measured** ~10 ms for 9 orders (~1 ms per order); **estimate** ~100 ms for 80 | Recomputes every active order on every load |
| Order detail | **Measured** ~5 ms | |
| Web bundle | **Measured** 72 KB JS + 4 KB CSS gzipped | Fits a 2 GB phone on 3G |

**Known design smell:** `GET /api/m/board` recomputes and writes the cached status for every active order. That is fine at 80 orders and keeps the board always current, but a read that writes is not ideal. If the board gets slow or contended, switch to compute-on-write only (the update path already recomputes) plus a nightly refresh so days rolling over still move statuses.

**Concurrency:** one async process with one SQLite connection. Queries are quick and blocking, so requests effectively serialise; at ~150 updates a day, contention is not a concern.

---

## 12. Deployment and operations

### Demo (now): one laptop
```
npm start  →  builds the web app, one uvicorn process serves API + web on :4000
Ollama running locally (tray app)
Phones on the same Wi-Fi: http://<laptop-ip>:4000   (camera/mic need HTTPS: use a free Cloudflare Tunnel)
```

### Production (recommended): one small server in an India region
```
Internet ── HTTPS ──► Caddy (free, automatic certificates)
                         │
                         ▼
                      uvicorn (loomtrack.main:create_app --factory)    ← systemd service, auto-restart
                         │
         ┌───────────────┼──────────────────┐
         ▼               ▼                  ▼
   SQLite file     uploads/ folder     Ollama (same box, GPU preferred;
   (/var/lib/…)    (/var/lib/…)         or a second box on the LAN via OLLAMA_URL)
         │               │
         └── nightly backup: sqlite3 ".backup" + copy uploads → second disk / free object storage
```

The Windows equivalent is NSSM or Task Scheduler for the service and Caddy for HTTPS. Everything is free and open source; the only recurring cost is the server.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `LOOMTRACK_DB` | `backend/data/loomtrack.db` | Database file |
| `LOOMTRACK_UPLOADS` | `backend/data/uploads` | Photos and voice |
| `LOOMTRACK_TODAY` | real date (IST) | Pins "today". The npm scripts pin it to 2026-11-05 for the demo; **unset it to go live** |
| `LOOMTRACK_AI` | `on` | `off` forces the keyword classifier |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `llama3` | Local AI endpoint and model |
| `LOOMTRACK_SIGNING_KEY` | random per start | Set a fixed value so media links survive restarts |

### Operations checklist (not yet done)
Backups with a restore test · HTTPS · process supervisor · log rotation · seeded demo accounts removed and real users created · demo date pin removed · fixed signing key.

---

## 13. Observability

**Today:** uvicorn access logs; stored AI errors (`issue_reasons.ai_error`); `/api/docs`; the top-bar AI status.
**Needed for a pilot:** structured request logs with durations; an error log someone reads; a `/api/health` endpoint (DB reachable, Ollama reachable) for an uptime monitor; counts of updates received per unit per day, which also shows which supervisors have stopped reporting.

---

## 14. Testing strategy

| Layer | What | Where |
|---|---|---|
| Domain | Run-rate engine, calendar, TNA | `backend/tests/test_runrate.py` |
| AI fallback | Keyword classifier on Tamil and English notes | `test_classifier.py` |
| API | Buyer isolation, idempotent sends, unit scoping, AI fallback, warning confirmation, append-only audit, validation shape | `test_api.py` |
| Browser | Every screen as all three users; offline queue; dark mode | `e2e/walkthrough.py`, `e2e/offline_test.py` |
| **Not yet** | Real-phone test on a 2 GB Android over throttled 3G; AI accuracy on a labelled Tamil note set; load test with ~80 orders | See TODO |

---

## 15. Success metrics and what the system can measure

The brief's success criteria, and honest status of how LoomTrack would measure each:

| Goal | How to measure | Status |
|---|---|---|
| Late shipments 8% → 5% over two seasons | Share of orders shipped after planned ex-factory | **Not measurable yet**: there is no "mark shipped" step or actual ship date, so orders stay active forever. Add it before the pilot |
| Status-chasing time halved | Merchandiser time survey; proxy: how often orders are viewed vs how often phone calls are logged | Needs a before/after survey. System can log board views |
| Buyer status emails down 60% | Count buyer emails to merchandisers before/after | External count. System can log buyer link views as the "instead" signal |
| (Leading indicator) Warning lead time | Days between first warning and planned ex-factory | **Available now**: `warnings.created_at` vs `orders.ex_factory`; needs a small report |
| (Leading indicator) Supervisor adoption | Share of active stages with an update today | **Available now** from `daily_updates`; needs a small report |

---

## 16. Scaling and evolution path

| Trigger | Move |
|---|---|
| More than ~5 office users writing at once, or managed backups wanted | PostgreSQL (free, open source). SQL is plain and isolated in routes and services |
| Photos exceed local disk | S3-compatible storage (e.g. self-hosted MinIO); the upload path is one function |
| Board slow beyond ~300 active orders | Compute-on-write only + nightly refresh (§11) |
| AI needs more accuracy | Evaluate other Ollama models (`qwen2.5:7b`, `gemma2:9b`) on a labelled Tamil set; later fine-tune or add few-shot examples from corrected notes (the human overrides are already stored: free training data) |
| Voice quality | faster-whisper (MIT) for server-side Tamil transcription; keep original audio |
| Real buyer emails / WhatsApp | Replace the outbox write with an SMTP sender (free) behind the same confirm step |
| Multiple factories or tenants | Add a company ID to every table; today it is single-tenant by design |
| Line capacity shared between orders in the delay engine | The acceptance-time capacity check already spreads booked stitching across a unit's days; feeding that into the run-rate projection (so a crowded unit lowers each order's expected rate) is still to do |

---

## 17. Risks and open questions

| Risk | Impact | Mitigation |
|---|---|---|
| Supervisors don't enter data daily | Projections go stale | Show last-update age on the board (done); per-unit "no update today" report (to build); keep the screen to three inputs |
| Free local AI misreads Tamil | Wrong reason on a buyer message | Human confirms before send (done); show original (done); eval set and model comparison (to do) |
| 7-day average reacts slowly | Late warning on a sudden collapse | Weighted average option; tune with real pilot data |
| Phones lack camera/mic on HTTP | Feature appears broken | HTTPS in production; tunnel for demos |
| Demo date pinned to 5 Nov 2026 | Real use would look wrong | `LOOMTRACK_TODAY` must be unset for live use (on the checklist) |
| Sample orders and 6 more are synthetic | Client may confuse demo data with reality | Labelled in README and seed |
| Compliance expects tamper-proof logs | SQLite triggers aren't enough | Ship the log to write-once storage if required |

**Questions for the client:** Which holidays apply per unit? Does a unit ever run Sundays? Who can change an ex-factory date, and does the buyer have to approve first? Is the run-rate window of 7 days right for their lines? Do job-work units get their own logins and phones? What counts as "shipped" for the late-shipment metric?

---

## 18. Roadmap

| Phase | Contents | Status |
|---|---|---|
| 1. Core build | Setup + TNA, supervisor update (offline), board, projection, AI reason, buyer link | **Done** |
| 2. Depth | Weekly export, mock outbox, milestone marking, dark mode, PWA shell | **Done** |
| 3. Pilot-ready | Mark shipped + actual ship date, health endpoint, session-token hashing, upload checks, CSP, backups, HTTPS, real accounts, adoption and warning-lead-time reports, real-phone test | To do |
| 4. Improve | AI eval and model choice, local Whisper, weighted run rate, per-unit capacity view (done: Units page and the acceptance check) | To do |
| 5. Grow | Real email/WhatsApp, Postgres if needed, multi-factory, line loading | Later |
