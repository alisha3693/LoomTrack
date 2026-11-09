"""Writes docs/WHATSAPP_TEMPLATES.md from the event list in notify.py, so the document sent to Meta for review
can never differ from what the app sends. Run from the backend folder:

    python -m loomtrack.services.whatsapp_doc

A test fails when the file on disk is out of date.
"""

from __future__ import annotations

import json

from .. import config
from . import notify

TARGET = config.REPO_ROOT / "docs" / "WHATSAPP_TEMPLATES.md"

USE_CASE = {
    "request_received": "A buyer sent a complete order through LoomTrack; this confirms we have it and gives the page where they can follow it.",
    "request_accepted": "The merchandiser confirmed the order; this gives our order number and the link to track its progress.",
    "delay_notice": "Production is behind plan on an order; the merchandiser confirmed a delay notice, and the buyer acknowledges it on the order's page.",
}

MEANING = {
    "buyer": "the buyer's company name",
    "request_no": "the request number",
    "po": "the buyer's PO number",
    "date": "a date",
    "order_no": "our order number",
    "title": "what needs approving",
    "summary": "a one-line summary of the change",
    "text": "a short note written by the merchandiser (one line, up to 120 characters)",
    "link": "the buyer's own tracking page for this order (an https address)",
}

INTRO = """# WhatsApp templates for Meta review

Everything needed to register LoomTrack's WhatsApp messages with Meta, and to turn on email. This file is **generated** from `backend/loomtrack/services/notify.py` (`python -m loomtrack.services.whatsapp_doc`), so the wording below is exactly what the app sends. A test fails if the two drift apart.

## What is sent, and to whom

LoomTrack keeps WhatsApp to what matters to a buyer: **where their order is**. The buyer sends a complete order, the merchandiser confirms it, the supervisors on the floor report progress to the merchandiser in the app, and the buyer can follow it on their own tracking page. WhatsApp tells the buyer three things, each with the link to that page:

1. **Order received**: we have the order they sent.
2. **Order confirmed**: it is accepted, with our order number.
3. **Delay**: production is behind plan; they acknowledge it on the page.

Everything else (the merchandiser and the supervisors working on the order) stays in the app, with email for the office. WhatsApp is used only for **buyers who agreed to it** (the merchandiser records the number and the buyer's agreement on the buyer's profile; the agreement, who recorded it and when are stored). Every message is one of the **{count} templates** below, all in the **Utility** category: each one is about an order the buyer already has with the company, and none promotes anything.

A buyer can stop WhatsApp at any time by replying **STOP**; the webhook switches it off at once. Every template carries that line as its footer.

## Before you submit

1. **Meta Business account** (business.facebook.com), with the business verified. Template approval and a real phone number both need it.
2. **App** at developers.facebook.com: type *Business*, add the **WhatsApp** product.
3. **A phone number.** For the demo, Meta gives a free *test number* that can message up to 5 verified numbers. For the client, add their own number in WhatsApp Manager; it must not be in use on the WhatsApp or WhatsApp Business app. Its display name is reviewed too.
4. Note three values for `backend/.env`: the **Phone number ID** and the **WhatsApp Business Account ID** (WhatsApp, API Setup), and a **permanent access token** (Business settings, System users, add a user, give it the app and the `whatsapp_business_messaging` and `whatsapp_business_management` permissions, generate a token with no expiry). The temporary token on the API Setup page lasts 24 hours.
5. Submit the templates below, either one by one in **WhatsApp Manager, Message templates, Create template**, or with the API call at the end of each section. Approval of a Utility template usually takes minutes to a day.

In the form: *Category* **Utility**, *Language* **English**, *Name* as given, *Header* none, then paste the body and footer. Leave *Buttons* empty. For every variable Meta asks for a sample value; use the ones in the tables.

## The tracking link

There is **no button**: the link is written in the message text, as a variable (the last one in each template). That way the templates do not change when the address does: today it can be a free tunnel address for the demo, later the company's own domain, and the same approved templates keep working.

The app builds the link from `LOOMTRACK_PUBLIC_URL` in `backend/.env` and the buyer's own tracking code: `https://<address>/b/<code>/orders/<order>` (or `/orders` for an order not confirmed yet). The page opens without a password, so treat the link like the buyer's key. Set `LOOMTRACK_PUBLIC_URL` to an https address that opens from outside before the first real message goes; a `localhost` link is useless on a buyer's phone.

## Cost, said plainly

The Cloud API itself is free to use and so is the test number. Meta charges **per template message delivered**, by category and country (Utility is the cheapest paid category; a Utility template is free when it is sent inside a 24-hour window the buyer opened by messaging you). There is no monthly fee. Meta changes the rate card from time to time, so read the current one at developers.facebook.com/docs/whatsapp/pricing before the client goes live. For a demo on the test number, nothing is charged. Email costs nothing on the free tiers listed at the end.

## If a template is rejected

Meta's usual reasons: a variable at the very start or end of the body (so each link is followed by a few fixed words), a variable that stands for a whole sentence, wording that reads as promotion, or a missing sample. The templates avoid all four; the test suite checks where the variables sit, the wording and the samples. If `delay_notice`, which carries the merchandiser's note, is rejected, put more fixed text around the variable and shorten it; a changed body must be submitted again under a new name (add `_v2`), and the name in `notify.py` changed to match.

## The templates
"""

