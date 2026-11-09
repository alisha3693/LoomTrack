"""Messages outside the app: who gets which event by email and WhatsApp, the consent rules, the sender with its
retries, the delivery reports that come back, and the wording sent to Meta for approval."""

import asyncio
import hashlib
import hmac
import json
import re
import smtplib

import httpx
import pytest

from loomtrack import config
from loomtrack.routes import notifications
from loomtrack.services import delivery, notify
from test_api import _new_login, _new_order, env, fake_classify  # noqa: F401

SMTP_ENV = {"LOOMTRACK_SMTP_HOST": "smtp.example.test", "LOOMTRACK_SMTP_FROM": "LoomTrack <orders@mill.example>", "LOOMTRACK_SMTP_USER": "u", "LOOMTRACK_SMTP_PASSWORD": "p"}
WA_ENV = {"LOOMTRACK_WA_TOKEN": "tok", "LOOMTRACK_WA_PHONE_ID": "1234567890", "LOOMTRACK_WA_VERIFY_TOKEN": "verify-me", "LOOMTRACK_WA_APP_SECRET": "shh"}


@pytest.fixture
def providers(monkeypatch):
    for k, v in {**SMTP_ENV, **WA_ENV}.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def no_providers(monkeypatch):
    for k in [*SMTP_ENV, *WA_ENV]:
        monkeypatch.delenv(k, raising=False)


def _rows(env, **where):
    sql = "SELECT * FROM outbox_messages" + "".join(f" {'WHERE' if i == 0 else 'AND'} {k} = ?" for i, k in enumerate(where)) + " ORDER BY id"
    return env["db"].execute(sql, tuple(where.values())).fetchall()


def _enable_whatsapp(env, buyer_id=1, number="+91 98765-43210", optin=True):
    """What a buyer's own "My details" save does: a number is on file only together with the buyer's agreement."""
    number = notifications.clean_number(number) if (number or "").strip() else None
    on = bool(number) and optin
    env["db"].execute(
        """UPDATE buyers SET whatsapp_number = ?, whatsapp_opt_in = ?, whatsapp_opt_in_at = CASE WHEN ? THEN datetime('now') END,
             whatsapp_opt_in_by = CASE WHEN ? THEN 1 END WHERE id = ?""",
        (number, int(on), on, on, buyer_id),
    )
    return {"whatsappNumber": number}


def _email_on(env, buyer_id, on):
    env["db"].execute("UPDATE buyers SET notify_email = ? WHERE id = ?", (int(on), buyer_id))


def _say(env, oid, text="Samples left the unit today."):
    """Tell the order's buyer something by email (an order cancellation is the plainest event that goes to the buyer by email only)."""
    buyer_id, po = env["db"].execute("SELECT buyer_id, po_no FROM orders WHERE id = ?", (oid,)).fetchone()
    with env["db"]:
        notify.send(env["db"], "order_cancelled", buyer_id, oid, po=po, text=text)


# --- who gets what ---------------------------------------------------------------------------------------


def test_without_a_provider_the_messages_are_only_recorded(env, no_providers):
    oid = _new_order(env, "NT-1", 1).json()["id"]
    login = _new_login(env, 1, "hannah@buyerb.example")
    _say(env, oid)
    sent = [m for m in _rows(env, order_id=oid) if m["event"] == "order_cancelled"]
    assert [(m["channel"], m["recipient"], m["status"], m["audience"]) for m in sent] == [("email", login["login"], "logged", "buyer")]
    assert sent[0]["body"].startswith("Hello Hannah,") and "Samples left the unit today." in sent[0]["body"]


def test_with_a_provider_the_messages_wait_for_the_sender(env, providers):
    oid = _new_order(env, "NT-2", 1).json()["id"]
    _say(env, oid)
    assert {m["status"] for m in _rows(env, order_id=oid, event="order_cancelled")} == {"queued"}


def test_a_buyer_without_an_email_address_is_told_so_not_silently_skipped(env, no_providers):
    oid = _new_order(env, "NT-3", 2).json()["id"]                       # buyer C has no accounts
    _say(env, oid)
    (m,) = _rows(env, order_id=oid, event="order_cancelled")
    assert (m["status"], m["recipient"], m["error"]) == ("skipped", None, "No email address on file")


