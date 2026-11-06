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

## Order requests: from a buyer's ask to an order (`services/requests.py`)

1. **The buyer** opens their private link (or pastes it on the landing page) and sends an **order request**: their PO number, style, colour (name, optional Pantone and hex swatch), quantities by size and the ex-factory date they need.
2. **The merchandiser** sees it under **Requests** (a count shows in the top bar). They can **ask a question**, **propose another date**, **accept** it into an order, or **decline** it (with a reason).
3. The **status says whose turn it is**: `submitted` is the merchandiser's; `query` and `countered` are the buyer's. When the buyer answers or agrees, it returns to `submitted`.
4. **Agreeing** to a proposed date updates the request's date. **Accepting** creates the order, with exactly the quantities, colour and date the buyer asked for or agreed to. The merchandiser picks the production unit and the plan template.
5. Everything said or decided is a row in `request_messages`, which the buyer sees too. A copy of each merchandiser message goes to the (mock) sent-messages list.

### Changes to an order that already exists

- From an active order on their page, the buyer can **Ask for a change**: a new ex-factory date, new quantities by size, or both, with a reason. It travels the same conversation as a new request (question, counter-proposed date, agree, accept, decline, withdraw).
- While it is open the merchandiser sees **what the order says now beside what is asked for**. **Apply the change** updates the order in one step: the new ex-factory date goes into the order's date history (naming the request and the reason), the quantities are replaced, and the order is re-projected. The quantity cannot go below what the furthest stage has already made.
- If the buyer asks by email or phone, the merchandiser uses **Record a change** on the order: the same trail, applied at once, and the buyer sees it under their requests.
- One open change per order at a time. The planned dates of individual steps are **not** moved automatically; the merchandiser reviews them (each edit needs a reason and is logged).

A buyer reaches only their own requests: another buyer's request is "not found". The buyer link can now *submit and answer* requests, but it still cannot read anything belonging to another buyer. Open requests per buyer are capped at 25.

## Files: designs, patterns, print artwork, fabric (`services/attachments.py`)

- The **buyer** can add files to a request while it is open (when sending it, or later). The **merchandiser** can add files to a request or to an order.
- A file is **checked by its own bytes**, not its name or the type the browser claims. PDF, JPG, PNG, WebP, GIF, TIFF, Photoshop, ZIP (including Excel and Word) and DXF patterns are accepted; HTML, SVG, scripts and programs are refused. It is stored under a random name, capped at 15 MB, and never opened or unpacked by the server.
- **Who sees a file** is decided per file. The buyer's own uploads stay visible to that buyer. Our files are private until the merchandiser ticks **Buyer**. Ticking **Floor** lets supervisors open it, but only on orders their unit works on.
- When a request is **accepted**, its files move onto the new order. Buyers see their files on their order page, supervisors under "Files for this order" on a stage screen.
- Office and floor links are short-lived signed links; buyers open files through their own link, scoped to their own requests and orders.

## Finding your way: search, "needs you" and the conversation

- **Office navigation.** The bar keeps to daily work: Orders, Requests (with the count waiting for you), Buyers. Rarely changed things (plan templates, units and capacity) sit under **Set up**. **+ New order** is an action, not a page. **Search** (press `/` or Ctrl+K anywhere) finds an order, request or buyer by PO, our LT number, request number, style, colour or buyer name, and opens it with Enter (`services/search.py`).
- **Needs you** is the top of the order board: buyer requests waiting for your answer, buyer messages to answer, delay warnings to review, orders with late materials. One quiet list, one line each, and the same pattern on the buyer's overview. Each line goes straight to the thing (or filters the board to those orders), and "nothing is waiting for you" is said plainly when that is true.
- **Order page.** Breadcrumbs, a link from the buyer's name to all their orders, **What the buyer sees** (opens the buyer's own page for this order), and five tabs (Overview, Conversation, Materials, Files and requests, History and floor) that the address remembers (`?tab=`). A pending delay warning and "the buyer is waiting for your reply" sit above the tabs whichever one is open.
- **Request page (office).** The decision (accept, ask, propose another date, decline) is at the top; the request and conversation are in the middle; the side panel shows the buyer's live orders and how they are going, so the answer can take that into account.
- **Conversation about an order** (`services/order_messages.py`). A buyer can write to the merchandiser from any order (anything that is not a change of date or quantity, which stays a *change request*), and the merchandiser answers in the same thread. It is append-only, capped at 500 messages and 2,000 characters each, and scoped by buyer like everything else: another buyer's order and a cancelled order are simply "not found". The merchandiser's reply also lands in the buyer's inbox (mock email). The board and the order page show who owes a reply.
- **Buyer navigation.** A header with Overview, Orders and Requests (a count when their answer is needed) and **+ New request**. The **overview** starts with **Needs your attention**: a countered date to agree, a question to answer, a new reply, a delay notice, items the buyer must supply. Then summary tiles, a compact orders list and their requests. Each order has its own page with tabs (Progress, Conversation, Materials, Files and photos, Date history); a request page begins with whose turn it is and the one thing to do. "New reply" dots are remembered in the browser only.

