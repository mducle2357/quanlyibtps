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


def weeks_in_month(y: int, m: int) -> int:
    from math import ceil

    return ceil(days_in_month(y, m) / 7)


def week_key_month(week_key: str) -> str:
    """'2025-11-W2' -> '2025-11'."""
    return week_key.rsplit("-W", 1)[0]


def week_key_index(week_key: str) -> int:
    return int(week_key.rsplit("-W", 1)[1])


def is_valid_week_key(key: str) -> bool:
    try:
        ym, w = key.rsplit("-W", 1)
        y, m = ym_parse(ym)
        w = int(w)
        return 1 <= m <= 12 and 1 <= w <= weeks_in_month(y, m)
    except (ValueError, AttributeError, IndexError):
        return False


def current_week_key(today: date) -> str:
    from math import ceil

    ym = ym_of(today)
    w = min(ceil(today.day / 7), weeks_in_month(today.year, today.month))
    return f"{ym}-W{w}"


def all_week_keys(start_ym: str, end_ym: str) -> list[str]:
    out = []
    n = ym_diff(start_ym, end_ym)
    for i in range(n + 1):
        ym = ym_add(start_ym, i)
        y, m = ym_parse(ym)
        for w in range(1, weeks_in_month(y, m) + 1):
            out.append(f"{ym}-W{w}")
    return out