OUTRO = """
## Setting it up in LoomTrack

Put the values in `backend/.env` (it is not committed; `backend/.env.example` lists every setting), then restart the server.

| Setting | Where it comes from |
|---|---|
| `LOOMTRACK_WA_TOKEN` | the permanent token of the system user |
| `LOOMTRACK_WA_PHONE_ID` | Phone number ID |
| `LOOMTRACK_WA_LANGUAGE` | `en`, the language the templates were approved in |
| `LOOMTRACK_WA_VERIFY_TOKEN` | any long random string you choose; paste the same one into the webhook form |
| `LOOMTRACK_WA_APP_SECRET` | App settings, Basic, App secret; used to check that a webhook call really comes from Meta |
| `LOOMTRACK_PUBLIC_URL` | the address buyers open, with `https` |

**Webhook** (delivery reports and STOP replies): in the app's WhatsApp, Configuration, set the callback URL to `https://YOUR-DOMAIN/api/webhooks/whatsapp` and the verify token to the string above, then subscribe to the **messages** field. It needs an address reachable from the internet; while developing, a tunnel such as `cloudflared tunnel --url http://localhost:4000` (free) gives one.

**Check it works**: sign in as the merchandiser, open *Notifications* in the sidebar, and use *Send a test*. WhatsApp's test sends Meta's built-in `hello_world` template, which exists on every account, so it works before your own templates are approved. With a test number, the recipient must first be added under API Setup, To.

**Consent**: a number is saved only with the box ticked that the buyer agreed to WhatsApp messages. Keep proof outside the app too (a signed form or the email where they agreed); Meta can ask for it.

## Email (SMTP)

Email needs only an SMTP server. Any of these is free for a demo:

| Option | Settings | Limit |
|---|---|---|
| **Gmail** with an app password (Google account, Security, 2-step verification on, App passwords) | host `smtp.gmail.com`, port `587`, security `starttls`, user is the address, password is the app password | about 500 a day |
| **Brevo** (free plan; create an SMTP key) | host `smtp-relay.brevo.com`, port `587`, `starttls` | 300 a day |
| **Mailpit** on your own machine, to see every email without sending any | host `localhost`, port `1025`, security `none`, no user | unlimited, nothing leaves the machine |

Settings: `LOOMTRACK_SMTP_HOST`, `LOOMTRACK_SMTP_PORT`, `LOOMTRACK_SMTP_SECURITY` (`starttls`, `ssl` or `none`), `LOOMTRACK_SMTP_USER`, `LOOMTRACK_SMTP_PASSWORD`, `LOOMTRACK_SMTP_FROM` (for example `LoomTrack <orders@yourmill.example>`). For the client's own domain, publish SPF and DKIM records for the sending service so the mail is not marked as spam.

Emails go to the buyer's signed-in accounts (their email addresses), one message each. The merchandisers' own events go to the merchandisers' accounts. A buyer with no account has no address on file; the sent-messages log says so instead of failing quietly.

## Every event

| Event | Goes to | Email | WhatsApp template | When |
|---|---|---|---|---|
{events}

## What happens when sending fails

Every message is a row in the sent-messages log with a status: *recorded* (no provider set up, so only logged), *queued*, *sent*, *delivered*, *read*, *failed* or *skipped* (no address, or switched off). A message that cannot be sent is tried again after 1, 5 and 30 minutes, then marked *failed* with the reason; the office can send it again from the log. A refusal that cannot succeed (a wrong number, a template that does not exist) fails at once. WhatsApp's own delivery reports move *sent* to *delivered* and *read*.
"""


def _example_message(ev: notify.Event) -> str:
    return notify.render_whatsapp(ev, [notify.SAMPLES[n] for n in ev.wa_names])


def _api_payload(ev: notify.Event) -> str:
    components: list[dict] = [{"type": "BODY", "text": ev.wa_numbered}]
    if ev.wa_names:
        components[0]["example"] = {"body_text": [[notify.SAMPLES[n] for n in ev.wa_names]]}
    components.append({"type": "FOOTER", "text": notify.WA_FOOTER})
    return json.dumps({"name": ev.template, "language": "en", "category": "UTILITY", "components": components}, indent=2, ensure_ascii=False)


def _section(n: int, ev: notify.Event) -> str:
    rows = "\n".join(f"| `{{{{{i}}}}}` | {MEANING[name]} | {notify.SAMPLES[name]} |" for i, name in enumerate(ev.wa_names, start=1))
    return f"""
### {n}. `{ev.template}`

{USE_CASE[ev.key]}

| Field | Value |
|---|---|
| Name | `{ev.template}` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | {notify.WA_FOOTER} |
| Buttons | none |

**Body**

```
{ev.wa_numbered}
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
{rows}

**What the buyer sees**

> {_example_message(ev)}
>
> _{notify.WA_FOOTER}_

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{_api_payload(ev)}
```
"""


def _events_table() -> str:
    lines = []
    for ev in notify.EVENTS.values():
        who = "Buyer's people" if ev.audience == "buyer" else "Merchandisers"
        wa = f"`{ev.template}`" if ev.wa else "email only"
        lines.append(f"| `{ev.key}` | {who} | yes | {wa} | {ev.when} |")
    return "\n".join(lines)


def build() -> str:
    text = INTRO.replace("{count}", str(len(notify.TEMPLATES)))
    text += "".join(_section(n, ev) for n, ev in enumerate(notify.TEMPLATES, start=1))
    text += OUTRO.replace("{events}", _events_table())
    return text


if __name__ == "__main__":
    TARGET.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {TARGET}")
