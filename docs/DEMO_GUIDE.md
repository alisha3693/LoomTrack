# Demo and test guide

> **Note (9 Nov 2026):** buyer approvals, the conversation on live orders, materials tracking and the documents page were taken out after this guide was written, and the seeded board now shows 3 red, 4 amber and 2 green. Sections that mention them no longer apply. The current, tested walkthrough is in [DEPLOYMENT.md](DEPLOYMENT.md).

A click-by-click script that walks through every requirement in the brief. It works for testing the build yourself and for showing it to the client (about 15 minutes). Every step lists what you should see.

## Before you start
1. The translation models are downloaded (`python -m loomtrack.ai.setup_models`). Without them, notes are categorised by keywords and the account menu (bottom of the sidebar) shows **Keywords only**. Everything else still works.
2. Reset the demo data: `npm run seed`. This prints the three buyer links.
3. Start the app: `npm start` → open **http://localhost:4000**. Or use `npm run dev` for live reload while coding (web on :5173).

"Today" is pinned to **Thu 5 Nov 2026** so the client's sample orders make sense.

**Dark mode** follows your device. The round ◐ button on every screen cycles *device → light → dark*, and the choice is remembered per browser.

**Use two browser windows:** a normal one for the office, and a phone-sized one for the supervisor. In Chrome, press F12, then the phone icon, then pick a 390 px phone. A private window keeps the logins apart.

---

## 1. The order board: trouble at a glance (Must have #3)
Log in as **priya@companya.example / loom1234**.

- **Expect:** 3 red · 2 amber · 4 green, sorted trouble first.
- Each row shows one line of maths, e.g. **B-PO-88213** (sample data): *Stitching 57% · need 743/day, making 669/day*.
- Filter by **Company C (Germany)**: only C's orders remain. Try unit and ship week too. Click a count chip (e.g. red) to show only those orders.
- The account menu (bottom of the sidebar) says **AI on**. That's the local model; nothing is sent to a paid service.

## 2. The delay warning shows its maths (Must have #4, the hard part)
Open **C-PO-0488** (kids printed tee, sample data).

- **Expect:** *Will miss ex-factory*, projected **Mon 30 Nov** vs planned **Sat 28 Nov**.
- The projection table shows printing (job work) needing **767/day** but making **443/day**. That's flagged 23 days before ex-factory: the "two weeks early, not two days" goal.
- Stitching says *waiting on upstream*. It isn't slow itself; it's starved by printing. The headline names printing as the root cause.
- The method is in [RUN_RATE.md](RUN_RATE.md) if anyone asks how the numbers are worked out.

## 3. Warnings reach buyers only after a merchandiser confirms
Still on C-PO-0488:

- The red card says *Not visible to the buyer until you confirm*. Its suggested message already names the cause found in the Tamil notes (*power cut*).
- Open Company C's buyer link (from **Buyers → the buyer → What the buyer sees**). **Expect:** no delay notice on C-PO-0488.
- Back in the office: edit the message if you like → **Confirm & send to buyer**.
- Refresh the buyer view. **Expect:** an *Update from your merchandiser* banner with the expected date.
- **Buyers → Sent messages** shows the email (and WhatsApp, for a buyer who agreed) with how far it got: *recorded only* until email or WhatsApp is connected, then *sent*, *delivered*, *read* or *failed*.

## 4. Supervisor daily update on the phone, in Tamil (Must have #2)
Phone window → log in as **9840000001 / 1111** (Murugan, Unit 1).

- **Expect:** a Tamil interface (switch with த / EN) listing only Unit 1's stages, each with today's number.
- Tap **C-PO-0488 · கட்டிங்** (cutting). Enter **600**, take or choose a photo, and write a note, e.g. `மெஷின் பழுது, இரண்டு மணி நேரம் வேலை நின்றது` (machine broke down, work stopped for two hours). Or press 🎤 and speak.
- **அனுப்பு** (Send). **Expect:** *அனுப்பப்பட்டது* (sent), and the card shows 600 for today.

**Offline test:** DevTools → Network → **Offline**. Send another update. **Expect:** *சேமிக்கப்பட்டது…* (saved, will send when online) and an amber *1 waiting to send* chip. Switch back to Online: the chip clears within seconds and the server counts the pieces once.

**Unit scoping:** log in as Unit 2 (**9840000002 / 2222**). C-PO-0488 isn't in the list, because Unit 2 doesn't run it.

