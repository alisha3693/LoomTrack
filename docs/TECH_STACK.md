# LoomTrack — Tech stack decisions

Each decision is tied to a constraint from the brief. Two decisions came from the client side during the build and override earlier choices. They are logged at the bottom.

**Everything in the stack is free and open source. Running cost for the demo: ₹0.**

## Constraints that drive the stack

| # | Constraint | What it forces |
|---|---|---|
| C1 | Supervisors on 2–3 GB RAM Android phones, patchy network | Small JS bundle, no app-store install, **offline queue** for updates and photos |
| C2 | Tamil interface | i18n from day one, Tamil font, Tamil voice/text input |
| C3 | One buyer must never see another's styles or volumes | Server-side scoping on every buyer query, allow-listed buyer views, tested |
| C4 | Compliance wants history of every date change | Append-only audit table written in the same transaction as the change |
| C5 | Delay warning must show its maths | Deterministic, unit-tested run-rate engine. AI is *not* used for the projection |
| C6 | AI reason category can be wrong | Original note kept, AI output stored apart from the final category, human override, buyer sees only confirmed warnings |
| C7 | ₹7 lakh, 6 weeks; demo must not depend on paid services | One backend language, boring dependencies, **no paid APIs** |
| C8 | Minimal, clean design | No heavy UI kit; hand-built CSS with a small set of design tokens |

## Decisions

### 1. Backend: Python 3.12 + FastAPI
- One backend language, and the AI lives in it. The Python ecosystem also covers the next AI steps (local Whisper speech-to-text, IndicTrans2 translation) without a second service.
- FastAPI gives typed request validation (Pydantic), automatic API docs at `/api/docs`, and async handlers. That lets a few-seconds AI call run in the background without blocking supervisors' uploads.
- All handlers and dependencies are `async` on purpose. FastAPI runs plain `def` code in a thread pool, and the single SQLite connection must stay on the event-loop thread.

### 2. Database: SQLite (stdlib `sqlite3`) → PostgreSQL later if needed
- Zero-ops and file-based. Transactions make the audit-trail guarantee simple (C4). Append-only is enforced by triggers, not just by convention.
- At ~500 orders/year SQLite in WAL mode can run production. Postgres (free, open source) is the path if the client wants managed backups or point-in-time recovery. The SQL is plain and lives in a few service modules.

### 3. Translation: IndicTrans2 on this machine (free, MIT licence, nothing leaves the machine)
- **Models:** `ai4bharat/indictrans2-indic-en-dist-200M` (Tamil to English) and `ai4bharat/indictrans2-en-indic-dist-200M` (English to Tamil), about 200M parameters each. They run through PyTorch and `transformers`, on the GPU when PyTorch can use one (about 0.4 GB each in half precision) and on the CPU otherwise. They are downloaded once with a free Hugging Face token (`python -m loomtrack.ai.setup_models`); the app never downloads anything and loads only a pinned commit of each repository, because the repositories ship Python code that runs when loaded.
- **What it does:** translates a supervisor's Tamil note to English; names a new plan step in Tamil when it is saved (a glossary of floor words first); the merchandiser never types a Tamil name. The reason category is then picked by deterministic keyword rules over the note and its translation, not by the model.
- **Not measured yet:** the models need a Hugging Face login to download, so their Tamil quality and speed on real supervisor notes have not been measured. Ollama with Llama 3.2 was tried first and got 2 of 4 sample notes right; an ungated Marian model was worse. Measure before trusting it.
- **Fallback:** the Tamil + English keyword rules alone, when the models are not downloaded, when they error, or when AI is switched off (`LOOMTRACK_AI=off`). Every record stores which one produced it (`ai_source`) and any error.
- **Failure handling (C6):** original note shown beside the translation; `ai_category` and `final_category` are separate columns; the merchandiser can change the category; warnings reach buyers **only** after a merchandiser confirms them.

