"""What happens to every request on its way in and out: a request number, the security headers, and one log line.

The log line is JSON, one per request: when, the request number, method, path, status, how long it took in milliseconds and
the caller's address. It never holds a request body, a query string (signed media links carry their signature there), a
password or a session, and the private link inside `/b/<link>` is replaced. It goes to the console and to
`data/logs/access.log` (5 MB files, the last 5 kept). Errors that were not handled are logged with their traceback.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("loomtrack.access")

SLOW_MS = 1000
_LINK = re.compile(r"/b/[A-Za-z0-9_-]{20,}")
_QUIET = ("/assets/", "/api/health")  # frequent and uninteresting: not logged unless they fail

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",  # the private buyer link is in the address; it must not travel to other sites
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def setup_logging(folder: Path) -> None:
    """Send the access log to the console and a rotating file. Safe to call twice."""
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    log.propagate = False
    plain = logging.Formatter("%(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(plain)
    log.addHandler(console)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        files = RotatingFileHandler(folder / "access.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        files.setFormatter(plain)
        log.addHandler(files)
    except OSError as e:  # a log folder that cannot be written must not stop the app
        print(f"access log file not available: {e}")


def _address(scope: Scope) -> str:
    headers = {k: v for k, v in scope.get("headers", [])}
    peer = (scope.get("client") or ("unknown", 0))[0]
    if peer in ("127.0.0.1", "::1"):
        passed = headers.get(b"cf-connecting-ip", b"").decode() or headers.get(b"x-forwarded-for", b"").decode().split(",")[0].strip()
        if passed:
            return passed[:64]
    return peer


class Edge:
    """Pure ASGI middleware (not BaseHTTPMiddleware), so file downloads and background tasks behave as they do without it."""

    def __init__(self, app: ASGIApp, csp: Callable[[str], str | None] = lambda path: None):
        self.app = app
        self.csp = csp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id
        path = scope["path"]
        status = 500
        secure = scope.get("scheme") == "https"

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                policy = self.csp(path)
                if policy:
                    headers.setdefault("Content-Security-Policy", policy)
                if secure:
                    headers.setdefault("Strict-Transport-Security", "max-age=15552000")
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            status = 500
            log.error(self._line(scope, request_id, status, started), exc_info=True)
            raise
        else:
            ms = (time.perf_counter() - started) * 1000
            if status >= 500 or ms >= SLOW_MS or not path.startswith(_QUIET):
                log.log(logging.ERROR if status >= 500 else logging.WARNING if ms >= SLOW_MS else logging.INFO,
                        self._line(scope, request_id, status, started))

    @staticmethod
    def _line(scope: Scope, request_id: str, status: int, started: float) -> str:
        return json.dumps({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": request_id,
            "method": scope["method"],
            "path": _LINK.sub("/b/<link>", scope["path"]),
            "status": status,
            "ms": round((time.perf_counter() - started) * 1000),
            "ip": _address(scope),
        }, ensure_ascii=False)
