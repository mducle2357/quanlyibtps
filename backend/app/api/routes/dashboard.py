from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_staff_up
from app.core.errors import ValidationAppError
from app.models.user import User
from app.models.weekly import EquityMonthlyValue
from app.schemas.dashboard import Alert, DashboardResponse, EquityValueSet
from app.services.concurrency import check_version
from app.services.dashboard_service import get_alerts, get_dashboard
from app.services.dates import is_valid_month_key

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
StaffUp = Annotated[User, Depends(require_staff_up)]


@router.get("/{month_key}", response_model=DashboardResponse)
def dashboard(month_key: str, db: DbSession, _user: CurrentUser):
    if not is_valid_month_key(month_key):
        raise ValidationAppError("month_key phải theo dạng YYYY-MM.")
    return get_dashboard(db, month_key)


@router.get("/alerts/upcoming", response_model=list[Alert])
def alerts(db: DbSession, _user: CurrentUser):
    return get_alerts(db)


@router.put("/equity/{month_key}", response_model=dict)
def set_equity(month_key: str, payload: EquityValueSet, db: DbSession, user: StaffUp):
    if not is_valid_month_key(month_key):
        raise ValidationAppError("month_key phải theo dạng YYYY-MM.")
    row = db.query(EquityMonthlyValue).filter(EquityMonthlyValue.month_key == month_key).first()
    if row:
        check_version(row.version, payload.version if payload.version is not None else -1)
        row.value = payload.value
        row.updated_by = user.id
    else:
        if payload.version is not None:
            raise ValidationAppError("Tháng này chưa có dữ liệu; không thể gửi version.")
        db.add(EquityMonthlyValue(month_key=month_key, value=payload.value, updated_by=user.id))
    db.commit()
    row = db.query(EquityMonthlyValue).filter(EquityMonthlyValue.month_key == month_key).first()
    return {"month_key": month_key, "value": float(row.value), "version": row.version}


@router.get("/equity/{month_key}", response_model=dict)
def get_equity(month_key: str, db: DbSession, _user: CurrentUser):
    row = db.query(EquityMonthlyValue).filter(EquityMonthlyValue.month_key == month_key).first()
    if not row:
        return {"month_key": month_key, "value": None, "version": None}
    return {"month_key": month_key, "value": float(row.value), "version": row.version}
