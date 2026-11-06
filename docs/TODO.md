# LoomTrack — To-do

Status key: `[x]` done · `[~]` in progress · `[ ]` not started. Updated as work lands. Each item names the brief requirement it serves.

## Phase 0 — Foundation
- [x] Read brief, list constraints, write tech-stack decisions ([TECH_STACK.md](TECH_STACK.md))
- [x] Repo layout: `backend/` (Python + FastAPI), `web/` (Vite + React + TS)
- [x] Port backend from Node to Python (decision log in TECH_STACK.md)
- [x] Database schema + migrations (orders, sizes, milestones, updates, photos, reasons, warnings, date changes, buyers, units, users)
- [x] Normalised: step names in `plan_steps`, redundant `order_id` removed from `daily_updates` and `photos`, v0 databases migrated in place (version stored in `user_version`)
- [x] Our own order number (`LT-year-n`) generated at creation, the buyer's PO kept as typed and unique per buyer; colour name + Pantone + hex swatch
- [ ] Next schema change: add a migration step per version (v0 to v1 and v1 to v2 exist)
- [x] Seed from sample data (3 POs from brief) + synthetic history so run-rates exist
- [x] Design tokens + base layout (desktop office, phone supervisor)
- [x] Tamil / English i18n dictionary

## Phase 1 — Core build (must ship end to end)
### Order setup with TNA milestones  *(Must have #1)*
- [x] TNA template (milestones + production stages, offsets from ex-factory)
- [x] Create-order screen: PO, buyer, style, colour, size × qty grid, ex-factory, unit, template
- [x] Milestones generated back from ex-factory, editable before save
- [x] Changing any planned date writes an audit row with a reason *(constraint: compliance history)*

### Supervisor daily update  *(Must have #2)*
- [x] Phone login (phone + PIN), Tamil by default
- [x] "My orders" list for the supervisor's unit
- [x] Update screen: stage, today's quantity, photo, note (text or voice), send
- [x] Client-side photo compression (≤1280 px, JPEG ~0.7)
- [x] Offline outbox in IndexedDB, idempotent send with client UUID, retry on reconnect
- [x] Pending-count indicator ("2 waiting to send")

### Order board  *(Must have #3)*
- [x] Green / amber / red per order from the run-rate engine
- [x] Filters: buyer, unit, ship week
- [x] Sorted by trouble first; reads at a glance

### Delay warning — run-rate projection  *(Must have #4, the hard part)*
- [x] Pure engine: per-stage run rate, required/day, projected finish, pipeline chaining, projected ex-factory
- [x] Working-day calendar (Sunday off + holidays)
- [x] Shows its maths in the UI
- [x] Unit tests incl. the three sample POs
- [x] Warning lifecycle: generated → merchandiser confirms / dismisses → buyer sees confirmed only

### AI reason category  *(AI requirement)*
- [x] Local open-source classifier via Ollama (Llama 3 8B): Tamil/English → fixed English category + translation
- [x] Keyword fallback when Ollama is down or AI is switched off
- [ ] Eval script: labelled Tamil notes → accuracy per model (compare llama3, qwen2.5:7b, gemma2:9b)
- [x] Order detail shows original note beside translation; merchandiser can change category

### Buyer read-only link  *(Must have #5)*
- [x] Token link per buyer; only that buyer's orders
- [x] Milestones, progress %, photos, confirmed warnings, date-change history
- [x] Isolation tests (buyer A cannot read buyer B's orders, photos or exports)

## Phase 2 — Optional depth
- [x] Weekly status export per buyer — Excel  *(Must have #6)*
- [x] Print-styled PDF version of the weekly status
- [x] Mock "message buyer" outbox for confirmed warnings
- [x] Merchandiser can mark non-production milestones done (actual date)
- [x] Service worker app-shell caching (installable PWA)
- [ ] Server-side Tamil speech-to-text with faster-whisper (open source)

## Phase 2b — Found while testing (5 Nov)
- [x] Browser walkthrough of every screen (e2e/walkthrough.py) and offline-queue test (e2e/offline_test.py)
- [x] Readable dates in server-written reasons and buyer messages
- [x] Seed placeholder photos broke on "&" in stage names, fixed
- [x] Tamil floor glossary in the AI prompt (நூல் = thread, not "book")
- [x] npm scripts work from Windows cmd/PowerShell (scripts/py.cjs)
- [x] Demo and test guide (docs/DEMO_GUIDE.md)
- [x] Dark mode: follows device, toggle on every screen (system → light → dark), print stays light
- [ ] AI still mis-files some notes (thread → fabric). Build the labelled eval set and compare models

## Phase 3 — Hardening (pre-pilot)
- [ ] Mark an order shipped and record the actual ship date (without it the 8% → 5% late-shipment goal can't be measured)
- [ ] `/api/health` endpoint (database and Ollama reachable)
- [ ] Hash session tokens in the database (stored in plain text today)
- [ ] Move the app from the localStorage Bearer token to the `HttpOnly` cookie only (the cookie exists since login sets it; the app still sends the header)
- [ ] Upload checks: verify file signatures, send `X-Content-Type-Options: nosniff`, add a Content-Security-Policy
- [ ] Login lockout per IP as well as per login, persisted across restarts
- [ ] Reports: warning lead time, supervisor adoption (no update today), buyer link views
- [ ] Structured request logging with durations
- [x] Rate limiting on login
- [ ] Postgres migration path tested (only if the client wants it)
- [ ] Backups (DB + photos)
- [ ] Field test on a 2 GB Android phone over throttled 3G

## Constraints from the client
- Free / open-source models and services only; nothing paid.
- Python for the backend.

## Out of scope (per brief)
Costing, invoicing, export documents · fabric inventory · attendance and payroll.