## Fabric and materials (`services/materials.py`, `domain/materials.py`)

- **Fabric** (type, composition, GSM, a note) is optional on a buyer's request and on a new order, and goes from the request onto the order when it is accepted. An order created with fabric starts with a **Main fabric** line under Materials. The buyer sees type, composition and GSM on their order; the note stays internal.
- **Materials** are the lines an order needs: fabric, trims, packing. Each is *not ordered*, *ordered* (with an expected date) or *received* (with the date), may be supplied by the buyer (free issue, such as their labels), and names the plan step that needs it. **Add the standard list** adds the usual eight (main and rib fabric, thread, labels, hangtag, polybag, carton).
- **When it is needed** is read from that step on every request: when a stage starts, or when a milestone is due. Move a step's date and every line that depends on it moves too.
- **Late, at risk, on track**: late if the expected date is after the need date, the expected date has passed without arrival, or it is needed now with no date; at risk if it is not ordered and needed within 14 days, or ordered with no date and needed within 7; otherwise on track. The board shows "N materials late" beside the delay status. **This does not change the delay projection**, which stays driven only by the floor's numbers.
- **Fabric in-house**: when every fabric line is received, that plan milestone is marked done on the latest receipt date; taking a received fabric line back unmarks it. Both go into the date history.
- **What the buyer sees**: for each line only its name, whether it has arrived and when. No supplier, quantity, expected date or lateness. A line the buyer supplies that has not arrived says "We are waiting for this from you".

## Capacity check (`services/capacity.py`, `domain/capacity.py`)

- Each of our units has a **daily stitching capacity** (pieces a day), set on the Units page. Stitching is the step measured, because it decides how many pieces a unit can turn out.
- **What is booked**: every active order with stitching at that unit, spread evenly over the working days it has left (Monday to Saturday, minus holidays), using the pieces still to be made. A stitching window that has already passed is spread over the next five working days.
- **The new order** is spread over the stitching window its plan template gives it for that ship date. Utilisation = (already booked + this order) / (capacity x working days in the window). Up to 85% is *room to spare*, up to 100% *tight*, above that *over capacity*; a window that has already passed is *no time*. A unit with no capacity set is not checked.
- **When it is asked**: in the Accept dialog for a buyer's request and on the New order form, side by side for every unit. Picking a unit that would be over (or has no time) needs a tick on "I want it anyway"; the server refuses without it (`overCapacityOk`). It also offers the first ship date the unit could take (searched four months ahead), with a button that opens the counter-proposal with that date, or says no date helps when the window is simply too short for the quantity.
- Not covered: cutting, finishing and packing capacity; a quantity increase on an existing order; the run-rate engine still treats each order on its own.

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
- **Buyer accounts.** A buyer's people can also sign in with an email and password the office creates (Buyers & exports → *Add a person*). The office sees a random temporary password once and passes it on; it is stored only as a hash. The first sign-in forces a new password (the server refuses the buyer pages until it is changed). Signed in, the buyer uses `/b/me`: the same pages and the same endpoints as the link, with the word `me` in place of the token and the buyer id taken from the session instead. Changing or resetting a password signs the other devices out; removing the account ends its sessions. Staff and buyer accounts are told apart by role, so a buyer can never reach an office or floor endpoint.

## The date-change trail

Changing ex-factory, or any planned date, requires a reason and writes a row to `date_changes` in the same transaction as the change. Database triggers refuse any UPDATE or DELETE on that table, so the history is append-only even if someone edits the database directly. Marking a milestone done or undone is logged too. The same history shows on the buyer link.

## The screens and where their data comes from