## 5. AI reason category, and what happens when it's wrong
Office → C-PO-0488 → **Floor updates** (allow ~5–20 s for the local model).

- **Expect:** your Tamil note on the left and the English translation on the right, with a reason picked from a fixed list.
- **When it's wrong** (it will be sometimes; it's a free 8B model): change the dropdown. The page then shows *Set by merchandiser · AI said "…"*. Both values are kept.
- **Seeded example:** B-PO-88240 has `கார்ட்டன் பெட்டி இன்னும் வரவில்லை` (carton box not arrived yet) → trims delay.
- Untick **buyer** under a photo to hide it from the buyer link.

## 6. Order setup with a TNA plan (Must have #1)
**New order** → buyer's PO `B-PO-88350`, Company B, *Men's raglan tee*, colour Charcoal with Pantone `19-3906 TCX` and hex `#36454F`, ex-factory **18 Dec 2026**, Unit 1, sizes S 800 / M 1600 / L 1600 / XL 900 / XXL 300.

- **Expect:** the form says our own order number is assigned on save. After saving, the order header shows it (e.g. `LT-2026-0010`) with a colour chip and the Pantone reference.
- Try the same PO number again for Company B: it is refused. The same number for Company C is accepted, because a PO number only has to be unique per buyer.
- Hex accepts `36454f` or `#36454F` and tidies it. The swatch is labelled approximate on purpose: Pantone is the real colour spec.

- **Expect:** the total shows 5,200 and the time-and-action plan fills in, worked back from ex-factory (cutting, stitching, … final inspection). Sundays and holidays are skipped. Change any date before saving.
- Pick the **Knit printed** template: a *Printing · job work* stage appears and is assigned to the print unit automatically.
- **Create order** → the detail page shows green, on plan.

## 6b. Your own plan templates
**Plan templates**, under **Set up** in the sidebar.

- **Expect:** the three built-in templates (marked *Built in*, no Edit button), each drawn as a time-and-action chart: 9 milestones (fit sample, lab dip / colour, PP sample, fabric in-house, fabric inspection and shrinkage test, trims in-house, inline inspection, final inspection, ex-factory) and the production stages as bars, counted in days before ex-factory. **Copy** on *Knit basic*.
- Name it *Embroidered polo*. **+ New production stage**: name *Embroidery*, process **Embroidery** (chosen from the list; **Other…** is for work not in it, and a misspelling of a known process such as "stiching" is refused), due **30** (days before ex-factory), and type its **Starts** yourself (for example **40**, which overlaps the end of Cutting): every Starts and Due is a plain number you set, and stages can overlap or leave gaps. There is no Tamil name box: when you save, the app writes the Tamil name supervisors will see (a glossary of floor words first, then the translation model). The row moves into due order when you leave a field, and *Runs* shows how many days each stage takes.
- **Expect:** *Plan and example dates* draws Embroidery as a bar between Cutting and Stitching, with the dates worked back from a sample ex-factory date. Reopen the template later and the numbers are as you left them.
- **Save template.** It now appears in the **New order** template dropdown. Create an order with it: the plan includes Embroidery, and the stage goes to your own unit (no embroidery subcontractor exists).
- Edit the template afterwards: the order you created does not change. Retire it: it leaves the dropdown, existing orders are unaffected.
- Try a stage whose start is later than its end (the editor flags it and will not save), or two steps with the same name: the server explains what's wrong.

## 6c. A buyer asks for an order (home page, request, conversation)
Use two windows: the office (signed in as Priya) and a private window for the buyer.

1. Buyer window: open **http://localhost:4000** signed out. **Expect:** the home page. Paste a buyer link (**Buyers → the buyer → What the buyer sees** shows it) and **Open my orders**.
2. **New order request**: PO `B-PO-91000`, style, colour (Pantone and hex optional), a date, quantities by size. **Send request.** **Expect:** *With the merchandiser*.
3. Office: **Requests** shows a count. Open it. **Ask a question.** The status becomes *Waiting for the buyer*.
4. Buyer: reload. **Expect:** *Question for you*. Reply. The status goes back to *With the merchandiser*.
5. Office: **Propose another date** with a reason. Buyer: *New date proposed*. **Agree.** The request now carries the new date.
6. Office: **Accept into an order**: pick the unit and a template. **Expect:** the order opens with its own number (`LT-...`) and exactly the buyer's quantities, colour and agreed date. The buyer's request shows *Accepted* with that number.
7. **Buyers → Sent messages** lists the messages the buyer was sent.

