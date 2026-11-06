"""Order requests, from both sides: the buyer's link (submit, reply, agree, withdraw) and the office (query, counter, accept, decline)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..services import requests as svc
from ..services.orders import refresh_order
from .buyer import NO_STORE, current_buyer
from .merchandiser import IsoDate, SizeIn

# --- The buyer's side: the private link is the credential, every query is scoped to its buyer ---------

buyer_router = APIRouter(prefix="/api/b/{token}/requests")


class RequestIn(BaseModel):
    poNo: str = Field(min_length=3, max_length=40)  # the buyer's own PO number
    style: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    colour: str = Field(min_length=1, max_length=60)
    colourHex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    colourPantone: str | None = Field(default=None, max_length=30)
    exFactory: IsoDate
    sizes: list[SizeIn] = Field(min_length=1, max_length=30)


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@buyer_router.get("")
async def buyer_list(response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return {"requests": svc.list_requests(c.db, buyer["id"], "all")}


@buyer_router.post("", status_code=201)
async def buyer_submit(body: RequestIn, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    return {"id": svc.submit_request(c.db, buyer["id"], body, c.today())}


@buyer_router.get("/{request_id}")
async def buyer_detail(request_id: int, response: Response, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    return svc.request_detail(c.db, request_id, buyer["id"])


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


class CounterIn(BaseModel):
    exFactory: IsoDate
    message: str = Field(min_length=1, max_length=2000)


class AcceptIn(BaseModel):
    unitId: int
    templateKey: str
    message: str | None = Field(default=None, max_length=2000)


@office_router.get("")
async def office_list(filter: str = "mine", c: AppContext = Depends(ctx)):
    return {"requests": svc.list_requests(c.db, None, filter), "openCount": svc.open_count(c.db)}


@office_router.get("/{request_id}")
async def office_detail(request_id: int, c: AppContext = Depends(ctx)):
    return svc.request_detail(c.db, request_id)


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
async def office_accept(request_id: int, body: AcceptIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    order_id, order_no = svc.office_accept(c.db, user.id, request_id, body.unitId, body.templateKey, body.message, c.today())
    refresh_order(c.db, order_id, c.today())
    return {"orderId": order_id, "orderNo": order_no}