| Screen | URL | Main endpoint(s) |
|---|---|---|
| Login | `/login` | `POST /api/auth/login` |
| Order board | `/m` | `GET /api/m/board?buyer=&unit=&week=` |
| New order | `/m/orders/new` | `POST /api/m/plan-preview`, `POST /api/m/orders` |
| Order detail | `/m/orders/:id` | `GET /api/m/orders/:id`, warning confirm/dismiss, date changes, reason override |
| Materials (on the order) | `/m/orders/:id` | `GET`/`POST /api/m/orders/:id/materials`, `POST .../materials/standard`, `PATCH`/`DELETE /api/m/materials/:id` |
| Units and capacity | `/m/units` | `GET /api/m/units`, `PATCH /api/m/units/:id`, `POST /api/m/capacity/check` |
| Buyers & exports | `/m/buyers` | `GET /api/m/buyers`, `/exports/weekly`, `/outbox` |
| Requests | `/m/requests`, `/m/requests/:id` | `GET /api/m/requests?filter=`, `POST /api/m/requests/:id/query`, `/counter`, `/accept`, `/decline` |
| Buyer: new request | `/b/:token/requests/new` | `POST /api/b/:token/requests` |
| Buyer: one request | `/b/:token/requests/:id` | `GET /api/b/:token/requests/:id`, `POST .../reply`, `.../agree`, `.../withdraw` |
| Files | on request, order and stage pages | `POST /api/b/:token/requests/:id/attachments`, `POST /api/m/requests/:id/attachments`, `POST /api/m/orders/:id/attachments`, `PATCH`/`DELETE /api/m/attachments/:id`, `GET /api/s/orders/:id/attachments`, `GET /api/b/:token/attachments/:id` |
| Buyer: ask for a change | `/b/:token/orders/:id/change` | `POST /api/b/:token/orders/:id/amendments` |
| Record a change (office) | button on the order page | `POST /api/m/orders/:id/amend` |
| Home page | `/` (signed out) | none: explains the product, sign in, or paste a buyer link |
| Sign in | `/login` | `POST /api/auth/login`, `GET /api/auth/me` (all three roles) |
| Change password | `/account/password` | `POST /api/auth/password` |
| Buyer: own page | `/b/me` (and `/b/me/...` for requests and changes) | the `/api/b/me/...` endpoints, signed in |
| Buyer sign-in accounts (office) | Buyers & exports | `POST /api/m/buyers/:id/logins`, `POST /api/m/buyer-logins/:id/reset`, `DELETE /api/m/buyer-logins/:id` |
| Templates | `/m/templates`, `/m/templates/new`, `/m/templates/:id` | `GET/POST /api/m/templates`, `PUT /api/m/templates/:id`, retire/restore, `POST /api/m/templates/preview`, `PATCH /api/m/steps/:code` |
| Supervisor home | `/s` | `GET /api/s/orders` (cached on the phone) |
| Supervisor update | `/s/update/:id` | `POST /api/s/updates` (through the offline queue) |
| Buyer: overview | `/b/:token` | `GET /api/b/:token`, `GET /api/b/:token/requests` |
| Buyer: orders | `/b/:token/orders` | `GET /api/b/:token` |
| Buyer: one order | `/b/:token/orders/:id?tab=` | `GET /api/b/:token`, `GET`/`POST /api/b/:token/orders/:id/messages` |
| Buyer: requests | `/b/:token/requests` | `GET /api/b/:token/requests` |
| Office: search | `/` or Ctrl+K anywhere | `GET /api/m/search?q=` |
| Order conversation (office) | `/m/orders/:id` | `GET`/`POST /api/m/orders/:id/messages` |

Live API docs with every endpoint: http://localhost:4000/api/docs

## Data model (SQLite)

```
buyers ──< orders >── units        attachments hang off a request, an order, or both
   │
   └──< order_requests ──< request_sizes, request_messages   (a buyer's asks; accepted ones point at an order)
             │ ├──< order_sizes
             │ └──< milestones >── plan_steps    one order's plan; each row points at a step
             │        └──< daily_updates ──< photos
             │                  └── issue_reasons    (AI result + human decision, kept apart)
             ├──< warnings            pending / confirmed / dismissed / superseded / resolved
             └──< date_changes        append-only audit trail
users ──< sessions          outbox_messages (mock buyer emails)
```

`plan_steps` holds each step once (its English and Tamil name, and whether it is a stage or a milestone), so an order's `milestones` rows only store that order's dates. A *stage* is a production step with quantities (cutting, printing, stitching, washing, finishing, packing). A *milestone* is a dated checkpoint (sample approval, inspection, ex-factory). Both live in `milestones`, told apart by `kind`.

## Where things are in the code

```
backend/loomtrack/
  main.py              app setup, error format, serves the built web app
  config.py            database path, holidays, AI model, "today" (pinned for the demo)
  db.py                schema, in-place migration from the old layout, transaction helper
  security.py          password hashing, session tokens, signed media URLs
  deps.py              "who is signed in", role guards
  domain/              no database, no web: calendar, runrate, tna templates, reason list
  services/            orders (projection + warnings), templates (load/validate/save), requests (order requests), attachments (files), buyer_view, export (Excel)
  routes/              auth, merchandiser, templates, requests (both sides), attachments, supervisor, buyer
  ai/classifier.py     Ollama call + keyword fallback
  seed.py / explain.py demo data / prints the run-rate maths for every order
backend/tests/         124 tests
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
- Materials are tracked by hand; nothing reads a purchase order or a supplier's confirmation. The capacity check models stitching only, with even spreading, and assumes the unit's stated capacity is real.
- Voice: the original audio is always kept for the merchandiser. The live transcript uses the phone browser's speech service where available; local Whisper is on the to-do list.
- The run rate is a 7-day average and doesn't model capacity shared between orders on one line (see RUN_RATE.md, "Known limits").
- One SQLite file is right for this size. Postgres is the path if the client wants managed backups.
