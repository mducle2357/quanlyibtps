from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPk

STATUS_DRAFT = "Dự thảo"
STATUS_ONGOING = "Ongoing"
STATUS_DONE = "Done"
STATUS_DENIED = "Denied"
CONTRACT_STATUSES = [STATUS_DRAFT, STATUS_ONGOING, STATUS_DONE, STATUS_DENIED]


class ContractProject(Base, UUIDPk, TimestampMixin):
    """Level-1 row in Sổ Hợp đồng, numbered with Roman numerals in the UI (prompt §19)."""

    __tablename__ = "contracts_projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    contracts: Mapped[list["Contract"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Contract(Base, UUIDPk, TimestampMixin):
    """Level-2 row (an individual contract under a project)."""

    __tablename__ = "contracts"

    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("contracts_projects.id", ondelete="CASCADE"))
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    parties: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    project: Mapped[ContractProject] = relationship(back_populates="contracts")
