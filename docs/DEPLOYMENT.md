# LoomTrack: deployment.md

Production order tracking with a buyer view, for Company A (Tiruppur knitwear exporter).
Repository: https://github.com/alisha3693/LoomTrack

LoomTrack is one Python process (FastAPI with uvicorn) that serves the API, the built web app and three background loops (email/WhatsApp sender, weekly status email, daily backup). The data is one SQLite file plus an uploads folder. The Tamil-to-English and voice-to-text models are optional and run on the same machine. There is no other service to install.

- [1. Run it locally](#1-run-it-locally)
- [2. Demo login details](#2-demo-login-details)
- [3. A ten-minute path through the main flows](#3-a-ten-minute-path-through-the-main-flows)
- [4. How it is deployed](#4-how-it-is-deployed)
- [5. Environment variables](#5-environment-variables-names-only)
- [6. Operations: health, logs, backups, restore](#6-operations-health-logs-backups-restore)
- [7. Known gaps before real use](#7-known-gaps-before-real-use)

---

## 1. Run it locally

**You need:** Python 3.12, Node.js 22 (only to build the web app; there is no Node server) and Git. The commands below work on Windows (PowerShell) and on Linux or macOS.

```bash
# 1. Get the code
git clone https://github.com/alisha3693/LoomTrack.git
cd LoomTrack

# 2. Backend dependencies (a virtual environment inside backend/)
cd backend
python -m venv .venv
#   Windows:        .venv\Scripts\pip install -r requirements.txt
#   Linux / macOS:  .venv/bin/pip install -r requirements.txt
cd ..

# 3. Web app dependencies (run in the repository root)
npm install

# 4. Create the demo data. Prints the three buyers' private links.
npm run seed

# 5. Build the web app and start everything on http://localhost:4000
npm start
```

Open **http://localhost:4000**. Interactive API documentation is at http://localhost:4000/api/docs.

- `npm run dev` runs the API on port 4000 and the web app with live reload on port 5173 (for development).
- `npm test` runs the 227 backend tests (a few seconds, no network needed).
- `npm run explain` prints the delay arithmetic for every order in the terminal.
- **"Today" is pinned to 5 Nov 2026** by `scripts/py.cjs`, because the client's sample orders have November 2026 ex-factory dates. Set `LOOMTRACK_TODAY=YYYY-MM-DD` to use another date. Production (section 4) does not use this script, so it runs on the real date.
- To start again from clean demo data: stop the server, run `npm run seed`, start the server.

**What you should see after seeding:** the office board shows 9 live orders as of Thu 5 Nov: **3 red** (will miss ex-factory), **4 amber** (behind plan), **2 green** (on track). The first three orders in the list (B-PO-88213, B-PO-88240, C-PO-0488) are the client's sample data; the other six are synthetic.

### Optional: Tamil to English translation and voice notes

The app works without these. Without them a Tamil note is classified by keyword rules and shown without a translation, and a voice note stays a recording the merchandiser can play. The Account menu says "Keywords only" and why. Both models run on this machine, on a GPU when PyTorch can use one and on the CPU otherwise.

```bash
# Translation (IndicTrans2, two ~200M models). Needs a free Hugging Face read token
# (the models are gated: accept the terms on each model page). Put it in backend/.env as HF_TOKEN=...
backend/.venv/bin/pip install -r backend/requirements-translate.txt
cd backend && .venv/bin/python -m loomtrack.ai.setup_models

# Voice to text (Whisper large-v3 through faster-whisper, ~3 GB, downloaded once)
.venv/bin/pip install -r requirements-speech.txt
.venv/bin/python -m loomtrack.ai.setup_speech
```

For an NVIDIA GPU, install PyTorch's CUDA build first (the command is at the top of `backend/requirements-translate.txt`).

### Optional: real email and WhatsApp

With nothing configured, every message to a buyer or the office is recorded under **Buyers, Sent messages** and nothing leaves the machine. To send for real, copy `backend/.env.example` to `backend/.env` and fill in the SMTP settings and/or the WhatsApp Cloud API settings (names in section 5). `backend/.env` is ignored by Git.

---

## 2. Demo login details

Created by `npm run seed`. These are demo accounts on fictional `.example` addresses. Nothing here is a real person or a real secret.

| Role | Sign in with | PIN / password | What it shows |
|---|---|---|---|
| Merchandiser | `priya@companya.example` | `loom1234` | The office: board, requests, buyers, reports, templates, settings |
| Merchandiser | `arun@companya.example` | `loom1234` | Same role, second person |
| Supervisor, Unit 1 · Avinashi Road | `9840000001` | `1111` | Phone app in Tamil; sees its own unit's stages only |
| Supervisor, Unit 2 · Tiruppur North | `9840000002` | `2222` | |
| Supervisor, Unit 3 · Palladam | `9840000003` | `3333` | |
| Print job-work unit | `9840000004` | `4444` | Printing stages only |
| Wash job-work unit | `9840000005` | `5555` | Washing stages only |
| Buyer, Company B (UK), full access | `hannah@companyb.example` | `buyer1234` | Company B's orders only |
| Buyer, Company B (UK), view only | `qc@companyb.example` | `buyer1234` | Reads everything, changes nothing |
| Buyer, Company C (Germany) | `jonas@companyc.example` | `buyer1234` | Company C's orders only |

The buyers also have a **private read-only link** (`/b/<token>`) that needs no sign-in. The seed prints the three links; they are also under Buyers, a company, **Link and exports**.

Sign in at `/login`. A supervisor's login is a phone number and a four-digit PIN. After five wrong tries a sign-in name is locked for five minutes; after twenty from one network address that address is locked for fifteen.

---

## 3. A ten-minute path through the main flows

Use two browser windows, one resized to phone width (about 390 px) for the supervisor.

1. **Supervisor (phone).** Sign in as `9840000001` / `1111`. The page is in Tamil (the தமிழ் / EN switch is at the top). Open the first order card (B-PO-88213, stitching). The grey box shows **how many pieces are left to do today**. Type `412`, and in the issue box type `இரண்டு மெஷின் பழுது` (two machines broken down). Press **அனுப்பு** (Send).
   *Try offline:* in the browser's developer tools set Network to Offline and send another entry. It is saved on the phone and sent when the network returns.
2. **Office.** In the other window sign in as `priya@companya.example`. **Notifications** shows "Supervisor reported on B-PO-88213: machine breakdown". Open **Orders**: the board is sorted with trouble first, with the **Needs you** list above it. Filter by buyer, unit or ship week.
3. **Delay warning.** Open B-PO-88213. The warning card says *Not visible to the buyer until you confirm*, with a message drafted around the machine breakdown. Open the **Plan and delay** tab to see the arithmetic: pieces needed per day against pieces made per day, stage by stage. Open **History and floor** to see the Tamil note beside its category (change the category in the dropdown to see the draft follow it). Press **Confirm & send to buyer**.
4. **Buyer.** Sign in as `hannah@companyb.example` / `buyer1234`. The overview says **Needs your attention: delay notice**. Open the order: progress, milestones, photos, the notice, and the **History** tab with every date change. Company C's and D's orders are not visible anywhere. Try `/b/<link>` for another buyer's link in a private window to see their separate view.
5. **Order request and capacity check.** As Hannah choose **New request**, fill in a PO, style, colour, sizes and a date, and send. As Priya open **Requests**, press **Accept into an order**: the dialog compares every unit's load for that ship date and asks for a tick before booking over capacity. You can instead propose another date; the buyer is told and agrees or asks again.
6. **Plan templates.** In the office open **Settings, Plan templates**: the time-and-action plans are drawn as a chart. Copy one, add a step, and see the example dates.
7. **Reports and the weekly export.** **Reports** measures the client's own goals (late shipments against 5%, days of warning before ex-factory against 14). Under **Buyers, Link and exports** download the weekly status Excel for a buyer.

---

## 4. How it is deployed

**Status at submission:** the app is **not hosted at a public address**. It runs from a laptop with `npm start`. When a phone or a reviewer needs to reach it, a free Cloudflare quick tunnel gives it a temporary https address:

```bash
cloudflared tunnel --url http://localhost:4000      # prints https://<random>.trycloudflare.com
```

Phones need https for the camera and microphone, which is why a tunnel (or a real domain) is needed for the supervisor flow on a real phone. The address changes each time the tunnel starts.

**Recommended production set-up (one small Linux server in an India region, all free software).** This is the topology the code is written for; it has not been run on a rented server yet.

```
Internet ── https ──► Caddy (automatic certificates)
                         └──► uvicorn  loomtrack.main:create_app   (systemd service, restarts on failure)
                                 ├── SQLite file   /var/lib/loomtrack/loomtrack.db
                                 ├── uploads/      /var/lib/loomtrack/uploads
                                 ├── backups/      another disk (LOOMTRACK_BACKUPS)
                                 └── optional local models (GPU or CPU)
```

1. Create a user and clone the repository to `/opt/loomtrack`.
2. `cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. Build the web app once: `cd /opt/loomtrack && npm ci && npm run build` (creates `web/dist`, which the server serves). Node is not needed after that.
4. Create the environment file `/etc/loomtrack.env` with the settings from section 5 (at least `LOOMTRACK_DB`, `LOOMTRACK_UPLOADS`, `LOOMTRACK_PUBLIC_URL`, `LOOMTRACK_SIGNING_KEY`, `LOOMTRACK_BACKUPS`). Do **not** set `LOOMTRACK_TODAY` or `LOOMTRACK_ALLOW_RESET` on the real site.
5. Create the tables and the demo data once with `.venv/bin/python -m loomtrack.seed` (or let the first start create an empty database).
6. systemd unit `/etc/systemd/system/loomtrack.service`:

   ```ini
   [Unit]
   Description=LoomTrack
   After=network.target

   [Service]
   User=loomtrack
   WorkingDirectory=/opt/loomtrack/backend
   EnvironmentFile=/etc/loomtrack.env
   ExecStart=/opt/loomtrack/backend/.venv/bin/python -m uvicorn loomtrack.main:create_app --factory --host 127.0.0.1 --port 4000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

7. Caddy `/etc/caddy/Caddyfile` (https and certificates are automatic):

   ```
   loomtrack.yourdomain.in {
       reverse_proxy 127.0.0.1:4000
   }
   ```

   The login lockout reads the caller's address from `X-Forwarded-For` (set by Caddy) only when the connection comes from the same machine.
8. `sudo systemctl enable --now loomtrack`, then check `https://loomtrack.yourdomain.in/api/health`.

The server runs one process on purpose: the database is one SQLite connection used from the event loop, which is far more than 500 orders a year needs. PostgreSQL is the path if the client wants managed backups or several servers.

---

## 5. Environment variables (names only)

Every variable is optional for the local demo. Values live in the environment or in `backend/.env` (never committed; `backend/.env.example` is the template). A variable set in the real environment wins over the file.

| Group | Names |
|---|---|
| Where data lives | `LOOMTRACK_DB`, `LOOMTRACK_UPLOADS`, `LOOMTRACK_LOGS`, `LOOMTRACK_BACKUPS` |
| Behaviour | `LOOMTRACK_TODAY` (pin the date for demos), `LOOMTRACK_PUBLIC_URL` (links in messages), `LOOMTRACK_SIGNING_KEY` (fixed key so media links survive a restart), `LOOMTRACK_ALLOW_RESET` (test machines only) |
| AI | `LOOMTRACK_AI` (`off` switches translation and speech off), `LOOMTRACK_TRANSLATE_DEVICE` (`auto`, `cuda`, `cpu`), `HF_TOKEN` (only to download the gated translation models) |
| Email (SMTP) | `LOOMTRACK_SMTP_HOST`, `LOOMTRACK_SMTP_PORT`, `LOOMTRACK_SMTP_SECURITY`, `LOOMTRACK_SMTP_USER`, `LOOMTRACK_SMTP_PASSWORD`, `LOOMTRACK_SMTP_FROM` |
| WhatsApp (Meta Cloud API) | `LOOMTRACK_WA_TOKEN`, `LOOMTRACK_WA_PHONE_ID`, `LOOMTRACK_WA_LANGUAGE`, `LOOMTRACK_WA_API_VERSION`, `LOOMTRACK_WA_VERIFY_TOKEN`, `LOOMTRACK_WA_APP_SECRET` |
| Weekly status email | `LOOMTRACK_WEEKLY` (`off` to stop), `LOOMTRACK_WEEKLY_DAY`, `LOOMTRACK_WEEKLY_HOUR` |
| Backups | `LOOMTRACK_BACKUP` (`off` to stop), `LOOMTRACK_BACKUP_KEEP` |

No secret is in the repository. The demo accounts above are the only credentials committed, and they exist only in the seed script.

---

## 6. Operations: health, logs, backups, restore

- **Health:** `GET /api/health` needs no sign-in and says nothing about people or orders. It returns `ok`, `database`, `uploads`, `schema`, `translation`, `speech` and `lastBackup`, with status 503 when the database or the uploads folder fails. Point an uptime monitor at it.
- **Log:** one JSON line per request (time, request number, method, path with private links hidden, status, milliseconds, address) to the console and to `data/logs/access.log` (5 MB files, the last 5 kept). The same request number is returned in the `X-Request-ID` header. No request bodies, query strings, passwords or session values are logged.
- **Backups:** about once a day the app copies the database (SQLite's online backup, integrity-checked, newest 14 kept as `daily-<date>-<time>.db`) and mirrors the uploaded files into `data/backups/`. Run one now with `python -m loomtrack.backup` (safe while the app runs). Set `LOOMTRACK_BACKUPS` to another drive or a synced folder so one failed disk does not lose the copies as well.
- **Restore:** stop the app, copy a `daily-*.db` over the database file (delete its `-wal` and `-shm` files), copy `backups/uploads/` back over `uploads/`, start the app. A restore on a clean machine has not been rehearsed yet.

---

## 7. Known gaps before real use

- **Staff accounts.** Merchandiser and supervisor accounts come from the seed script; there is no admin screen for them yet (buyer accounts are created in the app, and the office edits a supervisor's phone number on the Units page). For a first real user, insert one with the same hashing the app uses:

  ```bash
  cd backend && .venv/bin/python - <<'EOF'
  from loomtrack import config
  from loomtrack.db import open_db
  from loomtrack.security import hash_secret
  db = open_db(config.DB_FILE)
  db.execute("INSERT INTO users (name, role, login, secret_hash, lang) VALUES (?,?,?,?,?)",
             ("Name", "merchandiser", "name@yourmill.in", hash_secret("choose-a-strong-password"), "en"))
  EOF
  ```

  (A supervisor also needs a `unit_id`.) Remove the demo accounts before going live.
- **HTTPS** is required in production, for the phones' camera and microphone as well as for the session cookie.
- **Real phones.** The supervisor app has been tested in browser emulation and on the developer's phone over a tunnel, not yet on a 2 to 3 GB Android phone on a throttled network.
- **WhatsApp** messages need Meta-approved templates and the client's own business account; the template wording is in `docs/WHATSAPP_TEMPLATES.md`. Email works with any SMTP server.
- Sessions are not bound to a device, and uploaded files are not virus-scanned.
