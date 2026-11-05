"""Working-day calendar.

Dates are ISO 'YYYY-MM-DD' strings at every boundary (DB, JSON, engine), so
they compare correctly as strings and never shift with the server time zone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


def to_date(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def add_days(iso: str, n: int) -> str:
    return (to_date(iso) + timedelta(days=n)).isoformat()


@dataclass(frozen=True)
class Calendar:
    """Tiruppur units work Monday–Saturday; Sunday and listed holidays are off."""

    holidays: frozenset[str] = field(default_factory=frozenset)

    def is_working_day(self, iso: str) -> bool:
        return to_date(iso).weekday() != 6 and iso not in self.holidays

    def next_working_day(self, iso: str) -> str:
        d = add_days(iso, 1)
        while not self.is_working_day(d):
            d = add_days(d, 1)
        return d

    def prev_working_day(self, iso: str) -> str:
        d = add_days(iso, -1)
        while not self.is_working_day(d):
            d = add_days(d, -1)
        return d

    def snap_back(self, iso: str) -> str:
        """Same day if it is a working day, otherwise the working day before it."""
        return iso if self.is_working_day(iso) else self.prev_working_day(iso)

    def add_working_days(self, iso: str, n: int) -> str:
        """Move forward n working days (the start day itself is not counted)."""
        d = iso
        for _ in range(n):
            d = self.next_working_day(d)
        return d

    def shift_working_days(self, iso: str, n: int) -> str:
        """Like add_working_days, but n may be negative."""
        d = iso
        for _ in range(abs(n)):
            d = self.next_working_day(d) if n > 0 else self.prev_working_day(d)
        return d

    def count_working_days(self, start: str, end: str) -> int:
        """Working days in [start, end], both inclusive. 0 when end < start."""
        if end < start:
            return 0
        n, d = 0, start
        while d <= end:
            if self.is_working_day(d):
                n += 1
            d = add_days(d, 1)
        return n

    def working_day_diff(self, a: str, b: str) -> int:
        """Signed working days from a to b: positive when b is later."""
        if a == b:
            return 0
        if b > a:
            return self.count_working_days(add_days(a, 1), b)
        return -self.count_working_days(add_days(b, 1), a)
