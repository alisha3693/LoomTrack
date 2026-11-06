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

## Stack
**Backend:** Python 3.12, FastAPI, SQLite · **AI:** Ollama + Llama 3 8B (local), keyword fallback · **Web:** React + Vite PWA (offline queue for supervisors)

## Run it locally (Windows)

Prerequisites: Python 3.12, Node 22 (build tooling only), and [Ollama](https://ollama.com) with the model pulled:
```
ollama pull llama3
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
| `npm test` | backend tests (72) |
| `npm run explain` | run-rate maths for every order, in the terminal |
| `python e2e/walkthrough.py` | headless browser walkthrough with screenshots |
| `python e2e/offline_test.py` | offline queue check |

API docs: http://localhost:4000/api/docs

Without Ollama running, everything still works. Issue notes are then categorised by keywords and shown without a translation.

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
