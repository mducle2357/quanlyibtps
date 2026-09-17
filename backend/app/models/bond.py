from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPk

RATE_FIXED = "fixed"
RATE_FLOATING = "floating"
RATE_COMBINED = "combined"
RATE_CONDITIONAL = "conditional"
RATE_TYPES = [RATE_FIXED, RATE_FLOATING, RATE_COMBINED, RATE_CONDITIONAL]

# 6 fee types are fixed by the business (prompt §13) — modelled as a Python constant
# rather than a lookup table, since they are not user-creatable/deletable.
FEE_ADVISORY = "advisory"
FEE_ISSUING = "issuing"
FEE_CUSTODY = "custody"
FEE_NSHTP = "nshtp"
FEE_COLLATERAL = "collateral"
FEE_OTHER = "other"

METHOD_ONCE = "once"
METHOD_ACTUAL = "actual"
METHOD_FLAT = "flat"

FEE_DEFS = [
    {
        "key": FEE_ADVISORY, "name": "Phí tư vấn phát hành", "base": "advised", "methods": [METHOD_ONCE],
        "basis": "Tính trên 1.1 Khối lượng tư vấn",
    },
    {
        "key": FEE_ISSUING, "name": "Phí đại lý phát hành", "base": "advised", "methods": [METHOD_ONCE],
        "basis": "Tính trên 1.1 Khối lượng tư vấn",
    },
    {
        "key": FEE_CUSTODY, "name": "Phí đại lý lưu ký", "base": "outstanding", "methods": [METHOD_ACTUAL, METHOD_FLAT],
        "basis": "Tính trên Khối lượng lưu hành",
    },
    {
        "key": FEE_NSHTP, "name": "Phí đại diện NSHTP", "base": "outstanding", "methods": [METHOD_ACTUAL, METHOD_FLAT],
        "basis": "Tính trên Khối lượng lưu hành",
    },
    {
        "key": FEE_COLLATERAL,
        "name": "Phí quản lý TSBĐ",
        "base": "outstanding",
        "methods": [METHOD_ACTUAL, METHOD_FLAT],
        "basis": "Tính trên Khối lượng lưu hành",
    },
    {
        "key": FEE_OTHER, "name": "Phí khác (thu xếp vốn)", "base": "invested", "methods": [METHOD_ONCE],
        "basis": "Tính trên 1.2 Khối lượng đầu tư",
    },
]
FEE_KEYS = [f["key"] for f in FEE_DEFS]


class Bond(Base, UUIDPk, TimestampMixin):
    """Internal id is permanent; `code` is the renameable display/business key (prompt 1.3, 8.1)."""

    __tablename__ = "bonds"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_fee_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pay_freq_months: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    xhtn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    par_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=100)  # triệu đồng

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    interest_config: Mapped["BondInterestConfig | None"] = relationship(
        back_populates="bond", uselist=False, cascade="all, delete-orphan"
    )
    monthly_data: Mapped[list["BondMonthlyData"]] = relationship(back_populates="bond", cascade="all, delete-orphan")
    fee_configs: Mapped[list["BondFeeConfig"]] = relationship(back_populates="bond", cascade="all, delete-orphan")


class BondInterestConfig(Base, UUIDPk):
    __tablename__ = "bond_interest_config"

    bond_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bonds.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    rate_type: Mapped[str] = mapped_column(String(20), nullable=False, default=RATE_FIXED)
    fixed_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    spread: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    reference_rate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("reference_rates.id"), nullable=True
    )
    first4_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    floor_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    cap_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    bond: Mapped[Bond] = relationship(back_populates="interest_config")


class BondMonthlyData(Base, UUIDPk, TimestampMixin):
    """One row per bond per month: manual volumes + optional holding-period override (prompt 12, 15.2)."""

    __tablename__ = "bond_monthly_data"

    bond_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("bonds.id", ondelete="CASCADE"))
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)

    advised_volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    buyback_volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    invested_volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    sold_volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)

    hold_start_override: Mapped[date | None] = mapped_column(Date, nullable=True)
    hold_end_override: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    bond: Mapped[Bond] = relationship(back_populates="monthly_data")

    __table_args__ = (UniqueConstraint("bond_id", "month_key", name="uq_bond_month"),)


class BondFeeConfig(Base, UUIDPk, TimestampMixin):
    """One row per bond per fee type (fixed set of 6). Rate here is the *default*
    rate; time-varying rates are layered on top via BondFeeRatePeriod (prompt 13.1)."""

    __tablename__ = "bond_fee_configs"

    bond_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("bonds.id", ondelete="CASCADE"))
    fee_type_key: Mapped[str] = mapped_column(String(30), nullable=False)
    default_rate: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False, default=0)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    recognition_month: Mapped[str | None] = mapped_column(String(7), nullable=True)  # for method=once
    freq_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    timing: Mapped[str] = mapped_column(String(10), nullable=False, default="end")  # begin|end of period

    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    bond: Mapped[Bond] = relationship(back_populates="fee_configs")
    rate_periods: Mapped[list["BondFeeRatePeriod"]] = relationship(
        back_populates="fee_config", cascade="all, delete-orphan", order_by="BondFeeRatePeriod.effective_from"
    )

    __table_args__ = (UniqueConstraint("bond_id", "fee_type_key", name="uq_bond_fee_type"),)


class BondFeeRatePeriod(Base, UUIDPk):
    """A step in the fee-rate schedule: rate `fee_rate` applies from `effective_from`
    up to (but not including) the next period's start, or `effective_to` if set."""

    __tablename__ = "bond_fee_rate_periods"

    bond_fee_config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("bond_fee_configs.id", ondelete="CASCADE")
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    fee_rate: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    # Kept for schema fidelity with the suggested data model (prompt §29). The engine
    # applies the parent BondFeeConfig.method uniformly for a fee type (prompt §13.2
    # ties method to fee *type*, not to a time slice) — see README "Assumptions".
    calculation_method: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    fee_config: Mapped[BondFeeConfig] = relationship(back_populates="rate_periods")
