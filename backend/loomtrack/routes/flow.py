"""What passes between the buyer and the merchandiser beyond requests: the inbox, read marks, approvals,
delay-notice receipts, the order timeline and the buyer's documents. Both sides are here so they stay in step."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..services import activity, approvals, feed, inbox, notices, order_messages
from ..services import requests as request_svc
from ..services.attachments import _item
from ..services.approvals import KIND_LABEL
from .buyer import NO_STORE, current_buyer, writable_buyer

buyer_router = APIRouter(prefix="/api/b/{token}")
office_router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])


# --- Inbox and read marks --------------------------------------------------------------------------------

@buyer_router.get("/inbox")
async def buyer_inbox(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {"conversations": inbox.conversations(c.db, "buyer", buyer["id"])}


@buyer_router.get("/badges")
async def buyer_badges(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    """The counts the sidebar shows: things waiting on the buyer."""
    response.headers.update(NO_STORE)
    waiting = c.db.execute(
        "SELECT COUNT(*) FROM order_requests WHERE buyer_id = ? AND status IN ('query','countered')", (buyer["id"],)
    ).fetchone()[0]
    return {"requests": waiting, "messages": inbox.unread_count(c.db, "buyer", buyer["id"]), "notifications": feed.unread_count(c.db, "buyer", buyer["id"], "buyer", buyer["id"]), "approvals": approvals.to_decide(c.db, buyer["id"])}


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


@buyer_router.post("/orders/{order_id}/messages/read")
async def buyer_read_order(order_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    order_messages.thread(c.db, order_id, buyer["id"])  # 404 unless it is theirs
    inbox.mark_read(c.db, "order", order_id, "buyer")
    return {"ok": True}


@buyer_router.post("/requests/{request_id}/read")
async def buyer_read_request(request_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    request_svc.find_request(c.db, request_id, buyer["id"])
    inbox.mark_read(c.db, "request", request_id, "buyer")
    return {"ok": True}


@office_router.get("/inbox")
async def office_inbox(c: AppContext = Depends(ctx)):
    return {"conversations": inbox.conversations(c.db, "merchandiser")}


@office_router.post("/orders/{order_id}/messages/read")
async def office_read_order(order_id: int, c: AppContext = Depends(ctx)):
    order_messages.thread(c.db, order_id)
    inbox.mark_read(c.db, "order", order_id, "merchandiser")
    return {"ok": True}


@office_router.post("/requests/{request_id}/read")
async def office_read_request(request_id: int, c: AppContext = Depends(ctx)):
    request_svc.find_request(c.db, request_id)
    inbox.mark_read(c.db, "request", request_id, "merchandiser")
    return {"ok": True}


@buyer_router.get("/orders/{order_id}/read-state")
async def buyer_read_state(order_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    order_messages.thread(c.db, order_id, buyer["id"])
    return {"readUpTo": inbox.other_read_up_to(c.db, "order", order_id, "buyer")}


@office_router.get("/orders/{order_id}/read-state")
async def office_read_state(order_id: int, c: AppContext = Depends(ctx)):
    order_messages.thread(c.db, order_id)
    return {"readUpTo": inbox.other_read_up_to(c.db, "order", order_id, "merchandiser")}


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


# --- Approvals -------------------------------------------------------------------------------------------

class ApprovalIn(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@office_router.get("/approvals")
async def office_approvals(c: AppContext = Depends(ctx)):
    return {"approvals": approvals.for_office(c.db), "kinds": [{"key": k, "label": v} for k, v in KIND_LABEL.items()]}


@office_router.post("/orders/{order_id}/approvals", status_code=201)
async def office_request_approval(order_id: int, body: ApprovalIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    return {"id": approvals.request_approval(c.db, order_id, user.id, body.kind, body.title, body.note)}


@office_router.post("/approvals/{approval_id}/resubmit")
async def office_resubmit(approval_id: int, body: NoteIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    approvals.resubmit(c.db, approval_id, user.id, body.note)
    return {"ok": True}


@office_router.post("/approvals/{approval_id}/withdraw")
async def office_withdraw(approval_id: int, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    approvals.withdraw(c.db, approval_id, user.id)
    return {"ok": True}


@buyer_router.get("/approvals")
async def buyer_approvals(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    approvals.mark_seen(c.db, buyer["id"])
    return {"approvals": approvals.for_buyer(c.db, buyer["id"])}


@buyer_router.post("/approvals/{approval_id}/approve")
async def buyer_approve(approval_id: int, body: NoteIn, buyer: sqlite3.Row = Depends(writable_buyer), c: AppContext = Depends(ctx)):
    approvals.decide(c.db, buyer["id"], approval_id, True, body.note, c.today())
    return {"ok": True}


@buyer_router.post("/approvals/{approval_id}/changes")
async def buyer_changes(approval_id: int, body: NoteIn, buyer: sqlite3.Row = Depends(writable_buyer), c: AppContext = Depends(ctx)):
    approvals.decide(c.db, buyer["id"], approval_id, False, body.note, c.today())
    return {"ok": True}


# --- Timeline and documents ------------------------------------------------------------------------------

@buyer_router.get("/orders/{order_id}/activity")
async def buyer_activity(order_id: int, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    order_messages.thread(c.db, order_id, buyer["id"])  # 404 unless it is theirs
    return {"activity": activity.for_order(c.db, order_id, "buyer")}


@buyer_router.get("/documents")
async def buyer_documents(token: str, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    """Every file the office has shared with this buyer, and the ones they sent, across orders and requests."""
    response.headers.update(NO_STORE)
    rows = c.db.execute(
        """SELECT a.*, o.po_no AS order_po, o.id AS order_ref, q.po_no AS request_po, q.id AS request_ref
           FROM attachments a LEFT JOIN orders o ON o.id = a.order_id LEFT JOIN order_requests q ON q.id = a.request_id
           WHERE (o.buyer_id = :b OR q.buyer_id = :b) AND (a.buyer_visible = 1 OR a.uploaded_by = 'buyer')
             AND (o.id IS NULL OR o.state != 'cancelled') ORDER BY a.id DESC""",
        {"b": buyer["id"]},
    ).fetchall()
    return {"documents": [
        {**_item(r), "uploadedBy": "you" if r["uploaded_by"] == "buyer" else "merchandiser",
         "orderId": r["order_ref"], "orderPo": r["order_po"], "requestId": r["request_ref"], "requestPo": r["request_po"],
         "url": f"/api/b/{token}/attachments/{r['id']}"}
        for r in rows
    ]}

