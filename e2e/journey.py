"""The buyer-and-merchandiser journey in a real browser, with checks along the way.

The office finds a buyer's message from the board and answers it; the buyer sees the reply and reads it; a
countered date is agreed and accepted into an order, and the buyer follows it to the order; then every main page
is checked at phone width for sideways scrolling and for titles squeezed into a sliver.

Needs a freshly seeded database (it creates PO B-PO-96001) and the app running:
    python -m loomtrack.seed   (in backend/, with LOOMTRACK_TODAY=2026-11-05)
    python e2e/journey.py      (LOOMTRACK_URL and LOOMTRACK_DB can point at another instance)
Exits with 1 if any check fails.
"""
import json
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("LOOMTRACK_DB", ROOT.parent / "backend" / "data" / "loomtrack.db"))
token = sqlite3.connect(DB).execute("SELECT link_token FROM buyers WHERE name LIKE 'Company B%'").fetchone()[0]
errors, results = [], []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def call(method, path, body=None, auth=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", **({"authorization": f"Bearer {auth}"} if auth else {})})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


office_token = call("POST", "/api/auth/login", {"login": "priya@companya.in", "secret": "loom1234"})["token"]
sizes = [{"size": "M", "qty": 1500}, {"size": "L", "qty": 1500}]
rq = call("POST", f"/api/b/{token}/requests", {"poNo": "B-PO-96001", "style": "Crew tee", "colour": "Charcoal", "exFactory": "2026-12-12", "sizes": sizes})["id"]
call("POST", f"/api/m/requests/{rq}/counter", {"exFactory": "2026-12-18", "message": "18 Dec is the earliest we can do."}, office_token)
orders = {o["poNo"]: o["id"] for o in call("GET", f"/api/b/{token}")["orders"]}
call("POST", f"/api/b/{token}/orders/{orders['B-PO-88240']}/messages", {"message": "Please send a photo of the cartons when they arrive."})

with sync_playwright() as p:
    b = p.chromium.launch()
    office = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    buyer = b.new_context(viewport={"width": 1100, "height": 900}).new_page()
    for pg in (office, buyer):
        pg.on("pageerror", lambda e: errors.append(str(e)))

    # ---- Office: what needs me, found from the board
    office.goto(BASE + "/login")
    office.fill("input[autocomplete=username]", "priya@companya.in")
    office.fill("input[type=password]", "loom1234")
    office.click("button.btn-primary")
    office.wait_for_selector("text=Needs you")
    check("office board opens with a Needs-you strip", office.locator("section[aria-label='Needs you'] .attn").count() >= 3)
    check("only one New order button on the board", office.locator("a.btn:has-text('New order')").count() == 1)
    office.click("button.attn:has-text('buyer message')")
    office.wait_for_selector(".chip-filter")
    check("the message card filters the board to that order", office.locator("table.board tbody tr").count() == 1 and "B-PO-88240" in office.inner_text("table.board"))
    office.click(".chip-filter button")
    check("the filter clears", office.locator("table.board tbody tr").count() > 3)

    # ---- Office: find anything from anywhere
    office.keyboard.press("/")
    check("/ opens search", office.locator(".palette").count() == 1)
    office.fill(".palette input", "raglan") if False else office.fill(".palette input", "88213")
    office.wait_for_selector(".palette-item:has-text('B-PO-88213')")
    office.keyboard.press("Enter")
    office.wait_for_url(re.compile(r"/m/orders/\d+$"))
    check("search + Enter opens the order", "B-PO-88213" in office.inner_text("h1"))
    check("order page has breadcrumbs", office.locator(".crumbs a:has-text('Orders')").count() == 1)
    check("buyer name links to their orders", office.locator("p.sub a:has-text('Company B')").count() == 1)
    href = office.locator("a:has-text('What the buyer sees')").get_attribute("href")
    check("preview link points at this buyer's page for this order", bool(href) and href.startswith(f"/b/{token}/orders/") and href.endswith(str(orders["B-PO-88213"])))
    office.click(".anchor-nav a:has-text('Materials')")
    office.wait_for_timeout(900)
    box = office.locator("#materials h2").bounding_box()
    check("section nav scrolls to Materials", box is not None and 0 <= box["y"] < 400)

    # ---- Office answers the buyer's message on B-PO-88240
    office.goto(BASE + "/m")
    office.locator("a:visible", has_text="B-PO-88240").first.click()
    office.wait_for_selector("text=Waiting for your reply")
    office.fill("#messages textarea", "Will do. Photos go out the day the cartons land.")
    office.click("#messages button:has-text('Send message')")
    office.wait_for_selector("#messages .bubble.mine")
    office.wait_for_timeout(500)
    check("answering clears 'waiting for your reply'", office.locator("#messages >> text=Waiting for your reply").count() == 0)

    # ---- Buyer: sees the reply, reads it, and it stops asking for attention
    buyer.goto(f"{BASE}/b/{token}")
    buyer.wait_for_selector("text=Needs your attention")
    buyer.wait_for_selector(".attn")
    titles = buyer.locator(".attn b").all_inner_texts()
    check("buyer is told about the countered date", any("Agree to a new date for B-PO-96001" in t for t in titles))
    check("buyer is told about the new reply", any("New reply about B-PO-88240" in t for t in titles))
    check("buyer is told about the delay notice", any("Delay notice for B-PO-88240" in t for t in titles))
    buyer.click(".attn:has-text('New reply about B-PO-88240')")
    buyer.wait_for_selector(".bubble:has-text('Photos go out the day')")
    check("reply card opens the conversation tab", "tab=messages" in buyer.url)
    buyer.goto(f"{BASE}/b/{token}")
    buyer.wait_for_selector(".attn")
    check("a read reply stops asking for attention", not any("New reply about B-PO-88240" in t for t in buyer.locator(".attn b").all_inner_texts()))

    # ---- Buyer writes about another order; the office sees it on the board
    buyer.goto(f"{BASE}/b/{token}/orders/{orders['B-PO-88213']}?tab=messages")
    buyer.fill("textarea", "Is the inline inspection still on for 10 Nov?")
    buyer.click("button:has-text('Send message')")
    buyer.wait_for_selector(".bubble.mine")
    office.goto(BASE + "/m")
    office.wait_for_selector("text=Needs you")
    check("office board shows the buyer's new message", "B-PO-88213" in office.locator("button.attn:has-text('buyer message')").inner_text())

    # ---- Buyer agrees to the countered date; office accepts; buyer follows it to the order
    buyer.goto(f"{BASE}/b/{token}")
    buyer.click(".attn:has-text('Agree to a new date')")
    buyer.wait_for_selector("text=Your turn")
    buyer.click("button:has-text('Agree to 18 Dec')")
    buyer.wait_for_selector("text=With your merchandiser")
    check("agreeing hands the turn back to the merchandiser", buyer.locator("text=With your merchandiser").count() >= 1)
    office.goto(BASE + "/m/requests")
    office.locator("td:visible", has_text="B-PO-96001").first.click()
    office.wait_for_selector("text=The buyer is waiting for your answer")
    office.click("button:has-text('Accept into an order')")
    office.wait_for_selector("text=Capacity check")
    office.locator(".modal select").first.select_option(label="Unit 3 · Palladam")
    office.wait_for_selector("text=Room to spare")
    office.click(".modal button:has-text('Create order')")
    office.wait_for_url(re.compile(r"/m/orders/\d+$"))
    buyer.reload()
    buyer.wait_for_selector("text=Accepted")
    buyer.click("a:has-text('See progress on your order')")
    buyer.wait_for_selector("h1:has-text('B-PO-96001')")
    check("an accepted request leads straight to the order", True)

    # ---- Nothing scrolls sideways on a phone, on either side
    phone_office = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    phone_buyer = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    phone_office.goto(BASE + "/login")
    phone_office.fill("input[autocomplete=username]", "priya@companya.in")
    phone_office.fill("input[type=password]", "loom1234")
    phone_office.click("button.btn-primary")
    phone_office.wait_for_selector("text=Needs you")
    pages = [(phone_office, "/m"), (phone_office, "/m/requests"), (phone_office, "/m/buyers"), (phone_office, f"/m/orders/{orders['B-PO-88240']}"),
             (phone_office, f"/m/requests/{rq}"), (phone_office, "/m/units"),
             (phone_buyer, f"/b/{token}"), (phone_buyer, f"/b/{token}/orders"), (phone_buyer, f"/b/{token}/orders/{orders['B-PO-88240']}"),
             (phone_buyer, f"/b/{token}/orders/{orders['B-PO-88240']}?tab=materials"), (phone_buyer, f"/b/{token}/requests"), (phone_buyer, f"/b/{token}/requests/{rq}"),
             (phone_buyer, f"/b/{token}/requests/new")]
    wide = []
    for pg, path in pages:
        pg.goto(BASE + path)
        pg.wait_for_timeout(700)
        over = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if over > 1:
            wide.append((path, over))
    # A row squeezed into a sliver still fits the screen, so also check that titles keep a readable width.
    squeezed = []
    for pg, path in pages:
        pg.goto(BASE + path)
        pg.wait_for_timeout(500)
        for w in pg.evaluate("[...document.querySelectorAll('.order-row .t, .anchor-nav a, .tabs button, .attn b, .tile b')].filter(e => e.offsetParent).map(e => Math.round(e.getBoundingClientRect().width))"):
            if w < 40:
                squeezed.append((path, w))
    check("no title is squeezed into a sliver on a phone", not squeezed)
    if squeezed:
        print("   squeezed:", squeezed[:5])
    check(f"no page scrolls sideways on a phone ({len(pages)} checked)", not wide)
    if wide:
        print("   sideways:", wide)
    b.close()

print("errors:", errors or "none")
failed = [n for n, ok in results if not ok]
print("FAILED:", failed or "none")
sys.exit(1 if failed or errors else 0)
