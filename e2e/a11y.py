"""An automated accessibility scan (axe) of the main pages, light or dark.

Needs a seeded database and the app running:
    python e2e/a11y.py [light|dark]    (LOOMTRACK_URL and LOOMTRACK_DB can point at another instance)
Install the checker once with:  pip install axe-playwright-python
Prints every serious or moderate problem and exits with 1 if there is any.
"""
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
ROOT = Path(__file__).resolve().parent
db = sqlite3.connect(os.environ.get("LOOMTRACK_DB", ROOT.parent / "backend" / "data" / "loomtrack.db"))
token = db.execute("SELECT link_token FROM buyers WHERE name LIKE 'Company B%'").fetchone()[0]
oid = db.execute("SELECT id FROM orders WHERE po_no = 'B-PO-88240'").fetchone()[0]
bid = db.execute("SELECT id FROM buyers WHERE name LIKE 'Company B%'").fetchone()[0]
scheme = sys.argv[1] if len(sys.argv) > 1 else "light"

OFFICE = ["/m", f"/m/orders/{oid}", f"/m/orders/{oid}?tab=approvals", f"/m/orders/{oid}?tab=conversation", "/m/messages", "/m/approvals", "/m/requests", "/m/buyers", f"/m/buyers/{bid}?tab=people", f"/m/buyers/{bid}?tab=notify", f"/m/buyers/{bid}?tab=sent", "/m/units", "/m/templates", "/m/notifications"]
BUYER = [f"/b/{token}", f"/b/{token}/orders", f"/b/{token}/orders/{oid}", f"/b/{token}/approvals", f"/b/{token}/messages", f"/b/{token}/documents", f"/b/{token}/requests", f"/b/{token}/requests/new"]
PUBLIC = ["/", "/login"]
issues = defaultdict(set)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
    pg = ctx.new_page()
    axe = Axe()

    def scan(path):
        pg.goto(BASE + path)
        pg.wait_for_timeout(900)
        res = axe.run(pg)
        for v in res.response["violations"]:
            if v["impact"] in ("serious", "critical", "moderate"):
                for n in v["nodes"][:2]:
                    issues[(v["id"], v["impact"], v["help"])].add((path.split("?")[0].replace(token, "T"), n["target"][0] if n["target"] else ""))

    for path in PUBLIC:
        scan(path)
    pg.goto(BASE + "/login")
    pg.fill("input[autocomplete=username]", "priya@companya.in")
    pg.fill("input[type=password]", "loom1234")
    pg.click("button.btn-primary")
    pg.wait_for_selector(".rail", state="attached")
    for path in OFFICE + BUYER:
        scan(path)
    b.close()
print(f"[{scheme}] axe violations (moderate and above):")
for (rid, impact, help_), where in sorted(issues.items()):
    print(f"- {impact:8} {rid}: {help_}")
    for path, target in sorted(where)[:4]:
        print(f"      {path}  {target}")
if not issues:
    print("none")
sys.exit(1 if issues else 0)
