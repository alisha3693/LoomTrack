"""Floor API: the supervisor's stages and the daily update."""

from __future__ import annotations

import re
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile

from ..ai.classifier import classify_by_keywords
from ..db import transaction
from ..deps import AppContext, User, ctx, supervisor
from ..domain.calendar import add_days
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
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a"}


@router.get("/orders")
async def my_stages(user: User = Depends(supervisor), c: AppContext = Depends(ctx)):
    """Active stages run by this supervisor's unit, minus finished ones and ones not due for a fortnight."""
    today = c.today()
    found = c.db.execute(
        """SELECT o.id AS order_id, o.order_no, o.po_no, o.style, o.colour, o.colour_hex, o.qty_total, o.ex_factory,
             m.id AS milestone_id, m.code, s.name_en, s.name_ta, m.planned_start, m.planned_date,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id), 0) AS done,
             COALESCE((SELECT SUM(qty) FROM daily_updates d WHERE d.milestone_id = m.id AND d.work_date = ?), 0) AS today_qty
           FROM milestones m JOIN orders o ON o.id = m.order_id JOIN plan_steps s ON s.code = m.code
           WHERE s.kind = 'stage' AND m.unit_id = ? AND o.state = 'active'
           ORDER BY o.ex_factory, m.seq""",
        (today, user.unit_id),
    ).fetchall()
    horizon = add_days(today, 14)
    stages = [dict(r) for r in found if r["done"] < r["qty_total"] and (r["planned_start"] <= horizon or r["done"] > 0)]
    return {"today": today, "stages": stages}


async def _save(upload: UploadFile | None, kind: str, dest: Path) -> tuple[str, str] | None:
    if upload is None or not upload.filename:
        return None
    mime = (upload.content_type or "").split(";")[0]
    if not mime.startswith(f"{kind}/"):
        raise HttpError(400, f"Expected a {kind} file, got {mime or 'unknown'}")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HttpError(413, "File too large")
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{int(time.time() * 1000)}-{secrets.token_hex(4)}{_EXT.get(mime, '')}"
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
    return {"ok": True}


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
