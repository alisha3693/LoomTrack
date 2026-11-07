# WhatsApp templates for Meta review

Everything needed to register LoomTrack's WhatsApp messages with Meta, and to turn on email. This file is **generated** from `backend/loomtrack/services/notify.py` (`python -m loomtrack.services.whatsapp_doc`), so the wording below is exactly what the app sends. A test fails if the two drift apart.

## What is sent, and to whom

LoomTrack tells a buyer's people about their orders: a request was answered, a delay was confirmed, a sample needs approval. WhatsApp is used only for **buyers who agreed to it** (the merchandiser records the number and the buyer's agreement on the buyer's profile; the agreement, who recorded it and when are stored). Every message is one of the **11 templates** below, all in the **Utility** category: each one is about an order the buyer already has with the company, and none promotes anything. The merchandisers themselves are told by email only.

A buyer can stop WhatsApp at any time by replying **STOP**; the webhook switches it off at once. Every template carries that line as its footer.

## Before you submit

1. **Meta Business account** (business.facebook.com), with the business verified. Template approval and a real phone number both need it.
2. **App** at developers.facebook.com: type *Business*, add the **WhatsApp** product.
3. **A phone number.** For the demo, Meta gives a free *test number* that can message up to 5 verified numbers. For the client, add their own number in WhatsApp Manager; it must not be in use on the WhatsApp or WhatsApp Business app. Its display name is reviewed too.
4. Note three values for `backend/.env`: the **Phone number ID** and the **WhatsApp Business Account ID** (WhatsApp, API Setup), and a **permanent access token** (Business settings, System users, add a user, give it the app and the `whatsapp_business_messaging` and `whatsapp_business_management` permissions, generate a token with no expiry). The temporary token on the API Setup page lasts 24 hours.
5. Submit the templates below, either one by one in **WhatsApp Manager, Message templates, Create template**, or with the API call at the end of each section. Approval of a Utility template usually takes minutes to a day.

In the form: *Category* **Utility**, *Language* **English**, *Name* as given, *Header* none, then paste the body, footer and button. For every variable Meta asks for a sample value; use the ones in the tables.

## Cost, said plainly

The Cloud API itself is free to use and so is the test number. Meta charges **per template message delivered**, by category and country (Utility is the cheapest paid category; a Utility template is free when it is sent inside a 24-hour window the buyer opened by messaging you). There is no monthly fee. Meta changes the rate card from time to time, so read the current one at developers.facebook.com/docs/whatsapp/pricing before the client goes live. For a demo on the test number, nothing is charged. Email costs nothing on the free tiers listed at the end.

## If a template is rejected

Meta's usual reasons: a variable at the very start or end of the body, a variable that stands for a whole sentence, wording that reads as promotion, or a missing sample. The templates avoid all four; the test suite checks where the variables sit, the wording and the samples. If a template with long variable text (`delay_notice`, `order_message`, `request_question`) is rejected, put more fixed text around the variable and shorten it; a changed body must be submitted again under a new name (add `_v2`), and the name in `notify.py` changed to match.

## The templates

### 1. `loomtrack_request_received`

A buyer sent an order request through LoomTrack; this confirms we have it.

| Field | Value |
|---|---|
| Name | `loomtrack_request_received` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, we have received your order request {{2}} for PO {{3}}. Your merchandiser will review it and reply in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |
| `{{3}}` | the buyer's PO number | B-PO-88213 |

**What the buyer sees**

> Hello Company B Sourcing, we have received your order request REQ-2026-0042 for PO B-PO-88213. Your merchandiser will review it and reply in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_received",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, we have received your order request {{2}} for PO {{3}}. Your merchandiser will review it and reply in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042",
            "B-PO-88213"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 2. `loomtrack_request_question`

The merchandiser needs one more detail before accepting an order request.

| Field | Value |
|---|---|
| Name | `loomtrack_request_question` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, your merchandiser has a question about request {{2}}: {{3}} Please answer it in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |
| `{{3}}` | a short note written by the merchandiser (one line, up to 120 characters) | The neck rib needs a second wash test. We now expect to ship on 10 Dec. |

**What the buyer sees**

> Hello Company B Sourcing, your merchandiser has a question about request REQ-2026-0042: The neck rib needs a second wash test. We now expect to ship on 10 Dec. Please answer it in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_question",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your merchandiser has a question about request {{2}}: {{3}} Please answer it in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042",
            "The neck rib needs a second wash test. We now expect to ship on 10 Dec."
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 3. `loomtrack_request_counter`

The merchandiser proposes a different delivery date for an order request.

| Field | Value |
|---|---|
| Name | `loomtrack_request_counter` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, for request {{2}} your merchandiser proposes the ex-factory date {{3}}. Please agree or reply in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |
| `{{3}}` | a date | 12 Dec 2026 |

