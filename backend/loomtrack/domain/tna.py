"""Time-and-action templates.

Offsets are calendar days before ex-factory; generated dates snap back to
the nearest working day.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import Calendar, add_days


@dataclass(frozen=True)
class TemplateItem:
    code: str
    name_en: str
    name_ta: str
    kind: str  # 'milestone' | 'stage'
    end_offset: int
    start_offset: int | None = None  # stages only
    process: str | None = None  # stages only: decides own unit vs subcontractor


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    items: tuple[TemplateItem, ...]


def _m(code, en, ta, end):
    return TemplateItem(code, en, ta, "milestone", end)


def _s(code, en, ta, process, start, end):
    return TemplateItem(code, en, ta, "stage", end, start, process)


FIT = _m("FIT", "Fit sample approval", "ஃபிட் மாதிரி ஒப்புதல்", 60)
PP = _m("PP", "PP sample approval", "பிபி மாதிரி ஒப்புதல்", 40)
FAB = _m("FAB", "Fabric in-house", "துணி வந்து சேர்ந்தது", 32)
INLINE = _m("INLINE", "Inline inspection", "இடைநிலை ஆய்வு", 10)
FINAL = _m("FINAL", "Final inspection", "இறுதி ஆய்வு", 2)
EXF = _m("EXF", "Ex-factory", "ஏற்றுமதி", 0)

CUT = _s("CUT", "Cutting", "கட்டிங்", "cutting", 30, 20)
PRINT = _s("PRINT", "Printing", "பிரிண்டிங்", "printing", 26, 14)
STITCH = _s("STITCH", "Stitching", "தையல்", "stitching", 24, 7)
WASH = _s("WASH", "Washing", "வாஷிங்", "washing", 14, 6)
FINISH = _s("FINISH", "Finishing & checking", "ஃபினிஷிங் & செக்கிங்", "finishing", 14, 4)
PACK = _s("PACK", "Packing", "பேக்கிங்", "packing", 8, 3)

# Starting templates, copied into the database at startup. Merchandisers add their own in the app.
BUILTIN_TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (
        Template("basic", "Knit basic (tee / polo)", (FIT, PP, FAB, CUT, STITCH, INLINE, FINISH, PACK, FINAL, EXF)),
        Template("printed", "Knit printed (subcontract print)", (FIT, PP, FAB, CUT, PRINT, STITCH, INLINE, FINISH, PACK, FINAL, EXF)),
        Template("washed", "Knit garment-washed (subcontract wash)", (FIT, PP, FAB, CUT, STITCH, INLINE, WASH, FINISH, PACK, FINAL, EXF)),
    )
}


@dataclass(frozen=True)
class PlannedItem:
    seq: int
    item: TemplateItem
    planned_start: str | None
    planned_date: str

    def to_json(self) -> dict:
        i = self.item
        return {
            "seq": self.seq, "code": i.code, "nameEn": i.name_en, "nameTa": i.name_ta, "kind": i.kind,
            "process": i.process, "plannedStart": self.planned_start, "plannedDate": self.planned_date,
        }


def plan_from_template(cal: Calendar, t: Template, ex_factory: str) -> list[PlannedItem]:
    return [
        PlannedItem(
            seq=n,
            item=it,
            planned_start=cal.snap_back(add_days(ex_factory, -it.start_offset)) if it.start_offset is not None else None,
            planned_date=ex_factory if it.code == "EXF" else cal.snap_back(add_days(ex_factory, -it.end_offset)),
        )
        for n, it in enumerate(t.items, start=1)
    ]
