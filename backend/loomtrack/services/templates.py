"""Plan templates: load them, check a merchandiser's layout, save it.

A template is an ordered list of steps with offsets (calendar days before ex-factory). The delay
engine reads a plan's stages in order and assumes each starts and ends after the one before,
so a saved template is always ordered by end offset, and ex-factory is always the last step.
"""

from __future__ import annotations

import difflib
import re
import secrets
import sqlite3
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, Field

from ..config import CALENDAR
from ..db import transaction
from ..domain.tna import PlannedItem, Template, TemplateItem, plan_from_template
from ..util import HttpError

MAX_STEPS = 30
_STEP_SQL = """SELECT ts.code, s.name_en, s.name_ta, s.kind, s.process, s.builtin, ts.end_offset, ts.start_offset, ts.after_code
               FROM template_steps ts JOIN plan_steps s ON s.code = ts.code WHERE ts.template_id = ? ORDER BY ts.seq"""


class StepIn(BaseModel):
    """One row of the editor. With `code` it points at an existing step; without, it defines a new one."""

    code: str | None = Field(default=None, max_length=24)
    nameEn: str | None = Field(default=None, max_length=60)
    nameTa: str | None = Field(default=None, max_length=80)
    kind: Literal["milestone", "stage"] | None = None
    process: str | None = Field(default=None, max_length=30)
    endOffset: int = Field(ge=0, le=365)
    startOffset: int | None = Field(default=None, ge=0, le=365)
    after: str | None = Field(default=None, max_length=60)  # stages: start the day after this step ends (its code, or its name if it is new)


def load_template(db: sqlite3.Connection, key: str, active_only: bool = False) -> Template | None:
    t = db.execute("SELECT id, key, name, active FROM templates WHERE key = ?", (key,)).fetchone()
    if not t or (active_only and not t["active"]):
        return None
    items = tuple(
        TemplateItem(r["code"], r["name_en"], r["name_ta"], r["kind"], r["end_offset"], r["start_offset"], r["process"], r["after_code"])
        for r in db.execute(_STEP_SQL, (t["id"],))
    )
    return Template(t["key"], t["name"], items)


def _step_json(r: sqlite3.Row) -> dict:
    return {
        "code": r["code"], "nameEn": r["name_en"], "nameTa": r["name_ta"], "kind": r["kind"], "process": r["process"],
        "builtin": bool(r["builtin"]), "endOffset": r["end_offset"], "startOffset": r["start_offset"], "after": r["after_code"],
    }


def list_templates(db: sqlite3.Connection, include_retired: bool = False) -> list[dict]:
    out = []
    for t in db.execute(
        """SELECT t.*, (SELECT COUNT(*) FROM orders o WHERE o.template_key = t.key) AS used_by FROM templates t
           WHERE ? OR t.active = 1 ORDER BY t.builtin DESC, lower(t.name)""",
        (1 if include_retired else 0,),
    ):
        out.append({
            "id": t["id"], "key": t["key"], "name": t["name"], "builtin": bool(t["builtin"]), "active": bool(t["active"]),
            "usedBy": t["used_by"], "steps": [_step_json(r) for r in db.execute(_STEP_SQL, (t["id"],))],
        })
    return out


def step_library(db: sqlite3.Connection) -> list[dict]:
    return [
        {"code": r["code"], "nameEn": r["name_en"], "nameTa": r["name_ta"], "kind": r["kind"], "process": r["process"], "builtin": bool(r["builtin"])}
        for r in db.execute("SELECT * FROM plan_steps WHERE code != 'EXF' ORDER BY builtin DESC, kind DESC, name_en")
    ]


# What the work is called. The app matches on these words, so the editor offers them as a list.
STANDARD_PROCESSES = ("cutting", "printing", "embroidery", "stitching", "washing", "finishing", "packing")


def known_processes(db: sqlite3.Connection) -> list[str]:
    """The standard processes, plus any a subcontract unit or an earlier custom step already uses."""
    found = {r[0] for r in db.execute("SELECT process FROM plan_steps WHERE process IS NOT NULL")}
    found |= {r[0] for r in db.execute("SELECT process FROM units WHERE process IS NOT NULL")}
    return sorted(set(STANDARD_PROCESSES) | found)


