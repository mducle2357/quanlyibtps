"""Pure calculation engine — ported 1:1 from the approved prototype's JS engine
(see docs/reference-prototype.html, sections 3–5 of the prototype's own comments)
so behaviour matches what the business has already reviewed. No I/O here: every
function takes plain values/dataclasses and returns plain values, which is what
makes the 17 acceptance tests in tests/test_calc_engine.py exercise it directly
without a database.

Percentages are stored and passed around as the number the user typed (12 means
12%, not 0.12) — prompt §7. Division by 100 happens only where an amount is
actually derived from a rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.dates import day_diff, days_in_month, month_first, month_last, ym_diff, ym_parse

RATE_FIXED = "fixed"
RATE_FLOATING = "floating"
RATE_COMBINED = "combined"
RATE_CONDITIONAL = "conditional"

METHOD_ONCE = "once"
METHOD_ACTUAL = "actual"
METHOD_FLAT = "flat"

FEE_BASE_ADVISED = "advised"
FEE_BASE_INVESTED = "invested"
FEE_BASE_OUTSTANDING = "outstanding"

FEE_DEFS = [
    {"key": "advisory", "base": FEE_BASE_ADVISED, "methods": [METHOD_ONCE]},
    {"key": "issuing", "base": FEE_BASE_ADVISED, "methods": [METHOD_ONCE]},
    {"key": "custody", "base": FEE_BASE_OUTSTANDING, "methods": [METHOD_ACTUAL, METHOD_FLAT]},
    {"key": "nshtp", "base": FEE_BASE_OUTSTANDING, "methods": [METHOD_ACTUAL, METHOD_FLAT]},
    {"key": "collateral", "base": FEE_BASE_OUTSTANDING, "methods": [METHOD_ACTUAL, METHOD_FLAT]},
    {"key": "other", "base": FEE_BASE_INVESTED, "methods": [METHOD_ONCE]},
]


def num(v: float | None) -> float:
    return 0.0 if v is None else float(v)


# --------------------------------------------------------------------------- #
# Reference rate resolution (prompt §17)
# --------------------------------------------------------------------------- #


@dataclass
class RefRateDef:
    id: str
    rate_type: str  # "manual" | "calculated"
    calc_method: str | None  # "average" | "min" | "max"
    monthly_values: dict[str, float]  # month_key -> rate
    component_ids: list[str] = field(default_factory=list)


class ReferenceRateResolver:
    """Resolves a benchmark's value at a given month, recursing into calculated
    rates' components and refusing to loop forever on a circular definition."""

    def __init__(self, rates: dict[str, RefRateDef]):
        self._rates = rates

    def value(self, rate_id: str | None, ym: str, _seen: frozenset[str] = frozenset()) -> float | None:
        if rate_id is None or rate_id in _seen:
            return None
        r = self._rates.get(rate_id)
        if r is None:
            return None
        if r.rate_type == "calculated":
            seen2 = _seen | {rate_id}
            vals = [v for cid in r.component_ids if (v := self.value(cid, ym, seen2)) is not None]
            if not vals:
                return None
            if r.calc_method == "min":
                return min(vals)
            if r.calc_method == "max":
                return max(vals)
            return sum(vals) / len(vals)
        return r.monthly_values.get(ym)

    def would_cycle(self, rate_id: str, new_component_id: str) -> bool:
        if rate_id == new_component_id:
            return True

        def visit(cid: str, seen: set[str]) -> bool:
            if cid == rate_id:
                return True
            if cid in seen:
                return False
            seen.add(cid)
            r = self._rates.get(cid)
            if not r or r.rate_type != "calculated":
                return False
            return any(visit(c, seen) for c in r.component_ids)

        return visit(new_component_id, set())


# --------------------------------------------------------------------------- #
# Bond lifecycle & coupon (prompt §10, §11)
# --------------------------------------------------------------------------- #


@dataclass
class BondInfo:
    issue_date: date | None
    maturity_date: date | None
    first_fee_date: date | None
    pay_freq_months: int
    par_value: float


@dataclass
class RateConfig:
    rate_type: str
    fixed_rate: float | None = None
    spread: float | None = None
    reference_rate_id: str | None = None
    first4_rate: float | None = None
    floor_rate: float | None = None
    cap_rate: float | None = None


def bond_active_month(info: BondInfo, ym: str) -> bool:
    if info.issue_date and ym_diff(f"{info.issue_date.year:04d}-{info.issue_date.month:02d}", ym) < 0:
        return False
    if info.maturity_date and ym_diff(f"{info.maturity_date.year:04d}-{info.maturity_date.month:02d}", ym) > 0:
        return False
    return True


def bond_status(info: BondInfo, today: date) -> tuple[str, str]:
    if info.issue_date and today < info.issue_date:
        return "pre", "Pre-Issuance"
    if info.maturity_date and today > info.maturity_date:
        return "matured", "Matured"
    return "active", "Active"