def test_email_can_be_switched_off_for_a_buyer(env, no_providers):
    oid = _new_order(env, "NT-4", 1).json()["id"]
    _email_on(env, 1, False)
    try:
        _say(env, oid)
        assert {(m["status"], m["error"]) for m in _rows(env, order_id=oid, event="order_cancelled")} == {("skipped", "Email is switched off for this buyer")}
    finally:
        _email_on(env, 1, True)


def test_a_buyers_reply_goes_to_the_merchandisers_by_email_only(env, no_providers):
    oid = _new_order(env, "NT-5", 1).json()["id"]
    with env["db"]:
        notify.send(env["db"], "buyer_reply", 1, oid, po="NT-5", request_no="REQ-1", text="Can we ship by air?")
    got = _rows(env, order_id=oid, event="buyer_reply")
    assert [(m["audience"], m["channel"], m["recipient"]) for m in got] == [("office", "email", "m@x.in")]
    assert "Buyer B answered on request REQ-1" in got[0]["body"]


# --- consent for WhatsApp -------------------------------------------------------------------------------


def test_whatsapp_goes_only_to_a_buyer_who_agreed_and_only_as_the_approved_template(env, providers):
    oid = _new_order(env, "NT-6", 1).json()["id"]

    def tell(text):
        with env["db"]:
            notify.send(env["db"], "delay_notice", 1, oid, po="NT-6", text=text)

    tell("Packing starts\ntomorrow.   We will   send photos.")
    assert _rows(env, order_id=oid, channel="whatsapp") == []                                    # not agreed yet
    _enable_whatsapp(env)
    try:
        tell("Packing starts\ntomorrow.   We will   send photos.")
        (m,) = _rows(env, order_id=oid, channel="whatsapp")
        assert (m["recipient"], m["template"], m["status"]) == ("+919876543210", "loomtrack_delay_notice", "queued")
        link = f"{config.public_url()}/b/{env['tokenB']}/orders/{oid}"                          # the buyer's own page for this order
        assert json.loads(m["params"]) == ["Buyer B", "NT-6", "Packing starts tomorrow. We will send photos.", link]   # one line, single spaces
        assert m["body"] == f"Hello Buyer B, there is a delay on PO NT-6: Packing starts tomorrow. We will send photos. The details are at {link} where you can acknowledge it."
        tell("x" * 400)
        assert all(len(v) <= notify.WA_VALUE_LIMIT for v in json.loads(_rows(env, order_id=oid, channel="whatsapp")[-1]["params"])[:-1])
        _say(env, oid)                                                                            # an event with no WhatsApp template: email only
        assert {m["channel"] for m in _rows(env, order_id=oid, event="order_cancelled")} == {"email"}
    finally:
        _enable_whatsapp(env, number="", optin=False)


def test_a_buyer_replying_stop_switches_whatsapp_off(env, providers):
    _enable_whatsapp(env)
    payload = {"entry": [{"changes": [{"value": {"messages": [{"from": "919876543210", "type": "text", "text": {"body": " STOP "}}]}}]}]}
    assert _webhook(env, payload).status_code == 200
    assert env["db"].execute("SELECT whatsapp_opt_in FROM buyers WHERE id = 1").fetchone()[0] == 0
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"] = "919000000000"        # someone else's number changes nothing
    _enable_whatsapp(env)
    _webhook(env, payload)
    assert env["db"].execute("SELECT whatsapp_opt_in FROM buyers WHERE id = 1").fetchone()[0] == 1
    _enable_whatsapp(env, number="", optin=False)


# --- the sender ---------------------------------------------------------------------------------------------


def _deliver(env, smtp=None, whatsapp=None):
    sent = []

    def default_smtp(cfg, to, subject, body):
        sent.append(("email", to, subject))

    async def default_wa(cfg, to, template, values, client, language=None):
        sent.append(("whatsapp", to, template, values))
        return f"wamid.{len(sent)}"

    n = asyncio.run(delivery.deliver_pending(env["db"], smtp=smtp or default_smtp, whatsapp=whatsapp or default_wa))
    return n, sent