**What the buyer sees**

> Hello Company B Sourcing, for request REQ-2026-0042 your merchandiser proposes the ex-factory date 12 Dec 2026. Please agree or reply in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_counter",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, for request {{2}} your merchandiser proposes the ex-factory date {{3}}. Please agree or reply in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042",
            "12 Dec 2026"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 4. `loomtrack_request_declined`

An order request cannot be accepted; the reason is in the app.

| Field | Value |
|---|---|
| Name | `loomtrack_request_declined` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, your order request {{2}} could not be accepted. The reason is in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |

**What the buyer sees**

> Hello Company B Sourcing, your order request REQ-2026-0042 could not be accepted. The reason is in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_declined",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your order request {{2}} could not be accepted. The reason is in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 5. `loomtrack_request_accepted`

An order request became a confirmed order; this gives the order number.

| Field | Value |
|---|---|
| Name | `loomtrack_request_accepted` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, your order request {{2}} is accepted. Your order number is {{3}}.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the request number | REQ-2026-0042 |
| `{{3}}` | our order number | LT-2026-0117 |

**What the buyer sees**

> Hello Company B Sourcing, your order request REQ-2026-0042 is accepted. Your order number is LT-2026-0117.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_request_accepted",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your order request {{2}} is accepted. Your order number is {{3}}.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "REQ-2026-0042",
            "LT-2026-0117"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 6. `loomtrack_change_accepted`

A change the buyer asked for on an existing order (date or quantity) was accepted.

| Field | Value |
|---|---|
| Name | `loomtrack_change_accepted` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, the change you asked for on PO {{2}} is accepted. The details are in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |

**What the buyer sees**

> Hello Company B Sourcing, the change you asked for on PO B-PO-88213 is accepted. The details are in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_change_accepted",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, the change you asked for on PO {{2}} is accepted. The details are in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 7. `loomtrack_change_recorded`

The merchandiser recorded a change the buyer asked for by phone or email.

| Field | Value |
|---|---|
| Name | `loomtrack_change_recorded` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, a change was recorded on PO {{2}}: {{3}} The reason is in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |
| `{{3}}` | a one-line summary of the change | Ex-factory moved from 5 Dec to 10 Dec 2026. |

**What the buyer sees**

> Hello Company B Sourcing, a change was recorded on PO B-PO-88213: Ex-factory moved from 5 Dec to 10 Dec 2026. The reason is in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_change_recorded",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, a change was recorded on PO {{2}}: {{3}} The reason is in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213",
            "Ex-factory moved from 5 Dec to 10 Dec 2026."
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 8. `loomtrack_delay_notice`

Production is behind plan on an order; the merchandiser confirmed a delay notice for the buyer.

| Field | Value |
|---|---|
| Name | `loomtrack_delay_notice` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, there is a production update on PO {{2}}: {{3}} Please open LoomTrack and acknowledge it.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |
| `{{3}}` | a short note written by the merchandiser (one line, up to 120 characters) | The neck rib needs a second wash test. We now expect to ship on 10 Dec. |

**What the buyer sees**

> Hello Company B Sourcing, there is a production update on PO B-PO-88213: The neck rib needs a second wash test. We now expect to ship on 10 Dec. Please open LoomTrack and acknowledge it.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_delay_notice",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, there is a production update on PO {{2}}: {{3}} Please open LoomTrack and acknowledge it.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213",
            "The neck rib needs a second wash test. We now expect to ship on 10 Dec."
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 9. `loomtrack_order_message`

The merchandiser wrote a message in the order's conversation.

| Field | Value |
|---|---|
| Name | `loomtrack_order_message` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, your merchandiser sent a message about PO {{2}}: {{3}} You can reply in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | the buyer's PO number | B-PO-88213 |
| `{{3}}` | a short note written by the merchandiser (one line, up to 120 characters) | The neck rib needs a second wash test. We now expect to ship on 10 Dec. |

**What the buyer sees**

> Hello Company B Sourcing, your merchandiser sent a message about PO B-PO-88213: The neck rib needs a second wash test. We now expect to ship on 10 Dec. You can reply in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_order_message",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your merchandiser sent a message about PO {{2}}: {{3}} You can reply in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "B-PO-88213",
            "The neck rib needs a second wash test. We now expect to ship on 10 Dec."
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 10. `loomtrack_approval_requested`

A sample, lab dip or packaging needs the buyer's approval before production continues.

| Field | Value |
|---|---|
| Name | `loomtrack_approval_requested` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, your approval is needed for {{2}} on PO {{3}}. Please review it in LoomTrack.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | what needs approving | Pre-production sample, navy crew neck |
| `{{3}}` | the buyer's PO number | B-PO-88213 |

