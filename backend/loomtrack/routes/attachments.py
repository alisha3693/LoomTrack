"""Files on requests and orders: upload (buyer and office), the floor's list, and the downloads."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..deps import AppContext, User, ctx, merchandiser, supervisor
from ..security import sign_path, verify_signed_path
from ..services import attachments as svc
from ..services.requests import find_request, require_open
from ..util import HttpError
from .buyer import NO_STORE, current_buyer

SAFE_HEADERS = {**NO_STORE, "X-Content-Type-Options": "nosniff"}


def _send(row: sqlite3.Row) -> FileResponse:
    return FileResponse(
        row["path"], media_type=row["mime"], filename=row["filename"], headers=SAFE_HEADERS,
        content_disposition_type="inline" if svc.is_inline(row["mime"]) else "attachment",
    )


def _one(db: sqlite3.Connection, attachment_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if row is None:
        raise HttpError(404, "File not found")
    return row


# --- The buyer (private link): their own requests only ---------------------------------------------

buyer_router = APIRouter(prefix="/api/b/{token}")


@buyer_router.post("/requests/{request_id}/attachments", status_code=201)
async def buyer_upload(
    request_id: int, kind: str = Form(...), file: UploadFile = File(...),
    buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx),
):
    require_open(find_request(c.db, request_id, buyer["id"]))
    aid = await svc.store(c.db, c.upload_dir, file, kind=kind, uploaded_by="buyer", user_id=None, request_id=request_id)
    return {"id": aid}


@buyer_router.delete("/requests/{request_id}/attachments/{attachment_id}")
async def buyer_delete(request_id: int, attachment_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    require_open(find_request(c.db, request_id, buyer["id"]))
    row = _one(c.db, attachment_id)
    if row["request_id"] != request_id or row["uploaded_by"] != "buyer":
        raise HttpError(404, "File not found")
    svc.remove(c.db, attachment_id)
    return {"ok": True}


@buyer_router.get("/attachments/{attachment_id}")
async def buyer_download(attachment_id: int, buyer: sqlite3.Row = Depends(current_buyer), c: AppContext = Depends(ctx)):
    row = c.db.execute(
        """SELECT a.* FROM attachments a LEFT JOIN order_requests q ON q.id = a.request_id LEFT JOIN orders o ON o.id = a.order_id
           WHERE a.id = ? AND a.buyer_visible = 1 AND (q.buyer_id = ? OR o.buyer_id = ?)""",
        (attachment_id, buyer["id"], buyer["id"]),
    ).fetchone()
    if row is None:
        raise HttpError(404, "File not found")
    return _send(row)


# --- The office ------------------------------------------------------------------------------------------

office_router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])


@office_router.post("/requests/{request_id}/attachments", status_code=201)
async def office_upload_to_request(
    request_id: int, kind: str = Form(...), buyerVisible: bool = Form(False), supervisorVisible: bool = Form(False),
    file: UploadFile = File(...), user: User = Depends(merchandiser), c: AppContext = Depends(ctx),
):
    find_request(c.db, request_id)
    aid = await svc.store(c.db, c.upload_dir, file, kind=kind, uploaded_by="merchandiser", user_id=user.id, request_id=request_id,
                          buyer_visible=buyerVisible, supervisor_visible=supervisorVisible)
    return {"id": aid}


@office_router.post("/orders/{order_id}/attachments", status_code=201)
async def office_upload_to_order(
    order_id: int, kind: str = Form(...), buyerVisible: bool = Form(False), supervisorVisible: bool = Form(False),
    file: UploadFile = File(...), user: User = Depends(merchandiser), c: AppContext = Depends(ctx),
):
    if not c.db.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone():
        raise HttpError(404, "Order not found")
    aid = await svc.store(c.db, c.upload_dir, file, kind=kind, uploaded_by="merchandiser", user_id=user.id, order_id=order_id,
                          buyer_visible=buyerVisible, supervisor_visible=supervisorVisible)
    return {"id": aid}


class AttachmentPatch(BaseModel):
    buyerVisible: bool | None = None
    supervisorVisible: bool | None = None
    kind: str | None = None


@office_router.patch("/attachments/{attachment_id}")
async def office_patch(attachment_id: int, body: AttachmentPatch, c: AppContext = Depends(ctx)):
    row = _one(c.db, attachment_id)
    if body.kind is not None and body.kind not in svc.KINDS:
        raise HttpError(400, "Unknown file kind")
    if body.buyerVisible is False and row["uploaded_by"] == "buyer":
        raise HttpError(409, "The buyer's own files stay visible to the buyer")
    c.db.execute(
        "UPDATE attachments SET buyer_visible = ?, supervisor_visible = ?, kind = ? WHERE id = ?",
        (int(row["buyer_visible"] if body.buyerVisible is None else body.buyerVisible),
         int(row["supervisor_visible"] if body.supervisorVisible is None else body.supervisorVisible),
         body.kind or row["kind"], attachment_id),
    )
    return {"ok": True}


@office_router.delete("/attachments/{attachment_id}")
async def office_delete(attachment_id: int, c: AppContext = Depends(ctx)):
    row = _one(c.db, attachment_id)
    if row["uploaded_by"] != "merchandiser":
        raise HttpError(403, "A file the buyer sent can only be removed by the buyer")
    svc.remove(c.db, attachment_id)
    return {"ok": True}


# --- The floor: only what the merchandiser shared, only for orders their unit works on -------------------

supervisor_router = APIRouter(prefix="/api/s")


@supervisor_router.get("/orders/{order_id}/attachments")
async def floor_files(order_id: int, user: User = Depends(supervisor), c: AppContext = Depends(ctx)):
    files = svc.for_supervisor(c.db, user.unit_id, order_id)
    return {"files": [{**f, "url": sign_path(f"/api/media/attachments/{f['id']}")} for f in files]}


# --- Signed download for staff (an <a> link cannot send a Bearer header) ----------------------------------

media_router = APIRouter(prefix="/api/media")


@media_router.get("/attachments/{attachment_id}")
async def staff_download(attachment_id: int, exp: str | None = None, sig: str | None = None, c: AppContext = Depends(ctx)):
    if not verify_signed_path(f"/api/media/attachments/{attachment_id}", exp, sig):
        raise HttpError(403, "Link expired")
    return _send(_one(c.db, attachment_id))