def _clear(env):
    env["db"].execute("DELETE FROM outbox_messages")


def test_the_sender_sends_each_queued_message_once_and_keeps_the_provider_id(env, providers):
    _clear(env)
    oid = _new_order(env, "NT-7", 1).json()["id"]
    _enable_whatsapp(env)
    with env["db"]:
        notify.send(env["db"], "delay_notice", 1, oid, po="NT-7", text="Knitting is two days behind.")
    n, sent = _deliver(env)
    assert n >= 2 and {s[0] for s in sent} == {"email", "whatsapp"}
    wa = next(s for s in sent if s[0] == "whatsapp")
    assert wa[1] == "+919876543210" and wa[2] == "loomtrack_delay_notice"
    done = _rows(env, order_id=oid, event="delay_notice")
    assert {m["status"] for m in done} == {"sent"} and all(m["sent_at"] for m in done)
    assert next(m for m in done if m["channel"] == "whatsapp")["provider_id"].startswith("wamid.")
    assert _deliver(env)[0] == 0                                                              # nothing is sent twice
    _enable_whatsapp(env, number="", optin=False)


def test_a_failure_is_kept_with_its_reason_and_retried_later_then_gives_up(env, providers):
    _clear(env)
    oid = _new_order(env, "NT-8", 1).json()["id"]
    _say(env, oid)

    def down(cfg, to, subject, body):
        raise delivery.SendError("Could not send the email: timed out")

    _deliver(env, smtp=down)
    (m,) = [m for m in _rows(env, order_id=oid, event="order_cancelled", channel="email")]
    assert (m["status"], m["attempts"], m["error"]) == ("queued", 1, "Could not send the email: timed out") and m["not_before"]
    assert _deliver(env, smtp=down)[0] == 0                                                   # not due yet: no hammering
    for expect in (2, 3):
        env["db"].execute("UPDATE outbox_messages SET not_before = datetime('now', '-1 minute') WHERE id = ?", (m["id"],))
        _deliver(env, smtp=down)
        assert _rows(env, id=m["id"])[0]["attempts"] == expect and _rows(env, id=m["id"])[0]["status"] == "queued"
    env["db"].execute("UPDATE outbox_messages SET not_before = NULL WHERE id = ?", (m["id"],))
    _deliver(env, smtp=down)
    last = _rows(env, id=m["id"])[0]
    assert (last["status"], last["attempts"]) == ("failed", 4)

    # The office can send it again once the problem is fixed.
    assert env["client"].post(f"/api/m/outbox/{m['id']}/retry", headers=env["merch"]).status_code == 200
    assert _deliver(env)[0] == 1 and _rows(env, id=m["id"])[0]["status"] == "sent"
    assert env["client"].post(f"/api/m/outbox/{m['id']}/retry", headers=env["merch"]).status_code == 409   # only a failed one


def test_a_refusal_that_cannot_succeed_fails_at_once(env, providers):
    _clear(env)
    oid = _new_order(env, "NT-9", 1).json()["id"]
    _say(env, oid)

    def refused(cfg, to, subject, body):
        raise delivery.SendError("The mail server refused the address", permanent=True)

    _deliver(env, smtp=refused)
    assert {(m["status"], m["attempts"]) for m in _rows(env, order_id=oid, event="order_cancelled")} == {("failed", 1)}


def test_a_message_queued_before_the_provider_was_removed_fails_with_a_reason(env, providers, monkeypatch):
    _clear(env)
    oid = _new_order(env, "NT-10", 1).json()["id"]
    _say(env, oid)
    monkeypatch.delenv("LOOMTRACK_SMTP_HOST")
    _deliver(env)
    assert {(m["status"], m["error"]) for m in _rows(env, order_id=oid, event="order_cancelled")} == {("failed", "Email is not set up any more")}


