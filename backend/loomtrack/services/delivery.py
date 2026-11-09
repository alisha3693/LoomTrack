"""Sends the queued rows of `outbox_messages`: email through any SMTP server, WhatsApp through Meta's Cloud API.

Sending never happens inside a request. `deliver_pending()` takes the queued rows one by one, so a slow or
broken provider cannot hold up the app, and a failure is kept on the row (with a reason the office can read)
instead of being lost. A message that could not be sent is tried again after 1, 5 and 30 minutes, and then
marked failed; a refusal that will never succeed (a wrong number, a template that does not exist) fails at once.
A crash between "sent" and "saved" can send the same message twice; that is the safe side of the two.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import smtplib
import sqlite3
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Awaitable, Callable

import httpx

from .. import config

GRAPH = "https://graph.facebook.com"
RETRY_MINUTES = (1, 5, 30)  # waits after the 1st, 2nd and 3rd failed try; the 4th failure is final
STOP_WORDS = {"stop", "stop all", "unsubscribe", "cancel", "end", "quit"}
_RANK = {"sent": 1, "delivered": 2, "read": 3}


class SendError(Exception):
    """`permanent` = trying again cannot help."""

    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


# --- The two providers -------------------------------------------------------------------------------


def send_smtp(cfg: dict, to: str, subject: str, body: str, attachment: tuple[str, bytes, str] | None = None) -> None:
    """Blocking; run it in a thread. `attachment` is (file name, bytes, MIME type). Raises SendError."""
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["from"], to, subject
    msg["Date"], msg["Message-ID"] = formatdate(localtime=True), make_msgid(domain=cfg["from"].rpartition("@")[2].strip("> ") or None)
    msg.set_content(body)
    if attachment:
        name, data, mime = attachment
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    try:
        if cfg["security"] == "ssl":
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
        with server:
            if cfg["security"] == "starttls":
                server.starttls(context=ssl.create_default_context())
            if cfg["user"]:
                server.login(cfg["user"], cfg["password"] or "")
            server.send_message(msg)
    except smtplib.SMTPRecipientsRefused as e:
        raise SendError(f"The mail server refused the address: {_first(e.recipients)}", permanent=True)
    except smtplib.SMTPAuthenticationError:
        raise SendError("The mail server refused the user name or password")
    except (smtplib.SMTPException, OSError) as e:
        raise SendError(f"Could not send the email: {e}")


def _first(recipients: dict) -> str:
    for _, (code, reason) in recipients.items():
        return f"{code} {reason.decode(errors='replace') if isinstance(reason, bytes) else reason}"
    return "unknown reason"


async def send_whatsapp(
    cfg: dict, to: str, template: str, values: list[str], client: httpx.AsyncClient, language: str | None = None
) -> str:
    """Send one approved template. Returns the message id Meta gives back. Raises SendError."""
    payload = {
        "messaging_product": "whatsapp",
        "to": re.sub(r"\D", "", to),
        "type": "template",
        "template": {"name": template, "language": {"code": language or cfg["language"]}},
    }
    if values:
        payload["template"]["components"] = [{"type": "body", "parameters": [{"type": "text", "text": v} for v in values]}]
    try:
        r = await client.post(
            f"{GRAPH}/{cfg['version']}/{cfg['phone_id']}/messages",
            json=payload,
            headers={"Authorization": f"Bearer {cfg['token']}"},
            timeout=20,
        )
    except httpx.HTTPError as e:
        raise SendError(f"Could not reach WhatsApp: {type(e).__name__}")
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code == 200 and data.get("messages"):
        return data["messages"][0]["id"]
    err = data.get("error") or {}
    message = f"WhatsApp refused it ({err.get('code', r.status_code)}): {err.get('error_data', {}).get('details') or err.get('message') or r.text[:200]}"
    # Rate limits and server trouble are worth another try; everything else the same request would meet again.
    raise SendError(message, permanent=r.status_code not in (429, 500, 502, 503, 504) and err.get("code") not in (4, 80007, 130429, 131056))


# --- Working through the queue -----------------------------------------------------------------------

SmtpSender = Callable[[dict, str, str, str], None]
WhatsAppSender = Callable[..., Awaitable[str]]


async def deliver_pending(
    db: sqlite3.Connection,
    *,
    smtp: SmtpSender = send_smtp,
    whatsapp: WhatsAppSender = send_whatsapp,
    limit: int = 25,
    client: httpx.AsyncClient | None = None,
) -> int:
    """Send what is due. Returns how many rows were tried. The database is touched only here, never in the sender."""
    rows = db.execute(
        """SELECT id, buyer_id, event, channel, recipient, subject, body, template, params, attempts FROM outbox_messages
           WHERE status = 'queued' AND (not_before IS NULL OR not_before <= datetime('now')) ORDER BY id LIMIT ?""",
        (limit,),
    ).fetchall()
    own_client = client is None and any(r["channel"] == "whatsapp" for r in rows)
    client = client or (httpx.AsyncClient() if own_client else None)
    try:
        for r in rows:
            db.execute("UPDATE outbox_messages SET attempts = attempts + 1 WHERE id = ?", (r["id"],))
            try:
                provider_id = None
                if r["channel"] == "email":
                    cfg = config.smtp_settings()
                    if cfg is None:
                        raise SendError("Email is not set up any more", permanent=True)
                    extra = {"attachment": _weekly_file(db, r["buyer_id"])} if r["event"] == "weekly_status" else {}
                    await asyncio.to_thread(smtp, cfg, r["recipient"], r["subject"], r["body"], **extra)
                else:
                    cfg = config.whatsapp_settings()
                    if cfg is None:
                        raise SendError("WhatsApp is not set up any more", permanent=True)
                    provider_id = await whatsapp(cfg, r["recipient"], r["template"], json.loads(r["params"] or "[]"), client)
            except SendError as e:
                final = e.permanent or r["attempts"] + 1 > len(RETRY_MINUTES)
                if final:
                    db.execute("UPDATE outbox_messages SET status = 'failed', error = ? WHERE id = ?", (str(e), r["id"]))
                else:
                    db.execute(
                        "UPDATE outbox_messages SET error = ?, not_before = datetime('now', ?) WHERE id = ?",
                        (str(e), f"+{RETRY_MINUTES[r['attempts']]} minutes", r["id"]),
                    )
            else:
                db.execute(
                    "UPDATE outbox_messages SET status = 'sent', error = NULL, sent_at = datetime('now'), provider_id = ? WHERE id = ?",
                    (provider_id, r["id"]),
                )
    finally:
        if own_client and client:
            await client.aclose()
    return len(rows)


def _weekly_file(db: sqlite3.Connection, buyer_id: int) -> tuple[str, bytes, str]:
    """The buyer edition of the weekly Excel, made when the email is sent, so it is as current as the email."""
    from . import clock
    from .export import weekly_workbook
    from ..util import iso_week

    today = clock.today(db)
    try:
        data = weekly_workbook(db, buyer_id, today, "buyer")
    except Exception as e:
        raise SendError(f"Could not make the Excel file: {type(e).__name__}")
    return (f"order-status-{iso_week(today)}.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def retry(db: sqlite3.Connection, message_id: int) -> bool:
    """Put a failed message back in the queue, with a fresh set of tries."""
    row = db.execute("SELECT channel FROM outbox_messages WHERE id = ? AND status = 'failed'", (message_id,)).fetchone()
    if row is None:
        return False
    configured = config.smtp_settings() if row["channel"] == "email" else config.whatsapp_settings()
    if not configured:
        return False
    db.execute("UPDATE outbox_messages SET status = 'queued', attempts = 0, not_before = NULL, error = NULL WHERE id = ?", (message_id,))
    return True


async def run_forever(db: sqlite3.Connection, every: float = 10.0) -> None:
    """The app's background loop. It only works while a provider is set up, and never stops on an error."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                if config.smtp_settings() or config.whatsapp_settings():
                    await deliver_pending(db, client=client)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the loop alive; the next round tries again
                print(f"delivery loop: {type(e).__name__}: {e}")
            await asyncio.sleep(every)


