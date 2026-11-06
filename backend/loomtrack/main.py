"""FastAPI app. Run with: uvicorn loomtrack.main:create_app --factory --port 4000"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .ai.classifier import classify_note
from .db import open_db
from .deps import AppContext
from .routes import attachments, auth, buyer, merchandiser, requests, supervisor, templates
from .util import HttpError


def create_app(db: sqlite3.Connection | None = None, **overrides) -> FastAPI:
    app = FastAPI(title="LoomTrack", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.ctx = AppContext(
        db=db if db is not None else open_db(config.DB_FILE),
        today=overrides.get("today", config.today),
        classify=overrides.get("classify", classify_note),
        upload_dir=Path(overrides.get("upload_dir", config.UPLOAD_DIR)),
    )

    # Every error is {"error": "..."} so the client has one shape to show.
    @app.exception_handler(HttpError)
    async def _http_error(_: Request, e: HttpError):
        return JSONResponse({"error": e.message}, status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        parts = [f"{'.'.join(str(x) for x in err['loc'][1:]) or 'input'}: {err['msg']}" for err in e.errors()]
        return JSONResponse({"error": "; ".join(parts)}, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _starlette(_: Request, e: StarletteHTTPException):
        return JSONResponse({"error": "No such endpoint" if e.status_code == 404 else str(e.detail)}, status_code=e.status_code)

    for r in (auth.router, merchandiser.router, templates.router, requests.office_router, supervisor.router, buyer.router, requests.buyer_router,
              attachments.buyer_router, attachments.office_router, attachments.supervisor_router, attachments.media_router):
        app.include_router(r)

    # Built web app (production): static assets plus SPA fallback.
    dist = config.WEB_DIST
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"error": "No such endpoint"}, status_code=404)
            f = dist / path
            return FileResponse(f if path and f.is_file() and dist in f.resolve().parents else dist / "index.html")

    return app

