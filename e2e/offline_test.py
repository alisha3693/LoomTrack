"""Offline queue: send while offline, check it waits, reconnect, check it lands exactly once.

Needs the app on :4000 (npm start).  python e2e/offline_test.py
"""
import os, sqlite3, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
ROOT = Path(__file__).resolve().parent
DB = ROOT.parent / "backend" / "data" / "loomtrack.db"
OUT = ROOT / "shots"
OUT.mkdir(exist_ok=True)

def total(po, code):
    db = sqlite3.connect(DB)
    return db.execute(
        "SELECT COALESCE(SUM(d.qty),0) FROM daily_updates d JOIN milestones m ON m.id=d.milestone_id JOIN orders o ON o.id=m.order_id WHERE o.po_no=? AND m.code=?",
        (po, code)).fetchone()[0]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/login")
    pg.fill("input[autocomplete=username]", "9840000003")  # Selvi, Unit 3
    pg.fill("input[type=password]", "3333")
    pg.click("button.btn-primary")
    pg.wait_for_selector(".stage-card")

    before = total("D-PO-1112", "STITCH")
    ctx.set_offline(True)
    pg.click(".stage-card >> text=D-PO-1112")
    pg.wait_for_selector(".qty-input")
    pg.fill(".qty-input", "355")
    pg.fill("textarea", "இரண்டு ஆபரேட்டர் லீவு")
    pg.click("text=அனுப்பு")
    pg.wait_for_selector(".queue-chip", timeout=10000)
    time.sleep(0.5)
    pg.screenshot(path=OUT / "12-offline-queued.png", full_page=True)
    offline_total = total("D-PO-1112", "STITCH")
    chip = pg.inner_text(".queue-chip")

    # Reload while offline: the queued item must survive (IndexedDB), the screen still renders from cache.
    ctx.set_offline(False)
    ctx.set_offline(True)
    survived = pg.evaluate("""() => new Promise(r => { const q = indexedDB.open('loomtrack'); q.onsuccess = () => {
        const g = q.result.transaction('outbox').objectStore('outbox').getAll(); g.onsuccess = () => r(g.result.length); }; })""")

    ctx.set_offline(False)
    pg.evaluate("window.dispatchEvent(new Event('online'))")
    for _ in range(20):
        if total("D-PO-1112", "STITCH") > before:
            break
        time.sleep(0.5)
    time.sleep(1.5)
    after = total("D-PO-1112", "STITCH")
    pg.screenshot(path=OUT / "13-back-online.png", full_page=True)
    chip_gone = pg.query_selector(".queue-chip") is None
    b.close()

print(f"before={before} while_offline={offline_total} chip='{chip}' queued_in_idb={survived} after={after} chip_gone={chip_gone}")
assert offline_total == before, "nothing should reach the server while offline"
assert survived == 1
assert after == before + 355, "update should land exactly once"
print("OFFLINE QUEUE OK")
