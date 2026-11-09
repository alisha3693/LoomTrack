from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .domain.calendar import Calendar

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


def _load_env_file(path: Path) -> None:
    """Settings for email and WhatsApp may live in backend/.env (never committed). Real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file(BACKEND_ROOT / ".env")

DB_FILE = os.environ.get("LOOMTRACK_DB", str(BACKEND_ROOT / "data" / "loomtrack.db"))
UPLOAD_DIR = Path(os.environ.get("LOOMTRACK_UPLOADS", str(BACKEND_ROOT / "data" / "uploads")))
WEB_DIST = REPO_ROOT / "web" / "dist"
BACKUP_DIR = Path(os.environ.get("LOOMTRACK_BACKUPS", str(Path(DB_FILE).parent / "backups")))
LOG_DIR = Path(os.environ.get("LOOMTRACK_LOGS", str(Path(DB_FILE).parent / "logs")))


def backup_enabled() -> bool:
    """A copy of the database and the photos is made about once a day unless LOOMTRACK_BACKUP=off."""
    return os.environ.get("LOOMTRACK_BACKUP", "").strip().lower() not in ("off", "0", "no", "false")


def backup_keep() -> int:
    """How many daily copies of the database to keep (the older ones are deleted)."""
    try:
        return max(1, int(os.environ.get("LOOMTRACK_BACKUP_KEEP", "14")))
    except ValueError:
        return 14


def ai_enabled() -> bool:
    """Translation is on unless switched off; until the models are downloaded the keyword fallback is used."""
    return os.environ.get("LOOMTRACK_AI", "on") != "off"


def translate_device() -> str:
    """'auto' (the GPU when PyTorch can use one, else the CPU), 'cuda' or 'cpu'."""
    v = os.environ.get("LOOMTRACK_TRANSLATE_DEVICE", "auto").lower()
    return v if v in ("auto", "cuda", "cpu") else "auto"


def hf_token() -> str | None:
    """Hugging Face read token, only needed to download the translation models."""
    return os.environ.get("HF_TOKEN") or None


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


# --- Outside the app: email (SMTP) and WhatsApp (Meta Cloud API) -------------------------------------
# Read on every call so a change to the environment, or a test, takes effect at once. Nothing here is
# stored in the database, and no setting is ever sent to the browser.


def allow_reset() -> bool:
    """The "Reset test data" button exists only where this is switched on (a test machine, never the live site)."""
    return os.environ.get("LOOMTRACK_ALLOW_RESET", "").strip().lower() in ("1", "true", "yes")


def public_url() -> str:
    """Where the buyers open the app; used for the links in messages."""
    return os.environ.get("LOOMTRACK_PUBLIC_URL", "http://localhost:4000").rstrip("/")


def smtp_settings() -> dict | None:
    host, sender = os.environ.get("LOOMTRACK_SMTP_HOST"), os.environ.get("LOOMTRACK_SMTP_FROM")
    if not host or not sender:
        return None
    security = os.environ.get("LOOMTRACK_SMTP_SECURITY", "starttls").lower()  # starttls | ssl | none
    return {
        "host": host,
        "port": int(os.environ.get("LOOMTRACK_SMTP_PORT") or {"ssl": 465, "none": 25}.get(security, 587)),
        "user": os.environ.get("LOOMTRACK_SMTP_USER") or None,
        "password": os.environ.get("LOOMTRACK_SMTP_PASSWORD") or None,
        "from": sender,
        "security": security,
    }


def whatsapp_settings() -> dict | None:
    token, phone_id = os.environ.get("LOOMTRACK_WA_TOKEN"), os.environ.get("LOOMTRACK_WA_PHONE_ID")
    if not token or not phone_id:
        return None
    return {
        "token": token,
        "phone_id": phone_id,
        "version": os.environ.get("LOOMTRACK_WA_API_VERSION", "v21.0"),
        "language": os.environ.get("LOOMTRACK_WA_LANGUAGE", "en"),
        "verify_token": os.environ.get("LOOMTRACK_WA_VERIFY_TOKEN") or None,
        "app_secret": os.environ.get("LOOMTRACK_WA_APP_SECRET") or None,
    }


def weekly_schedule() -> tuple[int, int] | None:
    """(weekday, hour) when each buyer's weekly status email goes out, on the server's clock; None = switched off.
    Monday 08:00 unless LOOMTRACK_WEEKLY_DAY (mon..sun) and LOOMTRACK_WEEKLY_HOUR (0-23) say otherwise; LOOMTRACK_WEEKLY=off stops it."""
    if os.environ.get("LOOMTRACK_WEEKLY", "").strip().lower() in ("off", "0", "no", "false"):
        return None
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day = os.environ.get("LOOMTRACK_WEEKLY_DAY", "mon").strip().lower()[:3]
    try:
        hour = int(os.environ.get("LOOMTRACK_WEEKLY_HOUR", "8"))
    except ValueError:
        hour = 8
    return (days.index(day) if day in days else 0, min(max(hour, 0), 23))
