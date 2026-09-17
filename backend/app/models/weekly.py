from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import UUIDPk


class WeeklyPortfolioValue(Base, UUIDPk):
    """Manually entered weekly volume for a bond (prompt §21.3). week_key is
    'YYYY-MM-Wn', sortable as a string within a month because n stays single-digit
    (max 5 weeks/month) — validated in the service layer, not the DB."""

    __tablename__ = "weekly_portfolio_values"

    bond_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("bonds.id", ondelete="CASCADE"))
    week_key: Mapped[str] = mapped_column(String(10), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (UniqueConstraint("bond_id", "week_key", name="uq_weekly_bond_week"),)


class EquityMonthlyValue(Base, UUIDPk):
    """TPS's own equity per month (prompt §18.1), used for the 70% portfolio limit."""

    __tablename__ = "equity_monthly_values"

    month_key: Mapped[str] = mapped_column(String(7), unique=True, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
