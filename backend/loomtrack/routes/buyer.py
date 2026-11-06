"""The buyer's own pages.

Two ways in, one buyer id out. The private link token in the path is a credential by itself. A buyer
who signed in with an account uses the word "me" in its place and the id comes from their session.
Every lookup below is scoped to that id and nothing else.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from ..deps import AppContext, ctx, optional_user
from ..services.buyer_view import buyer_by_token, buyer_orders
from ..services.export import weekly_workbook
from ..util import HttpError, iso_week

router = APIRouter(prefix="/api/b/{token}")

NO_STORE = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


ACCOUNT = "me"  # link tokens are 43 random characters, so this can never be one


async def current_buyer(token: str, request: Request, c: AppContext = Depends(ctx)) -> sqlite3.Row:
    if token == ACCOUNT:
        user = await optional_user(request, c)
        if user is None:
            raise HttpError(401, "Sign in required")
        if user.role != "buyer":
            raise HttpError(403, "This page is for buyer accounts")
        if user.must_change_secret:
            raise HttpError(403, "Choose a new password first")
        return c.db.execute("SELECT * FROM buyers WHERE id = ?", (user.buyer_id,)).fetchone()
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
        """SELECT p.path, p.mime FROM photos p JOIN daily_updates u ON u.id = p.update_id
           JOIN milestones m ON m.id = u.milestone_id JOIN orders o ON o.id = m.order_id
           WHERE p.id = ? AND o.buyer_id = ? AND p.buyer_visible = 1""",
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
