"""The supervisor, merchandiser and buyer journey in a real browser, with checks along the way.

A supervisor sends a Tamil issue note from a phone; the office sees the reason, reviews the drafted delay warning and
confirms it; the buyer sees it, acknowledges it and sees nothing of another buyer; a buyer's request becomes an order with
a capacity check; then the main pages are checked at phone width for sideways scrolling.

Needs a freshly seeded database (it changes B-PO-88213) and the app running:
    npm run seed
    npm start                  (LOOMTRACK_URL can point at another instance)
    python e2e/journey.py
Exits with 1 if any check fails.
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
LOGIN = "input[autocomplete=username]"
errors, results = [], []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def sign_in(page, who, secret):
    page.goto(BASE + "/login")
    page.fill(LOGIN, who)
    page.fill("input[type=password]", secret)
    page.click("button.btn-primary")
    page.wait_for_timeout(1800)


def api(ctx, method, path, body=None):
    """A call from a signed-in browser context: the session cookie goes along by itself."""
    r = ctx.request.fetch(BASE + path, method=method, data=json.dumps(body) if body is not None else None, headers={"content-type": "application/json"})
    return r.status, (r.json() if r.ok else {})


with sync_playwright() as p:
    b = p.chromium.launch()

    # ---- Supervisor, on a phone, in Tamil
    sup_ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    sup_ctx.add_init_script("localStorage.setItem('lt.lang','ta')")
    sup = sup_ctx.new_page()
    sup.on("pageerror", lambda e: errors.append(f"supervisor: {e}"))
    sign_in(sup, "9840000001", "1111")
    welcome = sup.get_by_role("button", name="புரிந்தது")
    if welcome.count():
        welcome.click()
    cards = sup.locator("a.stage-card")
    check("the supervisor sees a card for each stage of their unit", cards.count() >= 3)
    check("the supervisor's cards say how many pieces are left today", sup.locator(".todo").count() >= 1)
    cards.first.click()
    sup.wait_for_selector("input.qty-input")
    sup.fill("input.qty-input", "412")
    sup.fill("textarea", "இரண்டு மெஷின் பழுது")
    sup.get_by_role("button", name="அனுப்பு").click()
    sup.wait_for_url(re.compile(r"/s$"), timeout=15000)
    check("sending an update returns to the stage list", True)
    code, me = api(sup_ctx, "GET", "/api/m/board")
    check("a supervisor cannot open the office board", code == 403)

    # ---- Office: the reason arrives, the warning is reviewed and confirmed
    off_ctx = b.new_context(viewport={"width": 1366, "height": 900})
    off = off_ctx.new_page()
    off.on("pageerror", lambda e: errors.append(f"office: {e}"))
    sign_in(off, "priya@companya.example", "loom1234")
    off.wait_for_selector("table tbody tr")
    check("the board lists the nine seeded orders", off.locator("table tbody tr").count() == 9)
    check("the board has a Needs-you list", off.locator("text=Needs you").count() >= 1)
    reason = False
    for _ in range(12):  # the reason is found in the background, a moment after the phone is told "sent"
        off.goto(BASE + "/m/feed")
        off.wait_for_timeout(700)
        if "Supervisor reported on B-PO-88213" in off.locator("main").inner_text():
            reason = True
            break
    check("the office is told what the supervisor reported", reason)
    off.goto(BASE + "/m/orders/1")  # LT-2026-0001 is B-PO-88213
    off.wait_for_selector("text=Not visible to the buyer until you confirm")
    check("the order shows a drafted delay warning that waits for the office", off.get_by_role("button", name="Confirm & send to buyer").count() == 1)
    check("the draft names the cause the supervisor gave", "machine breakdown" in off.locator("textarea").first.input_value().lower())
    off.get_by_role("tab", name="History and floor").click()
    off.wait_for_selector("text=Floor updates")
    check("the supervisor's Tamil note sits beside its translation or category", "இரண்டு மெஷின் பழுது" in off.locator("main").inner_text())
    off.get_by_role("tab", name="Overview").click()
    off.get_by_role("button", name="Confirm & send to buyer").click()
    off.wait_for_timeout(1500)
    check("confirming sends the warning (the button is gone)", off.get_by_role("button", name="Confirm & send to buyer").count() == 0)

    # ---- Buyer: sees the notice, acknowledges it, and sees only their own orders
    buy_ctx = b.new_context(viewport={"width": 1280, "height": 900})
    buy = buy_ctx.new_page()
    buy.on("pageerror", lambda e: errors.append(f"buyer: {e}"))
    sign_in(buy, "hannah@companyb.example", "buyer1234")
    check("a buyer account lands on its own page", "/b/me" in buy.url)
    buy.goto(BASE + "/b/me/orders")
    buy.wait_for_selector("table tbody tr, .order-row")
    text = buy.locator("main").inner_text()
    check("the buyer sees their own orders", "B-PO-88213" in text and "B-PO-88240" in text)
    check("the buyer sees nothing of another buyer's orders", "C-PO-0488" not in text and "D-PO-1112" not in text)
    code, _ = api(buy_ctx, "GET", "/api/m/board")
    check("a buyer cannot open the office board", code in (401, 403))
    buy.goto(BASE + "/b/me/orders/1")
    buy.wait_for_selector("text=Delay notice")
    buy.get_by_role("button", name="Acknowledge", exact=True).click()
    buy.wait_for_timeout(1200)
    check("acknowledging a notice is recorded", buy.get_by_role("button", name="Acknowledge", exact=True).count() == 0)
    _, board = api(off_ctx, "GET", "/api/m/board")
    check("the office is no longer asked about that notice once the buyer acknowledged it", next(o for o in board["orders"] if o["id"] == 1)["noticeUnacknowledged"] is False)

    # ---- A view-only buyer account can look, not ask
    qc_ctx = b.new_context(viewport={"width": 1280, "height": 900})
    qc = qc_ctx.new_page()
    sign_in(qc, "qc@companyb.example", "buyer1234")
    qc.goto(BASE + "/b/me/orders")
    qc.wait_for_selector("table tbody tr, .order-row")
    check("a view-only account sees the orders", "B-PO-88213" in qc.locator("main").inner_text())
    status, _ = api(qc_ctx, "POST", "/api/b/me/requests", {"poNo": "X-1", "style": "Tee", "colour": "Navy", "exFactory": "2026-12-30", "sizes": [{"size": "M", "qty": 10}]})
    check("a view-only account is refused when it tries to send a request", status == 403)

    # ---- A buyer's request becomes an order, through the capacity check
    status, made = api(buy_ctx, "POST", "/api/b/me/requests", {"poNo": "B-PO-96001", "style": "Crew tee", "colour": "Charcoal", "exFactory": "2026-12-28", "sizes": [{"size": "M", "qty": 800}, {"size": "L", "qty": 800}]})
    check("a buyer can send a request", status == 201)
    off.goto(BASE + "/m/requests")
    off.wait_for_selector("text=B-PO-96001")
    off.locator("td", has_text="B-PO-96001").first.click()
    off.get_by_role("button", name="Accept into an order").first.click()
    off.wait_for_selector("text=Capacity check")
    check("accepting a request shows every unit's capacity", off.locator("text=Unit 3").count() >= 1)
    off.locator(".modal select").first.select_option(label="Unit 3 · Palladam")
    off.wait_for_selector("text=Room to spare")
    for tick in off.locator(".modal input[type=checkbox]").all():  # steps already late for a new order, or over capacity: the dialog asks for an explicit tick
        tick.check()
    off.locator(".modal").get_by_role("button", name="Create order").click()
    off.wait_for_url(re.compile(r"/m/orders/\d+$"), timeout=15000)
    check("the accepted request becomes an order", "B-PO-96001" in off.locator("h1").first.inner_text())

    # ---- Nothing scrolls sideways on a phone
    phone_off = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    po = phone_off.new_page()
    sign_in(po, "priya@companya.example", "loom1234")
    check("on a phone the office sidebar becomes a tab bar", po.locator("nav.tabbar").is_visible())
    phone_buy = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pb = phone_buy.new_page()
    sign_in(pb, "hannah@companyb.example", "buyer1234")
    pages = [(po, "/m"), (po, "/m/requests"), (po, "/m/buyers"), (po, "/m/reports"), (po, "/m/settings"), (po, "/m/orders/1"), (po, "/m/units"),
             (pb, "/b/me"), (pb, "/b/me/orders"), (pb, "/b/me/orders/1"), (pb, "/b/me/requests"), (pb, "/b/me/requests/new"), (sup, "/s")]
    wide = []
    for pg, path in pages:
        pg.goto(BASE + path)
        pg.wait_for_timeout(700)
        over = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if over > 1:
            wide.append((path, over))
    check(f"no page scrolls sideways on a phone ({len(pages)} checked)", not wide)
    if wide:
        print("   sideways:", wide)
    b.close()

print("errors:", errors or "none")
failed = [n for n, ok in results if not ok]
print("FAILED:", failed or "none")
sys.exit(1 if failed or errors else 0)
