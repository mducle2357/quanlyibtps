from datetime import date, datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    user_email: str | None
    timestamp: datetime
    module: str
    record_id: str
    field: str | None
    old_value: str | None
    new_value: str | None
    action: str


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class AuditLogFilter(BaseModel):
    user_id: str | None = None
    module: str | None = None
    action: str | None = None
    date_from: date | None = None
    date_to: date | None = None
