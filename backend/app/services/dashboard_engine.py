"""Portfolio/revenue aggregation across all bonds for the Dashboard (prompt §18).

Pure function over a list of already-computed BondMonthResult so it can be unit
tested (acceptance tests 8, 10, 16) without touching the database.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.calc_engine import BondMonthResult, num


@dataclass
class BondValueInput:
    bond_id: str
    par_value: float
    month: BondMonthResult


@dataclass
class DashboardMonthResult:
    holding_volume: float
    holding_value: float
    advised_volume: float
    advised_value: float
    fee_total: float
    coupon_revenue: float
    ir_revenue: float
    fee_by_type: dict[str, float]
    equity: float | None
    limit: float | None
    remaining_capacity: float | None
    usage_ratio: float | None
    total_revenue: float


def compute_dashboard_month(
    bonds: list[BondValueInput], ir_revenue: float, equity: float | None
) -> DashboardMonthResult:
    holding_volume = holding_value = advised_volume = advised_value = 0.0
    fee_total = coupon_revenue = 0.0
    fee_by_type: dict[str, float] = {}

    for b in bonds:
        m = b.month
        holding_volume += num(m.holding)
        # §18.1: compare against VALUE (volume × par value of THAT bond), never raw volume,
        # because par values differ bond to bond (acceptance test 16).
        holding_value += num(m.holding) * num(b.par_value)
        advised_volume += num(m.advised)
        advised_value += num(m.advised) * num(b.par_value)
        fee_total += m.fee_total
        coupon_revenue += m.coupon_revenue
        for k, v in m.fees.items():
            fee_by_type[k] = fee_by_type.get(k, 0.0) + v

    limit = None if equity is None else equity * 0.7
    return DashboardMonthResult(
        holding_volume=holding_volume,
        holding_value=holding_value,
        advised_volume=advised_volume,
        advised_value=advised_value,
        fee_total=fee_total,
        coupon_revenue=coupon_revenue,
        ir_revenue=ir_revenue,
        fee_by_type=fee_by_type,
        equity=equity,
        limit=limit,
        remaining_capacity=None if limit is None else limit - holding_value,
        usage_ratio=None if not limit else holding_value / limit,
        total_revenue=fee_total + coupon_revenue + ir_revenue,
    )