def _new_code(db: sqlite3.Connection, name: str, taken: set[str]) -> str:
    base = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:16] or "STEP"
    code, n = base, 2
    while code == "EXF" or code in taken or db.execute("SELECT 1 FROM plan_steps WHERE code = ?", (code,)).fetchone():
        code, n = f"{base[:13]}_{n}", n + 1
    return code


def resolve_steps(db: sqlite3.Connection, steps: list[StepIn], create: bool) -> list[TemplateItem]:
    """Check the editor's rows and return the full, ordered step list (ex-factory added last).
    With create=True, steps defined inline are saved to plan_steps; call inside a transaction."""
    items: list[TemplateItem] = []
    seen: set[str] = set()
    given: list[StepIn] = []  # the editor row behind each item, to resolve "starts after" once every step is known
    for s in steps:
        if s.code == "EXF":
            continue  # ex-factory is always added, last
        if s.code:
            row = db.execute("SELECT code, name_en, name_ta, kind, process FROM plan_steps WHERE code = ?", (s.code,)).fetchone()
            if not row:
                raise HttpError(400, f"Unknown step {s.code}")
            code, en, ta, kind, process = row["code"], row["name_en"], row["name_ta"], row["kind"], row["process"]
        else:
            en = (s.nameEn or "").strip()
            if len(en) < 2:
                raise HttpError(400, "Every new step needs a name")
            if s.kind is None:
                raise HttpError(400, f"Say whether {en} is a production stage or a milestone")
            kind = s.kind
            same = db.execute("SELECT code, name_en, name_ta, kind, process FROM plan_steps WHERE lower(name_en) = lower(?)", (en,)).fetchone()
            if same and same["code"] == "EXF":
                raise HttpError(400, "Ex-factory is added to every plan automatically")
            if same and same["kind"] == kind:
                # Already in the library under this name: use that step rather than make a second one.
                code, en, ta, process = same["code"], same["name_en"], same["name_ta"], same["process"]
            else:
                process = re.sub(r"[^a-z0-9 ]+", "", (s.process or "").lower()).strip() or None if kind == "stage" else None
                if kind == "stage" and not process:
                    raise HttpError(400, f"{en}: a production stage needs a process name (for example embroidery)")
                if process and process not in known_processes(db):
                    # An unknown word matches no subcontractor and no capacity check, so a typo would go unnoticed.
                    close = difflib.get_close_matches(process, known_processes(db), n=1, cutoff=0.75)
                    if close:
                        raise HttpError(400, f"{en}: the process \"{process}\" looks like \"{close[0]}\". Choose \"{close[0]}\" from the list, or something else if it really is a different process.")
                ta = (s.nameTa or "").strip() or en
                code = _new_code(db, en, seen)
                if create:
                    db.execute(
                        "INSERT INTO plan_steps (code, name_en, name_ta, kind, process, builtin) VALUES (?,?,?,?,?,0)",
                        (code, en, ta, kind, process),
                    )
        if code in seen:
            raise HttpError(400, f"{en} is in the plan twice")
        seen.add(code)
        start = None
        if kind == "stage":
            if s.after is None and (s.startOffset is None or s.startOffset <= s.endOffset):
                raise HttpError(400, f"{en}: the start must be earlier than the end (more days before ex-factory)")
            start = s.startOffset
        elif s.after:
            raise HttpError(400, f"{en} is a milestone: only a production stage can start after another step")
        items.append(TemplateItem(code, en, ta, kind, s.endOffset, start, process))
        given.append(s)

    # A stage that starts after another step starts the next day, so its start follows that step's end.
    names = {i.code.lower(): n for n, i in enumerate(items)} | {i.name_en.lower(): n for n, i in enumerate(items)}
    for n, s in enumerate(given):
        if not s.after:
            continue
        target = names.get(s.after.strip().lower())
        item = items[n]
        if target is None:
            raise HttpError(400, f"{item.name_en}: the step it should start after is not in this plan")
        if target == n:
            raise HttpError(400, f"{item.name_en} cannot start after itself")
        pred = items[target]
        start = pred.end_offset - 1
        if start <= item.end_offset:
            raise HttpError(400, f"{item.name_en} would start {start} days before ex-factory, which is not before it is due ({item.end_offset} days). Make it due later, or start it after a step that ends sooner than {pred.name_en}.")
        items[n] = replace(item, start_offset=start, after=pred.code)

    if not any(i.kind == "stage" for i in items):
        raise HttpError(400, "Add at least one production stage")
    # the steps keep the order the merchandiser gave them; changing a date never reorders them
    exf = db.execute("SELECT name_en, name_ta FROM plan_steps WHERE code = 'EXF'").fetchone()
    items.append(TemplateItem("EXF", exf["name_en"], exf["name_ta"], "milestone", 0))
    if len(items) > MAX_STEPS:
        raise HttpError(400, f"A plan can have at most {MAX_STEPS} steps")
    return items


