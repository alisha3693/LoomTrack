# LoomTrack

Production order tracking for a Tiruppur knitwear exporter. Supervisors enter daily numbers from the floor in Tamil; every order shows green / amber / red against its time-and-action plan; buyers see their own orders' progress through a private link.

Free and open source end to end. The AI runs locally.

| Doc | What's in it |
|---|---|
| [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) | **Click-by-click demo and test script** |
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | **Whole system design**: requirements, architecture, data, security, failure modes, capacity, deployment, roadmap |
| [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | **How it all works**: data flow, warnings, AI, buyer isolation, offline, code map |
| [docs/TODO.md](docs/TODO.md) | Build plan and progress |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | Stack decisions and why |
| [docs/RUN_RATE.md](docs/RUN_RATE.md) | How the delay projection works, with a worked example |
| [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | The interface: palette, type, spacing, shared parts and the rules for a new screen |
| [docs/SUPERVISOR_INSTALL.md](docs/SUPERVISOR_INSTALL.md) | Putting the app on a supervisor's phone: what the office does, what the supervisor sees the first time, and what is not yet checked on a real phone |
| [docs/WHATSAPP_TEMPLATES.md](docs/WHATSAPP_TEMPLATES.md) | The WhatsApp templates with sample values, ready to submit to Meta, and how to connect email and WhatsApp |
| [docs/UX_GAPS.md](docs/UX_GAPS.md) | Gaps found between the buyer and the merchandiser, and what was done about them |

## Stack
**Backend:** Python 3.12, FastAPI, SQLite · **Translation:** IndicTrans2 on this machine (GPU or CPU, Tamil and English), keyword fallback · **Web:** React + Vite PWA (installable on a phone, offline queue for supervisors)

## Run it locally (Windows)

Prerequisites: Python 3.12 and Node 22 (build tooling only). For Tamil to English and English to Tamil translation, once: install the libraries and download the two models (needs a free Hugging Face token in `backend/.env` as `HF_TOKEN`; steps are at the top of `backend/loomtrack/ai/setup_models.py`):
```
pip install -r backend/requirements-translate.txt
python -m loomtrack.ai.setup_models      (in backend/)
```

First time:
```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd ..
npm install
```

Seed the demo data (prints the three buyer links):
```
npm run seed
```

Run it:
```
npm start          # builds the web app, serves everything on http://localhost:4000
npm run dev        # or: API on :4000 + web with live reload on :5173
```
"Today" is pinned to 5 Nov 2026 so the sample orders make sense; set `LOOMTRACK_TODAY` to override.

| Command | |
|---|---|
| `npm test` | backend tests (202) |
| `npm run explain` | run-rate maths for every order, in the terminal |
| `python e2e/walkthrough.py` | headless browser walkthrough with screenshots |
| `python e2e/offline_test.py` | offline queue check |
| `python e2e/journey.py` | the buyer-and-merchandiser journey (sidebar, inbox, approvals, receipts, view-only accounts), plus phone-width layout checks (needs a freshly seeded database) |
| `python e2e/pwa.py` | installability (manifest, icons, service worker), offline start, the Android and iPhone install pages and the supervisor's first-time welcome |
| `python e2e/a11y.py [light\|dark]` | an automated accessibility scan (axe) of the main pages, in light or dark |

API docs: http://localhost:4000/api/docs

Email and WhatsApp: copy `backend/.env.example` to `backend/.env` and fill in what you use (an SMTP server; Meta's WhatsApp Cloud API). With nothing set, messages to buyers are only recorded under Buyers, Sent messages. Setup steps and the template wording for Meta's review are in [docs/WHATSAPP_TEMPLATES.md](docs/WHATSAPP_TEMPLATES.md).

Without the translation models, everything still works. Issue notes are then categorised by keywords and shown without a translation.

To try the supervisor screens on a real phone on the same Wi-Fi, open `http://<laptop-ip>:4000` (`npm start` listens on the LAN). Camera and microphone need HTTPS on phones; a free Cloudflare Tunnel provides that.

## Demo logins
| Who | Login | PIN / password |
|---|---|---|
| Merchandiser | priya@companya.in | loom1234 |
| Supervisor, Unit 1 · Avinashi Road | 9840000001 | 1111 |
| Supervisor, Unit 2 · Tiruppur North | 9840000002 | 2222 |
| Supervisor, Unit 3 · Palladam | 9840000003 | 3333 |
| Print job-work unit | 9840000004 | 4444 |
| Wash job-work unit | 9840000005 | 5555 |

## Sample data
B-PO-88213, B-PO-88240 and C-PO-0488 are the client's sample orders. The other six orders, Company D, the people and the daily history are synthetic.
