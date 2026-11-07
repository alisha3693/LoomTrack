"""Email and WhatsApp setup for the office, and the webhook WhatsApp calls back."""

from __future__ import annotations

import asyncio
import json
import re

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .. import config
from ..deps import AppContext, User, ctx, merchandiser
from ..services import delivery, notify
from ..util import HttpError

router = APIRouter(prefix="/api/m", tags=["notifications"])
webhook_router = APIRouter(prefix="/api/webhooks", tags=["notifications"])

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_number(raw: str) -> str:
    """'+91 98765-43210' -> '+919876543210'. The country code is required: a number without one is a guess."""
    n = re.sub(r"[\s\-().]", "", raw or "")
    if n.startswith("00"):
        n = "+" + n[2:]
    if not E164.match(n):
        raise HttpError(400, "Enter the WhatsApp number with its country code, for example +91 98765 43210")
    return n


@router.get("/notifications")
async def settings(c: AppContext = Depends(ctx), user: User = Depends(merchandiser)):
    """What is set up and what the app sends. Never the keys or the password."""
    smtp, wa = config.smtp_settings(), config.whatsapp_settings()
    counts = {r["status"]: r["n"] for r in c.db.execute("SELECT status, COUNT(*) AS n FROM outbox_messages WHERE created_at >= datetime('now', '-7 days') GROUP BY status")}
    return {
        "publicUrl": config.public_url(),
        "email": {"configured": smtp is not None, "from": smtp["from"] if smtp else None, "host": smtp["host"] if smtp else None},
        "whatsapp": {
            "configured": wa is not None,
            "language": wa["language"] if wa else None,
            "webhookReady": bool(wa and wa["verify_token"] and wa["app_secret"]),
        },
        "last7days": counts,
        "events": [
            {"key": e.key, "audience": e.audience, "when": e.when, "whatsapp": e.template if e.wa else None}
            for e in notify.EVENTS.values()
        ],
    }


class TestIn(BaseModel):
    channel: str = Field(pattern="^(email|whatsapp)$")
    to: str = Field(min_length=3, max_length=120)


@router.post("/notifications/test")
async def test_send(body: TestIn, c: AppContext = Depends(ctx), user: User = Depends(merchandiser)):
    """Send one real message now, to check the setup. WhatsApp uses Meta's built-in `hello_world` template."""
    if body.channel == "email":
        cfg = config.smtp_settings()
        if cfg is None:
            raise HttpError(409, "Email is not set up yet. Add the SMTP settings to backend/.env and restart.")
        to = body.to.strip()
        if not EMAIL.match(to):
            raise HttpError(400, "Enter a valid email address")
        try:
            await asyncio.to_thread(
                delivery.send_smtp, cfg, to, "LoomTrack test message",
                f"Hello,\n\nThis is a test from LoomTrack. If you can read it, email is set up.\n\nOpen LoomTrack: {config.public_url()}\n",
            )
        except delivery.SendError as e:
            raise HttpError(502, str(e))
        return {"ok": True, "message": f"Sent to {to}"}
    cfg = config.whatsapp_settings()
    if cfg is None:
        raise HttpError(409, "WhatsApp is not set up yet. Add the WhatsApp settings to backend/.env and restart.")
    to = clean_number(body.to)
    try:
        async with httpx.AsyncClient() as client:
            await delivery.send_whatsapp(cfg, to, "hello_world", [], client, language="en_US")
    except delivery.SendError as e:
        raise HttpError(502, str(e))
    return {"ok": True, "message": f"Sent to {to}. On a test number it only reaches numbers added in the Meta dashboard."}


class BuyerNotifyIn(BaseModel):
    notifyEmail: bool
    whatsappNumber: str | None = Field(default=None, max_length=40)
    whatsappOptIn: bool = False


@router.patch("/buyers/{buyer_id}/notifications")
async def buyer_notifications(buyer_id: int, body: BuyerNotifyIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    """Who hears from LoomTrack outside the app. A WhatsApp number is stored only with the buyer's agreement on record."""
    b = c.db.execute("SELECT whatsapp_number, whatsapp_opt_in FROM buyers WHERE id = ?", (buyer_id,)).fetchone()
    if b is None:
        raise HttpError(404, "Buyer not found")
    number = clean_number(body.whatsappNumber) if (body.whatsappNumber or "").strip() else None
    if body.whatsappOptIn and not number:
        raise HttpError(400, "Enter the WhatsApp number to switch WhatsApp on")
    if number and not body.whatsappOptIn:
        raise HttpError(400, "Tick that the buyer agreed to WhatsApp messages, or remove the number")
    keep_consent = bool(b["whatsapp_opt_in"]) and b["whatsapp_number"] == number  # the same number, still agreed to
    c.db.execute(
        """UPDATE buyers SET notify_email = ?, whatsapp_number = ?, whatsapp_opt_in = ?,
             whatsapp_opt_in_at = CASE WHEN ? THEN COALESCE(whatsapp_opt_in_at, datetime('now')) WHEN ? THEN datetime('now') END,
             whatsapp_opt_in_by = CASE WHEN ? THEN whatsapp_opt_in_by WHEN ? THEN ? END
           WHERE id = ?""",
        (int(body.notifyEmail), number, int(body.whatsappOptIn), keep_consent, body.whatsappOptIn, keep_consent, body.whatsappOptIn, user.id, buyer_id),
    )
    return {"ok": True, "whatsappNumber": number}


@router.post("/outbox/{message_id}/retry")
async def retry(message_id: int, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    if not delivery.retry(c.db, message_id):
        raise HttpError(409, "Only a failed message can be sent again, and only while its channel is set up")
    return {"ok": True}


# --- What WhatsApp calls --------------------------------------------------------------------------------


@webhook_router.get("/whatsapp", include_in_schema=False)
async def verify(request: Request):
    """Meta checks the address once, when the webhook is saved in its dashboard."""
    cfg = config.whatsapp_settings()
    q = request.query_params
    if cfg and cfg["verify_token"] and q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == cfg["verify_token"]:
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)


@webhook_router.post("/whatsapp", include_in_schema=False)
async def receive(request: Request, c: AppContext = Depends(ctx)):
    """Delivery reports (sent, delivered, read, failed) and a buyer replying STOP. Only a call signed with the app secret counts."""
    cfg = config.whatsapp_settings()
    if not cfg or not cfg["app_secret"]:
        return JSONResponse({"error": "Not set up"}, status_code=503)
    raw = await request.body()
    if not delivery.signature_ok(cfg["app_secret"], raw, request.headers.get("x-hub-signature-256")):
        return JSONResponse({"error": "Bad signature"}, status_code=403)
    try:
        payload = json.loads(raw)
    except ValueError:
        return JSONResponse({"error": "Not JSON"}, status_code=400)
    delivery.apply_report(c.db, payload)
    return {"ok": True}