**Files.** On the new-request form, **Add files** (a PNG print design, a PDF pattern). Try a text file renamed to `.png`: the request is sent, and the buyer sees which file was refused and why.
- Office, on the request: the buyer's files are listed under **Files** with **Buyer** and **Floor** ticks. Upload one of your own (for example a cutting pattern): it is private until you tick **Buyer**.
- Tick **Floor** on the print artwork, accept the request, then sign in as a supervisor (Unit 1, `9840000001` / `1111`) and open that order's stage: **Files for this order (1)** shows only the shared file. Unit 2's supervisor sees none.
- The buyer's order page lists their files and not your private ones.
8. Try with another buyer's link: that buyer cannot see or answer these requests.

## 6d. A buyer changes an order that already exists
1. Buyer window, on their order page: **Ask for a change** on B-PO-88301. Move the ex-factory date and raise a quantity, add a reason, **Send change request**.
2. Office → **Requests**: the row is tagged *Change to LT-...*. Open it: a table shows **Now** against **Asked for**, with the changed values in bold.
3. **Apply the change.** **Expect:** the order opens with the new date and total. **Date change history** has a new entry that names the request and the reason. The quantity change is recorded in the request's history.
4. Try lowering a quantity below what is already made (for example cutting 2,400 on B-PO-88301, then ask for fewer than that): applying is refused and nothing changes.
5. On the order, **Record a change** (as if the buyer emailed): it is applied at once, and the buyer sees it under *Order requests* as *Accepted*.
6. The stage dates are deliberately not moved. Open the plan and edit any date: each edit needs a reason and is logged.

## 6e. A buyer signs in with their own account, and the home page
1. Signed out, open **http://localhost:4000**. **Expect:** the home page: what LoomTrack does, who it is for, how an order moves, a box for a private link and a **Sign in** button.
2. Office, **Buyers**, Company B, **People and access**: **Add a person**, name *Sam Patel*, email *sam@companyb.example*, access *Full access*, **Create sign-in**. **Expect:** a temporary password in an amber box, with a note that it is not shown again. A second sign-in with the same email is refused.
3. Buyer window: **Sign in** with that email and the temporary password. **Expect:** you are sent to *Choose your own password* and cannot skip it, even by typing `/b/me`. Try a password under 8 characters, then a good one.
4. **Expect:** Company B's own orders and requests, with **Password** and **Sign out** in the header, and none of Company C's. The private link still works the same way.
5. Office: **New password** beside Sam. **Expect:** Sam's open window is signed out at once and the account shows *Has not signed in yet* again. **Remove** ends the account the same way.
6. Demo accounts after `npm run seed`: `hannah@companyb.example` / `buyer1234` (Company B), `jonas@companyc.example` / `buyer1234` (Company C).

## 6f. Materials: will the fabric and trims be there in time
1. Office, board: **B-PO-88240**, **B-PO-88301** and **D-PO-1107** show a red "1 material late" under their status. Their delay status is unchanged: materials sit beside it.
2. Open **B-PO-88301**. **Expect:** a **Materials** card. *Sewing thread* is late ("Arrives Fri 20 Nov, 4 days after it is needed (Stitching starts Mon 16 Nov)") and *Main label* is at risk ("Not ordered yet and needed in 11 days"). The fabric lines are received.
3. Click **Received** on *Main label*. It turns green. Click **Edit** on the thread, set *Expected on* to 12 Nov, **Save**. It is no longer late.
4. Open **D-PO-1107** (organic cotton). **Expect:** *Main fabric* is late: it arrives 20 Nov, 7 days after "Fabric in-house is due". The milestone itself is not overdue yet, so this warns a week early.
5. Mark both fabric lines received on an order whose *Fabric in-house* is not done: the milestone is ticked on the receipt date, and the date history says why. Take one back: it is unticked.
6. The buyer's window, order **B-PO-88301**: *Materials for your order* shows names and ticks only, and the fabric type, composition and GSM. No supplier or dates.

