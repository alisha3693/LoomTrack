"""Floor API: the supervisor's stages and the daily update."""

from __future__ import annotations

import re
import secrets
import time
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile

from ..ai.classifier import classify_by_keywords
from ..db import transaction
from ..deps import AppContext, User, ctx, supervisor
from ..config import CALENDAR
from ..domain.calendar import add_days
from .. import config
from ..domain.reasons import REASON_LABEL_EN
from ..services import clock, notify
from ..services.orders import refresh_order
from ..util import HttpError

router = APIRouter(prefix="/api/s")

# How far back an offline-queued update may be dated.
MAX_BACKDATE_DAYS = 7
# Cut/knit allowance: cumulative output may exceed order qty by this much.
OVER_QTY_ALLOWANCE = 0.05
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _upstream(db, milestone_id: int, order_id: int) -> dict | None:
    """The stage just before this one that our own units do, and how much of the order it has finished.
    Job work (printing, washing) is not entered here, so it is skipped: stitching follows cutting, not the printer."""
    rows = db.execute(
        """SELECT m.id, m.seq, s.name_en, s.name_ta,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS done
           FROM milestones m JOIN plan_steps s ON s.code = m.code JOIN units u ON u.id = m.unit_id
           WHERE m.order_id = ? AND s.kind = 'stage' AND u.kind = 'own' ORDER BY m.seq""",
        (order_id,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if milestone_id not in ids or ids.index(milestone_id) == 0:
        return None
    return dict(rows[ids.index(milestone_id) - 1])


def _waiting_on(db, order_id: int, stage_seq: int) -> list[dict]:
    """What the office has not marked done that comes before this stage in the plan: every checkpoint (approvals,
    fabric, trims, inspection) and every job-work step (printing, washing) ahead of it in the template's order.
    The stage's task starts when the merchandiser has marked all of them done."""
    return [
        dict(r) for r in db.execute(
            """SELECT s.name_en, s.name_ta FROM milestones m JOIN plan_steps s ON s.code = m.code LEFT JOIN units u ON u.id = m.unit_id
               WHERE m.order_id = ? AND m.actual_date IS NULL AND m.code NOT IN ('EXF', 'FINAL')
                 AND m.seq < ? AND (s.kind = 'milestone' OR u.kind = 'subcontract')
               ORDER BY m.seq""",
            (order_id, stage_seq),
        )
    ]


def _target(today: str, planned_date: str, remaining: int) -> int:
    """Pieces a day to finish on plan: what is left over the working days left, today included."""
    days = CALENDAR.count_working_days(today, planned_date) if planned_date >= today else 0
    return remaining if days <= 1 else -(-remaining // days)


class ClockIn(BaseModel):
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.get("/clock")
async def get_clock(user: User = Depends(supervisor), c: AppContext = Depends(ctx)):
    """The date the app is using, and, on a test machine, whether it has been set by hand."""
    return {"allowed": config.allow_reset(), "today": c.today(), "testDate": clock.test_date(c.db), "realToday": config.today()}


@router.put("/clock")
async def set_clock(body: ClockIn, user: User = Depends(supervisor), c: AppContext = Depends(ctx)):
    if not config.allow_reset():
        raise HttpError(404, "No such endpoint")
    if body.date:
        try:
            when = date.fromisoformat(body.date)
        except ValueError:
            raise HttpError(400, "That is not a date")
        if abs((when - date.fromisoformat(config.today())).days) > 800:
            raise HttpError(400, "Pick a date within about two years of today")
    clock.set_test_date(c.db, body.date)
    return {"ok": True, "today": c.today(), "testDate": clock.test_date(c.db)}


@router.get("/orders")
async def my_stages(user: User = Depends(supervisor), c: AppContext = Depends(ctx)):
    """What this supervisor's unit has to work on today: stages that are due to be worked by now, that the office has
    unlocked, and that have pieces ready from the stage before. A locked or not-yet-due stage is not shown at all."""
    today = c.today()
    found = c.db.execute(
        """SELECT o.id AS order_id, o.order_no, o.po_no, o.style, o.colour, o.colour_hex, o.qty_total, o.ex_factory,
             m.id AS milestone_id, m.seq, m.code, s.name_en, s.name_ta, m.planned_start, m.planned_date,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS done,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id AND d.work_date = ?), 0) AS today_qty
           FROM milestones m JOIN orders o ON o.id = m.order_id JOIN plan_steps s ON s.code = m.code
           WHERE s.kind = 'stage' AND m.unit_id = ? AND o.state = 'active'
           ORDER BY o.ex_factory, m.seq""",
        (today, user.unit_id),
    ).fetchall()
    stages = []
    for r in found:
        if r["done"] >= r["qty_total"] or (r["planned_start"] > today and r["done"] == 0):
            continue  # finished, or not due to be worked yet
        st = dict(r)
        # Fixed for the day: worked out from what was left when today began, so entering pieces does not move it.
        st["target_per_day"] = _target(today, r["planned_date"], r["qty_total"] - r["done"] + r["today_qty"])
        up = _upstream(c.db, r["milestone_id"], r["order_id"])
        # What the stage before has handed over and not yet been worked on here. None when this is the first stage.
        st["upstream_name_en"], st["upstream_name_ta"] = (up["name_en"], up["name_ta"]) if up else (None, None)
        st["ready"] = max(0, up["done"] - r["done"]) if up else None
        # Once a stage has output it is never locked again, even if the office later unmarks a step.
        waiting = _waiting_on(c.db, r["order_id"], r["seq"]) if r["done"] == 0 else []
        st["waiting_on_en"], st["waiting_on_ta"] = [w["name_en"] for w in waiting], [w["name_ta"] for w in waiting]
        if waiting:
            continue  # the office has not unlocked it: the supervisor does not see it
        if st["ready"] is not None and st["ready"] <= 0:
            continue  # nothing has come from the stage before, so there is nothing to work on
        stages.append(st)
    return {"today": today, "stages": stages}


def sniff_media(data: bytes) -> tuple[str, str, str] | None:
    """(kind, mime, extension) read from a file's own first bytes, or None. What the phone claims is never trusted:
    the type that is stored, served and named comes from here."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png", ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp", ".webp"
    if data.startswith(b"\x1a\x45\xdf\xa3"):  # the Matroska/WebM container Chrome and Firefox record in
        return "audio", "audio/webm", ".webm"
    if data.startswith(b"OggS"):
        return "audio", "audio/ogg", ".ogg"
    if data[4:8] == b"ftyp":  # MP4 audio, what Safari on iPhone records
        return "audio", "audio/mp4", ".m4a"
    return None


async def _save(upload: UploadFile | None, kind: str, dest: Path) -> tuple[str, str] | None:
    if upload is None or not upload.filename:
        return None
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HttpError(413, "File too large")
    found = sniff_media(data)
    if found is None or found[0] != kind:
        raise HttpError(400, f"That is not a {'photo' if kind == 'image' else 'voice note'} the app can use")
    _, mime, ext = found
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{int(time.time() * 1000)}-{secrets.token_hex(4)}{ext}"
    path.write_bytes(data)
    return str(path), mime


@router.post("/updates", status_code=201)
async def post_update(
    response: Response,
    background: BackgroundTasks,
    id: str = Form(...),
    milestoneId: int = Form(...),
    workDate: str = Form(...),
    qty: int = Form(..., ge=0),
    noteText: str = Form("", max_length=1000),
    noteSource: str | None = Form(None),
    createdAt: str | None = Form(None, max_length=40),
    photo: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    user: User = Depends(supervisor),
    c: AppContext = Depends(ctx),
):
    db, today = c.db, c.today()
    if not _ID.match(id) or not _DATE.match(workDate):
        raise HttpError(400, "Malformed update")

    # Retried send from the offline queue: already have it, say so.
    if db.execute("SELECT 1 FROM daily_updates WHERE id = ?", (id,)).fetchone():
        response.status_code = 200
        return {"ok": True, "duplicate": True}

    stage = db.execute(
        """SELECT m.id, m.order_id, m.unit_id, s.kind, o.qty_total, o.state,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS done
           FROM milestones m JOIN orders o ON o.id = m.order_id JOIN plan_steps s ON s.code = m.code WHERE m.id = ?""",
        (milestoneId,),
    ).fetchone()
    if not stage or stage["kind"] != "stage":
        raise HttpError(404, "Stage not found")
    if stage["unit_id"] != user.unit_id:
        raise HttpError(403, "This stage is not run by your unit")
    if stage["state"] != "active":
        raise HttpError(409, "Order is not active")
    if workDate > today:
        raise HttpError(400, "Work date is in the future")
    if workDate < add_days(today, -MAX_BACKDATE_DAYS):
        raise HttpError(400, "Work date is too old")
    if stage["done"] == 0:
        mine = db.execute("SELECT planned_start, seq FROM milestones WHERE id = ?", (stage["id"],)).fetchone()
        waiting = _waiting_on(db, stage["order_id"], mine["seq"])
        if waiting:
            raise HttpError(409, "Waiting for the office to mark done: " + ", ".join(w["name_en"] for w in waiting))
    up = _upstream(db, stage["id"], stage["order_id"])
    if up and stage["done"] + qty > up["done"]:
        raise HttpError(422, f"{up['name_en']} has finished {up['done']} so far, so this stage can have at most {up['done']} (it would be {stage['done'] + qty})")
    cap = int(stage["qty_total"] * (1 + OVER_QTY_ALLOWANCE))
    if stage["done"] + qty > cap:
        raise HttpError(422, f"Total would be {stage['done'] + qty}, more than the order quantity {stage['qty_total']}")

    saved_photo = await _save(photo, "image", c.upload_dir)
    saved_audio = await _save(audio, "audio", c.upload_dir)
    note = noteText.strip()
    source = (noteSource if noteSource in ("text", "voice") else ("voice" if saved_audio else "text")) if (note or saved_audio) else None

    try:
        with transaction(db):
            db.execute(
                """INSERT INTO daily_updates (id, milestone_id, user_id, work_date, qty, note_text, note_source, audio_path, created_at_client)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (id, stage["id"], user.id, workDate, qty, note or None, source, saved_audio[0] if saved_audio else None, createdAt),
            )
            if saved_photo:
                db.execute("INSERT INTO photos (update_id, path, mime) VALUES (?,?,?)", (id, *saved_photo))
            if note or saved_audio:
                db.execute("INSERT INTO issue_reasons (update_id) VALUES (?)", (id,))
    except Exception:
        for f in (saved_photo, saved_audio):
            if f:
                Path(f[0]).unlink(missing_ok=True)
        raise

    refresh_order(db, stage["order_id"], today)
    if note:
        # Classification takes a few seconds on the local model; the phone doesn't wait for it.
        background.add_task(classify_in_background, c, id, note, stage["order_id"])
    elif saved_audio:
        # A voice note with no typed words: write it out on this machine first, then it is read like a typed one.
        background.add_task(transcribe_in_background, c, id, saved_audio[0], stage["order_id"])
    return {"ok": True}


async def transcribe_in_background(c: AppContext, update_id: str, path: str, order_id: int) -> None:
    try:
        text = await c.transcribe(path)
    except Exception:  # no model, or the recording could not be read: it stays a recording to listen to
        return
    if not text:
        return
    c.db.execute("UPDATE daily_updates SET note_text = ?, note_source = 'voice' WHERE id = ? AND note_text IS NULL", (text, update_id))
    await classify_in_background(c, update_id, text, order_id)


async def classify_in_background(c: AppContext, update_id: str, note: str, order_id: int) -> None:
    try:
        r = await c.classify(note)
        error = None
    except Exception as e:  # local model down or returned junk: keywords give a first guess
        r = classify_by_keywords(note)
        error = str(e)[:300] or type(e).__name__
    # Never overwrite a category a merchandiser has already set by hand.
    c.db.execute(
        """UPDATE issue_reasons SET ai_category = ?, ai_translation = ?, ai_confidence = ?, ai_source = ?, ai_error = ?,
             final_category = CASE WHEN changed_by IS NULL THEN ? ELSE final_category END, classified_at = datetime('now')
           WHERE update_id = ?""",
        (r.category, r.translation, r.confidence, r.source, error, r.category, update_id),
    )
    # The reason feeds the suggested buyer message on any pending warning.
    refresh_order(c.db, order_id, c.today())
    if r.category != "NO_ISSUE":
        _tell_the_office(c, update_id, note, r)


def _tell_the_office(c: AppContext, update_id: str, note: str, r) -> None:
    """Put the supervisor's reason in the merchandisers' notifications as soon as it is understood."""
    row = c.db.execute(
        """SELECT o.id, o.buyer_id, o.po_no, s.name_en FROM daily_updates d JOIN milestones m ON m.id = d.milestone_id
           JOIN orders o ON o.id = m.order_id JOIN plan_steps s ON s.code = m.code WHERE d.id = ?""",
        (update_id,),
    ).fetchone()
    if row is None:
        return
    said = r.translation or note
    text = f"{REASON_LABEL_EN.get(r.category, r.category)}\n\n{said}" + (f"\n\nHis words: {note}" if r.translation else "")
    notify.send(c.db, "supervisor_reported", row["buyer_id"], row["id"], po=row["po_no"], stage=row["name_en"],
                reason=REASON_LABEL_EN.get(r.category, r.category).lower(), text=text)