**What the buyer sees**

> Hello Company B Sourcing, your approval is needed for Pre-production sample, navy crew neck on PO B-PO-88213. Please review it in LoomTrack.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_approval_requested",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, your approval is needed for {{2}} on PO {{3}}. Please review it in LoomTrack.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "Pre-production sample, navy crew neck",
            "B-PO-88213"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
    }
  ]
}
```

### 11. `loomtrack_approval_resubmitted`

An item the buyer asked changes on was corrected and needs approval again.

| Field | Value |
|---|---|
| Name | `loomtrack_approval_resubmitted` |
| Category | Utility |
| Language | English (`en`) |
| Header | none |
| Footer | Reply STOP to stop WhatsApp messages from LoomTrack. |
| Button | URL, text "Open LoomTrack", address `https://YOUR-LOOMTRACK-DOMAIN` (fixed, no variable) |

**Body**

```
Hello {{1}}, {{2}} on PO {{3}} was updated after your comments and needs your approval again.
```

**Sample values** (paste these into Meta's form)

| Variable | Stands for | Sample |
|---|---|---|
| `{{1}}` | the buyer's company name | Company B Sourcing |
| `{{2}}` | what needs approving | Pre-production sample, navy crew neck |
| `{{3}}` | the buyer's PO number | B-PO-88213 |

**What the buyer sees**

> Hello Company B Sourcing, Pre-production sample, navy crew neck on PO B-PO-88213 was updated after your comments and needs your approval again.
>
> _Reply STOP to stop WhatsApp messages from LoomTrack._
> [ Open LoomTrack ]

**Create it through the API** (`POST https://graph.facebook.com/v21.0/<WABA_ID>/message_templates`, header `Authorization: Bearer <token>`)

```json
{
  "name": "loomtrack_approval_resubmitted",
  "language": "en",
  "category": "UTILITY",
  "components": [
    {
      "type": "BODY",
      "text": "Hello {{1}}, {{2}} on PO {{3}} was updated after your comments and needs your approval again.",
      "example": {
        "body_text": [
          [
            "Company B Sourcing",
            "Pre-production sample, navy crew neck",
            "B-PO-88213"
          ]
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Reply STOP to stop WhatsApp messages from LoomTrack."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Open LoomTrack",
          "url": "https://YOUR-LOOMTRACK-DOMAIN"
        }
      ]
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
| `request_question` | Buyer's people | yes | `loomtrack_request_question` | The merchandiser asked a question on a request |
| `request_counter` | Buyer's people | yes | `loomtrack_request_counter` | The merchandiser proposed a different delivery date |
| `request_declined` | Buyer's people | yes | `loomtrack_request_declined` | The merchandiser declined a request |
| `request_accepted` | Buyer's people | yes | `loomtrack_request_accepted` | A request became an order |
| `change_accepted` | Buyer's people | yes | `loomtrack_change_accepted` | A change the buyer asked for on an order was accepted |
| `change_recorded` | Buyer's people | yes | `loomtrack_change_recorded` | The merchandiser recorded a change the buyer asked for outside the app |
| `delay_notice` | Buyer's people | yes | `loomtrack_delay_notice` | The merchandiser confirmed a delay notice for an order |
| `order_message` | Buyer's people | yes | `loomtrack_order_message` | The merchandiser wrote in an order's conversation |
| `approval_requested` | Buyer's people | yes | `loomtrack_approval_requested` | The merchandiser asked for an approval (sample, lab dip, packaging) |
| `approval_resubmitted` | Buyer's people | yes | `loomtrack_approval_resubmitted` | The merchandiser sent an approval again after the buyer asked for changes |
| `request_submitted` | Merchandisers | yes | email only | A buyer sent a request (new order or a change) |
| `buyer_reply` | Merchandisers | yes | email only | A buyer answered on a request |
| `order_message_in` | Merchandisers | yes | email only | A buyer wrote in an order's conversation |
| `approval_decided` | Merchandisers | yes | email only | A buyer approved, or asked for changes |
| `notice_acknowledged` | Merchandisers | yes | email only | A buyer acknowledged a delay notice |

## What happens when sending fails

Every message is a row in the sent-messages log with a status: *recorded* (no provider set up, so only logged), *queued*, *sent*, *delivered*, *read*, *failed* or *skipped* (no address, or switched off). A message that cannot be sent is tried again after 1, 5 and 30 minutes, then marked *failed* with the reason; the office can send it again from the log. A refusal that cannot succeed (a wrong number, a template that does not exist) fails at once. WhatsApp's own delivery reports move *sent* to *delivered* and *read*.