# --- What WhatsApp tells us back --------------------------------------------------------------------


def signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    """Meta signs every webhook call with the app secret: `sha256=<hmac of the raw body>`."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def apply_report(db: sqlite3.Connection, payload: dict) -> dict:
    """Delivery reports update the matching row; a buyer replying STOP switches their WhatsApp off."""
    updated = stopped = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for s in value.get("statuses", []):
                row = db.execute("SELECT id, status FROM outbox_messages WHERE provider_id = ?", (s.get("id"),)).fetchone()
                if row is None:
                    continue
                new = s.get("status")
                if new == "failed":
                    err = (s.get("errors") or [{}])[0]
                    detail = err.get("error_data", {}).get("details") or err.get("title") or "WhatsApp could not deliver it"
                    if row["status"] != "read":
                        db.execute("UPDATE outbox_messages SET status = 'failed', error = ? WHERE id = ?", (f"{detail} ({err.get('code', '?')})", row["id"]))
                        updated += 1
                elif new in _RANK and _RANK[new] > _RANK.get(row["status"], 0):
                    db.execute("UPDATE outbox_messages SET status = ?, error = NULL WHERE id = ?", (new, row["id"]))
                    updated += 1
            for m in value.get("messages", []):
                text = ((m.get("text") or {}).get("body") or (m.get("button") or {}).get("text") or "").strip().lower()
                if text in STOP_WORDS:
                    number = re.sub(r"\D", "", m.get("from", ""))
                    cur = db.execute(
                        "UPDATE buyers SET whatsapp_opt_in = 0 WHERE whatsapp_opt_in = 1 AND REPLACE(whatsapp_number, '+', '') = ?", (number,)
                    )
                    stopped += cur.rowcount
    return {"updated": updated, "stopped": stopped}
