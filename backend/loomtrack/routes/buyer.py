"""Read-only buyer link.

The token is the only credential; the buyer id comes from it and from
nowhere else, and every lookup below is scoped to it.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse

from ..deps import AppContext, ctx
from ..services.buyer_view import buyer_by_token, buyer_orders
from ..services.export import weekly_workbook
from ..util import HttpError, iso_week

router = APIRouter(prefix="/api/b/{token}")

NO_STORE = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


async def current_buyer(token: str, c: AppContext = Depends(ctx)) -> sqlite3.Row:
    buyer = buyer_by_token(c.db, token)
    if buyer is None:
        raise HttpError(404, "This link is not valid. Ask your merchandiser for a new one.")
    return buyer


@router.get("")
async def view(response: Response, buyer=Depends(current_buyer), c: AppContext = Depends(ctx)):
    response.headers.update(NO_STORE)
    today = c.today()
    return {"buyer": {"name": buyer["name"], "country": buyer["country"]}, "today": today, "orders": buyer_orders(c.db, buyer["id"], today)}


@router.get("/photos/{photo_id}")
async def photo(photo_id: int, buyer=Depends(current_buyer), c: AppContext = Depends(ctx)):
    row = c.db.execute(
        "SELECT p.path, p.mime FROM photos p JOIN orders o ON o.id = p.order_id WHERE p.id = ? AND o.buyer_id = ? AND p.buyer_visible = 1",
        (photo_id, buyer["id"]),
    ).fetchone()
    if row is None:
        raise HttpError(404, "Photo not found")
    return FileResponse(row["path"], media_type=row["mime"], headers=NO_STORE)


@router.get("/weekly.xlsx")
async def weekly(buyer=Depends(current_buyer), c: AppContext = Depends(ctx)):
    today = c.today()
    data = weekly_workbook(c.db, buyer["id"], today, "buyer")
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={**NO_STORE, "Content-Disposition": f'attachment; filename="order-status-{iso_week(today)}.xlsx"'},
    )
