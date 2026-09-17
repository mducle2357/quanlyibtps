from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPk

GROUP_CBTT = "cbtt"
GROUP_KTDK = "ktdk"

# Seeded once via migration; matches prompt §16 exactly. Not user-creatable —
# admins may still add ad-hoc checklist *items* per month via ComplianceChecklistEntry.
COMPLIANCE_ITEM_DEFS = [
    {"group": GROUP_CBTT, "key": "bctc_nam", "name": "BCTC năm"},
    {"group": GROUP_CBTT, "key": "bctc_bn", "name": "BCTC bán niên"},
    {"group": GROUP_CBTT, "key": "sd_von", "name": "BC tình hình sử dụng vốn"},
    {"group": GROUP_CBTT, "key": "goc_lai", "name": "BC tình hình thanh toán gốc lãi"},
    {"group": GROUP_CBTT, "key": "cam_ket", "name": "BC thực hiện cam kết với nhà đầu tư"},
    {"group": GROUP_KTDK, "key": "bbkt", "name": "BBKT sau đầu tư"},
    {"group": GROUP_KTDK, "key": "ubck", "name": "BC gửi UBCK (TV, DLPH, Đại diện)"},
    {"group": GROUP_KTDK, "key": "dinh_gia", "name": "Định giá TSBĐ"},
    {"group": GROUP_KTDK, "key": "cap_nhat_ls", "name": "Cập nhật LS"},
]


class ComplianceItem(Base, UUIDPk):
    __tablename__ = "compliance_items"

    group_key: Mapped[str] = mapped_column(String(20), nullable=False)
    item_key: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ComplianceChecklistEntry(Base, UUIDPk, TimestampMixin):
    """One checklist line for a bond/item/month; a month can hold several lines
    for the same item (prompt §16: 'cho phép có nhiều checklist item')."""

    __tablename__ = "compliance_checklist_entries"

    bond_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("bonds.id", ondelete="CASCADE"))
    compliance_item_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("compliance_items.id"))
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("ix_compliance_bond_month", "bond_id", "month_key"),
        Index("ix_compliance_item_month", "compliance_item_id", "month_key"),
    )
