from sqlalchemy.orm import Session

from app.models.bond import Bond
from app.models.weekly import WeeklyPortfolioValue
from app.schemas.weekly import WeeklyBondRow, WeeklyCell, WeeklyGridBondRow, WeeklyGridResponse, WeeklyResponse
from app.services import bond_service as svc
from app.services.calc_engine import weekly_accrual_for_bond
from app.services.dates import all_week_keys, week_key_month
from app.services.reference_rate_service import build_resolver


def get_week(db: Session, week_key: str) -> WeeklyResponse:
    ym = week_key_month(week_key)
    bonds = db.query(Bond).filter(Bond.is_deleted.is_(False)).order_by(Bond.code).all()
    resolver = build_resolver(db)
    rows: list[WeeklyBondRow] = []
    total = 0.0
    any_accrual = False

    for b in bonds:
        full = svc.load_bond_full(db, b.id)
        m = svc.compute_month(db, full, ym, resolver)
        vol_row = (
            db.query(WeeklyPortfolioValue)
            .filter(WeeklyPortfolioValue.bond_id == b.id, WeeklyPortfolioValue.week_key == week_key)
            .first()
        )
        volume = float(vol_row.volume) if vol_row else None
        coupon = m.coupon
        accrual = weekly_accrual_for_bond(float(full.par_value), volume, coupon, ym)
        if accrual is not None:
            total += accrual
            any_accrual = True
        rows.append(
            WeeklyBondRow(
                bond_id=b.id, code=b.code, par_value=float(full.par_value),
                volume=volume, volume_version=vol_row.version if vol_row else None,
                coupon=coupon, accrual=accrual,
            )
        )

    latest = latest_week_with_data(db)
    return WeeklyResponse(
        week_key=week_key, rows=rows, total_accrual=total if any_accrual else None, latest_week_with_data=latest
    )


def get_week_range(db: Session, start_week: str, end_week: str) -> WeeklyGridResponse:
    weeks = [w for w in all_week_keys(week_key_month(start_week), week_key_month(end_week))]
    # Trim to the exact requested week endpoints within the first/last month.
    weeks = [w for w in weeks if start_week <= w <= end_week]

    bonds = db.query(Bond).filter(Bond.is_deleted.is_(False)).order_by(Bond.code).all()
    resolver = build_resolver(db)

    all_values = db.query(WeeklyPortfolioValue).filter(WeeklyPortfolioValue.week_key.in_(weeks)).all()
    by_bond_week: dict[tuple[str, str], WeeklyPortfolioValue] = {(v.bond_id, v.week_key): v for v in all_values}

    grid_rows: list[WeeklyGridBondRow] = []
    totals: dict[str, float] = {w: 0.0 for w in weeks}
    any_accrual: dict[str, bool] = {w: False for w in weeks}

    for b in bonds:
        full = svc.load_bond_full(db, b.id)
        par = float(full.par_value)
        month_cache: dict[str, float | None] = {}
        cells: dict[str, WeeklyCell] = {}
        for w in weeks:
            ym = week_key_month(w)
            if ym not in month_cache:
                month_cache[ym] = svc.compute_month(db, full, ym, resolver).coupon
            coupon = month_cache[ym]
            vol_row = by_bond_week.get((b.id, w))
            volume = float(vol_row.volume) if vol_row else None
            accrual = weekly_accrual_for_bond(par, volume, coupon, ym)
            if accrual is not None:
                totals[w] += accrual
                any_accrual[w] = True
            cells[w] = WeeklyCell(volume=volume, version=vol_row.version if vol_row else None, coupon=coupon, accrual=accrual)
        grid_rows.append(WeeklyGridBondRow(bond_id=b.id, code=b.code, par_value=par, cells=cells))

    return WeeklyGridResponse(
        weeks=weeks,
        bonds=grid_rows,
        totals={w: (totals[w] if any_accrual[w] else None) for w in weeks},
        latest_week_with_data=latest_week_with_data(db),
    )


def latest_week_with_data(db: Session) -> str | None:
    # 'YYYY-MM-Wn' sorts lexicographically the same as chronologically, since
    # the month is zero-padded and n is always a single digit (max 5/month).
    row = db.query(WeeklyPortfolioValue.week_key).order_by(WeeklyPortfolioValue.week_key.desc()).first()
    return row[0] if row else None


def carry_forward(db: Session, from_week: str, to_week: str, user_id: str | None) -> int:
    """Copies each bond's volume from `from_week` into `to_week`, but only for
    bonds that don't already have a value there — never overwrites (prompt
    §21.5: 'Không tự forward-fill', this endpoint is the explicit, user-
    triggered exception to that rule)."""
    from_rows = {r.bond_id: r.volume for r in db.query(WeeklyPortfolioValue).filter(WeeklyPortfolioValue.week_key == from_week).all()}
    existing_to = {r.bond_id for r in db.query(WeeklyPortfolioValue).filter(WeeklyPortfolioValue.week_key == to_week).all()}
    copied = 0
    for bond_id, volume in from_rows.items():
        if bond_id in existing_to:
            continue
        db.add(WeeklyPortfolioValue(bond_id=bond_id, week_key=to_week, volume=volume, updated_by=user_id))
        copied += 1
    return copied