def test_smtp_logs_in_over_starttls_and_sends_a_plain_message(monkeypatch):
    calls = []

    class Fake:
        def __init__(self, host, port, timeout=None, **kw):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["Subject"], msg["From"], msg.get_content().strip()))

    monkeypatch.setattr(smtplib, "SMTP", Fake)
    cfg = {"host": "smtp.example.test", "port": 587, "user": "u", "password": "p", "from": "LoomTrack <orders@mill.example>", "security": "starttls"}
    delivery.send_smtp(cfg, "buyer@x.example", "Hi", "Body")
    assert calls == [("connect", "smtp.example.test", 587), ("starttls",), ("login", "u", "p"), ("send", "buyer@x.example", "Hi", "LoomTrack <orders@mill.example>", "Body")]


def test_smtp_errors_become_readable_failures(monkeypatch):
    class Refuses:
        def __init__(self, *a, **k):
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    monkeypatch.setattr(smtplib, "SMTP", Refuses)
    with pytest.raises(delivery.SendError, match="user name or password"):
        delivery.send_smtp({"host": "h", "port": 587, "user": "u", "password": "p", "from": "a@b.c", "security": "starttls"}, "x@y.z", "s", "b")


def _whatsapp_call(handler, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await delivery.send_whatsapp({"token": "tok", "phone_id": "111", "version": "v21.0", "language": "en"}, "+91 98765 43210", "loomtrack_order_message", ["a", "b"], client, **kw)

    return asyncio.run(go())


def test_the_whatsapp_request_has_the_shape_meta_expects():
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers["authorization"], body=json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]})

    assert _whatsapp_call(handler) == "wamid.ABC"
    assert seen["url"] == "https://graph.facebook.com/v21.0/111/messages" and seen["auth"] == "Bearer tok"
    assert seen["body"] == {
        "messaging_product": "whatsapp", "to": "919876543210", "type": "template",
        "template": {"name": "loomtrack_order_message", "language": {"code": "en"},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}]},
    }


@pytest.mark.parametrize("status,code,permanent", [(400, 132001, True), (401, 190, True), (429, 130429, False), (503, None, False), (400, 4, False)])
def test_whatsapp_errors_are_split_into_worth_retrying_and_not(status, code, permanent):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "nope", "code": code}})

    with pytest.raises(delivery.SendError) as e:
        _whatsapp_call(handler)
    assert e.value.permanent is permanent and "nope" in str(e.value)


def test_an_unreachable_whatsapp_is_a_retryable_failure():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(delivery.SendError) as e:
        _whatsapp_call(handler)
    assert not e.value.permanent


# --- what WhatsApp tells us back ---------------------------------------------------------------------


def _webhook(env, payload, secret="shh", sign=True):
    raw = json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if sign:
        headers["x-hub-signature-256"] = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return env["client"].post("/api/webhooks/whatsapp", content=raw, headers=headers)


def _report(wamid, status, **extra):
    return {"entry": [{"changes": [{"value": {"statuses": [{"id": wamid, "status": status, **extra}]}}]}]}


def test_delivery_reports_move_a_message_forward_and_never_back(env, providers):
    _clear(env)
    env["db"].execute("INSERT INTO outbox_messages (buyer_id, channel, subject, body, status, provider_id) VALUES (1, 'whatsapp', 's', 'b', 'sent', 'wamid.R1')")
    status = lambda: env["db"].execute("SELECT status FROM outbox_messages WHERE provider_id = 'wamid.R1'").fetchone()[0]
    assert _webhook(env, _report("wamid.R1", "delivered")).status_code == 200 and status() == "delivered"
    _webhook(env, _report("wamid.R1", "read"))
    assert status() == "read"
    _webhook(env, _report("wamid.R1", "delivered"))                                            # a late, older report
    assert status() == "read"
    _webhook(env, _report("wamid.R1", "failed", errors=[{"code": 131026, "title": "Message undeliverable"}]))
    assert status() == "read"                                                                  # it was read, so it was delivered


def test_a_failed_report_keeps_the_reason(env, providers):
    _clear(env)
    env["db"].execute("INSERT INTO outbox_messages (buyer_id, channel, subject, body, status, provider_id) VALUES (1, 'whatsapp', 's', 'b', 'sent', 'wamid.R2')")
    _webhook(env, _report("wamid.R2", "failed", errors=[{"code": 131026, "title": "Message undeliverable"}]))
    row = env["db"].execute("SELECT status, error FROM outbox_messages WHERE provider_id = 'wamid.R2'").fetchone()
    assert (row["status"], row["error"]) == ("failed", "Message undeliverable (131026)")


