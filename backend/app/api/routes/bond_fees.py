from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_staff_up
from app.core.errors import NotFoundError, ValidationAppError
from app.models.bond import Bond, BondFeeConfig, BondFeeRatePeriod
from app.models.user import User
from app.schemas.fee import FeeConfigOut, FeeConfigUpdate, FeeRatePeriodCreate, FeeRatePeriodOut
from app.services import fee_service as svc
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version
from app.services.dates import is_valid_month_key

router = APIRouter(prefix="/bonds/{bond_id}/fees", tags=["bond-fees"])
StaffUp = Annotated[User, Depends(require_staff_up)]
MODULE = "bond_fee_configs"


def _get_config(db: DbSession, bond_id: str, fee_type_key: str) -> BondFeeConfig:
    if not db.get(Bond, bond_id):
        raise NotFoundError("Không tìm thấy trái phiếu.")
    cfg = (
        db.query(BondFeeConfig)
        .filter(BondFeeConfig.bond_id == bond_id, BondFeeConfig.fee_type_key == fee_type_key)
        .first()
    )
    if not cfg:
        raise NotFoundError("Không tìm thấy cấu hình phí cho loại này.")
    return cfg


@router.patch("/{fee_type_key}", response_model=FeeConfigOut)
def update_fee_config(bond_id: str, fee_type_key: str, payload: FeeConfigUpdate, db: DbSession, user: StaffUp):
    cfg = _get_config(db, bond_id, fee_type_key)
    check_version(cfg.version, payload.version)
    d = svc.fee_def(fee_type_key)
    if payload.method not in d["methods"]:
        raise ValidationAppError(f"Phương pháp '{payload.method}' không hợp lệ cho {d['name']}.")
    if payload.method == "once" and payload.recognition_month and not is_valid_month_key(payload.recognition_month):
        raise ValidationAppError("recognition_month phải theo dạng YYYY-MM.")

    before = {
        "default_rate": cfg.default_rate, "method": cfg.method, "recognition_month": cfg.recognition_month,
        "freq_months": cfg.freq_months, "timing": cfg.timing,
    }
    cfg.default_rate = payload.default_rate
    cfg.method = payload.method
    cfg.recognition_month = payload.recognition_month if payload.method == "once" else None
    cfg.freq_months = payload.freq_months
    cfg.timing = payload.timing
    cfg.updated_by = user.id
    after = {
        "default_rate": cfg.default_rate, "method": cfg.method, "recognition_month": cfg.recognition_month,
        "freq_months": cfg.freq_months, "timing": cfg.timing,
    }
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=cfg.id, before=before, after=after)
    db.commit()
    db.refresh(cfg)
    return svc.to_dict(cfg)


@router.post("/{fee_type_key}/periods", response_model=FeeConfigOut, status_code=201)
def add_period(bond_id: str, fee_type_key: str, payload: FeeRatePeriodCreate, db: DbSession, user: StaffUp):
    cfg = _get_config(db, bond_id, fee_type_key)
    clash = svc.find_overlap(cfg.rate_periods, payload.effective_from, payload.effective_to)
    if clash:
        raise ValidationAppError(
            f"Giai đoạn mới ({payload.effective_from} → {payload.effective_to or '...'}) chồng lấn với giai đoạn "
            f"hiện có ({clash.effective_from} → {clash.effective_to or '...'})."
        )
    period = BondFeeRatePeriod(
        bond_fee_config_id=cfg.id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        fee_rate=payload.fee_rate,
        created_by=user.id,
    )
    db.add(period)
    db.flush()
    record_create(
        db, user_id=user.id, module="bond_fee_rate_periods", record_id=period.id,
        snapshot={"fee_type_key": fee_type_key, "effective_from": str(payload.effective_from), "fee_rate": payload.fee_rate},
    )
    db.commit()
    db.refresh(cfg)
    return svc.to_dict(cfg)


@router.delete("/{fee_type_key}/periods/{period_id}", response_model=FeeConfigOut)
def delete_period(bond_id: str, fee_type_key: str, period_id: str, db: DbSession, user: StaffUp):
    cfg = _get_config(db, bond_id, fee_type_key)
    period = next((p for p in cfg.rate_periods if p.id == period_id), None)
    if not period:
        raise NotFoundError("Không tìm thấy giai đoạn phí.")
    record_delete(
        db, user_id=user.id, module="bond_fee_rate_periods", record_id=period.id,
        snapshot={"fee_type_key": fee_type_key, "effective_from": str(period.effective_from), "fee_rate": float(period.fee_rate)},
    )
    db.delete(period)
    db.commit()
    db.refresh(cfg)
    return svc.to_dict(cfg)
