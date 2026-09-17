from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_manager_up, require_staff_up
from app.core.errors import NotFoundError, ValidationAppError
from app.models.reference_rate import ReferenceRate, ReferenceRateComponent, ReferenceRateMonthlyValue
from app.models.user import User
from app.schemas.reference_rate import ReferenceRateCreate, ReferenceRateOut, ReferenceRateUpdate, SetMonthlyValueRequest
from app.services import reference_rate_service as svc
from app.services.audit_service import record_create, record_delete, record_field_changes
from app.services.concurrency import check_version
from app.services.dates import is_valid_month_key, ym_add, ym_diff

router = APIRouter(prefix="/reference-rates", tags=["reference-rates"])
StaffUp = Annotated[User, Depends(require_staff_up)]
ManagerUp = Annotated[User, Depends(require_manager_up)]
MODULE = "reference_rates"


@router.get("", response_model=list[ReferenceRateOut])
def list_rates(db: DbSession, _user: CurrentUser):
    return [svc.to_dict(r) for r in svc.load_all(db)]


@router.get("/resolved")
def resolved_values(db: DbSession, _user: CurrentUser, start: str, end: str):
    """Every benchmark's effective value per month, with calculated rates already
    averaged/min/max'd server-side — the frontend renders the Control grid and
    chart from this without re-implementing the resolution logic (prompt §17.4)."""
    if not is_valid_month_key(start) or not is_valid_month_key(end) or ym_diff(start, end) < 0:
        raise ValidationAppError("Khoảng thời gian không hợp lệ.")
    if ym_diff(start, end) > 600:
        raise ValidationAppError("Khoảng thời gian quá dài.")
    resolver = svc.build_resolver(db)
    rates = svc.load_all(db)
    months = []
    k = start
    for _ in range(ym_diff(start, end) + 1):
        months.append(k)
        k = ym_add(k, 1)
    return {r.id: {m: resolver.value(r.id, m) for m in months} for r in rates}


@router.post("", response_model=ReferenceRateOut, status_code=201)
def create_rate(payload: ReferenceRateCreate, db: DbSession, user: StaffUp):
    if db.query(ReferenceRate).filter(ReferenceRate.name == payload.name).first():
        raise ValidationAppError("Tên benchmark đã tồn tại.")
    for cid in payload.component_ids:
        if not db.get(ReferenceRate, cid):
            raise ValidationAppError(f"Benchmark thành phần không tồn tại: {cid}")

    rate = ReferenceRate(
        name=payload.name,
        rate_type=payload.rate_type,
        calc_method=payload.calc_method if payload.rate_type == "calculated" else None,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(rate)
    db.flush()

    if payload.rate_type == "calculated":
        err = svc.validate_no_cycle(db, rate.id, payload.component_ids)
        if err:
            raise ValidationAppError(err)
        for cid in payload.component_ids:
            db.add(ReferenceRateComponent(reference_rate_id=rate.id, component_rate_id=cid))

    record_create(db, user_id=user.id, module=MODULE, record_id=rate.id, snapshot={"name": rate.name, "rate_type": rate.rate_type})
    db.commit()
    db.refresh(rate)
    return svc.to_dict(db.get(ReferenceRate, rate.id))


@router.patch("/{rate_id}", response_model=ReferenceRateOut)
def update_rate(rate_id: str, payload: ReferenceRateUpdate, db: DbSession, user: StaffUp):
    rate = db.get(ReferenceRate, rate_id)
    if not rate:
        raise NotFoundError("Không tìm thấy benchmark.")
    check_version(rate.version, payload.version)

    if rate.rate_type == "calculated":
        for cid in payload.component_ids:
            if not db.get(ReferenceRate, cid):
                raise ValidationAppError(f"Benchmark thành phần không tồn tại: {cid}")
        err = svc.validate_no_cycle(db, rate.id, payload.component_ids)
        if err:
            raise ValidationAppError(err)
        if payload.calc_method not in ("average", "min", "max"):
            raise ValidationAppError("calc_method phải là average/min/max.")
    elif payload.component_ids:
        raise ValidationAppError("Manual Rate không có benchmark thành phần.")

    before = {"name": rate.name, "calc_method": rate.calc_method}
    rate.name = payload.name
    if rate.rate_type == "calculated":
        rate.calc_method = payload.calc_method
        db.query(ReferenceRateComponent).filter(ReferenceRateComponent.reference_rate_id == rate.id).delete()
        db.flush()
        for cid in payload.component_ids:
            db.add(ReferenceRateComponent(reference_rate_id=rate.id, component_rate_id=cid))
    rate.updated_by = user.id

    record_field_changes(
        db, user_id=user.id, module=MODULE, record_id=rate.id,
        before=before, after={"name": rate.name, "calc_method": rate.calc_method},
    )
    db.commit()
    db.refresh(rate)
    return svc.to_dict(db.get(ReferenceRate, rate.id))


@router.delete("/{rate_id}")
def delete_rate(rate_id: str, db: DbSession, user: ManagerUp):
    rate = db.get(ReferenceRate, rate_id)
    if not rate:
        raise NotFoundError("Không tìm thấy benchmark.")
    if svc.is_referenced(db, rate_id):
        raise ValidationAppError("Benchmark đang được dùng bởi trái phiếu hoặc benchmark tính toán khác, không thể xóa.")
    record_delete(db, user_id=user.id, module=MODULE, record_id=rate.id, snapshot={"name": rate.name})
    db.delete(rate)
    db.commit()
    return {"ok": True}


@router.put("/{rate_id}/monthly/{month_key}", response_model=ReferenceRateOut)
def set_monthly_value(rate_id: str, month_key: str, payload: SetMonthlyValueRequest, db: DbSession, user: StaffUp):
    rate = db.get(ReferenceRate, rate_id)
    if not rate:
        raise NotFoundError("Không tìm thấy benchmark.")
    if rate.rate_type != "manual":
        raise ValidationAppError("Chỉ Manual Rate mới nhập giá trị theo tháng trực tiếp.")
    if not is_valid_month_key(month_key):
        raise ValidationAppError("month_key không hợp lệ, cần dạng YYYY-MM.")

    existing = (
        db.query(ReferenceRateMonthlyValue)
        .filter(ReferenceRateMonthlyValue.reference_rate_id == rate_id, ReferenceRateMonthlyValue.month_key == month_key)
        .first()
    )
    if existing:
        check_version(existing.version, payload.version if payload.version is not None else -1)
        existing.rate = payload.rate
        existing.updated_by = user.id
    else:
        if payload.version is not None:
            raise ValidationAppError("Ô này chưa có dữ liệu; không thể gửi version.")
        db.add(ReferenceRateMonthlyValue(reference_rate_id=rate_id, month_key=month_key, rate=payload.rate, updated_by=user.id))

    db.commit()
    db.refresh(rate)
    return svc.to_dict(db.get(ReferenceRate, rate_id))
