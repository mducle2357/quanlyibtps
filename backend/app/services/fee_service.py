from datetime import date

from sqlalchemy.orm import Session

from app.models.bond import FEE_DEFS, BondFeeConfig, BondFeeRatePeriod

FEE_DEF_BY_KEY = {d["key"]: d for d in FEE_DEFS}


def fee_def(fee_type_key: str) -> dict:
    d = FEE_DEF_BY_KEY.get(fee_type_key)
    if not d:
        raise ValueError(f"Unknown fee type: {fee_type_key}")
    return d


def to_dict(cfg: BondFeeConfig) -> dict:
    d = fee_def(cfg.fee_type_key)
    return {
        "fee_type_key": cfg.fee_type_key,
        "name": d["name"],
        "basis": d["basis"],
        "allowed_methods": d["methods"],
        "default_rate": float(cfg.default_rate),
        "method": cfg.method,
        "recognition_month": cfg.recognition_month,
        "freq_months": cfg.freq_months,
        "timing": cfg.timing,
        "version": cfg.version,
        "updated_at": cfg.updated_at,
        "periods": [
            {"id": p.id, "effective_from": p.effective_from, "effective_to": p.effective_to, "fee_rate": float(p.fee_rate)}
            for p in sorted(cfg.rate_periods, key=lambda p: p.effective_from)
        ],
    }


def _intervals_overlap(a1: date, b1: date | None, a2: date, b2: date | None) -> bool:
    end1 = b1 or date.max
    end2 = b2 or date.max
    return a1 <= end2 and a2 <= end1


def find_overlap(existing: list[BondFeeRatePeriod], new_from: date, new_to: date | None, exclude_id: str | None = None) -> BondFeeRatePeriod | None:
    for p in existing:
        if exclude_id and p.id == exclude_id:
            continue
        if _intervals_overlap(p.effective_from, p.effective_to, new_from, new_to):
            return p
    return None
