from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPk

RATE_TYPE_MANUAL = "manual"
RATE_TYPE_CALCULATED = "calculated"

CALC_METHOD_AVERAGE = "average"
CALC_METHOD_MIN = "min"
CALC_METHOD_MAX = "max"


class ReferenceRate(Base, UUIDPk, TimestampMixin):
    """A benchmark row on the Control tab (prompt 17). GROUP A = manual, GROUP B = calculated."""

    __tablename__ = "reference_rates"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(20), nullable=False)
    calc_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # only for calculated
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    components: Mapped[list["ReferenceRateComponent"]] = relationship(
        foreign_keys="ReferenceRateComponent.reference_rate_id",
        back_populates="reference_rate",
        cascade="all, delete-orphan",
    )
    monthly_values: Mapped[list["ReferenceRateMonthlyValue"]] = relationship(
        back_populates="reference_rate", cascade="all, delete-orphan"
    )


class ReferenceRateComponent(Base, UUIDPk):
    """One component benchmark feeding into a calculated rate (prompt 17.2)."""

    __tablename__ = "reference_rate_components"

    reference_rate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reference_rates.id", ondelete="CASCADE"), nullable=False
    )
    component_rate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reference_rates.id", ondelete="RESTRICT"), nullable=False
    )

    reference_rate: Mapped[ReferenceRate] = relationship(foreign_keys=[reference_rate_id])

    __table_args__ = (UniqueConstraint("reference_rate_id", "component_rate_id", name="uq_ref_rate_component"),)


class ReferenceRateMonthlyValue(Base, UUIDPk):
    __tablename__ = "reference_rate_monthly_values"

    reference_rate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reference_rates.id", ondelete="CASCADE"), nullable=False
    )
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    reference_rate: Mapped[ReferenceRate] = relationship(back_populates="monthly_values")

    __table_args__ = (
        UniqueConstraint("reference_rate_id", "month_key", name="uq_ref_rate_month"),
    )
