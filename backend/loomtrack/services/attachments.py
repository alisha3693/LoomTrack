"""Design, pattern, print and fabric files on requests and orders.

Files are untrusted. The type is decided from the file's own first bytes (never the browser's claim or
the extension), only a short list of design-work formats is accepted, the stored name is random, and
nothing is ever executed or unpacked. Images and PDFs open in the browser; everything else downloads.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import UploadFile

from ..util import HttpError

MAX_BYTES = 15 * 1024 * 1024
MAX_PER_REQUEST = 10
MAX_PER_ORDER = 30
KINDS = ("design", "pattern", "print", "fabric", "other")

# (mime, extension, opens in the browser)
_JPEG, _PNG, _GIF, _WEBP = ("image/jpeg", ".jpg", True), ("image/png", ".png", True), ("image/gif", ".gif", True), ("image/webp", ".webp", True)
_PDF = ("application/pdf", ".pdf", True)  # also Illustrator .ai, which is a PDF underneath
_PSD = ("image/vnd.adobe.photoshop", ".psd", False)
_TIFF = ("image/tiff", ".tif", False)
_ZIP = ("application/zip", ".zip", False)  # tech-pack bundles, Excel and Word files; kept as an opaque download
_DXF = ("image/vnd.dxf", ".dxf", False)  # pattern files


def sniff(data: bytes) -> tuple[str, str, bool] | None:
    """The real type of an upload, or None if it is not one we accept."""
    if data.startswith(b"\xff\xd8\xff"):
        return _JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _PNG
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return _GIF
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _WEBP
    if data.startswith(b"%PDF-"):
        return _PDF
    if data.startswith(b"8BPS"):
        return _PSD
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return _TIFF
    if data.startswith(b"PK\x03\x04"):
        return _ZIP
    if re.match(rb"\s*0\s*\r?\nSECTION\b", data[:64]):
        return _DXF
    return None


def clean_filename(name: str | None, ext: str) -> str:
    """A safe display name: no folders, no control characters, bounded length."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]+", "", base).strip(" .")
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return (stem[:100] or "file") + ext


def _count(db: sqlite3.Connection, column: str, value: int | None) -> int:
    if value is None:
        return 0
    return db.execute(f"SELECT COUNT(*) FROM attachments WHERE {column} = ?", (value,)).fetchone()[0]  # column is ours, not input


async def store(
    db: sqlite3.Connection, upload_dir: Path, upload: UploadFile, *, kind: str, uploaded_by: str, user_id: int | None,
    request_id: int | None = None, order_id: int | None = None, buyer_visible: bool = False, supervisor_visible: bool = False,
) -> int:
    if kind not in KINDS:
        raise HttpError(400, "Say whether this is a design, pattern, print, fabric or other file")
    if request_id and _count(db, "request_id", request_id) >= MAX_PER_REQUEST:
        raise HttpError(409, f"A request can have at most {MAX_PER_REQUEST} files")
    if order_id and _count(db, "order_id", order_id) >= MAX_PER_ORDER:
        raise HttpError(409, f"An order can have at most {MAX_PER_ORDER} files")

    data = await upload.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HttpError(413, f"That file is over {MAX_BYTES // (1024 * 1024)} MB")
    if not data:
        raise HttpError(400, "That file is empty")
    kind_of = sniff(data)
    if kind_of is None:
        raise HttpError(400, "That file type is not accepted. Use PDF, image (JPG, PNG, WebP, GIF, TIFF), Photoshop, ZIP, Excel/Word or DXF files.")
    mime, ext, _ = kind_of

    dest = upload_dir / "attachments"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{int(time.time() * 1000)}-{secrets.token_hex(6)}{ext}"
    path.write_bytes(data)
    try:
        return db.execute(
            """INSERT INTO attachments (request_id, order_id, kind, filename, mime, size_bytes, sha256, path, uploaded_by, user_id, buyer_visible, supervisor_visible)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (request_id, order_id, kind, clean_filename(upload.filename, ext), mime, len(data), hashlib.sha256(data).hexdigest(), str(path),
             uploaded_by, user_id, int(buyer_visible or uploaded_by == "buyer"), int(supervisor_visible)),
        ).lastrowid
    except Exception:
        path.unlink(missing_ok=True)
        raise


def remove(db: sqlite3.Connection, attachment_id: int) -> None:
    row = db.execute("SELECT path FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    db.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    if row:
        Path(row["path"]).unlink(missing_ok=True)


def _item(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "kind": r["kind"], "filename": r["filename"], "mime": r["mime"], "size": r["size_bytes"],
        "uploadedBy": r["uploaded_by"], "at": r["created_at"],
    }


def for_office(db: sqlite3.Connection, *, request_id: int | None = None, order_id: int | None = None) -> list[dict]:
    """Everything on a request or order, with the visibility flags, for the merchandiser."""
    col, val = ("request_id", request_id) if request_id else ("order_id", order_id)
    return [
        {**_item(r), "buyerVisible": bool(r["buyer_visible"]), "supervisorVisible": bool(r["supervisor_visible"])}
        for r in db.execute(f"SELECT * FROM attachments WHERE {col} = ? ORDER BY id", (val,))
    ]


def for_buyer(db: sqlite3.Connection, buyer_id: int, *, request_id: int | None = None, order_id: int | None = None) -> list[dict]:
    """Only files this buyer may see: on their own request or order, and marked visible."""
    if request_id:
        rows = db.execute(
            """SELECT a.* FROM attachments a JOIN order_requests q ON q.id = a.request_id
               WHERE a.request_id = ? AND q.buyer_id = ? AND a.buyer_visible = 1 ORDER BY a.id""", (request_id, buyer_id))
    else:
        rows = db.execute(
            """SELECT a.* FROM attachments a JOIN orders o ON o.id = a.order_id
               WHERE a.order_id = ? AND o.buyer_id = ? AND a.buyer_visible = 1 ORDER BY a.id""", (order_id, buyer_id))
    return [{**_item(r), "uploadedBy": "you" if r["uploaded_by"] == "buyer" else "merchandiser"} for r in rows]


def for_supervisor(db: sqlite3.Connection, unit_id: int, order_id: int) -> list[dict]:
    """Files marked for the floor, on an order this supervisor's unit has a stage in."""
    return [
        _item(r)
        for r in db.execute(
            """SELECT a.* FROM attachments a WHERE a.order_id = ? AND a.supervisor_visible = 1
               AND EXISTS (SELECT 1 FROM milestones m WHERE m.order_id = a.order_id AND m.unit_id = ?) ORDER BY a.id""",
            (order_id, unit_id),
        )
    ]


def is_inline(mime: str) -> bool:
    return mime in {m for m, _, inline in (_JPEG, _PNG, _GIF, _WEBP, _PDF) if inline}