### 4. Voice notes
- The phone records audio with the browser's MediaRecorder and **always uploads the original audio**, kept beside the note.
- On-device live transcript via the browser's Web Speech API (`ta-IN`) where available. It's free to use, but note that Chrome's implementation sends the audio to Google's speech service.
- Fully open-source path (phase 2): server-side transcription with **faster-whisper** (MIT). Whisper's Tamil is usable but not great, so merchandisers can always play the original.

### 5. Client: installable PWA (React + Vite + TypeScript)
- Supervisors get a link and "Add to home screen". No Play Store, a small bundle, and one codebase for the office desktop, the supervisor phone and the buyer link (C1, C7).
- **Offline:** a service worker caches the app shell. Updates (numbers, compressed photo, voice) go to an **IndexedDB outbox** with a phone-generated ID and are sent when the network returns. The server ignores a repeated ID, so a retry can never double-count pieces.
- Node.js is used **only as build tooling** for the web app; there is no Node server.

### 6. Styling: plain CSS with design tokens
- One stylesheet with palette, spacing and type tokens. Green / amber / red carry meaning and nothing else is coloured (C8).
- **Light and dark themes** share the same token names; components never use raw colours. The theme follows the device by default, and a toggle on every screen pins it to light or dark (saved per browser). An inline script applies the saved theme before first paint, so there's no white flash. Print is always light.
- Fonts: Inter + **Noto Sans Tamil** (Google Fonts, free, open licence).

### 7. Auth and tenancy
- **Staff:** phone + PIN (supervisors) or email + password (office) → random session token stored server-side; scrypt-hashed secrets; login lockout after 5 tries. The token is accepted from an `Authorization: Bearer` header (the app) or an `HttpOnly`, `SameSite=Lax` cookie set at login (so the API also works when opened in the browser while signed in). `SameSite=Lax` is what protects the cookie from cross-site requests.
- **Buyers:** a private link with a random 32-byte token per buyer (revocable and rotatable), or a personal sign-in account (scrypt-hashed password, forced change of the office-issued temporary one, role-checked so it never reaches an office endpoint). The server resolves `buyer_id` from the token and every buyer query is scoped by it. Buyer responses are built field by field from an allow-list: no unit or subcontractor names, no internal status colour, no raw supervisor notes, no unconfirmed warnings. Covered by tests (C3).
- Staff photos and voice notes are served through short-lived HMAC-signed URLs.

### 8. Exports
- Weekly status per buyer as **Excel** via `openpyxl` (MIT). There's a buyer edition (same allow-list as the buyer link) and an internal edition (adds status and slack).

### 9. Hosting for the demo
- Runs on a laptop: `npm run dev` (API + web) with the translation models downloaded. To show it on the client's phones over Wi-Fi, use the laptop's LAN address. For an internet link, a free tunnel works (e.g. Cloudflare Tunnel's free tier).
- Production later: any small Linux VM; the stack has no licence costs.

### 10. Testing
- **axe** (through `axe-playwright-python`, development only) for the accessibility scan in `e2e/a11y.py`.
- **pytest** for the run-rate engine, the keyword classifier and end-to-end API tests: buyer isolation, idempotent updates, unit scoping, AI fallback, warning confirmation, append-only audit.

## What is mocked in the core build
| Area | Mock |
|---|---|
| Messages to buyers (email / WhatsApp) | Real once configured (SMTP through `smtplib`, WhatsApp through Meta's Cloud API with `httpx`), both free to set up; recorded only, in `outbox_messages`, until then |
| Server-side speech-to-text | Not yet; device transcript or typed text, original audio always kept |
| Outside systems (ERP, subcontractor portals) | None; seeded data |

## Decision log
| Date | Change | Why |
|---|---|---|
| 2026-11-05 | Backend moved from Node/Express to **Python/FastAPI** | One backend language alongside the AI feature |
| 2026-11-05 | A paid cloud AI API replaced by **local Ollama (Llama 3 8B)** + keyword fallback; on 2026-11-08 Ollama was replaced by **IndicTrans2** (Tamil and English, on the GPU) | Demo must use only free / open-source models and services |