def test_the_webhook_trusts_only_calls_signed_with_the_app_secret(env, providers, monkeypatch):
    env["db"].execute("INSERT INTO outbox_messages (buyer_id, channel, subject, body, status, provider_id) VALUES (1, 'whatsapp', 's', 'b', 'sent', 'wamid.R3')")
    assert _webhook(env, _report("wamid.R3", "read"), sign=False).status_code == 403
    assert _webhook(env, _report("wamid.R3", "read"), secret="wrong").status_code == 403
    assert env["db"].execute("SELECT status FROM outbox_messages WHERE provider_id = 'wamid.R3'").fetchone()[0] == "sent"
    monkeypatch.delenv("LOOMTRACK_WA_APP_SECRET")
    assert _webhook(env, _report("wamid.R3", "read")).status_code == 503                      # no secret, no way to check: refuse


def test_meta_can_verify_the_webhook_address(env, providers):
    c = env["client"]
    ok = c.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"})
    assert (ok.status_code, ok.text) == (200, "12345")
    assert c.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"}).status_code == 403


# --- setup and the test button ---------------------------------------------------------------------------------


def test_the_settings_page_shows_what_is_set_up_but_never_a_secret(env, providers):
    r = env["client"].get("/api/m/notifications", headers=env["merch"])
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == {"configured": True, "from": "LoomTrack <orders@mill.example>", "host": "smtp.example.test"}
    assert body["whatsapp"]["configured"] and body["whatsapp"]["webhookReady"]
    for secret in ("tok", "shh", "verify-me", "1234567890", '"p"'):
        assert secret not in r.text
    assert {e["key"] for e in body["events"]} == set(notify.EVENTS)
    env["client"].cookies.clear()                                                              # an earlier test signed a buyer in
    assert env["client"].get("/api/m/notifications").status_code == 401
    assert env["client"].get("/api/m/notifications", headers=env["sup1"]).status_code == 403


def test_the_test_button_explains_what_is_missing(env, no_providers):
    c, h = env["client"], env["merch"]
    assert "not set up" in c.post("/api/m/notifications/test", headers=h, json={"channel": "email", "to": "a@b.co"}).json()["error"]
    assert "not set up" in c.post("/api/m/notifications/test", headers=h, json={"channel": "whatsapp", "to": "+919876543210"}).json()["error"]


def test_the_test_button_sends_one_message(env, providers, monkeypatch):
    got = []
    monkeypatch.setattr(delivery, "send_smtp", lambda cfg, to, subject, body: got.append((to, subject)))
    r = env["client"].post("/api/m/notifications/test", headers=env["merch"], json={"channel": "email", "to": "me@mill.example"})
    assert r.status_code == 200 and got == [("me@mill.example", "LoomTrack test message")]
    assert env["client"].post("/api/m/notifications/test", headers=env["merch"], json={"channel": "email", "to": "not-an-address"}).status_code == 400


# --- the wording ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("event", notify.TEMPLATES, ids=lambda e: e.key)
def test_every_whatsapp_template_follows_metas_rules(event):
    body = event.wa_numbered
    assert re.fullmatch(r"[a-z0-9_]{1,512}", event.template)
    assert len(body) <= 1024 and len(event.wa_names) == len(set(event.wa_names)), "a variable is used once"
    assert not re.match(r"\s*\{\{", body) and not re.search(r"\}\}\s*$", body), "a body does not start or end with a variable"
    assert not re.search(r"\}\}\s*\{\{", body), "two variables never touch"
    assert re.findall(r"\{\{(\d+)\}\}", body) == [str(n) for n in range(1, len(event.wa_names) + 1)]
    assert all(n in notify.SAMPLES for n in event.wa_names), "Meta needs an example for every variable"
    assert "\n" not in body and "  " not in body
    # Templates are submitted as utility messages: no sales wording.
    assert not re.search(r"\b(offer|discount|sale|promo|free|buy now)\b", body, re.I)


