"""Is the app installable, does it open with no network, and what does a supervisor see the first time?

Needs the app running (a production build: npm run build) with the demo data:
    python e2e/pwa.py        (LOOMTRACK_URL can point at another instance; localhost counts as secure, a plain http LAN address does not)
Exits with 1 if any check fails.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("LOOMTRACK_URL", "http://localhost:4000")
SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
PIXEL = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
failed = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failed.append(name)


def sign_in(pg, login="9840000001", pin="1111"):
    pg.goto(f"{BASE}/login")
    pg.fill("input[autocomplete=username]", login)
    pg.fill("input[type=password]", pin)
    pg.click("button.btn-primary")
    pg.wait_for_url("**/s", timeout=8000)


with sync_playwright() as p:
    b = p.chromium.launch()

    # --- Android Chrome: the manifest, the icons, the service worker, and a cold start with no network
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=PIXEL)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{BASE}/login")
    pg.wait_for_selector("form")

    m = ctx.request.get(f"{BASE}/manifest.webmanifest")
    manifest = m.json()
    check("the manifest is served and parses", m.ok and manifest["name"] == "LoomTrack")
    check("it opens standalone, in the app's own scope", manifest["display"] == "standalone" and manifest["scope"] == "/" and manifest["id"] == "/")
    sizes = {(i["sizes"], i["purpose"]) for i in manifest["icons"] if i["type"] == "image/png"}
    check("it has 192 and 512 icons and a maskable one", {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= sizes, str(sizes))
    check("every icon in it can be fetched", all(ctx.request.get(BASE + i["src"]).ok for i in manifest["icons"]))
    check("the apple touch icon exists", pg.locator('link[rel="apple-touch-icon"]').count() == 1 and ctx.request.get(f"{BASE}/apple-touch-icon.png").ok)

    cdp = ctx.new_cdp_session(pg)
    cdp.send("Page.enable")
    pg.evaluate("navigator.serviceWorker.ready.then(() => true)")
    pg.reload()
    pg.wait_for_function("navigator.serviceWorker.controller !== null", timeout=8000)
    check("the service worker is running", True)
    cached = pg.evaluate("caches.keys().then(async ks => { const c = await caches.open(ks[0]); return (await c.keys()).map(r => new URL(r.url).pathname) })")
    check("the page and its scripts are stored for offline use", "/" in cached and any(u.startswith("/assets/") and u.endswith(".js") for u in cached), str(cached))
    errs = cdp.send("Page.getInstallabilityErrors")["installabilityErrors"]
    check("Chrome finds nothing in the way of installing", errs == [], str(errs))
    sw = ctx.request.get(f"{BASE}/sw.js")
    check("the service worker is never cached for long", "no-cache" in sw.headers.get("cache-control", ""), sw.headers.get("cache-control", ""))

    # A supervisor's first time: welcome, once; then offline start from the stored app and the stored orders.
    sign_in(pg)
    pg.wait_for_selector(".welcome")
    pg.screenshot(path=SHOTS / "pwa-welcome.png")
    check("the first sign-in shows a short welcome in Tamil", "புரிந்தது" in pg.locator(".welcome").inner_text())
    pg.click(".welcome button")
    pg.reload()
    pg.wait_for_selector(".stage-card")
    check("the welcome does not come back on this phone", pg.locator(".welcome").count() == 0)
    ctx.set_offline(True)
    pg.goto(f"{BASE}/s")
    pg.wait_for_selector(".stage-card", timeout=8000)
    check("with no network the installed app still opens and shows the orders", pg.locator(".stage-card").count() > 0)
    try:
        pg.wait_for_selector(".banner-warn", timeout=4000)
    except Exception:
        pass
    check("it says it is offline", pg.locator(".banner-warn").count() > 0, f"onLine={pg.evaluate('navigator.onLine')} url={pg.url} banners={pg.locator('.banner').evaluate_all('els => els.map(e => e.className)')}")
    ctx.set_offline(False)

    pg2 = ctx.new_page()
    pg2.goto(f"{BASE}/install")
    pg2.wait_for_selector(".install-steps, .btn-primary")
    pg2.screenshot(path=SHOTS / "pwa-install-android.png")
    check("the install page tells an Android phone what to do", pg2.locator(".install-steps li").count() == 3 or pg2.locator("button.btn-primary").count() == 1)
    check("it is in Tamil by default", "நிறுவ" in pg2.inner_text("main"))
    check("no script errors", not errors, str(errors))
    ctx.close()

    # --- iPhone Safari: no install button exists, so the page has to explain Share, Add to Home Screen
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=IPHONE)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/install")
    pg.wait_for_selector(".install-steps")
    pg.screenshot(path=SHOTS / "pwa-install-ios.png")
    text = pg.inner_text("main")
    check("an iPhone is told to use Share and Add to Home Screen", "Add to Home Screen" in text and "Safari" in text)
    sign_in(pg)
    pg.click(".welcome button")
    pg.wait_for_selector(".install-banner")
    check("the supervisor's home offers the install on an iPhone", pg.locator(".install-banner").count() == 1)
    pg.click(".install-banner .btn-ghost")
    pg.reload()
    pg.wait_for_selector(".stage-card")
    check("'Later' is remembered", pg.locator(".install-banner").count() == 0)
    ctx.close()
    b.close()

print("\nFAILED: " + (", ".join(failed) if failed else "none"))
sys.exit(1 if failed else 0)
