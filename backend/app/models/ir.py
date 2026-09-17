from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPk


class IRJob(Base, UUIDPk, TimestampMixin):
    __tablename__ = "ir_jobs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    monthly_revenue: Mapped[list["IRMonthlyRevenue"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class IRMonthlyRevenue(Base, UUIDPk):
    __tablename__ = "ir_monthly_revenue"

    ir_job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("ir_jobs.id", ondelete="CASCADE"))
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)
    revenue: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    job: Mapped[IRJob] = relationship(back_populates="monthly_revenue")

    __table_args__ = (UniqueConstraint("ir_job_id", "month_key", name="uq_ir_job_month"),)
