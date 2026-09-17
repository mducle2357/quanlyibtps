from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_staff_up
from app.core.errors import ValidationAppError
from app.models.bond import Bond
from app.models.user import User
from app.models.weekly import WeeklyPortfolioValue
from app.schemas.weekly import CarryForwardRequest, WeeklyGridResponse, WeeklyResponse, WeeklyVolumeSet
from app.services.concurrency import check_version
from app.services.dates import is_valid_week_key
from app.services.weekly_service import carry_forward, get_week, get_week_range

router = APIRouter(prefix="/weekly", tags=["weekly"])
StaffUp = Annotated[User, Depends(require_staff_up)]


@router.get("", response_model=WeeklyGridResponse)
def weekly_grid(db: DbSession, _user: CurrentUser, start: str, end: str):
    if not is_valid_week_key(start) or not is_valid_week_key(end):
        raise ValidationAppError("start/end phải theo dạng YYYY-MM-Wn.")
    if start > end:
        raise ValidationAppError("end phải sau hoặc bằng start.")
    return get_week_range(db, start, end)


@router.get("/{week_key}", response_model=WeeklyResponse)
def weekly(week_key: str, db: DbSession, _user: CurrentUser):
    if not is_valid_week_key(week_key):
        raise ValidationAppError("week_key phải theo dạng YYYY-MM-Wn.")
    return get_week(db, week_key)


@router.put("/{week_key}/bonds/{bond_id}", response_model=WeeklyResponse)
def set_volume(week_key: str, bond_id: str, payload: WeeklyVolumeSet, db: DbSession, user: StaffUp):
    if not is_valid_week_key(week_key):
        raise ValidationAppError("week_key phải theo dạng YYYY-MM-Wn.")
    if not db.get(Bond, bond_id):
        raise ValidationAppError("Không tìm thấy trái phiếu.")
    existing = (
        db.query(WeeklyPortfolioValue)
        .filter(WeeklyPortfolioValue.bond_id == bond_id, WeeklyPortfolioValue.week_key == week_key)
        .first()
    )
    if existing:
        check_version(existing.version, payload.version if payload.version is not None else -1)
        existing.volume = payload.volume
        existing.updated_by = user.id
    else:
        if payload.version is not None:
            raise ValidationAppError("Tuần này chưa có dữ liệu; không thể gửi version.")
        db.add(WeeklyPortfolioValue(bond_id=bond_id, week_key=week_key, volume=payload.volume, updated_by=user.id))
    db.commit()
    return get_week(db, week_key)


@router.post("/carry-forward", response_model=WeeklyResponse)
def carry_forward_endpoint(payload: CarryForwardRequest, db: DbSession, user: StaffUp):
    if not is_valid_week_key(payload.from_week) or not is_valid_week_key(payload.to_week):
        raise ValidationAppError("week_key phải theo dạng YYYY-MM-Wn.")
    carry_forward(db, payload.from_week, payload.to_week, user.id)
    db.commit()
    return get_week(db, payload.to_week)
