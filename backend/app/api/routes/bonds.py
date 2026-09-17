from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_manager_up, require_staff_up
from app.core.errors import NotFoundError, ValidationAppError
from app.models.bond import Bond, BondInterestConfig, BondMonthlyData
from app.models.user import User
from app.schemas.bond import (
    BondBasicInfoUpdate,
    BondCreate,
    BondDetail,
    BondListItem,
    BondMonthComputed,
    InterestConfigUpdate,
    MonthlyVolumeUpdate,
)
from app.services import bond_service as svc
from app.services import fee_service
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version
from app.services.dates import ym_diff
from app.services.reference_rate_service import build_resolver

router = APIRouter(prefix="/bonds", tags=["bonds"])
StaffUp = Annotated[User, Depends(require_staff_up)]
ManagerUp = Annotated[User, Depends(require_manager_up)]
MODULE = "bonds"


def _list_item(bond: Bond) -> BondListItem:
    status_key, status_label = svc.status_of(bond)
    return BondListItem(
        id=bond.id, code=bond.code, issue_date=bond.issue_date, maturity_date=bond.maturity_date,
        par_value=float(bond.par_value), status_key=status_key, status_label=status_label, version=bond.version,
    )


def _detail(bond: Bond) -> BondDetail:
    status_key, status_label = svc.status_of(bond)
    ic = bond.interest_config
    interest_config = {
        "rate_type": ic.rate_type if ic else "fixed",
        "fixed_rate": float(ic.fixed_rate) if ic and ic.fixed_rate is not None else None,
        "spread": float(ic.spread) if ic and ic.spread is not None else None,
        "reference_rate_id": ic.reference_rate_id if ic else None,
        "first4_rate": float(ic.first4_rate) if ic and ic.first4_rate is not None else None,
        "floor_rate": float(ic.floor_rate) if ic and ic.floor_rate is not None else None,
        "cap_rate": float(ic.cap_rate) if ic and ic.cap_rate is not None else None,
        "version": ic.version if ic else 0,
    } if ic else {"rate_type": "fixed", "version": 0}
    monthly = {
        md.month_key: {
            "advised_volume": float(md.advised_volume) if md.advised_volume is not None else None,
            "buyback_volume": float(md.buyback_volume) if md.buyback_volume is not None else None,
            "invested_volume": float(md.invested_volume) if md.invested_volume is not None else None,
            "sold_volume": float(md.sold_volume) if md.sold_volume is not None else None,
            "hold_start_override": md.hold_start_override.isoformat() if md.hold_start_override else None,
            "hold_end_override": md.hold_end_override.isoformat() if md.hold_end_override else None,
            "version": md.version,
        }
        for md in bond.monthly_data
    }
    return BondDetail(
        id=bond.id, code=bond.code, issue_date=bond.issue_date, maturity_date=bond.maturity_date,
        first_fee_date=bond.first_fee_date, pay_freq_months=bond.pay_freq_months, xhtn=bond.xhtn,
        par_value=float(bond.par_value), status_key=status_key, status_label=status_label,
        is_deleted=bond.is_deleted, version=bond.version, created_at=bond.created_at, updated_at=bond.updated_at,
        interest_config=interest_config, monthly_data=monthly,
        fee_configs=[fee_service.to_dict(f) for f in bond.fee_configs],
    )


def _get_or_404(db: DbSession, bond_id: str) -> Bond:
    bond = svc.load_bond_full(db, bond_id)
    if not bond:
        raise NotFoundError("Không tìm thấy trái phiếu.")
    return bond


@router.get("", response_model=list[BondListItem])
def list_bonds(db: DbSession, _user: CurrentUser, include_deleted: bool = False):
    q = db.query(Bond)
    if not include_deleted:
        q = q.filter(Bond.is_deleted.is_(False))
    return [_list_item(b) for b in q.order_by(Bond.code).all()]


