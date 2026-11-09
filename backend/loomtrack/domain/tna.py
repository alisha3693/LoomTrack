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
    after: str | None = None  # stages only: the step this one starts straight after (the next day). start_offset is kept in step with it


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    items: tuple[TemplateItem, ...]


def _m(code, en, ta, end):
    return TemplateItem(code, en, ta, "milestone", end)


def _s(code, en, ta, process, start, end):
    return TemplateItem(code, en, ta, "stage", end, start, process)


FIT = _m("FIT", "Fit sample approval", "ஃபிட் மாதிரி ஒப்புதல்", 0)
LAB = _m("LAB", "Lab dip / colour approval", "லேப் டிப் / நிற ஒப்புதல்", 0)
PP = _m("PP", "PP sample approval", "பிபி மாதிரி ஒப்புதல்", 0)
FAB = _m("FAB", "Fabric in-house", "துணி வந்து சேர்ந்தது", 0)
FABQC = _m("FABQC", "Fabric inspection & shrinkage test", "துணி ஆய்வு & சுருக்கச் சோதனை", 0)
TRIMS = _m("TRIMS", "Trims & packing material in-house", "ட்ரிம்ஸ் & பேக்கிங் பொருட்கள் வந்தன", 0)
INLINE = _m("INLINE", "Inline inspection", "இடைநிலை ஆய்வு", 0)
FINAL = _m("FINAL", "Final inspection (AQL)", "இறுதி ஆய்வு (AQL)", 2)
EXF = _m("EXF", "Ex-factory", "ஏற்றுமதி", 0)

# (code, English, Tamil, process, calendar days the stage runs)
CUT = ("CUT", "Cutting", "கட்டிங்", "cutting", 10)
PRINT = ("PRINT", "Printing", "பிரிண்டிங்", "printing", 12)
STITCH = ("STITCH", "Stitching", "தையல்", "stitching", 17)
WASH = ("WASH", "Washing", "வாஷிங்", "washing", 8)
FINISH = ("FINISH", "Finishing & checking", "ஃபினிஷிங் & செக்கிங்", "finishing", 10)
PACK = ("PACK", "Packing", "பேக்கிங்", "packing", 5)

PACK_DUE = 3  # packing ends three days before the goods leave; final inspection is at two


def _with_offset(item: TemplateItem, end: int) -> TemplateItem:
    return TemplateItem(item.code, item.name_en, item.name_ta, item.kind, end, item.start_offset, item.process, item.after)


def _build(*stages: tuple) -> tuple[TemplateItem, ...]:
    """A production plan where each stage starts the day after the one before it ends, worked back from packing.
    The checkpoints sit where a buyer expects them: fabric in and inspected before cutting starts, trims before
    stitching starts, the inline inspection while stitching runs, the approvals ahead of all of it."""
    items: dict[str, TemplateItem] = {}
    end, after = PACK_DUE, None
    for code, en, ta, process, runs in reversed(stages):
        start = end + runs
        items[code] = TemplateItem(code, en, ta, "stage", end, start, process, None)
        end = start + 1  # the stage before this one ends the day before it starts
    # each stage names the one before it; start offsets already match
    order = [s[0] for s in stages]
    for n, code in enumerate(order):
        if n:
            i = items[code]
            items[code] = TemplateItem(i.code, i.name_en, i.name_ta, i.kind, i.end_offset, i.start_offset, i.process, order[n - 1])
    first, stitch = items[order[0]], items["STITCH"]
    checkpoints = (
        _with_offset(FIT, first.start_offset + 20), _with_offset(LAB, first.start_offset + 14), _with_offset(PP, first.start_offset + 8),
        _with_offset(FAB, first.start_offset + 2), _with_offset(FABQC, first.start_offset + 1),
        _with_offset(TRIMS, stitch.start_offset + 4), _with_offset(INLINE, stitch.end_offset + 5),
    )
    plan = (*checkpoints, *items.values(), FINAL, EXF)
    return tuple(sorted(plan, key=lambda i: -i.end_offset))  # a plan reads in the order things are due


# Starting templates, copied into the database at startup. Merchandisers add their own in the app.
BUILTIN_TEMPLATES: dict[str, Template] = {
    t.key: t
    for t in (
        Template("basic", "Knit basic (tee / polo)", _build(CUT, STITCH, FINISH, PACK)),
        Template("printed", "Knit printed (subcontract print)", _build(CUT, PRINT, STITCH, FINISH, PACK)),
        Template("washed", "Knit garment-washed (subcontract wash)", _build(CUT, STITCH, WASH, FINISH, PACK)),
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
