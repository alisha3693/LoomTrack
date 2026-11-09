"""FastAPI app. Run with: uvicorn loomtrack.main:create_app --factory --port 4000"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .ai import speech
from .ai.classifier import classify_note
from .db import open_db
from .deps import AppContext
from .edge import Edge, setup_logging
from .routes import accounts, attachments, auth, capacity as capacity_routes, flow, buyer, health, merchandiser, notifications, requests, supervisor, templates
from .services import backup, clock, delivery, weekly
from .util import HttpError


def _csp_for(dist: Path):
    """The Content-Security-Policy for the app's pages: scripts only from this server, plus the one small inline script in
    index.html (allowed by its hash, read from the built page and re-read when the page is rebuilt). The API docs page is left out."""
    cache: dict = {}

    def policy(path: str) -> str | None:
        if path.startswith(("/api/docs", "/api/openapi")):
            return None
        index = dist / "index.html"
        try:
            stamp = index.stat().st_mtime_ns
        except OSError:
            stamp = None
        if cache.get("stamp") != stamp or "value" not in cache:
            hashes = []
            if stamp is not None:
                for m in re.finditer(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", index.read_text(encoding="utf-8"), re.S):
                    hashes.append("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode() + "'")
            fonts = "https://fonts.googleapis.com https://fonts.gstatic.com"  # the service worker fetches the fonts too
            cache["stamp"] = stamp
            cache["value"] = "; ".join([
                "default-src 'self'", "script-src 'self' " + " ".join(hashes), "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com", "img-src 'self' data: blob:", "media-src 'self' blob:", f"connect-src 'self' {fonts}",
                "worker-src 'self'", "manifest-src 'self'", "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
            ]).replace("script-src 'self' ;", "script-src 'self';")
        return cache["value"]

    return policy


def create_app(db: sqlite3.Connection | None = None, **overrides) -> FastAPI:
    # The sender of email and WhatsApp runs beside the app, only for the real database (tests call deliver_pending themselves).
    send_in_background = overrides.get("deliver", db is None)
    if db is None:
        setup_logging(config.LOG_DIR)  # the real app logs to the console and a file; tests do not

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        c = app.state.ctx
        tasks = [asyncio.create_task(delivery.run_forever(c.db)), asyncio.create_task(weekly.run_forever(c.db))] if send_in_background else []
        if send_in_background and config.backup_enabled():
            tasks.append(asyncio.create_task(backup.run_forever(c.db, c.backup_dir, c.upload_dir, config.backup_keep())))
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(title="LoomTrack", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None, lifespan=lifespan)
    database = db if db is not None else open_db(config.DB_FILE)
    app.state.ctx = AppContext(
        db=database,
        today=overrides.get("today") or (lambda: clock.today(database)),
        classify=overrides.get("classify", classify_note),
        upload_dir=Path(overrides.get("upload_dir", config.UPLOAD_DIR)),
        transcribe=overrides.get("transcribe", speech.to_text),
        backup_dir=Path(overrides.get("backup_dir", config.BACKUP_DIR)),
    )

    # Every error is {"error": "..."} so the client has one shape to show.
    @app.exception_handler(HttpError)
    async def _http_error(_: Request, e: HttpError):
        return JSONResponse({"error": e.message}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        parts = [f"{'.'.join(str(x) for x in err['loc'][1:]) or 'input'}: {err['msg']}" for err in e.errors()]
        return JSONResponse({"error": "; ".join(parts)}, status_code=400)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, e: Exception):
        # The traceback is in the log under the same number; the person sees only the number.
        rid = request.scope.get("state", {}).get("request_id", "")
        return JSONResponse({"error": f"Something went wrong on our side. Quote {rid} if you ask for help."}, status_code=500)

    @app.exception_handler(StarletteHTTPException)
    async def _starlette(_: Request, e: StarletteHTTPException):
        return JSONResponse({"error": "No such endpoint" if e.status_code == 404 else str(e.detail)}, status_code=e.status_code)

    for r in (health.router, auth.router, accounts.router, merchandiser.router, capacity_routes.router, templates.router, requests.office_router, requests.order_router, supervisor.router, buyer.router,
              requests.buyer_router, requests.buyer_orders_router, flow.buyer_router, flow.office_router, notifications.router, notifications.webhook_router,
              attachments.buyer_router, attachments.office_router, attachments.supervisor_router, attachments.media_router):
        app.include_router(r)

    # Built web app (production): static assets plus SPA fallback.
    dist = config.WEB_DIST
    app.add_middleware(Edge, csp=_csp_for(dist))
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"error": "No such endpoint"}, status_code=404)
            f = dist / path
            hit = path and f.is_file() and dist in f.resolve().parents
            # Hashed files under /assets never change; the page, the service worker and the manifest must be re-checked every time.
            headers = None if path.startswith("assets/") else {"Cache-Control": "no-cache"}
            return FileResponse(f if hit else dist / "index.html", headers=headers)

    return app