def test_every_event_renders_for_both_people_without_a_leftover_placeholder():
    for ev in notify.EVENTS.values():
        values = {**notify.SAMPLES, "what": "order request", "outcome": "approved"}
        subject, body = notify.render_email(ev, "Hannah", values)
        assert "{" not in subject + body, ev.key
        if ev.wa:
            text = notify.render_whatsapp(ev, notify.wa_values(ev, values))
            assert "{" not in text, ev.key


def test_footer_fits_metas_limit():
    assert len(notify.WA_FOOTER) <= 60


def test_the_document_for_meta_is_the_one_the_app_sends():
    from loomtrack.services import whatsapp_doc

    assert whatsapp_doc.TARGET.read_text(encoding="utf-8") == whatsapp_doc.build(), "run: python -m loomtrack.services.whatsapp_doc"
    text = whatsapp_doc.build()
    for ev in notify.TEMPLATES:
        assert ev.wa_numbered in text and ev.template in text


# --- cancelling an order ---------------------------------------------------------------------------------


def test_cancelling_an_order_tells_the_buyer_the_reason_and_shows_it_on_their_page(env, no_providers):
    oid = _new_order(env, "NT-CAN", 1).json()["id"]
    _new_login(env, 1, "hannah@buyerc.example")
    c, tok = env["client"], env["tokenB"]
    assert c.post(f"/api/m/orders/{oid}/cancel", headers=env["merch"], json={"reason": "  "}).status_code == 400
    r = c.post(f"/api/m/orders/{oid}/cancel", headers=env["merch"], json={"reason": "The fabric mill cannot supply in time."})
    assert r.status_code == 200, r.text
    sent = [m for m in _rows(env, order_id=oid) if m["event"] == "order_cancelled"]
    assert sent and "NT-CAN" in sent[0]["subject"] and "The fabric mill cannot supply in time." in sent[0]["body"]
    assert not any(m["channel"] == "whatsapp" for m in sent)  # a cancellation is email only
    page = c.get(f"/api/b/{tok}").json()
    assert all(o["id"] != oid for o in page["orders"])
    assert [(o["poNo"], o["reason"]) for o in page["cancelledOrders"] if o["id"] == oid] == [("NT-CAN", "The fabric mill cannot supply in time.")]
    assert c.post(f"/api/m/orders/{oid}/cancel", headers=env["merch"], json={"reason": "again"}).status_code == 409


def test_only_a_merchandiser_can_cancel(env):
    oid = _new_order(env, "NT-CAN2", 1).json()["id"]
    assert env["client"].post(f"/api/m/orders/{oid}/cancel", json={"reason": "no reason"}).status_code in (401, 403)


# --- the notifications page ------------------------------------------------------------------------------


def test_the_notifications_page_lists_each_event_once_and_remembers_what_was_seen(env, no_providers):
    oid = _new_order(env, "NT-FEED", 1).json()["id"]
    _new_login(env, 1, "a@feed.example")
    _new_login(env, 1, "b@feed.example")  # two recipients must still be one entry
    c, tok = env["client"], env["tokenB"]
    c.post(f"/api/m/orders/{oid}/cancel", headers=env["merch"], json={"reason": "Mill delay."})
    feed = c.get(f"/api/b/{tok}/feed").json()
    cancelled = [i for i in feed["items"] if i["event"] == "order_cancelled" and i["poNo"] == "NT-FEED"]
    assert len(cancelled) == 1 and cancelled[0]["text"].startswith("Your order for PO NT-FEED") and "Hello" not in cancelled[0]["text"]
    assert c.get(f"/api/b/{tok}/badges").json()["notifications"] >= 1
    assert c.post(f"/api/b/{tok}/feed/read").status_code == 200
    assert c.get(f"/api/b/{tok}/badges").json()["notifications"] == 0
    _say(env, oid)  # conversation notices are not part of the page
    assert all(i["event"] not in ("order_message", "order_message_in") for i in c.get(f"/api/b/{tok}/feed").json()["items"])
    office = c.get("/api/m/feed", headers=env["merch"]).json()
    assert office["seenUpTo"] == 0 and all(i["event"] not in ("order_message", "order_message_in") for i in office["items"])

