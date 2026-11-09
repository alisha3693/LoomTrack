# WhatsApp templates for Meta review

Everything needed to register LoomTrack's WhatsApp messages with Meta, and to turn on email. This file is **generated** from `backend/loomtrack/services/notify.py` (`python -m loomtrack.services.whatsapp_doc`), so the wording below is exactly what the app sends. A test fails if the two drift apart.

## What is sent, and to whom

LoomTrack keeps WhatsApp to what matters to a buyer: **where their order is**. The buyer sends a complete order, the merchandiser confirms it, the supervisors on the floor report progress to the merchandiser in the app, and the buyer can follow it on their own tracking page. WhatsApp tells the buyer three things, each with the link to that page:

1. **Order received**: we have the order they sent.
2. **Order confirmed**: it is accepted, with our order number.
3. **Delay**: production is behind plan; they acknowledge it on the page.

Everything else (the merchandiser and the supervisors working on the order, messages, approvals) stays in the app, with email for the office. WhatsApp is used only for **buyers who agreed to it** (the merchandiser records the number and the buyer's agreement on the buyer's profile; the agreement, who recorded it and when are stored). Every message is one of the **3 templates** below, all in the **Utility** category: each one is about an order the buyer already has with the company, and none promotes anything.

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

### 1. `loomtrack_request_received`

A buyer sent a complete order through LoomTrack; this confirms we have it and gives the page where they can follow it.

| Field | Value |
|---|---|
| Name | `loomtrack_request_received` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Buttons | none |

**Body**

```
Hello {{1}}, we have received your order {{2}} for PO {{3}}. We will confirm it soon. You can follow it at {{4}} at any time.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |
| `{{3}}` | the buyer's PO number | B-PO-88213 |
| `{{4}}` | the buyer's own tracking page for this order (an https address) | https://track.yourmill.com/b/k3Jq9xT2/orders/117 |

**What the buyer sees**

> Hello Company B Sourcing, we have received your order REQ-2026-0042 for PO B-PO-88213. We will confirm it soon. You can follow it at https://track.yourmill.com/b/k3Jq9xT2/orders/117 at any time.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_received",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, we have received your order {{2}} for PO {{3}}. We will confirm it soon. You can follow it at {{4}} at any time.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042",
            "B-PO-88213",
            "https://track.yourmill.com/b/k3Jq9xT2/orders/117"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    }
  ]
}
```

### 2. `loomtrack_request_accepted`

The merchandiser confirmed the order; this gives our order number and the link to track its progress.

| Field | Value |
|---|---|
| Name | `loomtrack_request_accepted` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Buttons | none |

**Body**

```
Hello {{1}}, your order for PO {{2}} is confirmed. Our order number is {{3}}. Track its progress at {{4}} at any time.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |
| `{{3}}` | our order number | LT-2026-0117 |
| `{{4}}` | the buyer's own tracking page for this order (an https address) | https://track.yourmill.com/b/k3Jq9xT2/orders/117 |

**What the buyer sees**

> Hello Company B Sourcing, your order for PO B-PO-88213 is confirmed. Our order number is LT-2026-0117. Track its progress at https://track.yourmill.com/b/k3Jq9xT2/orders/117 at any time.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_accepted",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your order for PO {{2}} is confirmed. Our order number is {{3}}. Track its progress at {{4}} at any time.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213",
            "LT-2026-0117",
            "https://track.yourmill.com/b/k3Jq9xT2/orders/117"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    }
  ]
}
```

### 3. `loomtrack_delay_notice`

Production is behind plan on an order; the merchandiser confirmed a delay notice, and the buyer acknowledges it on the order's page.

| Field | Value |
|---|---|
| Name | `loomtrack_delay_notice` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Buttons | none |

**Body**

```
Hello {{1}}, there is a delay on PO {{2}}: {{3}} The details are at {{4}} where you can acknowledge it.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |
| `{{3}}` | a short note written by the merchandiser (one line, up to 120 characters) | The neck rib needs a second wash test. We now expect to ship on 10 Dec. |
| `{{4}}` | the buyer's own tracking page for this order (an https address) | https://track.yourmill.com/b/k3Jq9xT2/orders/117 |

**What the buyer sees**

> Hello Company B Sourcing, there is a delay on PO B-PO-88213: The neck rib needs a second wash test. We now expect to ship on 10 Dec. The details are at https://track.yourmill.com/b/k3Jq9xT2/orders/117 where you can acknowledge it.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_delay_notice",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, there is a delay on PO {{2}}: {{3}} The details are at {{4}} where you can acknowledge it.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213",
            "The neck rib needs a second wash test. We now expect to ship on 10 Dec.",
            "https://track.yourmill.com/b/k3Jq9xT2/orders/117"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    }
  ]
}
```

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
| `request_received` | Buyer's people | yes | `loomtrack_request_received` | The buyer sent a new order request |
| `request_question` | Buyer's people | yes | email only | The merchandiser asked a question on a request |
| `request_counter` | Buyer's people | yes | email only | The merchandiser proposed a different delivery date |
| `request_declined` | Buyer's people | yes | email only | The merchandiser declined a request |
| `request_accepted` | Buyer's people | yes | `loomtrack_request_accepted` | A request became an order |
| `change_accepted` | Buyer's people | yes | email only | A change the buyer asked for on an order was accepted |
| `change_recorded` | Buyer's people | yes | email only | The merchandiser recorded a change the buyer asked for outside the app |
| `delay_notice` | Buyer's people | yes | `loomtrack_delay_notice` | The merchandiser confirmed a delay notice for an order |
| `order_cancelled` | Buyer's people | yes | email only | The merchandiser cancelled an order |
| `order_message` | Buyer's people | yes | email only | The merchandiser wrote in an order's conversation |
| `approval_requested` | Buyer's people | yes | email only | The merchandiser asked for an approval (sample, lab dip, packaging) |
| `approval_resubmitted` | Buyer's people | yes | email only | The merchandiser sent an approval again after the buyer asked for changes |
| `request_submitted` | Merchandisers | yes | email only | A buyer sent a request (new order or a change) |
| `buyer_reply` | Merchandisers | yes | email only | A buyer answered on a request |
| `order_message_in` | Merchandisers | yes | email only | A buyer wrote in an order's conversation |
| `approval_decided` | Merchandisers | yes | email only | A buyer approved, or asked for changes |
| `supervisor_reported` | Merchandisers | yes | email only | The supervisor sent a reason for a problem on the floor |
| `notice_acknowledged` | Merchandisers | yes | email only | A buyer acknowledged a delay notice |

## What happens when sending fails

Every message is a row in the sent-messages log with a status: *recorded* (no provider set up, so only logged), *queued*, *sent*, *delivered*, *read*, *failed* or *skipped* (no address, or switched off). A message that cannot be sent is tried again after 1, 5 and 30 minutes, then marked *failed* with the reason; the office can send it again from the log. A refusal that cannot succeed (a wrong number, a template that does not exist) fails at once. WhatsApp's own delivery reports move *sent* to *delivered* and *read*.
