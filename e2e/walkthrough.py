"""Browser walkthrough of every screen; saves screenshots to e2e/shots/.

Needs a freshly seeded database and the app on :4000 (npm start).
    pip install playwright && python -m playwright install chromium
    python e2e/walkthrough.py
"""
import os, sqlite3, struct, sys, time, zlib
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "shots"
OUT.mkdir(exist_ok=True)
DB = ROOT.parent / "backend" / "data" / "loomtrack.db"
token = sqlite3.connect(DB).execute("SELECT link_token FROM buyers WHERE name LIKE 'Company C%'").fetchone()[0]


def test_photo() -> bytes:
    """A small gradient PNG standing in for a phone-camera photo."""
    w, h = 320, 240
    rows = (bytes([0]) + b"".join(bytes([120 + x * 100 // w, 130 + y * 60 // h, 140]) for x in range(w)) for y in range(h))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
    return header + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


errors = []

with sync_playwright() as p:
    b = p.chromium.launch()

    # --- Office (desktop) ---
    ctx = b.new_context(viewport={"width": 1320, "height": 900})
    pg = ctx.new_page()
    pg.on("console", lambda m: m.type == "error" and errors.append(f"office: {m.text}"))
    pg.on("pageerror", lambda e: errors.append(f"office pageerror: {e}"))
    pg.goto(f"{BASE}/login")
    pg.screenshot(path=OUT / "01-login.png")
    pg.fill("input[autocomplete=username]", "priya@companya.in")
    pg.fill("input[type=password]", "loom1234")
    pg.click("button.btn-primary")
    pg.wait_for_selector("table.board tbody tr")
    time.sleep(0.5)
    pg.screenshot(path=OUT / "02-board.png", full_page=True)

    pg.click("text=B-PO-88213")
    pg.wait_for_selector("text=Delay projection")
    time.sleep(0.5)
    pg.screenshot(path=OUT / "03-detail-88213.png", full_page=True)

    pg.goto(f"{BASE}/m/orders/new")
    pg.wait_for_selector("text=Purchase order")
    pg.fill("input[placeholder='B-PO-88350']", "B-PO-88350")
    pg.select_option("select >> nth=0", label="Company B (UK)")
    pg.fill("input[placeholder=\"Men's crew neck tee\"]", "Men's raglan tee")
    pg.fill("input[placeholder=Navy]", "Charcoal")
    pg.fill("input[type=date]", "2026-12-18")
    pg.select_option("select >> nth=1", label="Unit 1 · Avinashi Road")
    for i, q in enumerate(["800", "1600", "1600", "900", "300"]):
        pg.fill(f"input[aria-label^='Quantity'] >> nth={i}", q)
    pg.wait_for_selector("text=Cutting")
    time.sleep(0.5)
    pg.screenshot(path=OUT / "04-new-order.png", full_page=True)
    pg.click("text=Create order")
    pg.wait_for_selector("text=Delay projection")
    pg.screenshot(path=OUT / "05-created.png", full_page=True)

    pg.goto(f"{BASE}/m/buyers")
    pg.wait_for_selector("text=Sent to buyers")
    pg.screenshot(path=OUT / "06-buyers.png", full_page=True)

    # --- Supervisor (phone) ---
    phone = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    sp = phone.new_page()
    sp.on("console", lambda m: m.type == "error" and errors.append(f"phone: {m.text}"))
    sp.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}"))
    sp.goto(f"{BASE}/login")
    sp.fill("input[autocomplete=username]", "9840000001")
    sp.fill("input[type=password]", "1111")
    sp.click("button.btn-primary")
    sp.wait_for_selector(".stage-card")
    time.sleep(0.5)
    sp.screenshot(path=OUT / "07-sup-home.png", full_page=True)
    sp.click(".stage-card >> text=C-PO-0488")
    sp.wait_for_selector(".qty-input")
    sp.fill(".qty-input", "640")
    sp.fill("textarea", "நூல் பற்றாக்குறை, மதியம் இரண்டு மணி நேரம் லைன் நின்றது")
    sp.set_input_files("input[type=file]", files=[{"name": "floor.png", "mimeType": "image/png",
        "buffer": test_photo()}])
    time.sleep(0.6)
    sp.screenshot(path=OUT / "08-sup-update.png", full_page=True)
    sp.click("text=அனுப்பு")
    sp.wait_for_selector(".stage-card", timeout=15000)
    time.sleep(1)
    sp.screenshot(path=OUT / "09-sup-after-send.png", full_page=True)

    # Back in the office: the update with its AI translation (classification runs in the background).
    time.sleep(12)
    pg.goto(f"{BASE}/m")
    pg.wait_for_selector("table.board tbody tr")
    pg.click("text=C-PO-0488")
    pg.wait_for_selector("text=Floor updates")
    time.sleep(0.5)
    pg.screenshot(path=OUT / "10-detail-0488.png", full_page=True)

    # --- Buyer link ---
    bc = b.new_context(viewport={"width": 1100, "height": 900})
    bp = bc.new_page()
    bp.on("pageerror", lambda e: errors.append(f"buyer pageerror: {e}"))
    bp.goto(f"{BASE}/b/{token}")
    bp.wait_for_selector("article")
    time.sleep(0.8)
    bp.screenshot(path=OUT / "11-buyer.png", full_page=True)
    b.close()

print("browser errors:", errors or "none")
print(f"screenshots in {OUT}")
sys.exit(1 if errors else 0)