def coupon_period(info: BondInfo, ym: str) -> int | None:
    """1-based index of the interest-payment period containing month `ym`."""
    if not info.issue_date or info.pay_freq_months <= 0:
        return None
    iy = f"{info.issue_date.year:04d}-{info.issue_date.month:02d}"
    d = ym_diff(iy, ym)
    if d < 0:
        return None
    return d // info.pay_freq_months + 1


def bond_coupon(info: BondInfo, rate: RateConfig, resolver: ReferenceRateResolver, ym: str) -> float | None:
    """Returns None (not 0) when a required input is missing — the caller must
    not silently treat that as a zero rate (prompt §12.2, §23)."""
    if rate.rate_type == RATE_FIXED:
        return rate.fixed_rate

    ref = resolver.value(rate.reference_rate_id, ym) if rate.reference_rate_id else None

    if rate.rate_type == RATE_FLOATING:
        if ref is None or rate.spread is None:
            return None
        return rate.spread + ref

    period = coupon_period(info, ym)
    if rate.rate_type in (RATE_COMBINED, RATE_CONDITIONAL):
        if period is not None and period <= 4:
            return rate.first4_rate
        if ref is None or rate.spread is None:
            return None
        raw = rate.spread + ref
        if rate.rate_type == RATE_COMBINED:
            return raw
        value = raw
        if rate.cap_rate is not None:
            value = min(value, rate.cap_rate)
        if rate.floor_rate is not None:
            value = max(value, rate.floor_rate)
        return value

    return None


def validate_rate_config(rate: RateConfig) -> str | None:
    """Returns a human-readable error, or None if valid (prompt §11.4, §23)."""
    if rate.rate_type == RATE_CONDITIONAL and rate.floor_rate is not None and rate.cap_rate is not None:
        if rate.floor_rate > rate.cap_rate:
            return "Không dưới (Floor) không được lớn hơn Không quá (Cap)."
    return None


# --------------------------------------------------------------------------- #
# Fee schedule (prompt §13)
# --------------------------------------------------------------------------- #


@dataclass
class FeeRatePeriod:
    effective_from: date
    effective_to: date | None
    fee_rate: float


@dataclass
class FeeConfig:
    fee_type_key: str
    default_rate: float
    method: str  # once | actual | flat
    recognition_month: str | None
    freq_months: int
    timing: str  # begin | end
    periods: list[FeeRatePeriod] = field(default_factory=list)


def fee_rate_at(fee: FeeConfig, ym: str) -> float:
    """Step schedule: the latest period whose effective_from has already started
    by month `ym` wins; falls back to the fee's default_rate (prototype's
    `feeRateAt`)."""
    month_start = month_first(ym)
    best: FeeRatePeriod | None = None
    for p in fee.periods:
        if p.effective_from > month_last(ym):
            continue
        if best is None or p.effective_from > best.effective_from:
            best = p
    if best is not None:
        return best.fee_rate
    return fee.default_rate


@dataclass
class FeePeriodWindow:
    start: date
    end: date
    days: int
    index: int
    start_ym: str
    end_ym: str


def fee_period(info: BondInfo, fee: FeeConfig, ym: str) -> FeePeriodWindow | None:
    """Returns the recognition window ending in month `ym` for a recurring fee,
    or None if `ym` is not a recognition month for this fee's frequency."""
    ff = info.first_fee_date or info.issue_date
    if not ff:
        return None
    ff_ym = f"{ff.year:04d}-{ff.month:02d}"
    freq = max(1, round(fee.freq_months or 1))
    timing = "begin" if fee.timing == "begin" else "end"
    n = ym_diff(ff_ym, ym)
    if n < 0:
        return None

    from app.services.dates import ym_add

    if timing == "end":
        if n < freq - 1:
            return None
        if (n - (freq - 1)) % freq != 0:
            return None
        idx = (n - (freq - 1)) // freq
    else:
        if n % freq != 0:
            return None
        idx = n // freq

    start_ym = ym_add(ff_ym, idx * freq)
    end_ym = ym_add(ff_ym, idx * freq + freq - 1)
    start = ff if idx == 0 else month_first(start_ym)
    if info.issue_date and info.issue_date > start:
        start = info.issue_date
    end = month_last(end_ym)
    if info.maturity_date and info.maturity_date < end:
        end = info.maturity_date
    days = day_diff(start, end) + 1
    if days <= 0:
        return None
    return FeePeriodWindow(start=start, end=end, days=days, index=idx, start_ym=start_ym, end_ym=end_ym)


# --------------------------------------------------------------------------- #
# Full month computation for one bond (prompt §12, §14, §15)
# --------------------------------------------------------------------------- #


