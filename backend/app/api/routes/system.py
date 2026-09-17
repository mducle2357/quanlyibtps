import json
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_manager_up
from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.models.audit import SystemSetting
from app.models.user import User
from app.schemas.system import TimelineRange
from app.services.dates import is_valid_month_key, ym_diff

router = APIRouter(prefix="/system", tags=["system"])
ManagerUp = Annotated[User, Depends(require_manager_up)]
settings = get_settings()

TIMELINE_KEYS = {
    "monthly": "timeline_monthly",
    "weekly": "timeline_weekly",
}


def _default_range(kind: str) -> TimelineRange:
    if kind == "weekly":
        start = settings.default_weekly_start
    else:
        start = settings.default_timeline_start
    from app.services.dates import ym_add

    return TimelineRange(start=start, end=ym_add(start, 23))  # 2 years of headroom by default


@router.get("/timeline/{kind}", response_model=TimelineRange)
def get_timeline(kind: str, db: DbSession, _user: CurrentUser):
    if kind not in TIMELINE_KEYS:
        raise ValidationAppError("kind phải là 'monthly' hoặc 'weekly'.")
    row = db.get(SystemSetting, TIMELINE_KEYS[kind])
    if not row:
        return _default_range(kind)
    data = json.loads(row.value)
    return TimelineRange(**data)


@router.put("/timeline/{kind}", response_model=TimelineRange)
def set_timeline(kind: str, payload: TimelineRange, db: DbSession, user: ManagerUp):
    if kind not in TIMELINE_KEYS:
        raise ValidationAppError("kind phải là 'monthly' hoặc 'weekly'.")
    if not is_valid_month_key(payload.start) or not is_valid_month_key(payload.end):
        raise ValidationAppError("start/end phải theo dạng YYYY-MM.")
    if ym_diff(payload.start, payload.end) < 0:
        raise ValidationAppError("end phải sau hoặc bằng start.")
    key = TIMELINE_KEYS[kind]
    row = db.get(SystemSetting, key)
    value = json.dumps({"start": payload.start, "end": payload.end})
    if row:
        row.value = value
        row.updated_by = user.id
    else:
        db.add(SystemSetting(key=key, value=value, updated_by=user.id))
    db.commit()
    return payload