@router.post("", response_model=BondDetail, status_code=201)
def create_bond(payload: BondCreate, db: DbSession, user: StaffUp):
    code = payload.code.strip()
    if not code:
        raise ValidationAppError("Mã trái phiếu không được để trống.")
    if db.query(Bond).filter(Bond.code == code).first():
        raise ValidationAppError(f"Mã trái phiếu '{code}' đã tồn tại.")
    bond = svc.create_bond_with_defaults(db, code, user.id)
    record_create(db, user_id=user.id, module=MODULE, record_id=bond.id, snapshot={"code": code})
    db.commit()
    return _detail(svc.load_bond_full(db, bond.id))


@router.get("/{bond_id}", response_model=BondDetail)
def get_bond(bond_id: str, db: DbSession, _user: CurrentUser):
    return _detail(_get_or_404(db, bond_id))


@router.patch("/{bond_id}", response_model=BondDetail)
def update_bond_info(bond_id: str, payload: BondBasicInfoUpdate, db: DbSession, user: StaffUp):
    bond = _get_or_404(db, bond_id)
    check_version(bond.version, payload.version)
    new_code = payload.code.strip()
    if new_code != bond.code and db.query(Bond).filter(Bond.code == new_code, Bond.id != bond.id).first():
        raise ValidationAppError(f"Mã trái phiếu '{new_code}' đã tồn tại.")

    before = {
        "code": bond.code, "issue_date": bond.issue_date, "maturity_date": bond.maturity_date,
        "first_fee_date": bond.first_fee_date, "pay_freq_months": bond.pay_freq_months,
        "xhtn": bond.xhtn, "par_value": float(bond.par_value),
    }
    bond.code = new_code
    bond.issue_date = payload.issue_date
    bond.maturity_date = payload.maturity_date
    bond.first_fee_date = payload.first_fee_date
    bond.pay_freq_months = payload.pay_freq_months
    bond.xhtn = payload.xhtn
    bond.par_value = payload.par_value
    bond.updated_by = user.id
    after = {
        "code": bond.code, "issue_date": bond.issue_date, "maturity_date": bond.maturity_date,
        "first_fee_date": bond.first_fee_date, "pay_freq_months": bond.pay_freq_months,
        "xhtn": bond.xhtn, "par_value": float(bond.par_value),
    }
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=bond.id, before=before, after=after)
    db.commit()
    return _detail(svc.load_bond_full(db, bond.id))


@router.delete("/{bond_id}")
def delete_bond(bond_id: str, db: DbSession, user: ManagerUp):
    bond = _get_or_404(db, bond_id)
    bond.is_deleted = True
    bond.deleted_at = datetime.now(timezone.utc)
    bond.deleted_by = user.id
    record_delete(db, user_id=user.id, module=MODULE, record_id=bond.id, snapshot={"code": bond.code})
    db.commit()
    return {"ok": True}


@router.post("/{bond_id}/restore", response_model=BondDetail)
def restore_bond(bond_id: str, db: DbSession, user: ManagerUp):
    bond = _get_or_404(db, bond_id)
    bond.is_deleted = False
    bond.deleted_at = None
    bond.deleted_by = None
    record_field_changes(db, user_id=user.id, module=MODULE, record_id=bond.id, before={"is_deleted": True}, after={"is_deleted": False})
    db.commit()
    return _detail(svc.load_bond_full(db, bond.id))


@router.patch("/{bond_id}/interest-config", response_model=BondDetail)
def update_interest_config(bond_id: str, payload: InterestConfigUpdate, db: DbSession, user: StaffUp):
    bond = _get_or_404(db, bond_id)
    cfg = bond.interest_config
    if not cfg:
        raise NotFoundError("Trái phiếu chưa có cấu hình lãi suất.")
    check_version(cfg.version, payload.version)
    if payload.reference_rate_id:
        from app.models.reference_rate import ReferenceRate

        if not db.get(ReferenceRate, payload.reference_rate_id):
            raise ValidationAppError("Lãi suất tham chiếu không tồn tại.")

    before = {
        "rate_type": cfg.rate_type, "fixed_rate": cfg.fixed_rate, "spread": cfg.spread,
        "reference_rate_id": cfg.reference_rate_id, "first4_rate": cfg.first4_rate,
        "floor_rate": cfg.floor_rate, "cap_rate": cfg.cap_rate,
    }
    cfg.rate_type = payload.rate_type
    cfg.fixed_rate = payload.fixed_rate
    cfg.spread = payload.spread
    cfg.reference_rate_id = payload.reference_rate_id
    cfg.first4_rate = payload.first4_rate
    cfg.floor_rate = payload.floor_rate
    cfg.cap_rate = payload.cap_rate
    cfg.updated_by = user.id
    after = {
        "rate_type": cfg.rate_type, "fixed_rate": cfg.fixed_rate, "spread": cfg.spread,
        "reference_rate_id": cfg.reference_rate_id, "first4_rate": cfg.first4_rate,
        "floor_rate": cfg.floor_rate, "cap_rate": cfg.cap_rate,
    }
    record_field_changes(db, user_id=user.id, module="bond_interest_config", record_id=bond.id, before=before, after=after)
    db.commit()
    return _detail(svc.load_bond_full(db, bond.id))


