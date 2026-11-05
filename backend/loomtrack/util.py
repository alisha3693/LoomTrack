from __future__ import annotations

from .domain.calendar import to_date


def iso_week(iso: str) -> str:
    """ISO-8601 week label, e.g. '2026-W47'. Ship weeks are reported this way to EU/UK buyers."""
    year, week, _ = to_date(iso).isocalendar()
    return f"{year}-W{week:02d}"


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message
