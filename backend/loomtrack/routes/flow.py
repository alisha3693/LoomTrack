"""What passes between the buyer and the merchandiser beyond requests: the notification feeds, delay-notice receipts
and the order timeline. Both sides are here so they stay in step."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..services import activity, feed, notices
from ..util import HttpError
from .buyer import NO_STORE, current_buyer, writable_buyer

buyer_router = APIRouter(prefix="/api/b/{token}")
office_router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])


# --- What is waiting, and the notification feeds ---------------------------------------------------------

@buyer_router.get("/badges")
async def buyer_badges(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    """The counts the sidebar shows: things waiting on the buyer."""
    response.headers.update(NO_STORE)
    waiting = c.db.execute(
        "SELECT COUNT(*) FROM order_requests WHERE buyer_id = ? AND status IN ('query','countered')", (buyer["id"],)
    ).fetchone()[0]
    return {"requests": waiting, "notifications": feed.unread_count(c.db, "buyer", buyer["id"], "buyer", buyer["id"])}


@buyer_router.get("/feed")
async def buyer_feed(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {"items": feed.items(c.db, "buyer", buyer["id"]), "seenUpTo": feed.seen_up_to(c.db, "buyer", buyer["id"])}


@buyer_router.post("/feed/read")
async def buyer_feed_read(buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    feed.mark_seen(c.db, "buyer", buyer["id"], "buyer", buyer["id"])
    return {"ok": True}


@office_router.get("/feed")
async def office_feed(user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    return {"items": feed.items(c.db, "office"), "seenUpTo": feed.seen_up_to(c.db, "merchandiser", user.id)}


@office_router.post("/feed/read")
async def office_feed_read(user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    feed.mark_seen(c.db, "merchandiser", user.id, "office")
    return {"ok": True}


# --- Delay notices ---------------------------------------------------------------------------------------

class AckIn(BaseModel):
    note: str | None = Field(default=None, max_length=1500)


@buyer_router.post("/orders/{order_id}/notice/seen")
async def notice_seen(order_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    notices.seen(c.db, buyer["id"], order_id)
    return {"ok": True}


@buyer_router.post("/orders/{order_id}/notice/acknowledge")
async def notice_acknowledge(order_id: int, body: AckIn, buyer: sqlite3.Row = Depends(writable_buyer), c: AppContext = Depends(ctx)):
    notices.acknowledge(c.db, buyer["id"], order_id, body.note)
    return {"ok": True}


# --- Timeline ------------------------------------------------------------------------------

@buyer_router.get("/orders/{order_id}/activity")
async def buyer_activity(order_id: int, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    if not c.db.execute("SELECT 1 FROM orders WHERE id = ? AND buyer_id = ? AND state != 'cancelled'", (order_id, buyer["id"])).fetchone():
        raise HttpError(404, "Order not found")  # never revealing that another buyer's order exists
    return {"activity": activity.for_order(c.db, order_id, "buyer")}