@dataclass
class MonthlyVolumeInput:
    advised: float | None = None
    buyback: float | None = None
    invested: float | None = None
    sold: float | None = None
    hold_start_override: date | None = None
    hold_end_override: date | None = None


@dataclass
class BondMonthResult:
    active: bool
    advised: float | None
    buyback: float | None
    outstanding: float | None
    invested: float | None
    sold: float | None
    holding: float | None
    coupon: float | None
    reference_value: float | None
    fees: dict[str, float]
    fee_rates: dict[str, float]
    fee_days: dict[str, int]
    fee_total: float
    hold_start: date | None
    hold_end: date | None
    hold_days: int | None
    hold_error: bool
    coupon_revenue: float
    total_revenue: float


def default_hold_start(info: BondInfo, ym: str) -> date:
    first = month_first(ym)
    if info.issue_date and f"{info.issue_date.year:04d}-{info.issue_date.month:02d}" == ym:
        return info.issue_date
    return first


def default_hold_end(info: BondInfo, ym: str) -> date:
    last = month_last(ym)
    if info.maturity_date and f"{info.maturity_date.year:04d}-{info.maturity_date.month:02d}" == ym:
        return info.maturity_date
    return last


def compute_bond_month(
    info: BondInfo,
    rate: RateConfig,
    fees: list[FeeConfig],
    volume: MonthlyVolumeInput,
    resolver: ReferenceRateResolver,
    ym: str,
) -> BondMonthResult:
    active = bond_active_month(info, ym)
    outstanding = None if volume.advised is None and volume.buyback is None else num(volume.advised) + num(volume.buyback)
    holding = None if volume.invested is None and volume.sold is None else num(volume.invested) + num(volume.sold)
    coupon = bond_coupon(info, rate, resolver, ym) if active else None
    ref_value = resolver.value(rate.reference_rate_id, ym) if rate.reference_rate_id else None
    par = num(info.par_value)

    fee_amounts: dict[str, float] = {}
    fee_rates: dict[str, float] = {}
    fee_days: dict[str, int] = {}
    fee_total = 0.0
    fee_def_by_key = {d["key"]: d for d in FEE_DEFS}

    for fee in fees:
        d = fee_def_by_key[fee.fee_type_key]
        rate_pct = fee_rate_at(fee, ym) / 100.0
        amount = 0.0
        if rate_pct != 0:
            if fee.method == METHOD_ONCE:
                if fee.recognition_month == ym:
                    base = {
                        FEE_BASE_ADVISED: num(volume.advised),
                        FEE_BASE_INVESTED: num(volume.invested),
                        FEE_BASE_OUTSTANDING: num(outstanding),
                    }[d["base"]]
                    amount = par * base * rate_pct
            elif active:
                base = num(outstanding)
                period = fee_period(info, fee, ym)
                if period is not None:
                    fee_days[fee.fee_type_key] = period.days
                    if fee.method == METHOD_FLAT:
                        amount = par * base * rate_pct
                    else:
                        amount = par * base * rate_pct * period.days / 365.0
        fee_amounts[fee.fee_type_key] = amount
        fee_rates[fee.fee_type_key] = fee_rate_at(fee, ym)
        fee_total += amount

    hold_start = volume.hold_start_override or default_hold_start(info, ym)
    hold_end = volume.hold_end_override or default_hold_end(info, ym)
    hold_days: int | None = None
    hold_error = False
    if hold_start and hold_end:
        hold_days = day_diff(hold_start, hold_end) + 1
        if hold_days < 0:
            hold_error = True
            hold_days = None

    coupon_revenue = 0.0
    if active and coupon is not None and holding is not None and hold_days is not None and hold_days > 0:
        coupon_revenue = par * holding * (coupon / 100.0) * hold_days / 365.0

    return BondMonthResult(
        active=active,
        advised=volume.advised,
        buyback=volume.buyback,
        outstanding=outstanding,
        invested=volume.invested,
        sold=volume.sold,
        holding=holding,
        coupon=coupon,
        reference_value=ref_value,
        fees=fee_amounts,
        fee_rates=fee_rates,
        fee_days=fee_days,
        fee_total=fee_total,
        hold_start=hold_start,
        hold_end=hold_end,
        hold_days=hold_days,
        hold_error=hold_error,
        coupon_revenue=coupon_revenue,
        total_revenue=fee_total + coupon_revenue,
    )


# --------------------------------------------------------------------------- #
# Weekly accrual (prompt §21.5)
# --------------------------------------------------------------------------- #


def weekly_accrual_for_bond(par_value: float, week_volume: float | None, coupon: float | None, ym: str) -> float | None:
    if week_volume is None or coupon is None:
        return None
    y, m = ym_parse(ym)
    dim = days_in_month(y, m)
    return num(par_value) * week_volume * (coupon / 100.0) * dim / 365.0
