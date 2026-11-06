"""Office: sign-in accounts for a buyer's own people."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppContext, ctx, merchandiser
from ..services import accounts

router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])


class LoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    canWrite: bool = True  # False = view-only: can read everything, cannot send, approve or change


@router.post("/buyers/{buyer_id}/logins", status_code=201)
async def create(buyer_id: int, body: LoginIn, c: AppContext = Depends(ctx)):
    return accounts.create_login(c.db, buyer_id, body.name, body.email, body.canWrite)


@router.post("/buyer-logins/{user_id}/reset")
async def reset(user_id: int, c: AppContext = Depends(ctx)):
    return accounts.reset_password(c.db, user_id)


class AccessIn(BaseModel):
    canWrite: bool


@router.patch("/buyer-logins/{user_id}")
async def access(user_id: int, body: AccessIn, c: AppContext = Depends(ctx)):
    accounts.set_access(c.db, user_id, body.canWrite)
    return {"ok": True}


@router.delete("/buyer-logins/{user_id}")
async def remove(user_id: int, c: AppContext = Depends(ctx)):
    accounts.remove_login(c.db, user_id)
    return {"ok": True}
