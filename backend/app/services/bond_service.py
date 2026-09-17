from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.models.bond import Bond, BondFeeConfig, BondInterestConfig, BondMonthlyData, FEE_DEFS
from app.services import calc_engine as ce
from app.services.reference_rate_service import build_resolver


def create_bond_with_defaults(db: Session, code: str, user_id: str | None) -> Bond:
    bond = Bond(code=code, par_value=100, pay_freq_months=3, created_by=user_id, updated_by=user_id)
    db.add(bond)
    db.flush()

    db.add(BondInterestConfig(bond_id=bond.id, rate_type=ce.RATE_FIXED, updated_by=user_id))
    for d in FEE_DEFS:
        db.add(
            BondFeeConfig(
                bond_id=bond.id,
                fee_type_key=d["key"],
                default_rate=0,
                method=d["methods"][0],
                freq_months=1,
                timing="end",
                updated_by=user_id,
            )
        )
    return bond


def to_bond_info(bond: Bond) -> ce.BondInfo:
    return ce.BondInfo(
        issue_date=bond.issue_date,
        maturity_date=bond.maturity_date,
        first_fee_date=bond.first_fee_date,
        pay_freq_months=bond.pay_freq_months,
        par_value=float(bond.par_value),
    )


def to_rate_config(cfg: BondInterestConfig | None) -> ce.RateConfig:
    if cfg is None:
        return ce.RateConfig(rate_type=ce.RATE_FIXED)
    return ce.RateConfig(
        rate_type=cfg.rate_type,
        fixed_rate=float(cfg.fixed_rate) if cfg.fixed_rate is not None else None,
        spread=float(cfg.spread) if cfg.spread is not None else None,
        reference_rate_id=cfg.reference_rate_id,
        first4_rate=float(cfg.first4_rate) if cfg.first4_rate is not None else None,
        floor_rate=float(cfg.floor_rate) if cfg.floor_rate is not None else None,
        cap_rate=float(cfg.cap_rate) if cfg.cap_rate is not None else None,
    )


def to_fee_configs(fee_rows: list[BondFeeConfig]) -> list[ce.FeeConfig]:
    out = []
    for f in fee_rows:
        periods = [
            ce.FeeRatePeriod(effective_from=p.effective_from, effective_to=p.effective_to, fee_rate=float(p.fee_rate))
            for p in f.rate_periods
        ]
        out.append(
            ce.FeeConfig(
                fee_type_key=f.fee_type_key,
                default_rate=float(f.default_rate),
                method=f.method,
                recognition_month=f.recognition_month,
                freq_months=f.freq_months,
                timing=f.timing,
                periods=periods,
            )
        )
    return out


def to_volume_input(md: BondMonthlyData | None) -> ce.MonthlyVolumeInput:
    if md is None:
        return ce.MonthlyVolumeInput()
    return ce.MonthlyVolumeInput(
        advised=float(md.advised_volume) if md.advised_volume is not None else None,
        buyback=float(md.buyback_volume) if md.buyback_volume is not None else None,
        invested=float(md.invested_volume) if md.invested_volume is not None else None,
        sold=float(md.sold_volume) if md.sold_volume is not None else None,
        hold_start_override=md.hold_start_override,
        hold_end_override=md.hold_end_override,
    )


def load_bond_full(db: Session, bond_id: str) -> Bond | None:
    return (
        db.query(Bond)
        .options(
            selectinload(Bond.interest_config),
            selectinload(Bond.monthly_data),
            selectinload(Bond.fee_configs).selectinload(BondFeeConfig.rate_periods),
        )
        .filter(Bond.id == bond_id)
        .first()
    )


def compute_month(db: Session, bond: Bond, month_key: str, resolver: ce.ReferenceRateResolver | None = None) -> ce.BondMonthResult:
    resolver = resolver or build_resolver(db)
    md = next((m for m in bond.monthly_data if m.month_key == month_key), None)
    return ce.compute_bond_month(
        to_bond_info(bond),
        to_rate_config(bond.interest_config),
        to_fee_configs(bond.fee_configs),
        to_volume_input(md),
        resolver,
        month_key,
    )


def status_of(bond: Bond) -> tuple[str, str]:
    return ce.bond_status(to_bond_info(bond), date.today())
