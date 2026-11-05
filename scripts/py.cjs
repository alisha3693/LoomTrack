// Runs the backend's virtualenv Python from npm scripts on Windows and Linux alike.
// The sample orders only make sense around 5 Nov 2026, so the demo pins "today"
// to that date unless LOOMTRACK_TODAY is set (set it to a real date to go live).
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const backend = path.join(__dirname, "..", "backend");
const python = [".venv/Scripts/python.exe", ".venv/bin/python"].map((p) => path.join(backend, p)).find((p) => fs.existsSync(p));
if (!python) {
  console.error("No virtualenv found. Run:  cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt");
  process.exit(1);
}
const env = { LOOMTRACK_TODAY: "2026-11-05", PYTHONIOENCODING: "utf-8", ...process.env };
const r = spawnSync(python, process.argv.slice(2), { cwd: backend, stdio: "inherit", env });
process.exit(r.status ?? 1);
