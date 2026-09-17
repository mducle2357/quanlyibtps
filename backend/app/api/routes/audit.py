from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_manager_up
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut, AuditLogPage

router = APIRouter(prefix="/audit-logs", tags=["audit"])
ManagerUp = Annotated[User, Depends(require_manager_up)]


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    db: DbSession,
    _user: ManagerUp,
    user_id: str | None = None,
    module: str | None = None,
    record_id: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, le=500, gt=0),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if module:
        q = q.filter(AuditLog.module == module)
    if record_id:
        q = q.filter(AuditLog.record_id == record_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if date_from:
        q = q.filter(AuditLog.timestamp >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        q = q.filter(AuditLog.timestamp <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))

    total = q.count()
    rows = q.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    user_ids = {r.user_id for r in rows if r.user_id}
    users = {u.id: u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    items = [
        AuditLogOut(
            id=r.id, user_id=r.user_id, user_email=users.get(r.user_id), timestamp=r.timestamp,
            module=r.module, record_id=r.record_id, field=r.field, old_value=r.old_value,
            new_value=r.new_value, action=r.action,
        )
        for r in rows
    ]
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset)
