"""Month-key (YYYY-MM) helpers shared by every timeline-based module (prompt §9)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date


def ym_parse(key: str) -> tuple[int, int]:
    y, m = key.split("-")
    return int(y), int(m)


def ym_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def ym_add(key: str, n: int) -> str:
    y, m = ym_parse(key)
    total = y * 12 + (m - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def ym_diff(a: str, b: str) -> int:
    ay, am = ym_parse(a)
    by, bm = ym_parse(b)
    return (by * 12 + bm) - (ay * 12 + am)


def days_in_month(y: int, m: int) -> int:
    return monthrange(y, m)[1]


def month_first(key: str) -> date:
    y, m = ym_parse(key)
    return date(y, m, 1)


def month_last(key: str) -> date:
    y, m = ym_parse(key)
    return date(y, m, days_in_month(y, m))


def day_diff(a: date, b: date) -> int:
    return (b - a).days


def is_valid_month_key(key: str) -> bool:
    try:
        y, m = ym_parse(key)
        return 1 <= m <= 12 and 1900 <= y <= 3000
    except (ValueError, AttributeError):
        return False
