"""Office: the materials an order needs, and unit capacity."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..services import capacity as cap
from ..services import materials as svc
from ..services.orders import refresh_order
from ..services.templates import load_template
from ..util import HttpError

router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])

IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class MaterialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["fabric", "trim", "packing"]
    name: str = Field(min_length=1, max_length=80)
    supplier: str | None = Field(default=None, max_length=80)
    suppliedBy: Literal["us", "buyer"] = "us"
    qty: float | None = Field(default=None, gt=0, le=10_000_000)
    unit: str | None = Field(default=None, max_length=12)
    status: Literal["not_ordered", "ordered", "received"] = "not_ordered"
    orderedDate: IsoDate | None = None
    expectedDate: IsoDate | None = None
    receivedDate: IsoDate | None = None
    neededFor: str | None = Field(default=None, max_length=20)
    neededBy: IsoDate | None = None
    note: str | None = Field(default=None, max_length=300)


class MaterialPatch(BaseModel):
    """Only the fields that are sent are changed."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["fabric", "trim", "packing"] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)
    supplier: str | None = Field(default=None, max_length=80)
    suppliedBy: Literal["us", "buyer"] | None = None
    qty: float | None = Field(default=None, gt=0, le=10_000_000)
    unit: str | None = Field(default=None, max_length=12)
    status: Literal["not_ordered", "ordered", "received"] | None = None
    orderedDate: IsoDate | None = None
    expectedDate: IsoDate | None = None
    receivedDate: IsoDate | None = None
    neededFor: str | None = Field(default=None, max_length=20)
    neededBy: IsoDate | None = None
    note: str | None = Field(default=None, max_length=300)


_COLUMN = {
    "suppliedBy": "supplied_by", "orderedDate": "ordered_date", "expectedDate": "expected_date",
    "receivedDate": "received_date", "neededFor": "needed_for", "neededBy": "needed_by",
}


def _fields(model: BaseModel, *, only_sent: bool) -> dict:
    data = model.model_dump(exclude_unset=only_sent)
    return {_COLUMN.get(k, k): v for k, v in data.items()}


@router.get("/orders/{order_id}/materials")
async def list_materials(order_id: int, c: AppContext = Depends(ctx)):
    if c.db.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        raise HttpError(404, "Order not found")
    items = svc.list_for_order(c.db, order_id, c.today())
    return {"materials": items, "summary": svc.summarise(items)}


@router.post("/orders/{order_id}/materials", status_code=201)
async def add_material(order_id: int, body: MaterialIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    mid = svc.add(c.db, order_id, user.id, _fields(body, only_sent=False), c.today())
    refresh_order(c.db, order_id, c.today())
    return {"id": mid}


@router.post("/orders/{order_id}/materials/standard")
async def add_standard_materials(order_id: int, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    added = svc.add_standard(c.db, order_id, user.id, c.today())
    return {"added": added}


@router.patch("/materials/{material_id}")
async def change_material(material_id: int, body: MaterialPatch, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    order_id = svc.update(c.db, material_id, user.id, _fields(body, only_sent=True), c.today())
    refresh_order(c.db, order_id, c.today())
    return {"ok": True}


@router.delete("/materials/{material_id}")
async def delete_material(material_id: int, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    order_id = svc.remove(c.db, material_id, user.id)
    refresh_order(c.db, order_id, c.today())
    return {"ok": True}


# --- Capacity -------------------------------------------------------------------------------------------


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