## 6g. Capacity: can the unit take it
1. Office, **Units**: the three units with their stitching capacity and how booked each of the next four weeks is.
2. A buyer sends a request: PO `B-PO-99100`, 9,000 pcs (M 4,500 and L 4,500), ex-factory 15 Dec, with a fabric (single jersey, 95% cotton 5% elastane, 185 GSM).
3. Office, **Requests**, open it, **Accept into an order**. Choose *Unit 1*. **Expect:** *Over capacity · 117%*: "15,587 pcs already booked, 9,000 more needed, 21,000 possible", which orders are using the unit (D-PO-1107, C-PO-0488), and "The first ship date this unit could take it: Fri 18 Dec". **Create order** stays disabled until you tick that you want it anyway.
4. **Propose this date** opens the counter-proposal with 18 Dec filled in. Send it.
5. Choose *Unit 3* instead: *Room to spare · 50%*, no tick needed. Create the order: it carries the fabric and starts a *Main fabric* line.
6. On **New order**, type 9,000 pcs and a 15 Dec date and pick *Unit 1*: the same check appears, and the same tick is required.

## 6h. Finding things and answering fast (both sides)
1. Office, **Orders**: the top is **Needs you**: requests waiting, buyer messages to answer, delay warnings, late materials. Click *buyer messages to answer*: the board shows only those orders, with a chip to clear it.
2. Press **/** anywhere in the office, type `88240` (or `Company B`, `raglan`, `LT-2026`) and press Enter. It opens the order. **Set up** in the sidebar holds Templates and Units; **New order** is always at the top of the sidebar.
3. On an order: breadcrumbs, the buyer's name (click it for all their orders), **What the buyer sees** (their view of this order), and the tabs: Overview, Plan and delay, Conversation, Approvals, Materials, Files and requests, History and floor.
4. Buyer window, an order, **Conversation**: write *"Can you send photos of the cartons?"* and send.
5. Office: the board's *Needs you* now lists it, the order shows *Buyer is waiting for your reply*, and the order page opens on a highlighted conversation. Reply.
6. Buyer, **Overview**: *New reply about …* is on the list. Open it: it goes away and does not come back, on any device. Back in the office, the conversation now says **Seen by Company B (UK)**.
7. A buyer's request that the office has countered: the buyer's overview has *Agree to a new date* first; the request page opens with **Your turn** and the *Agree* button before anything else. Agreeing hands it back; the office request page shows **The buyer is waiting for your answer**, with the buyer's other orders beside it.

## 6i. Approvals, delay-notice receipts, one inbox (both sides)
1. Office, **Orders**: the sidebar shows counts beside *Requests*, *Approvals* and *Messages*. Open **B-PO-88213**, tab **Approvals**: a pre-production sample is already waiting, with *Waiting for the buyer · not opened yet*.
2. Buyer (Hannah, `hannah@companyb.example` / `buyer1234`): **Overview** lists *Approve: Pre-production sample, navy crew neck*. Open **Approvals** and press **Ask for changes**: a reason is required. Write *Neck rib is too wide* and send.
3. Office: *Needs you* now says *an approval sent back by the buyer*. On the order, tab **Approvals**, **Answer and send again**, write what changed. The buyer sees it again and **Approve** completes it (for a fit or pre-production sample the plan step is marked done, and the date history says *approved by the buyer*).
4. **Ask the buyer to approve something** (order, Approvals tab): pick *Pre-production sample*, name it, send. The buyer gets a card on the overview and an email under Buyers → Sent messages.
5. Buyer, **B-PO-88240**: the delay notice has **Acknowledge** (or *Acknowledge with a note*). Office, the same order, **Overview**: *Acknowledged by the buyer …*; before that it said *Not opened* or *Opened, not acknowledged*, and the board's *Needs you* listed it.
6. **Messages** (either side): every conversation in one list, the ones waiting on you first, with a dot for what you have not opened. Open a request that became an order: its history opens the order's conversation.
7. Office, **Buyers → Company B → People and access**: *Maya Singh (QC)* is **View only**. Sign in as `qc@companyb.example` / `buyer1234`: everything can be read, nothing can be sent, approved or changed, and there is no New request button. Switch her to *Full access* and it works on her next request.
8. **Documents** (buyer): every file shared on their orders and requests, searchable. **History** on an order: what happened, when, and who did it.
9. Collapse the sidebar with the button at its foot (it remembers). On a phone the sidebar becomes a tab bar.

## 6j. Email and WhatsApp
1. Office, sidebar **Notifications**: two cards, *Not connected* until the settings are in `backend/.env` (see `backend/.env.example`). Below, every event, who it goes to and the WhatsApp template it uses.
2. To see real email without sending any, run a local mail catcher (for example Mailpit), set `LOOMTRACK_SMTP_HOST=localhost`, `LOOMTRACK_SMTP_PORT=1025`, `LOOMTRACK_SMTP_SECURITY=none`, `LOOMTRACK_SMTP_FROM=LoomTrack <orders@example.test>` and restart. The card turns to *Connected*; **Send test** delivers one.
3. Reply to a buyer in an order's conversation. Within about ten seconds **Buyers → Sent messages** shows it as *Sent*, with the address, and the mail catcher has it.
4. **Buyers → Company B → Notifications**: type a WhatsApp number, press Save. It is refused until *This buyer agreed to receive WhatsApp messages* is ticked; the agreement is recorded with the date. Switch email off for a buyer and the next message shows *Not sent: Email is switched off for this buyer*.
5. Break it on purpose (a wrong SMTP password): the message shows *Failed* with the server's reason after its retries, and **Send again** puts it back once fixed.
6. The WhatsApp wording is in [docs/WHATSAPP_TEMPLATES.md](WHATSAPP_TEMPLATES.md), ready to paste into Meta's template form.

## 6k. Installing the app on a supervisor's phone
1. Office, **Units and capacity**: the first card shows the install link. Open it on a phone (or a phone-sized window). **Expect:** a Tamil page with an Install button (Android) or three steps for Share, Add to Home Screen (iPhone).
2. Install it, open the icon, sign in as `9840000001` / `1111`. **Expect:** a short Tamil welcome, once. Tap *புரிந்தது*; it does not return on that phone.
3. Switch the phone to airplane mode and reopen the app. **Expect:** it opens, lists the orders, says *Offline*; an update entered now is *waiting to send* and goes when the network returns.
4. Phones install only from an https address; on a plain `http://` Wi-Fi address the install page says so. A free Cloudflare tunnel gives an https address for the demo.

Full steps, including what to do when a supervisor changes phone: [SUPERVISOR_INSTALL.md](SUPERVISOR_INSTALL.md).

## 7. Date changes leave a compliance trail
On any order: **Change ex-factory** (or click a due date in the TNA list).

- A reason is required. **Expect:** it appears under **Date change history**, and on the buyer link under *Date change history*.
- History can't be edited or deleted. The database refuses it (enforced by triggers, covered by tests).
- Seeded example: **B-PO-88301** shows the buyer-agreed move from 5 Dec to 10 Dec.

## 8. Buyer view: only their own orders (Must have #5)
Open each of the three buyer links.

- **Expect:** the overview opens with **Needs your attention**, then tiles, a compact list of orders and their requests. Each shows only its own orders. No unit names, no internal colours, no raw supervisor notes. Open an order for its tabs.
- **Weekly status (Excel)** downloads the buyer edition. **Print / PDF** gives a clean printout.
- Office → Buyers → Company B → **Link and exports** → **New link** revokes the old link immediately (try the old one: *This link is not valid*).

## 9. Weekly export per buyer (Must have #6)
**Buyers → Link and exports**: the *Buyer edition* matches the buyer link. The *Internal edition* adds status colour and slack per order.

---

## Automated checks
| Command | What it proves |
|---|---|
| `npm test` | 136 backend tests: run-rate maths, keyword classifier, schema migration, order requests and changes, file upload checks, buyer isolation, idempotent offline sends, unit scoping, AI fallback, confirm-before-buyer, append-only audit |
| `npm run explain` | Prints the run-rate maths for every order in the terminal |
| `python e2e/walkthrough.py` | Clicks through every screen in a headless browser, saves screenshots to `e2e/shots/`, fails on any browser error (run `npm run seed` first) |
| `python e2e/offline_test.py` | Phone offline → update queued → back online → lands exactly once |

The e2e scripts need Playwright (free): `pip install playwright && python -m playwright install chromium`.

## Known limits (say these out loud in the demo)
- The local AI is good but not perfect on Tamil. It once read நூல் (thread) as "book". The UI is built around that: the original note is always shown, and the category is one click to change.
- Voice transcription uses the phone browser's speech service where available. The audio itself is always kept for the merchandiser.
- Email and WhatsApp reach people only once the settings are in `backend/.env` (WhatsApp also needs Meta's approval of the templates). Until then messages are recorded in the app and nothing leaves it.
