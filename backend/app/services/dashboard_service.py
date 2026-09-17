from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.bond import Bond
from app.models.weekly import EquityMonthlyValue
from app.schemas.dashboard import Alert, BondPortfolioRow, DashboardResponse
from app.services import bond_service as svc
from app.services.calc_engine import num
from app.services.reference_rate_service import build_resolver


def get_dashboard(db: Session, month_key: str) -> DashboardResponse:
    bonds = db.query(Bond).filter(Bond.is_deleted.is_(False)).all()
    resolver = build_resolver(db)

    invested_rows: list[BondPortfolioRow] = []
    advised_rows: list[BondPortfolioRow] = []
    holding_value = 0.0
    advised_volume_total = 0.0
    fee_total = 0.0
    coupon_revenue = 0.0

    for b in bonds:
        full = svc.load_bond_full(db, b.id)
        m = svc.compute_month(db, full, month_key, resolver)
        par = float(full.par_value)
        fee_total += m.fee_total
        coupon_revenue += m.coupon_revenue
        if m.holding:
            value = num(m.holding) * par
            holding_value += value
            invested_rows.append(BondPortfolioRow(bond_id=b.id, code=b.code, volume=num(m.holding), value=value))
        if m.advised:
            advised_volume_total += num(m.advised)
            advised_rows.append(BondPortfolioRow(bond_id=b.id, code=b.code, volume=num(m.advised), value=num(m.advised) * par))

    eq_row = db.query(EquityMonthlyValue).filter(EquityMonthlyValue.month_key == month_key).first()
    equity = float(eq_row.value) if eq_row else None
    limit = equity * 0.7 if equity is not None else None

    ir_revenue = _ir_total(db, month_key)

    return DashboardResponse(
        month_key=month_key,
        equity=equity,
        limit=limit,
        holding_value=holding_value,
        remaining_capacity=(limit - holding_value) if limit is not None else None,
        usage_ratio=(holding_value / limit) if limit else None,
        invested_bonds=invested_rows,
        advised_bonds=advised_rows,
        advised_volume_total=advised_volume_total,
        fee_total=fee_total,
        coupon_revenue=coupon_revenue,
        ir_revenue=ir_revenue,
        total_revenue=fee_total + coupon_revenue + ir_revenue,
        # Compliance aggregation lands in Phase 5 once the checklist entities
        # exist; kept at 0/0 here rather than guessing, per prompt §0's rule
        # to preserve correctness over filling in a plausible-looking number.
        compliance_done=0,
        compliance_total=0,
    )


def _ir_total(db: Session, month_key: str) -> float:
    from app.models.ir import IRMonthlyRevenue

    rows = db.query(IRMonthlyRevenue).filter(IRMonthlyRevenue.month_key == month_key).all()
    return sum(float(r.revenue) for r in rows)


def get_alerts(db: Session, today: date | None = None) -> list[Alert]:
    today = today or date.today()
    horizon = today + timedelta(days=30)
    alerts: list[Alert] = []

    bonds = db.query(Bond).filter(Bond.is_deleted.is_(False)).all()
    for b in bonds:
        if b.maturity_date and today <= b.maturity_date <= horizon:
            days_left = (b.maturity_date - today).days
            alerts.append(
                Alert(
                    kind="w" if days_left > 7 else "d",
                    category="maturity",
                    title=f"{b.code} sắp đáo hạn",
                    detail=f"Còn {days_left} ngày (đáo hạn {b.maturity_date.isoformat()})",
                )
            )

    from app.models.reference_rate import ReferenceRate

    cur_ym = f"{today.year:04d}-{today.month:02d}"
    resolver = build_resolver(db)
    for r in db.query(ReferenceRate).all():
        if resolver.value(r.id, cur_ym) is None:
            alerts.append(
                Alert(kind="w", category="benchmark", title=f"{r.name} chưa cập nhật lãi suất", detail=f"Thiếu dữ liệu tháng {cur_ym}")
            )

    dash = get_dashboard(db, cur_ym)
    if dash.usage_ratio is not None:
        if dash.usage_ratio >= 1:
            alerts.append(Alert(kind="d", category="portfolio", title="Vượt giới hạn 70% VCSH", detail=f"% Limit Used: {dash.usage_ratio*100:.2f}%"))
        elif dash.usage_ratio >= 0.9:
            alerts.append(Alert(kind="w", category="portfolio", title="Sắp chạm giới hạn 70% VCSH", detail=f"% Limit Used: {dash.usage_ratio*100:.2f}%"))

    return alerts
