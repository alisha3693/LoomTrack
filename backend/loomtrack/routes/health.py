"""A check an uptime monitor can call: is the database there, can files be saved, are the language models loaded."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..ai import speech, translate
from ..db import SCHEMA_VERSION
from ..deps import AppContext, ctx
from ..services import backup

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(c: AppContext = Depends(ctx)):
    """200 when the app can do its job, 503 when it cannot. Says nothing about people or orders.
    A missing translation or speech model is not a failure: the app falls back to keyword matching and to keeping the recording."""
    try:
        c.db.execute("SELECT 1").fetchone()
        database = "ok"
    except Exception:
        database = "unreachable"
    folder = c.upload_dir if c.upload_dir.exists() else c.upload_dir.parent
    uploads = "ok" if os.access(folder, os.W_OK) else "not writable"
    last = backup.last_backup_time(c.backup_dir) if c.backup_dir else None
    body = {
        "ok": database == "ok" and uploads == "ok",
        "database": database,
        "uploads": uploads,
        "schema": SCHEMA_VERSION,
        "translation": translate.status()["mode"],
        "speech": speech.status()["mode"],
        "lastBackup": datetime.fromtimestamp(last, timezone.utc).isoformat() if last else None,
    }
    return JSONResponse(body, status_code=200 if body["ok"] else 503, headers={"Cache-Control": "no-store"})
