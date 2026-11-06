"""Order requests, from both sides: the buyer's link (submit, reply, agree, withdraw) and the office (query, counter, accept, decline)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..security import sign_path
from ..services import order_messages
from ..services import requests as svc
from ..services.attachments import for_buyer, for_office
from ..services.orders import refresh_order
from .buyer import NO_STORE, current_buyer
from .merchandiser import IsoDate, SizeIn

# --- The buyer's side: the private link is the credential, every query is scoped to its buyer ---------

buyer_router = APIRouter(prefix="/api/b/{token}/requests")
buyer_orders_router = APIRouter(prefix="/api/b/{token}/orders")


class RequestIn(BaseModel):
    poNo: str = Field(min_length=3, max_length=40)  # the buyer's own PO number
    style: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    colour: str = Field(min_length=1, max_length=60)
    colourHex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    colourPantone: str | None = Field(default=None, max_length=30)
    exFactory: IsoDate
    fabricType: str | None = Field(default=None, max_length=60)
    fabricComposition: str | None = Field(default=None, max_length=120)
    fabricGsm: int | None = Field(default=None, ge=50, le=800)
    fabricNote: str | None = Field(default=None, max_length=200)
    sizes: list[SizeIn] = Field(min_length=1, max_length=30)


class AmendmentIn(BaseModel):
    """A change to an order that exists: a new ex-factory date, new quantities by size, or both. Leave out what stays."""

    exFactory: IsoDate | None = None
    sizes: list[SizeIn] | None = Field(default=None, max_length=30)
    reason: str = Field(min_length=1, max_length=1000)


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@buyer_router.get("")
async def buyer_list(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {"requests": svc.list_requests(c.db, buyer["id"], "all")}


@buyer_router.post("", status_code=201)
async def buyer_submit(body: RequestIn, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    return {"id": svc.submit_request(c.db, buyer["id"], body, c.today())}


@buyer_orders_router.post("/{order_id}/amendments", status_code=201)
async def buyer_amend(order_id: int, body: AmendmentIn, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    return {"id": svc.submit_amendment(c.db, buyer["id"], order_id, body, c.today())}


class OrderMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@buyer_orders_router.get("/{order_id}/messages")
async def buyer_messages(order_id: int, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {"messages": order_messages.thread(c.db, order_id, buyer["id"])}


@buyer_orders_router.post("/{order_id}/messages", status_code=201)
async def buyer_send_message(order_id: int, body: OrderMessageIn, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    return {"id": order_messages.post(c.db, order_id, "buyer", body.message, buyer_id=buyer["id"])}


@buyer_router.get("/{request_id}")
async def buyer_detail(request_id: int, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {**svc.request_detail(c.db, request_id, buyer["id"]), "attachments": for_buyer(c.db, buyer["id"], request_id=request_id)}


@buyer_router.post("/{request_id}/reply")
async def buyer_reply(request_id: int, body: MessageIn, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    svc.buyer_reply(c.db, buyer["id"], request_id, body.message)
    return {"ok": True}


@buyer_router.post("/{request_id}/agree")
async def buyer_agree(request_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    svc.buyer_agree(c.db, buyer["id"], request_id, c.today())
    return {"ok": True}


@buyer_router.post("/{request_id}/withdraw")
async def buyer_withdraw(request_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    svc.buyer_withdraw(c.db, buyer["id"], request_id)
    return {"ok": True}


# --- The office -----------------------------------------------------------------------------------------

office_router = APIRouter(prefix="/api/m/requests", dependencies=[Depends(merchandiser)])
order_router = APIRouter(prefix="/api/m/orders", dependencies=[Depends(merchandiser)])


class CounterIn(BaseModel):
    exFactory: IsoDate
    message: str = Field(min_length=1, max_length=2000)


class AcceptIn(BaseModel):
    unitId: int | None = None  # needed for a new order, not for a change to an existing one
    templateKey: str | None = None
    message: str | None = Field(default=None, max_length=2000)
    overCapacityOk: bool = False  # the merchandiser has seen the unit would be over capacity and wants the order anyway


@office_router.get("")
async def office_list(filter: str = "mine", c: AppContext = Depends(ctx)):
    return {"requests": svc.list_requests(c.db, None, filter), "openCount": svc.open_count(c.db)}


@office_router.get("/{request_id}")
async def office_detail(request_id: int, c: AppContext = Depends(ctx)):
    files = [{**a, "url": sign_path(f"/api/media/attachments/{a['id']}")} for a in for_office(c.db, request_id=request_id)]
    return {**svc.request_detail(c.db, request_id), "attachments": files}


@office_router.post("/{request_id}/query")
async def office_query(request_id: int, body: MessageIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    svc.office_query(c.db, user.id, request_id, body.message)
    return {"ok": True}


@office_router.post("/{request_id}/counter")
async def office_counter(request_id: int, body: CounterIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    svc.office_counter(c.db, user.id, request_id, body.exFactory, body.message, c.today())
    return {"ok": True}


@office_router.post("/{request_id}/decline")
async def office_decline(request_id: int, body: MessageIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    svc.office_decline(c.db, user.id, request_id, body.message)
    return {"ok": True}


@office_router.post("/{request_id}/accept")
async def office_accept(request_id: int, body: AcceptIn | None = None, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    body = body or AcceptIn()  # a change to an existing order needs nothing more than "accept"
    order_id, order_no = svc.office_accept(c.db, user.id, request_id, body.unitId, body.templateKey, body.message, c.today(), body.overCapacityOk)
    refresh_order(c.db, order_id, c.today())
    return {"orderId": order_id, "orderNo": order_no}


@order_router.get("/{order_id}/messages")
async def office_messages(order_id: int, c: AppContext = Depends(ctx)):
    return {"messages": order_messages.thread(c.db, order_id)}


@order_router.post("/{order_id}/messages", status_code=201)
async def office_send_message(order_id: int, body: OrderMessageIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    return {"id": order_messages.post(c.db, order_id, "merchandiser", body.message, user_id=user.id)}


@order_router.post("/{order_id}/amend", status_code=201)
async def office_amend(order_id: int, body: AmendmentIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    """Record a change the buyer asked for outside the app, and apply it with the same trail as a request."""
    rid = svc.office_record_change(c.db, user.id, order_id, body.exFactory, body.sizes, body.reason, c.today())
    refresh_order(c.db, order_id, c.today())
    return {"id": rid}
