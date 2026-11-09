"""Backups of the database and the uploaded photos, voice notes and files.

The database is copied with SQLite's own online backup (safe while the app is running) into `daily-<date>-<time>.db`, checked,
and only then kept; the newest few are kept and older ones deleted. Uploaded files never change once saved (their names are
random), so they are mirrored: a file already in the copy is skipped, and nothing is ever deleted from the mirror.
The backup folder is on the same disk by default; point LOOMTRACK_BACKUPS at another drive, or a folder that is synced
elsewhere, so that losing the disk does not lose the copies as well.

Restore: stop the app, copy a `daily-*.db` over the database file (delete its `-wal` and `-shm` files), copy `uploads/` back, start the app.
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

PREFIX = "daily-"
EVERY_SECONDS = 24 * 3600


def snapshots(folder: Path) -> list[Path]:
    """The database copies in the folder, oldest first (the copy made before a reset has a different name and is left alone)."""
    return sorted(folder.glob(f"{PREFIX}*.db")) if folder.is_dir() else []


def last_backup_time(folder: Path) -> float | None:
    found = snapshots(folder)
    return found[-1].stat().st_mtime if found else None


def due(folder: Path, now: float | None = None) -> bool:
    last = last_backup_time(folder)
    return last is None or (time.time() if now is None else now) - last >= EVERY_SECONDS


def backup_database(db: sqlite3.Connection, folder: Path, keep: int, now: datetime | None = None) -> Path:
    """Copy the live database, check the copy, then drop the oldest copies beyond `keep`. Use from the thread that owns `db`."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{PREFIX}{(now or datetime.now()):%Y%m%d-%H%M%S}.db"
    part = target.with_name(target.name + ".part")
    copy = sqlite3.connect(part)
    try:
        db.backup(copy)
        verdict = copy.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copy.close()
    if verdict != "ok":
        part.unlink(missing_ok=True)
        raise RuntimeError(f"The backup copy failed its check: {verdict}")
    part.replace(target)
    for old in snapshots(folder)[:-keep]:
        old.unlink(missing_ok=True)
    return target


def mirror_uploads(source: Path, folder: Path) -> int:
    """Copy uploaded files that are not in the backup yet. Returns how many were copied. Does not touch the database."""
    if not source.is_dir():
        return 0
    dest_root = folder / "uploads"
    copied = 0
    for f in source.rglob("*"):
        if not f.is_file():
            continue
        dest = dest_root / f.relative_to(source)
        if dest.exists() and dest.stat().st_size == f.stat().st_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        shutil.copy2(f, part)
        part.replace(dest)
        copied += 1
    return copied


async def run_once(db: sqlite3.Connection, folder: Path, uploads: Path, keep: int) -> dict:
    target = backup_database(db, folder, keep)  # on the event loop: the connection belongs to it
    copied = await asyncio.to_thread(mirror_uploads, uploads, folder)  # plain files, safe off the loop
    return {"database": str(target), "files": copied}


async def run_forever(db: sqlite3.Connection, folder: Path, uploads: Path, keep: int, every: float = 900.0) -> None:
    """Back up when the newest copy is a day old (so also soon after a start-up that follows a long stop)."""
    while True:
        try:
            if due(folder):
                summary = await run_once(db, folder, uploads, keep)
                print(f"backup: {summary['database']} (+{summary['files']} files)")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # keep the loop alive; the next round tries again
            print(f"backup loop: {type(e).__name__}: {e}")
        await asyncio.sleep(every)
