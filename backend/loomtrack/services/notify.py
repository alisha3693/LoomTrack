"""Messages to people outside the app: what each event says by email and by WhatsApp, and who gets it.

`send()` only writes rows into `outbox_messages`, inside the caller's transaction, so a message exists if and
only if the change that caused it was saved. `services/delivery.py` sends the queued rows afterwards.

Every event is written once, here. The WhatsApp wording is also what is submitted to Meta for approval:
`python -m loomtrack.services.whatsapp_doc` writes it to docs/WHATSAPP_TEMPLATES.md, and a test keeps that file
in step with this one. If you change a body here, the template has to be approved again under a new name.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass

from .. import config

# WhatsApp refuses a value with a newline, a tab or four spaces in a row, and a body over 1024 characters.
WA_VALUE_LIMIT = 120
WA_FOOTER = "Reply STOP to stop WhatsApp messages from LoomTrack."

# Sample values for Meta's review form. Meta wants one per variable, and a real-looking one gets approved sooner.
SAMPLES = {
    "buyer": "Company B Sourcing",
    "request_no": "REQ-2026-0042",
    "po": "B-PO-88213",
    "date": "12 Dec 2026",
    "order_no": "LT-2026-0117",
    "title": "Pre-production sample, navy crew neck",
    "summary": "Ex-factory moved from 5 Dec to 10 Dec 2026.",
    "text": "The neck rib needs a second wash test. We now expect to ship on 10 Dec.",
    "link": "https://track.yourmill.com/b/k3Jq9xT2/orders/117",
}


@dataclass(frozen=True)
class Event:
    key: str
    audience: str  # "buyer" or "office"
    when: str  # for the people reading the docs
    subject: str
    email: str  # the middle of the email; {person} greets, {link} follows
    wa: str | None = None  # the WhatsApp body, with {name} variables; None = email only

    @property
    def template(self) -> str:
        return f"loomtrack_{self.key}"

    @property
    def wa_names(self) -> list[str]:
        """The WhatsApp variables in the order they appear, so {{1}} is the first."""
        return re.findall(r"\{(\w+)\}", self.wa or "")

    @property
    def wa_numbered(self) -> str:
        body = self.wa or ""
        for n, name in enumerate(self.wa_names, start=1):
            body = body.replace("{" + name + "}", "{{" + str(n) + "}}", 1)
        return body


_EVENTS = [
    # --- to the buyer's people: email, and WhatsApp when the buyer has agreed to it ---
    Event(
        "request_received", "buyer", "The buyer sent a new order request",
        "We received your order request {request_no}",
        "We received your order request {request_no} for PO {po}.\n\nYour merchandiser will look at it and answer in LoomTrack.",
        "Hello {buyer}, we have received your order {request_no} for PO {po}. We will confirm it soon. You can follow it at {link} at any time.",
    ),
    Event(
        "request_question", "buyer", "The merchandiser asked a question on a request",
        "A question about your order request {request_no}",
        "Your merchandiser has a question about request {request_no}:\n\n{text}\n\nPlease answer it in LoomTrack.",
    ),
    Event(
        "request_counter", "buyer", "The merchandiser proposed a different delivery date",
        "A different delivery date is proposed for {request_no}",
        "For request {request_no} your merchandiser proposes the ex-factory date {date}.\n\n{text}\n\nPlease agree, or reply, in LoomTrack.",
    ),
    Event(
        "request_declined", "buyer", "The merchandiser declined a request",
        "Your order request {request_no} was declined",
        "Your order request {request_no} could not be accepted.\n\nReason: {text}",
    ),
    Event(
        "request_accepted", "buyer", "A request became an order",
        "Your order request {request_no} was accepted",
        "Your order request {request_no} is accepted.\n\nYour order number with us is {order_no}.\n\n{text}",
        "Hello {buyer}, your order for PO {po} is confirmed. Our order number is {order_no}. Track its progress at {link} at any time.",
    ),
    Event(
        "change_accepted", "buyer", "A change the buyer asked for on an order was accepted",
        "The change you asked for on PO {po} was accepted",
        "The change you asked for on PO {po} is accepted.\n\n{text}",
    ),
    Event(
        "change_recorded", "buyer", "The merchandiser recorded a change the buyer asked for outside the app",
        "A change to PO {po} was recorded",
        "A change to PO {po} was recorded:\n\n{summary}\n\nReason: {text}",
    ),
    Event(
        "delay_notice", "buyer", "The merchandiser confirmed a delay notice for an order",
        "Production update: {po}",
        "There is a production update on PO {po}:\n\n{text}\n\nPlease open LoomTrack and acknowledge it, so we know you have seen it.",
        "Hello {buyer}, there is a delay on PO {po}: {text} The details are at {link} where you can acknowledge it.",
    ),
    Event(
        "order_shipped", "buyer", "The merchandiser marked an order as shipped",
        "PO {po} has shipped",
        "Your order for PO {po} left the factory on {date}.\n\n{text}",
    ),
    Event(
        "weekly_status", "buyer", "Every week: where each of the buyer's orders stands (the Excel file is attached)",
        "Weekly order status: {week}",
        "Here is where your orders stand this week:\n\n{text}\n\nThe Excel file with the details is attached.",
    ),
    Event(
        "order_cancelled", "buyer", "The merchandiser cancelled an order",
        "Order {po} was cancelled",
        "Your order for PO {po} has been cancelled.\n\nReason: {text}\n\nYou can see this at {link}.",
    ),
    # --- to the merchandisers: email only ---
    Event(
        "request_submitted", "office", "A buyer sent a request (new order or a change)",
        "New {what} {request_no} from {buyer}",
        "{buyer} sent a {what}: {request_no} (PO {po}).\n\n{text}",
    ),
    Event(
        "buyer_reply", "office", "A buyer answered on a request",
        "{buyer} answered on {request_no}",
        "{buyer} answered on request {request_no}:\n\n{text}",
    ),
    Event(
        "supervisor_reported", "office", "The supervisor sent a reason for a problem on the floor",
        "Supervisor reported on {po}: {reason}",
        "The supervisor reported a problem on PO {po} ({stage}):\n\n{text}",
    ),
    Event(
        "delay_detected", "office", "LoomTrack found an order running late (a new delay warning to look at)",
        "Delay detected on {po}: {level}",
        "LoomTrack expects PO {po} to be ready on {date}, which is later than the agreed ex-factory date.\n\n{text}\n\nOpen the order to review the warning and tell the buyer.",
    ),
    Event(
        "production_complete", "office", "Every stage of an order has reached the full quantity",
        "Production complete on {po}",
        "Every production stage of PO {po} has reached the full quantity.\n\nWhen it leaves the factory, open the order and mark it shipped with the ship date.",
    ),
    Event(
        "notice_acknowledged", "office", "A buyer acknowledged a delay notice",
        "{buyer} acknowledged the delay notice on {po}",
        "{buyer} has acknowledged the delay notice on PO {po}.\n\n{text}",
    ),
]

EVENTS: dict[str, Event] = {e.key: e for e in _EVENTS}
TEMPLATES = [e for e in _EVENTS if e.wa]


def _tidy(value: object, limit: int) -> str:
    text = " ".join(str(value if value is not None else "").split())  # one line, single spaces
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fill(template: str, values: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), "")), template)


def render_email(event: Event, person: str, values: dict) -> tuple[str, str]:
    subject = _tidy(_fill(event.subject, values), 150)
    body = _fill(event.email, values).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)  # an empty {text} leaves a gap
    link = values.get("link") or config.public_url()
    return subject, f"Hello {person},\n\n{body}\n\nOpen LoomTrack: {link}\n\n-- LoomTrack, order tracking for {values.get('buyer', 'your orders')}"


def wa_values(event: Event, values: dict) -> list[str]:
    # A cut link would not open, so the link is never shortened.
    return [_tidy(values.get(n, ""), 2000 if n == "link" else WA_VALUE_LIMIT) or "-" for n in event.wa_names]


def render_whatsapp(event: Event, values: list[str]) -> str:
    return _fill(event.wa or "", dict(zip(event.wa_names, values)))


# --- Who gets it -----------------------------------------------------------------------------------


def _email_people(db: sqlite3.Connection, audience: str, buyer_id: int) -> list[sqlite3.Row]:
    if audience == "buyer":
        sql, args = "SELECT name, login FROM users WHERE role = 'buyer' AND buyer_id = ? ORDER BY id", (buyer_id,)
    else:
        sql, args = "SELECT name, login FROM users WHERE role = 'merchandiser' ORDER BY id", ()
    return [u for u in db.execute(sql, args) if "@" in u["login"]]


def _queue_state(channel: str) -> str:
    """'queued' when a provider is set up for the channel; otherwise the message is only recorded."""
    configured = config.smtp_settings() if channel == "email" else config.whatsapp_settings()
    return "queued" if configured else "logged"


def send(db: sqlite3.Connection, event: str, buyer_id: int, order_id: int | None = None, **values) -> None:
    """Record the messages for one event. Call it inside the transaction that made the event true."""
    ev = EVENTS[event]
    buyer = db.execute(
        "SELECT name, link_token, notify_email, whatsapp_number, whatsapp_opt_in FROM buyers WHERE id = ?", (buyer_id,)
    ).fetchone()
    if buyer is None:
        return
    values = {**values, "buyer": buyer["name"]}
    if ev.audience == "buyer":  # the buyer's own tracking page: the order, or their orders while there is none yet
        values["link"] = f"{config.public_url()}/b/{buyer['link_token']}/orders" + (f"/{order_id}" if order_id else "")
    insert = (
        "INSERT INTO outbox_messages (buyer_id, order_id, channel, subject, body, event, audience, recipient, status, error, template, params)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
    )

    people = _email_people(db, ev.audience, buyer_id)
    if ev.audience == "buyer" and not buyer["notify_email"]:
        subject, body = render_email(ev, "", values)
        db.execute(insert, (buyer_id, order_id, "email", subject, body, event, ev.audience, None, "skipped", "Email is switched off for this buyer", None, None))
    elif not people:
        subject, body = render_email(ev, "", values)
        db.execute(insert, (buyer_id, order_id, "email", subject, body, event, ev.audience, None, "skipped", "No email address on file", None, None))
    for u in people if (ev.audience == "office" or buyer["notify_email"]) else []:
        subject, body = render_email(ev, u["name"], values)
        db.execute(insert, (buyer_id, order_id, "email", subject, body, event, ev.audience, u["login"], _queue_state("email"), None, None, None))

    if ev.wa and ev.audience == "buyer" and buyer["whatsapp_opt_in"] and buyer["whatsapp_number"]:
        wa = wa_values(ev, values)
        db.execute(
            insert,
            (buyer_id, order_id, "whatsapp", ev.template, render_whatsapp(ev, wa), event, ev.audience, buyer["whatsapp_number"],
             _queue_state("whatsapp"), None, ev.template, json.dumps(wa)),
        )