def _clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not 2 <= len(name) <= 60:
        raise HttpError(400, "Give the template a name of 2 to 60 characters")
    return name


def _write_steps(db: sqlite3.Connection, template_id: int, items: list[TemplateItem]) -> None:
    db.execute("DELETE FROM template_steps WHERE template_id = ?", (template_id,))
    db.executemany(
        "INSERT INTO template_steps (template_id, seq, code, end_offset, start_offset, after_code) VALUES (?,?,?,?,?,?)",
        [(template_id, n, i.code, i.end_offset, i.start_offset, i.after) for n, i in enumerate(items, start=1)],
    )


def create_template(db: sqlite3.Connection, name: str, steps: list[StepIn], user_id: int) -> int:
    name = _clean_name(name)
    try:
        with transaction(db):
            items = resolve_steps(db, steps, create=True)
            tid = db.execute(
                "INSERT INTO templates (key, name, created_by) VALUES (?,?,?)", (f"custom-{secrets.token_hex(4)}", name, user_id)
            ).lastrowid
            _write_steps(db, tid, items)
    except sqlite3.IntegrityError:
        raise HttpError(409, f"There is already a template called {name}")
    return tid


def update_template(db: sqlite3.Connection, template_id: int, name: str, steps: list[StepIn]) -> None:
    t = db.execute("SELECT builtin FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not t:
        raise HttpError(404, "Template not found")
    if t["builtin"]:
        raise HttpError(403, "Built-in templates can't be edited. Copy it and edit the copy.")
    name = _clean_name(name)
    try:
        with transaction(db):
            items = resolve_steps(db, steps, create=True)
            db.execute("UPDATE templates SET name = ?, updated_at = datetime('now') WHERE id = ?", (name, template_id))
            _write_steps(db, template_id, items)
    except sqlite3.IntegrityError:
        raise HttpError(409, f"There is already a template called {name}")


def set_active(db: sqlite3.Connection, template_id: int, active: bool) -> None:
    t = db.execute("SELECT builtin, name FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not t:
        raise HttpError(404, "Template not found")
    if t["builtin"]:
        raise HttpError(403, "Built-in templates can't be retired")
    try:
        db.execute("UPDATE templates SET active = ?, updated_at = datetime('now') WHERE id = ?", (int(active), template_id))
    except sqlite3.IntegrityError:
        raise HttpError(409, f"Another active template is already called {t['name']}. Rename one first.")


def delete_template(db: sqlite3.Connection, template_id: int) -> None:
    """Remove a template of your own. One that orders were made from is kept (retire it instead), so those orders stay explainable."""
    t = db.execute("SELECT key, builtin FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not t:
        raise HttpError(404, "Template not found")
    if t["builtin"]:
        raise HttpError(403, "Built-in templates can't be deleted")
    if db.execute("SELECT 1 FROM orders WHERE template_key = ? LIMIT 1", (t["key"],)).fetchone():
        raise HttpError(409, "Orders were made from this template, so it can't be deleted. Retire it instead and it will no longer be offered.")
    with transaction(db):
        db.execute("DELETE FROM templates WHERE id = ?", (template_id,))  # its steps go with it


def plan_json(db: sqlite3.Connection, t: Template, ex_factory: str) -> list[dict]:
    """The dated plan for the New order screen. `outsourced` = a subcontract unit exists for the step's process."""
    outsourced = {r["process"] for r in db.execute("SELECT process FROM units WHERE kind = 'subcontract' AND process IS NOT NULL")}
    planned: list[PlannedItem] = plan_from_template(CALENDAR, t, ex_factory)
    return [{**p.to_json(), "outsourced": p.item.process in outsourced} for p in planned]
