import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPk:
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)


class TimestampMixin:
    """created_at/updated_at required on every business record (prompt 1.3).

    created_by/updated_by are declared per-model (not here) because SQLAlchemy's
    declarative mixins do not resolve ForeignKey("users.id") reliably across
    modules without an explicit column on each concrete class.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


MONTH_KEY_LEN = 7  # 'YYYY-MM'
WEEK_KEY_LEN = 10  # 'YYYY-MM-Wn'
