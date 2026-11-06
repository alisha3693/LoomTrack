"""Office API for plan templates and the step library."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppContext, User, ctx, merchandiser
from ..domain.tna import Template
from ..services import templates as svc
from ..services.templates import StepIn
from ..util import HttpError
from .merchandiser import IsoDate

router = APIRouter(prefix="/api/m", dependencies=[Depends(merchandiser)])


class TemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    steps: list[StepIn] = Field(min_length=1, max_length=svc.MAX_STEPS)


class PreviewIn(BaseModel):
    exFactory: IsoDate
    steps: list[StepIn] = Field(min_length=1, max_length=svc.MAX_STEPS)


@router.get("/templates")
async def templates(retired: bool = False, c: AppContext = Depends(ctx)):
    return {"templates": svc.list_templates(c.db, include_retired=retired), "library": svc.step_library(c.db)}


@router.post("/templates", status_code=201)
async def create(body: TemplateIn, user: User = Depends(merchandiser), c: AppContext = Depends(ctx)):
    return {"id": svc.create_template(c.db, body.name, body.steps, user.id)}


@router.put("/templates/{template_id}")
async def update(template_id: int, body: TemplateIn, c: AppContext = Depends(ctx)):
    svc.update_template(c.db, template_id, body.name, body.steps)
    return {"ok": True}


@router.post("/templates/{template_id}/retire")
async def retire(template_id: int, c: AppContext = Depends(ctx)):
    svc.set_active(c.db, template_id, False)
    return {"ok": True}


@router.post("/templates/{template_id}/restore")
async def restore(template_id: int, c: AppContext = Depends(ctx)):
    svc.set_active(c.db, template_id, True)
    return {"ok": True}


@router.post("/templates/preview")
async def preview(body: PreviewIn, c: AppContext = Depends(ctx)):
    """Dates for an unsaved layout, so the editor can show what it will produce."""
    items = svc.resolve_steps(c.db, body.steps, create=False)
    return {"items": svc.plan_json(c.db, Template("preview", "Preview", tuple(items)), body.exFactory)}


class StepNameIn(BaseModel):
    nameEn: str = Field(min_length=2, max_length=60)
    nameTa: str = Field(min_length=1, max_length=80)


@router.patch("/steps/{code}")
async def rename_step(code: str, body: StepNameIn, c: AppContext = Depends(ctx)):
    """Fix a custom step's name once; every template and order that uses it shows the new name."""
    step = c.db.execute("SELECT builtin FROM plan_steps WHERE code = ?", (code,)).fetchone()
    if not step:
        raise HttpError(404, "Step not found")
    if step["builtin"]:
        raise HttpError(403, "Built-in steps can't be renamed")
    c.db.execute("UPDATE plan_steps SET name_en = ?, name_ta = ? WHERE code = ?", (body.nameEn.strip(), body.nameTa.strip(), code))
    return {"ok": True}
