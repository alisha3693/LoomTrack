from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .domain.calendar import Calendar

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

DB_FILE = os.environ.get("LOOMTRACK_DB", str(BACKEND_ROOT / "data" / "loomtrack.db"))
UPLOAD_DIR = Path(os.environ.get("LOOMTRACK_UPLOADS", str(BACKEND_ROOT / "data" / "uploads")))
WEB_DIST = REPO_ROOT / "web" / "dist"
# Local, free, open-source model served by Ollama (https://ollama.com).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def ai_enabled() -> bool:
    """AI is on unless switched off; if Ollama is down the keyword fallback takes over."""
    return os.environ.get("LOOMTRACK_AI", "on") != "off"


# Public holidays observed by the units (Tamil Nadu, 2026 season). Editable list.
CALENDAR = Calendar(
    frozenset(
        {
            "2026-10-20",  # Ayudha Puja
            "2026-11-08",  # Deepavali
            "2027-01-15",  # Pongal
            "2027-01-16",  # Mattu Pongal
        }
    )
)


def today() -> str:
    """Today's date in IST, overridable for demos and tests."""
    return os.environ.get("LOOMTRACK_TODAY") or datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