@router.put("/{bond_id}/monthly/{month_key}", response_model=BondDetail)
def upsert_monthly_volume(bond_id: str, month_key: str, payload: MonthlyVolumeUpdate, db: DbSession, user: StaffUp):
    bond = _get_or_404(db, bond_id)
    md = next((m for m in bond.monthly_data if m.month_key == month_key), None)
    if md:
        check_version(md.version, payload.version if payload.version is not None else -1)
        before = {
            "advised_volume": md.advised_volume, "buyback_volume": md.buyback_volume,
            "invested_volume": md.invested_volume, "sold_volume": md.sold_volume,
        }
        md.advised_volume = payload.advised_volume
        md.buyback_volume = payload.buyback_volume
        md.invested_volume = payload.invested_volume
        md.sold_volume = payload.sold_volume
        md.hold_start_override = payload.hold_start_override
        md.hold_end_override = payload.hold_end_override
        md.updated_by = user.id
        after = {
            "advised_volume": md.advised_volume, "buyback_volume": md.buyback_volume,
            "invested_volume": md.invested_volume, "sold_volume": md.sold_volume,
        }
        record_field_changes(db, user_id=user.id, module="bond_monthly_data", record_id=f"{bond.id}:{month_key}", before=before, after=after)
    else:
        if payload.version is not None:
            raise ValidationAppError("Tháng này chưa có dữ liệu; không thể gửi version.")
        db.add(
            BondMonthlyData(
                bond_id=bond.id, month_key=month_key,
                advised_volume=payload.advised_volume, buyback_volume=payload.buyback_volume,
                invested_volume=payload.invested_volume, sold_volume=payload.sold_volume,
                hold_start_override=payload.hold_start_override, hold_end_override=payload.hold_end_override,
                created_by=user.id, updated_by=user.id,
            )
        )
    db.commit()
    return _detail(svc.load_bond_full(db, bond.id))


@router.get("/{bond_id}/computed", response_model=list[BondMonthComputed])
def get_computed(bond_id: str, db: DbSession, _user: CurrentUser, start: str = Query(...), end: str = Query(...)):
    bond = _get_or_404(db, bond_id)
    if ym_diff(start, end) < 0:
        raise ValidationAppError("Khoảng thời gian không hợp lệ.")
    if ym_diff(start, end) > 600:
        raise ValidationAppError("Khoảng thời gian quá dài.")
    resolver = build_resolver(db)
    out = []
    n = ym_diff(start, end)
    from app.services.dates import ym_add

    for i in range(n + 1):
        mk = ym_add(start, i)
        res = svc.compute_month(db, bond, mk, resolver)
        out.append(BondMonthComputed(
            month_key=mk, active=res.active, advised=res.advised, buyback=res.buyback, outstanding=res.outstanding,
            invested=res.invested, sold=res.sold, holding=res.holding, coupon=res.coupon,
            reference_value=res.reference_value, fees=res.fees, fee_total=res.fee_total,
            hold_start=res.hold_start, hold_end=res.hold_end, hold_days=res.hold_days, hold_error=res.hold_error,
            coupon_revenue=res.coupon_revenue, total_revenue=res.total_revenue,
        ))
    return out
