"""Office: unit capacity and the capacity check before an order is accepted."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppContext, ctx, merchandiser
from ..services import capacity as cap
from ..services.templates import load_template
from ..util import HttpError

router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])

IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class CapacityIn(BaseModel):
    qty: int = Field(ge=1, le=10_000_000)
    exFactory: IsoDate
    templateKey: str


@router.post("/capacity/check")
async def capacity_check(body: CapacityIn, c: AppContext = Depends(ctx)):
    t = load_template(c.db, body.templateKey, active_only=True)
    if not t:
        raise HttpError(400, "Unknown template")
    return cap.check(c.db, body.qty, body.exFactory, t, c.today())


@router.get("/units")
async def units(c: AppContext = Depends(ctx)):
    return {"units": cap.units_with_load(c.db, c.today())}


class UnitIn(BaseModel):
    dailyCapacity: int | None = Field(ge=1, le=1_000_000)
    process: str = "stitching"  # which stage the number is for


@router.patch("/units/{unit_id}")
async def set_capacity(unit_id: int, body: UnitIn, c: AppContext = Depends(ctx)):
    if body.process not in cap.own_processes(c.db):
        raise HttpError(400, "Capacity is set for the stages we do ourselves, not for job work")
    if not c.db.execute("SELECT 1 FROM units WHERE id = ? AND kind = 'own'", (unit_id,)).fetchone():
        raise HttpError(404, "Not one of our own units")
    cap.set_capacity(c.db, unit_id, body.process, body.dailyCapacity)
    return {"ok": True}
