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
              └─ ai/            voice → Tamil text (Whisper) → English (IndicTrans2) → reason category
                       |
              SQLite file + uploads folder (photos, voice)
                       |
              Whisper and IndicTrans2 on the same machine (GPU or CPU), optional
```

Three kinds of user hit three separate sets of endpoints, and each set is guarded differently:

| Who | URL prefix | How they're identified |
|---|---|---|
| Merchandiser | `/api/m/` | Signs in with email + password → a session in an `HttpOnly` cookie (the database keeps only its hash) |
| Supervisor | `/api/s/` | Signs in with phone + PIN → session token, tied to one unit |
| Buyer | `/api/b/<token>/` | The random token in the link *is* the credential |

## The main loop: one supervisor update

1. **On the phone** the supervisor enters pieces, optionally a photo and a note (typed, or spoken). The photo is shrunk to ≤1280 px first.
2. **The update is saved to the phone's own storage (IndexedDB) before anything is sent.** It gets an ID generated on the phone. This is the offline queue.
3. **The app tries to send it** to `POST /api/s/updates`. If there's no network, it stays queued and retries when the phone reconnects, when the app comes to the foreground, and every 30 seconds.
4. **The server checks it:** the stage must belong to this supervisor's unit, the order must be active, the date can't be in the future or older than 7 days, the running total can't exceed the order quantity by more than 5%, and a stage can't pass what the stage before it (in our own units) has finished: stitching can't go past what has been cut. A stage that is still **locked** is refused (see *What the supervisor sees*).
5. **If the ID has been seen before, the server says "already have it" and does nothing.** That's what stops a retry from double-counting pieces.
6. **It's stored:** one row in `daily_updates`, one in `photos` if there's a photo, the recording if there is one, and one empty row in `issue_reasons` if there's a note or voice.
7. **The order is re-projected right away** (next section), so the board is current.
8. **If there's a note or a recording, the phone doesn't wait for the AI.** The server answers "sent" and does the rest in the background (see *Voice notes and the reason*): it writes out a recording as Tamil text when nothing was typed, translates and classifies the note, re-projects the order once more (the reason feeds the suggested buyer message) and tells the office a reason arrived.
9. **Offline or online makes no difference to the server.** An update that waited in the phone's queue is handled exactly like one sent at once.

### What the supervisor sees

- **A stage is hidden until the office has marked every earlier checkpoint done** (fit sample, fabric in-house, inspections ... whatever comes before it in the plan, and any earlier job-work step such as printing). The rule follows the order of the plan, not any step's name, so it holds for every order and every template. The server refuses an update to a locked stage with "Waiting for the office to mark done: ...". A stage that is not due, has no pieces ready from the stage before, or is finished is hidden as well.
- **A daily target that does not move.** The target is the pieces left at the start of the day over the working days left, and stays the same all day however many pieces are entered. Beside it the screen says **how many are left to do today**, or a green "target done".
- **The app date** can be set by hand for testing (`app_clock`, on the supervisor's home screen); the office sees a banner while it is set.

## Order requests: from a buyer's ask to an order (`services/requests.py`)

1. **The buyer** opens their private link (or pastes it on the landing page) and sends an **order request**: their PO number, style, colour (name, optional Pantone and hex swatch), quantities by size and the ex-factory date they need.
2. **The merchandiser** sees it under **Requests** (a count shows beside it in the sidebar). They can **ask a question**, **propose another date**, **accept** it into an order, or **decline** it (with a reason).
3. The **status says whose turn it is**: `submitted` is the merchandiser's; `query` and `countered` are the buyer's. When the buyer answers or agrees, it returns to `submitted`.
4. **Agreeing** to a proposed date updates the request's date. **Accepting** creates the order, with exactly the quantities, colour and date the buyer asked for or agreed to. The merchandiser picks the production unit and the plan template.
5. Everything said or decided is a row in `request_messages`, which the buyer sees too. Each step also goes to the buyer by email, and by WhatsApp if they agreed (see *Messages outside the app*).

### Changes to an order that already exists

- From an active order on their page, the buyer can **Ask for a change**: a new ex-factory date, new quantities by size, or both, with a reason. It travels the same conversation as a new request (question, counter-proposed date, agree, accept, decline, cancel by the buyer).
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

## Finding your way: the sidebar, search and "needs you"

- **One frame on every signed-in page** (`components/AppShell.tsx`). A sidebar with line icons, labels and counts: for the office Orders, Requests, Notifications, Buyers, Reports, then a **Set up** group (plan templates, units and capacity, email and WhatsApp); for the buyer Overview, Orders, Requests, Notifications. The one primary action (**New order** / **New request**) and **Search** sit at the top; the account (theme, sign out, and for buyers the password) at the bottom. The sidebar collapses to icons (and remembers it), and on a phone becomes a tab bar with a **More** sheet. Counts come from `/api/m/meta` and `/api/b/:token/badges` and refresh when something is read or decided. **Search** (press `/` or Ctrl+K anywhere in the office) finds an order, request or buyer by PO, our LT number, request number, style, colour or buyer name, and opens it with Enter (`services/search.py`).
- **Needs you** is the top of the order board: buyer requests waiting for your answer, delay warnings to review, delay notices the buyer has not acknowledged. One quiet list, one line each, and the same pattern on the buyer's overview. Each line goes straight to the thing (or filters the board to those orders), and "nothing is waiting for you" is said plainly when that is true.
- **Order page.** Breadcrumbs, a link from the buyer's name to all their orders, **What the buyer sees** (opens the buyer's own page for this order), and three tabs (Overview, Plan and delay, History and floor) that the address remembers (`?tab=`). A pending delay warning, the "production is complete" notice and the shipped notice sit above the tabs whichever one is open. Overview is the short version: the dates, why the date is where it is, whether the buyer has seen the delay notice, and the latest things that happened. **Mark shipped** is in the page's actions (see *Production complete and shipped*).
- **Request page (office).** One column: the decision (accept, ask, propose another date, decline) at the top, then the request, the conversation, the buyer's live orders and how they are going (so the answer can take that into account), and the files. The requests list says in a line what happens next on each one.

## Delay-notice receipts (`services/notices.py`)

- **Delay notices have a receipt.** When the buyer opens a confirmed notice it is *seen*; they can then **Acknowledge** it, optionally with a note. The note is kept on the notice (`warnings.buyer_ack_note`), shown on the order's timeline and emailed to the office. The order page shows "Not opened by the buyer yet", "Opened ... not acknowledged yet" or "Acknowledged ...", and the board lists notices nobody has acknowledged.

## Plan templates and checkpoints

- **Plan templates** follow a buyer's usual knit time-and-action calendar, always in due order: fit sample, lab dip / colour, PP sample, fabric in-house, fabric inspection and shrinkage test, trims in-house, then cutting (printing), stitching, inline inspection, (washing), finishing, packing, final inspection and ex-factory. The merchandiser writes only the English name of a new step. The Tamil name supervisors see is made once, when the step is saved, from a glossary of floor words and then the local translation model (the English name stays if neither can). They are drawn as a chart (bars for production stages, diamonds for milestones) on the templates page and in the editor, and a stage that ends before it starts is refused. A new stage's **process** (cutting, stitching, printing, washing, ...) is chosen from a list: it decides which unit does the stage and which stage the capacity check measures, so the editor refuses a near-miss spelling of a known process. In the editor every production stage has a typed **Starts** and **Due** (days before ex-factory) and they are completely free: stages may overlap, or leave gaps, however the factory really works. The only rule is that a stage starts before it is due. The built-in plans are set up so cutting, (printing), stitching, (washing), finishing and packing each start the day after the one before it ends (lead time about 68 to 81 days from fit sample to ex-factory).
- **Sample approvals are checkpoints the merchandiser marks done** (fit sample, lab dip / colour, PP sample). The app does not ask the buyer to approve anything: the approval happens by email or phone, and the office records it on the plan, which writes it into the date history. Until the early checkpoints are marked, the supervisor does not see the stages after them.

## View-only buyer accounts

A buyer account is created with **Full access** or **View only** (and the office can switch it later). A view-only account can read everything its buyer can, and every action that changes something (send a request or a change, acknowledge a delay notice, upload) is refused by the server with a plain message; the screens hide the buttons. A private link always has full access, as before.

## The order timeline and the buyer's pages

- Each order has a **timeline** of what happened and who did it (`services/activity.py`), assembled from the date history, the request's steps and delay notices (with the buyer's acknowledgement note). Nothing extra is stored. The buyer's version leaves out what is internal (dismissed warnings, who in the office changed what, whether the buyer opened a notice).
- **Buyer pages.** The **overview** starts with **Needs your attention**: a countered date to agree, a question to answer, a delay notice to acknowledge. Then **Coming up** (the next ship dates, with progress) and open requests. **Orders** is a sortable table with search. Each order has its own page with two tabs (Progress, History), and a shipped order shows its ship date. A request page begins with whose turn it is and the one thing to do. The **new request** form asks for the essentials first (PO, style, colour, date, quantities); fabric, colour reference, notes and files are behind one optional section. The buyer's **My details** (account menu) changes their name, sign-in email and WhatsApp number on one page.

## Fabric

**Fabric** (type, composition, GSM, a note) is optional on a buyer's request and on a new order, and goes from the request onto the order when it is accepted. The buyer sees type, composition and GSM on their order; the note stays internal. There is no materials tracking: whether fabric and trims have arrived is not recorded in the app, and the *Fabric in-house* checkpoint is marked by the merchandiser like any other.

## Capacity check (`services/capacity.py`, `domain/capacity.py`)

- Each of our units has a **daily capacity for each stage we do ourselves** (cutting, stitching, finishing, packing: pieces a day), set on the Units page. Milestones and job work (printing, washing) are not counted. Stitching is stored on the unit, the other stages in `unit_capacity`. A stage with no capacity set is listed as "not set" and never blocks.
- **What is booked**: every active order with stitching at that unit, spread evenly over the working days it has left (Monday to Saturday, minus holidays), using the pieces still to be made. A stitching window that has already passed is spread over the next five working days.
- **The new order** is spread over the window its plan template gives each stage for that ship date; a unit is as full as its tightest stage. Utilisation = (already booked + this order) / (capacity x working days in the window). Up to 85% is *room to spare*, up to 100% *tight*, above that *over capacity*; a window that has already passed is *no time*. A unit with no capacity set is not checked.
- **When it is asked**: in the Accept dialog for a buyer's request and on the New order form, side by side for every unit. Picking a unit that would be over (or has no time) needs a tick on "I want it anyway"; the server refuses without it (`overCapacityOk`). It also offers the first ship date the unit could take (searched four months ahead), with a button that opens the counter-proposal with that date, or says no date helps when the window is simply too short for the quantity.
- Not covered: a quantity increase on an existing order; the run-rate engine still treats each order on its own.

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
| Buyer was already told, and it's no worse, and the supervisor's reason is the one they were told | Nothing new (the buyer isn't spammed) |
| Buyer was told, and the supervisor has since given a *different* reason | A new **pending** draft with the new reason, for the office to review and send (a draft you dismissed is not offered again for the same reason) |
| Order recovers to green | Pending warning → *superseded*; confirmed warning → *resolved* |

A **new** warning (not an update to a draft) also emails every merchandiser "Delay detected on PO ...", once. The warning remembers the app date it was raised on and the reason it was written around (`warned_on`, `reason_category`).

## Production complete and shipped (`services/shipping.py`)

- When the last production stage reaches the order quantity, every merchandiser is emailed once ("Production complete on PO ..."). The order page shows a banner and the **Mark shipped** button turns blue.
- **Mark shipped** asks for the day the order left the factory (not in the future) and shows "due ...: 2 days late" before you confirm. The order becomes `shipped`: it leaves the live board and the supervisor's list, the ex-factory checkpoint is marked done on that date, open warnings are closed, and the buyer is emailed. The shipped date against the ex-factory date is what the *Shipped on time* report counts.

## Reports (`services/reports.py`)

The office **Reports** page measures the client's goals from what the app already records: how many shipped orders were late (against 5%, where the client is at 8% today), how many days ahead the first delay warning came (against 14), which supervisors sent updates today and in the last seven days, and how often each buyer opened their own page (`buyer_visits`, a counter per buyer and day, never what was looked at).

## The weekly status email (`services/weekly.py`)

From a chosen day and hour (Monday 08:00 unless `LOOMTRACK_WEEKLY_DAY` and `LOOMTRACK_WEEKLY_HOUR` say otherwise; `LOOMTRACK_WEEKLY=off` stops it) each buyer's people get one email a week with a line per order and the buyer edition of the Excel file attached. The outbox is the record of what was queued, so a restart the same morning sends nothing twice. It shows only that buyer's orders and never the internal green, amber or red: a delay reaches a buyer only after a merchandiser confirms it.

## My details (`/api/auth/profile`)

Buyers and merchandisers change their own name, sign-in email and phone on one page. A new email needs the current password and signs the other devices out. A buyer's number is the company's WhatsApp number and typing it records the agreement to receive messages; a merchandiser's phone is only a contact number. Supervisors sign in with their phone number, which the office changes on the Units page. The office does not change a buyer's email or number: the buyer does it here. On the buyer's profile the office can add a person, set full or view-only access, issue a new temporary password and remove a sign-in.

## Cancelling an order (`cancel_order` in `services/orders.py`)
When an order cannot go ahead (a delay that cannot be recovered, say), the merchandiser uses **Cancel order** on the order page and writes one reason. It is a single step with no discussion: the order's state becomes `cancelled`, its open delay notices are closed, and the buyer gets an email with the reason. WhatsApp is not used (the three approved templates are kept for request received, request accepted and delay notice). The buyer's page lists the order under *Cancelled* with the reason, and the link in the email opens it. A cancelled order cannot be reopened.

## The notifications page (`services/feed.py`)
Both sides have a **Notifications** page that lists what the app has told them, newest first and grouped by day. Nothing new is stored for it: every email is already recorded in `outbox_messages`, and the page shows one entry per event (not per recipient). Buyers see what their merchandiser sent them; the office sees what buyers did (new requests, answers, supervisor reasons, detected delays, completed production, acknowledged delay notices). The sidebar badge counts entries newer than the last visit, kept in `feed_reads`. The setup page for email and WhatsApp is called *Email and WhatsApp* under Set up. Floor reasons from supervisors show up here immediately as "Supervisor reported".

## Reset test data (`services/reset.py`)
On a test machine only: with `LOOMTRACK_ALLOW_RESET=1` in `backend/.env`, *Reset test data* appears under Set up. After typing RESET it saves a copy of the database to `data/backups/`, then removes all orders and everything under them (supervisor updates, photos, delay notices), change requests, uploaded order files and the sent-message record. Buyers, sign-ins, units, plan templates and the buyers' requests stay; a request that had become an order goes back to *submitted* so it can be accepted again. Without the setting the page and its endpoints do not exist.

## Warnings and the confirm-before-buyer rule

```
 engine says "late"  →  PENDING  →  merchandiser edits + confirms  →  CONFIRMED  →  buyer sees it
                            |
                            └→ merchandiser dismisses → DISMISSED  (buyer never sees it)
