# Demo and test guide

A click-by-click script that walks through every requirement in the brief. It works for testing the build yourself and for showing it to the client (about 15 minutes). Every step lists what you should see.

## Before you start
1. Ollama is running (the tray icon), with `llama3` pulled. Without it, notes are categorised by keywords and the top bar shows **AI off · keywords**. Everything else still works.
2. Reset the demo data: `npm run seed`. This prints the three buyer links.
3. Start the app: `npm start` → open **http://localhost:4000**. Or use `npm run dev` for live reload while coding (web on :5173).

"Today" is pinned to **Thu 5 Nov 2026** so the client's sample orders make sense.

**Dark mode** follows your device. The round ◐ button on every screen cycles *device → light → dark*, and the choice is remembered per browser.

**Use two browser windows:** a normal one for the office, and a phone-sized one for the supervisor. In Chrome, press F12, then the phone icon, then pick a 390 px phone. A private window keeps the logins apart.

---

## 1. The order board: trouble at a glance (Must have #3)
Log in as **priya@companya.in / loom1234**.

- **Expect:** 3 red · 2 amber · 4 green, sorted trouble first.
- Each row shows one line of maths, e.g. **B-PO-88213** (sample data): *Stitching 57% · need 743/day, making 669/day*.
- Filter by **Company C (Germany)**: only C's orders remain. Try unit and ship week too. Click a count chip (e.g. red) to show only those orders.
- The top bar says **AI · llama3**. That's the local model; nothing is sent to a paid service.

## 2. The delay warning shows its maths (Must have #4, the hard part)
Open **C-PO-0488** (kids printed tee, sample data).

- **Expect:** *Will miss ex-factory*, projected **Mon 30 Nov** vs planned **Sat 28 Nov**.
- The projection table shows printing (job work) needing **767/day** but making **443/day**. That's flagged 23 days before ex-factory: the "two weeks early, not two days" goal.
- Stitching says *waiting on upstream*. It isn't slow itself; it's starved by printing. The headline names printing as the root cause.
- The method is in [RUN_RATE.md](RUN_RATE.md) if anyone asks how the numbers are worked out.

## 3. Warnings reach buyers only after a merchandiser confirms
Still on C-PO-0488:

- The red card says *Not visible to the buyer until you confirm*. Its suggested message already names the cause found in the Tamil notes (*power cut*).
- Open Company C's buyer link (from **Buyers & exports → Open buyer view**). **Expect:** no delay notice on C-PO-0488.
- Back in the office: edit the message if you like → **Confirm & send to buyer**.
- Refresh the buyer view. **Expect:** an *Update from your merchandiser* banner with the expected date.
- **Buyers & exports → Sent to buyers** shows the (mock) email.

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

## 7. Date changes leave a compliance trail
On any order: **Change ex-factory** (or click a due date in the TNA list).

- A reason is required. **Expect:** it appears under **Date change history**, and on the buyer link under *Date change history*.
- History can't be edited or deleted. The database refuses it (enforced by triggers, covered by tests).
- Seeded example: **B-PO-88301** shows the buyer-agreed move from 5 Dec to 10 Dec.

## 8. Buyer view: only their own orders (Must have #5)
Open each of the three buyer links.

- **Expect:** each shows only its own orders. No unit names, no internal colours, no raw supervisor notes.
- **Weekly status (Excel)** downloads the buyer edition. **Print / PDF** gives a clean printout.
- Office → Buyers & exports → **New link** revokes the old link immediately (try the old one: *This link is not valid*).

## 9. Weekly export per buyer (Must have #6)
**Buyers & exports**: the *Buyer edition* matches the buyer link. The *Internal edition* adds status colour and slack per order.

---

## Automated checks
| Command | What it proves |
|---|---|
| `npm test` | 47 backend tests: run-rate maths, keyword classifier, schema migration, buyer isolation, idempotent offline sends, unit scoping, AI fallback, confirm-before-buyer, append-only audit |
| `npm run explain` | Prints the run-rate maths for every order in the terminal |
| `python e2e/walkthrough.py` | Clicks through every screen in a headless browser, saves screenshots to `e2e/shots/`, fails on any browser error (run `npm run seed` first) |
| `python e2e/offline_test.py` | Phone offline → update queued → back online → lands exactly once |

The e2e scripts need Playwright (free): `pip install playwright && python -m playwright install chromium`.

## Known limits (say these out loud in the demo)
- The local AI is good but not perfect on Tamil. It once read நூல் (thread) as "book". The UI is built around that: the original note is always shown, and the category is one click to change.
- Voice transcription uses the phone browser's speech service where available. The audio itself is always kept for the merchandiser.
- Messages to buyers are recorded in the app, not actually emailed (mocked, per the brief).
