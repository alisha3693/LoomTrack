# LoomTrack — To-do

Status key: `[x]` done · `[~]` in progress · `[ ]` not started. Updated as work lands. Each item names the brief requirement it serves.

## Phase 0 — Foundation
- [x] Read brief, list constraints, write tech-stack decisions ([TECH_STACK.md](TECH_STACK.md))
- [x] Repo layout: `backend/` (Python + FastAPI), `web/` (Vite + React + TS)
- [x] Port backend from Node to Python (decision log in TECH_STACK.md)
- [x] Database schema + migrations (orders, sizes, milestones, updates, photos, reasons, warnings, date changes, buyers, units, users)
- [x] Normalised: step names in `plan_steps`, redundant `order_id` removed from `daily_updates` and `photos`, v0 databases migrated in place (version stored in `user_version`)
- [x] Our own order number (`LT-year-n`) generated at creation, the buyer's PO kept as typed and unique per buyer; colour name + Pantone + hex swatch
- [x] Merchandiser-built plan templates: create, copy, edit, retire; reusable step library; example dates in the editor; built-ins read-only
- [x] Order requests: buyer sends from their link, merchandiser asks / counters / accepts / declines, accepted request becomes an order; landing page
- [x] Design, pattern, print and fabric files on requests and orders: byte-level type check, per-file visibility to buyer and floor, files follow a request onto its order
- [x] Buyer-requested changes to an existing order (date and quantities) with Now vs Asked-for, never below pieces already made, audited; merchandiser can record a change taken by email
- [ ] Offer to re-plan the stage dates when an ex-factory change is applied (today they are not moved; the merchandiser edits them, each edit audited)
- [ ] A new order whose early milestones (fit and PP approval) fall before its creation date shows amber "Behind plan" straight away. Let the merchandiser mark them already approved when creating the order
- [ ] Virus scanning for uploaded files (none today); thumbnails and in-browser preview for more than images and PDF
- [x] Buyer accounts: the office creates a sign-in for each person at the buyer, with a one-time temporary password and a forced first change; reset and remove; the private link still works
- [ ] Buyer accounts: email the invitation and a self-service "forgot password" (today the office passes the temporary password on and resets by hand)
- [ ] Buyer accounts: retire the private link once everyone has an account, and give each account its own view of who may send and who may only read (today every account for a buyer can do everything the link can)
- [x] Navigation and flow between buyer and merchandiser: global search, "needs you" on both sides, grouped office navigation, per-order pages and tabs for the buyer, a conversation about live orders, whose-turn banners, previews of what the buyer sees (see docs/UX_GAPS.md)
- [x] Notifications outside the app: email (any SMTP server) and WhatsApp (Meta Cloud API) for 16 events, with consent for WhatsApp, retries, delivery reports, STOP, a settings page with a test button, and the templates ready for Meta's review (docs/WHATSAPP_TEMPLATES.md)
- [ ] Notifications: submit the templates to Meta and connect the client's number and mail server (needs their Meta business account and domain), then try it with a real buyer
- [ ] Notifications: Tamil versions of the WhatsApp templates; a buyer's WhatsApp reply added to the conversation (today only STOP is understood); a reminder when an approval has waited for days; a choice of events per person
- [ ] Buyer accounts: email the invitation and the temporary password through the new mail sender (the office still passes it on by hand)
- [x] Read receipts both ways (seen / not opened) for conversations, approvals and delay notices
- [x] A request's talk carried onto its order, a timeline per order (the separate inbox list and its read marks were removed on 9 Nov: nothing used them any more)
- [x] Buyer approvals (fit, pre-production, lab dip, packaging) with a trail, completing the plan step
- [x] View-only buyer accounts
- [x] Sidebar frame for both sides (tab bar on a phone), buyer documents page, buyer profile page for the office
- [ ] Shipping step after ex-factory: packing list, invoice and booking details, confirmed ship date (not started on purpose)
- [ ] Bulk quick actions on the requests list (accepting needs a unit and a plan, so it stays on the request page)
- [ ] Per-user saved views on the order board (there are fixed views: ships in 7 days, needs a reply, late materials)
- [x] Fabric (type, composition, GSM, note) on requests and orders; materials tracking with late and at-risk flags, buyer-supplied items, fabric in-house milestone kept in step
- [x] Capacity check before accepting a request or creating an order: per-unit stitching capacity, what is booked, the first workable ship date, confirmation required to go over; Units page
- [ ] Unit management screen: add units and job-work units (subcontractors for new processes such as embroidery); today units come from the seed and only their capacity can be edited
- [ ] Capacity: other stages (cutting, finishing), a quantity increase on an existing order, uneven spreading (front-loaded stitching), and feeding crowded units into the run-rate projection
- [ ] Materials: purchase quantities from a bill of materials per style, supplier lead times that suggest when to order, and an email reminder when something is late
- [ ] Next schema change: add a migration step per version (v0 to v1, v1 to v2 and v2 to v3 exist)
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
- [x] Tamil to English and English to Tamil with IndicTrans2 on this machine (GPU or CPU), one sentence at a time; the category comes from keyword rules over the note and its translation. Ollama is no longer used
- [x] Keyword fallback when the models are not downloaded or fail, or AI is switched off
- [x] Models downloaded with a Hugging Face token (`python -m loomtrack.ai.setup_models`), running on the GPU
- [ ] Check the translations on real supervisor notes (some phone recordings are still misheard or mistranslated; see the eval item below)
- [ ] Use the larger IndicTrans2 1B models for better translations: needs access requested on Hugging Face for `indictrans2-indic-en-1B` and `en-indic-1B`, then a switch in `ai/translate.py` (about 4 GB each, fits the 6 GB GPU in half precision)
- [ ] Eval script: labelled Tamil notes → translation and category accuracy
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
- [x] Installable on a phone: PNG and maskable icons, a complete manifest, an install page and banner (Android prompt, iPhone steps), a one-time Tamil welcome, offline start checked in a phone-sized browser, install link on the Units page (docs/SUPERVISOR_INSTALL.md)
- [ ] Try the install on one real Android phone and one iPhone (camera and microphone prompts inside the installed app, voice on iOS); have a Tamil speaker read the new Tamil wording
- [ ] Supervisors: self-service PIN reset, and a QR code for the install link
- [x] Server-side Tamil speech-to-text with faster-whisper (Whisper large-v3, local, free): a voice note with no typed text is written out, translated, classified, shown as "AI-written, check by listening"; the recording stays. The app's own reason words are given to Whisper as a spelling hint (`python -m loomtrack.ai.setup_speech`)
- [ ] Measure Whisper on real phone recordings from supervisors on the floor (noise, accents, short phrases); tune the hint and the silence filter from the results