```

A warning is invisible to buyers until a merchandiser confirms it. Confirming also queues the message to the buyer in `outbox_messages` (email, and WhatsApp for a buyer who agreed), shown under **Buyers, Sent messages**. This is deliberate: the AI or the engine can be wrong, and a delay notice to a UK buyer is a business decision.

## Voice notes and the reason (`ai/speech.py`, `ai/translate.py`, `ai/classifier.py`)

- **Voice to text.** A recording with no typed note is written out as Tamil text on this machine by Whisper (large-v3, run by faster-whisper, free, about 3 GB, downloaded once with `python -m loomtrack.ai.setup_speech`). It is given the app's own Tamil reason words as a spelling hint, because Whisper otherwise drops letters in them. Silence and noise give no text. The text is marked "voice, written out by AI: check by listening" and the recording stays for the merchandiser to play. Without the model, a voice note stays a recording.
- **Translation.** The Tamil note is translated to English by IndicTrans2 (two small open models, one for each direction, MIT licence), one sentence at a time, on the GPU when there is one and on the CPU otherwise. The category is then chosen by the keyword rules from the note and its translation together, from a fixed list of 11 reason categories. So the category is only ever a guess, and the confidence number never goes above 0.6.
- **Both the AI's answer and the human's answer are stored, in separate columns** (`ai_category` and `final_category`). When a merchandiser changes the category, the AI's original guess stays visible ("AI said ..."), and the delay draft's message follows the change.
- A later AI run never overwrites a category a person set by hand.
- If the models are not downloaded, or fail, the keyword rules alone give the first guess and the note has no translation. The record says which one produced it (`ai_source`) and keeps any error. The account menu shows **Translation on** or **Keywords only**, and why. The same translation models write a suggested Tamil name for new plan steps (after a glossary of floor words).
- **Telling the office.** Once a reason is classified (and is not "no issue"), every merchandiser is emailed "Supervisor reported on PO ..." with the category, the English translation and the supervisor's words.

## What buyers can see (`services/buyer_view.py`)

The buyer endpoints never reuse the office responses. They build a separate response field by field:

- **Included:** PO, style, colour, sizes, quantities, ex-factory, shipped date, progress per stage, milestones, photos (unless hidden), date-change history, and *confirmed* notices.
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
| Units and capacity | `/m/units` | `GET /api/m/units`, `PATCH /api/m/units/:id`, `POST /api/m/capacity/check` |
| Buyers | `/m/buyers` (list), `/m/buyers/:id?tab=` (Orders, People and access, Link and exports, Sent messages) | `GET /api/m/buyers`, `/exports/weekly`, `/outbox`, `PATCH /api/m/buyer-logins/:id` (full access or view only) |
| Mark shipped, Reports | order page, `/m/reports` | `POST /api/m/orders/:id/ship`, `GET /api/m/reports` |
| Buyer: badges, notifications, timeline, delay notices | sidebar, order page | `GET /api/b/:token/badges`, `/feed`, `GET .../orders/:id/activity`, `POST .../orders/:id/notice/seen`, `/notice/acknowledge` |
| Requests | `/m/requests`, `/m/requests/:id` | `GET /api/m/requests?filter=`, `POST /api/m/requests/:id/query`, `/counter`, `/accept`, `/decline` |
| Buyer: new request | `/b/:token/requests/new` | `POST /api/b/:token/requests` |
| Buyer: one request | `/b/:token/requests/:id` | `GET /api/b/:token/requests/:id`, `POST .../reply`, `.../agree`, `.../withdraw` (shown as "Cancel request") |
| Files | on request, order and stage pages | `POST /api/b/:token/requests/:id/attachments`, `POST /api/m/requests/:id/attachments`, `POST /api/m/orders/:id/attachments`, `PATCH`/`DELETE /api/m/attachments/:id`, `GET /api/s/orders/:id/attachments`, `GET /api/b/:token/attachments/:id` |
| Buyer: ask for a change | `/b/:token/orders/:id/change` | `POST /api/b/:token/orders/:id/amendments` |
| Record a change (office) | button on the order page | `POST /api/m/orders/:id/amend` |
| Home page | `/` (signed out) | none: explains the product, sign in, or paste a buyer link |
| Sign in | `/login` | `POST /api/auth/login`, `GET /api/auth/me` (all three roles) |
| Change password | `/account/password` | `POST /api/auth/password` |
| Buyer: own page | `/b/me` (and `/b/me/...` for requests and changes) | the `/api/b/me/...` endpoints, signed in |
| Buyer sign-in accounts (office) | a buyer's profile, People and access | `POST /api/m/buyers/:id/logins`, `POST /api/m/buyer-logins/:id/reset`, `DELETE /api/m/buyer-logins/:id` |
| Templates | `/m/templates`, `/m/templates/new`, `/m/templates/:id` | `GET/POST /api/m/templates`, `PUT /api/m/templates/:id`, retire/restore, `POST /api/m/templates/preview`, `PATCH /api/m/steps/:code` |
| Supervisor home | `/s` | `GET /api/s/orders` (cached on the phone) |
| Supervisor update | `/s/update/:id` | `POST /api/s/updates` (through the offline queue) |
| Buyer: overview | `/b/:token` | `GET /api/b/:token`, `GET /api/b/:token/requests` |
| Buyer: orders | `/b/:token/orders` | `GET /api/b/:token` |
| Buyer: one order | `/b/:token/orders/:id?tab=` | `GET /api/b/:token`, `GET /api/b/:token/orders/:id/activity` |
| Buyer: requests | `/b/:token/requests` | `GET /api/b/:token/requests` |
| Office: search | `/` or Ctrl+K anywhere | `GET /api/m/search?q=` |
| My details | `/m/details`, `/b/me/details` | `GET`/`PATCH /api/auth/profile` |

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
users ──< sessions          outbox_messages (email / WhatsApp)       buyer_visits (page-view counters)
                            app_clock (the test date)               unit_capacity (pieces a day per stage)
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
  services/            orders (projection + warnings), shipping, reports, weekly (status email), templates, requests, attachments (files), buyer_view, notices,
                       activity, feed, capacity, clock, notify + delivery (email and WhatsApp), reset, export (Excel), search
  routes/              auth (+ My details), merchandiser, capacity, templates, requests (both sides), attachments, flow, notifications, supervisor, buyer
  ai/translate.py      IndicTrans2 Tamil<->English, ai/speech.py Whisper, ai/classifier.py keyword rules
  seed.py / explain.py demo data / prints the run-rate maths for every order
backend/tests/         216 tests
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
- **App shell:** in production builds, a service worker stores the page and its scripts the first time the app is opened online, so it opens without a network afterwards. Pages are fetched fresh whenever there is a network (the stored copy is the fallback), so a new version arrives by itself. It never caches API data.
- **Installing:** the manifest (name, standalone, scope, PNG icons including a maskable one) and the service worker make the app installable. On Android the `/install` page and a banner on the supervisor's home use the browser's own install box; on an iPhone, where no website can show one, they explain Share, Add to Home Screen. Installing needs an https address. The steps for the office and the supervisor are in [SUPERVISOR_INSTALL.md](SUPERVISOR_INSTALL.md).
- **First sign-in on a phone:** a one-time welcome in Tamil (daily entry, allow camera and microphone, offline is fine), remembered per person on that phone.
- **"Offline" is decided by reaching the server**, not by the phone's own online flag, which is wrong on Wi-Fi with no internet.
- **A refused update** (e.g. over the quantity cap) isn't retried forever. It's kept with the server's message and shown to the supervisor with a Discard button.

## Messages outside the app (email and WhatsApp)

Anything that needs the other side's attention also reaches them outside the app, so a buyer who has not opened LoomTrack still hears that their merchandiser replied.

- **One list of events**, `services/notify.py`: 11 to the buyer's people (request received, question, proposed date, declined, accepted; change accepted or recorded; delay notice; order shipped; the weekly status; order cancelled) and 6 to the merchandisers (a request arrived, a buyer answered, the supervisor reported a reason, a delay was detected, production is complete, a delay notice was acknowledged). Each has its email text and, for the buyer's events, its WhatsApp wording. Every place that used to write a mock email now calls `notify.send()`, inside the same transaction as the change, so a message exists if and only if the change was saved.
- **Who gets it.** Email goes to each signed-in person of the buyer (and to every merchandiser for the office events). WhatsApp goes only to a buyer whose number is on file **with the box ticked that they agreed to it**; the agreement, who recorded it and when are stored, and the buyer can reply STOP to switch it off. A buyer with no email address, or with email switched off, gets a row marked *skipped* with the reason instead of silence.
- **Sending is separate from asking.** `send()` only writes rows. A loop in the server (`services/delivery.py`, every 10 seconds, only while a provider is set up) sends the queued ones: email through any SMTP server (Python's `smtplib`), WhatsApp through Meta's Cloud API (`httpx`). A failure stays on the row with its reason; it is tried again after 1, 5 and 30 minutes, then marked *failed* and the office can press **Send again**. A wrong number or a template that does not exist fails at once.
- **What comes back.** Meta calls `/api/webhooks/whatsapp` with delivery reports (sent, delivered, read, failed), which move the row forward and never back, and with replies; *STOP* switches WhatsApp off for that number. The call is accepted only if it is signed with the app secret.
- **Nothing is set up by default.** Without settings the messages are only recorded (status *recorded only*), exactly as before. Settings live in `backend/.env` (see `backend/.env.example`); they never reach the browser or the database. **Notifications** in the sidebar shows what is connected, sends a test message, and lists the events.
- The WhatsApp wording submitted to Meta is generated from the same list: [WHATSAPP_TEMPLATES.md](WHATSAPP_TEMPLATES.md).

## Running it: sign-in, health, logs and backups

- **Sign-in.** The server sets one `HttpOnly` cookie; the app holds no token and sends no header, and the database keeps only the token's hash (`security.hash_token`). A cookie session is refused on a change the browser marks as coming from another site. Wrong passwords are counted per sign-in name (5 tries, locked 5 minutes) and per address (20 tries in 15 minutes, locked 15 minutes) in `login_attempts` (`services/lockout.py`). Behind a tunnel or proxy on the same machine the address is read from `CF-Connecting-IP` or `X-Forwarded-For`; from anywhere else those headers are ignored.
- **Files.** A supervisor's photo or voice note is identified from its own first bytes (`sniff_media` in `routes/supervisor.py`); the phone's claimed type is ignored. Design files are checked the same way (`services/attachments.py`). Every response carries `nosniff`, frame, referrer and permissions headers and a Content-Security-Policy built in `main.py` (scripts only from this server, plus the page's one inline theme script by its hash). All of this is in `edge.py`.
- **Health.** `GET /api/health` needs no sign-in and says nothing about people or orders: `ok`, `database`, `uploads`, `schema`, `translation`, `speech`, `lastBackup`. It answers 503 when the database or the uploads folder fails; a missing language model is not a failure. Point an uptime monitor at it.
- **Log.** One JSON line per request in the console and in `data/logs/access.log` (5 MB files, the last 5 kept): time, request number (also the `X-Request-ID` response header), method, path with the private buyer link hidden, status, milliseconds, address. No bodies, no query strings, no passwords or sessions. Requests over one second are logged as warnings; an unhandled error is logged with its traceback and the person sees only its request number.
- **Backups.** About once a day the app copies the database (SQLite online backup, checked, newest 14 kept as `daily-<date>-<time>.db`) and mirrors the uploaded files (`services/backup.py`) into `data/backups/`. `python -m loomtrack.backup` does the same now, safely while the app runs. Set `LOOMTRACK_BACKUPS` to another drive or a synced folder, or the copies share a disk with the data. **Restore:** stop the app, copy a `daily-*.db` over `data/loomtrack.db` (delete `loomtrack.db-wal` and `-shm`), copy `backups/uploads/` back over `uploads/`, start the app.

## What is mocked or limited today

- Email and WhatsApp are real only once you add the settings to `backend/.env` (and, for WhatsApp, Meta has approved the templates). Until then every message is recorded in the app and nothing leaves it. WhatsApp is one-way apart from STOP: a buyer's reply on WhatsApp is not added to the conversation.
- The capacity check spreads work evenly and assumes the unit's stated capacity is real.
- Voice: the original audio is always kept for the merchandiser. Whisper's Tamil is fair, not perfect: a misheard word shows up as a wrong translation, so the text is labelled for checking and the category can be changed. A new email or phone number in My details is not verified by a code.
- The run rate is a 7-day average and doesn't model capacity shared between orders on one line (see RUN_RATE.md, "Known limits").
- One SQLite file is right for this size. Postgres is the path if the client wants managed backups.