## Phase 2b — Found while testing (5 Nov)
- [x] Browser walkthrough of every screen (e2e/walkthrough.py) and offline-queue test (e2e/offline_test.py)
- [x] Readable dates in server-written reasons and buyer messages
- [x] Seed placeholder photos broke on "&" in stage names, fixed
- [x] Tamil floor glossary in the AI prompt (நூல் = thread, not "book")
- [x] npm scripts work from Windows cmd/PowerShell (scripts/py.cjs)
- [x] Demo and test guide (docs/DEMO_GUIDE.md)
- [x] Dark mode: follows device, toggle on every screen (system → light → dark), print stays light
- [ ] AI still mis-files some notes (thread → fabric). Build the labelled eval set and compare models

## Phase 2c — Floor, office and buyer flow (8-9 Nov)
- [x] A stage is hidden from the supervisor, and refused by the server, until every earlier checkpoint and subcontract step before it is marked done by the office (no hardcoded step names; follows the plan order)
- [x] Daily target is fixed for the day, with a "left to do today" figure that counts pieces already sent, or a green "target done"
- [x] The delay notice draft quotes the supervisor's latest reason in English (his translated words); it follows new notes while still a draft
- [x] A new supervisor reason after a notice was sent creates a new draft in Plan and delay (once per new reason; a dismissed one is not offered again for the same reason)
- [x] "Supervisor reported" notification to the office the moment a reason is classified (email, plus the notifications page)
- [x] "Delay detected" email to every merchandiser when LoomTrack creates a new delay warning
- [x] Simpler screens: approvals, messages, materials and files hidden from the office and buyer sidebars and order tabs (the code and tables stay for now); the buyer sees progress and history only
- [x] "My details" for buyers and merchandisers: name, sign-in email and phone in one form (a new email asks for the current password; a buyer's number is their WhatsApp opt-in); the office no longer edits a buyer's email or number (the Notifications tab and the Edit form on the buyer's profile were removed, because the buyer changes them in My details)
- [x] WhatsApp permanent system-user token in place (checked valid, never expires); the number behind it is still Meta's test number
- [x] A test date for the whole app (`app_clock`) set from the supervisor's home screen, and a reset page that clears orders and floor data and keeps buyers, people and requests
- [x] Phone testing through a free Cloudflare quick tunnel (`cloudflared tunnel --url http://localhost:4000`); the address changes each time
- [x] Removed the hidden buyer approvals, the conversation about a live order and materials tracking: routes, services, screens, tables (dropped on open, schema v18) and their tests. Design and other files on requests and orders stay (buyers submit designs with a request)
- [ ] Tamil wording I wrote (target left, target done, welcome) needs a Tamil speaker's review
- [ ] A new email or phone number is not verified (no code sent to it); needs the mail and WhatsApp senders to be live first
- [ ] A buyer company shares one WhatsApp number; per-person numbers if the client wants them
- [ ] A merchandiser's phone number is stored and shown on My details but is not used anywhere yet; office alerts are email only (WhatsApp for the office would need new Meta templates)
- [x] The demo addresses no longer use a real-looking domain: `companya.in` became `companya.example` (the `.example` ending can never be delivered). Put real addresses in My details or the buyer's Edit form before real use
- [x] HOW_IT_WORKS and DB_SCHEMA brought up to date (stage lock, fixed daily target, voice-to-text, delay drafts per reason, shipping, reports, weekly email, My details, test date, versions 14 to 18)

- [x] Shipping and reports added (schema v17: `orders.shipped_date`, `orders.production_complete_at`, `warnings.warned_on`, `buyer_visits`)
- [ ] Warnings raised before 9 Nov have no recorded raise date, so their lead time uses the real calendar date; new ones use the app date

- [x] The browser scripts in `e2e/` match the current screens: `journey.py` was rewritten (24 checks across supervisor, office and buyer, run on a fresh seed), `walkthrough.py`, `offline_test.py` and `pwa.py` pass, and `a11y.py` lists the current pages (the axe scan itself still needs a re-run after the re-theme)
- [x] Dead code removed (9 Nov): the inbox list and the read marks (endpoints, service, `thread_reads` table, web calls), the office's edit of a buyer's email switch and WhatsApp number (buyers do it in My details), an unused domain copy of the earliest-fit search, unused helpers and imports, and about 40 unused style rules. Backend tests 234 to 227 (the removed code's tests); schema version 20
- [x] Buyers now see the floor's photos on their order (the server already sent them, the page never showed them)

## Phase 3 — Hardening (pre-pilot)
- [x] Mark an order shipped with the actual ship date (button on the order, buyer told by email, order leaves the board and floor, ex-factory step marked done); the office is told once when production is complete
- [x] `/api/health` endpoint: database reachable, uploads writable, translation and speech state, time of the last backup; 503 when the database or uploads fail. Point an uptime monitor at it
- [x] Session tokens are stored as their SHA-256 (schema v19); sessions already in the database were hashed in place, nobody was signed out
- [x] The app uses the `HttpOnly` cookie only: login no longer returns the token, nothing is kept in localStorage (an old `lt.token` is deleted), the app sends no header. A cookie session is refused on a change the browser says came from another site (`Sec-Fetch-Site`)
- [x] Upload checks: supervisor photos and voice notes are now identified from their first bytes (JPEG, PNG, WebP; WebM, Ogg, MP4 audio) and stored under the real type; design files already were. Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and a Content-Security-Policy (scripts only from this server plus the one inline theme script by hash; HSTS over HTTPS)
- [x] Login lockout per sign-in name (5 wrong tries, 5 minutes) and per address (20 wrong tries in 15 minutes, locked 15 minutes), kept in the database so a restart does not clear it. The address behind a tunnel or proxy on this machine is read from `CF-Connecting-IP` / `X-Forwarded-For`
- [x] Reports page: shipped on time against the 8% to 5% goal, how many days ahead the first warning came (goal 14), supervisors who sent updates today and this week, buyer page views
- [ ] Reports: a per-month trend, export to Excel, and a shipped-orders view on the board; buyer page views count opens of the page, not who looked (a baseline of buyer status emails before LoomTrack is needed to show the 60% drop)
- [x] Request log: one JSON line per request (time, request number, method, path with the private link hidden, status, milliseconds, address) to the console and `data/logs/access.log` (5 MB, 5 files); slow requests (over 1 s) and errors stand out; an unhandled error is logged with its traceback and the person sees only the request number. No bodies, query strings, passwords or sessions are logged
- [x] Rate limiting on login
- [ ] Postgres migration path tested (only if the client wants it)
- [x] Backups: the database is copied about once a day (SQLite online backup, integrity-checked, newest 14 kept) and uploaded photos, voice notes and files are mirrored, into `data/backups/`. Run one now with `python -m loomtrack.backup`; `LOOMTRACK_BACKUP=off` stops it
- [ ] Put the backups where losing this computer does not lose them (`LOOMTRACK_BACKUPS` on another drive or a synced folder), and try a restore on a clean machine once
- [ ] Point an uptime monitor at `/api/health` and decide who reads `data/logs/access.log`
- [ ] Field test on a 2 GB Android phone over throttled 3G

## Constraints from the client
- Free / open-source models and services only; nothing paid.
- Python for the backend.

## Out of scope (per brief)
Costing, invoicing, export documents · fabric inventory · attendance and payroll.
