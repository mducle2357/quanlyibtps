"""seed roles and compliance items

Revision ID: 7ace0c07f7eb
Revises: abd3f5da62d6
Create Date: 2026-09-17 08:37:01.583602

"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "7ace0c07f7eb"
down_revision = "abd3f5da62d6"
branch_labels = None
depends_on = None

ROLES = [
    ("Admin", "Toàn quyền hệ thống; user/role; backup/restore; reset; cấu hình."),
    ("Manager", "Xem và sửa dữ liệu nghiệp vụ; xem audit; quản trị phần lớn nội dung."),
    ("Staff", "Nhập/sửa dữ liệu nghiệp vụ theo phạm vi được cấp."),
    ("Viewer", "Chỉ xem và export; không sửa."),
]

COMPLIANCE_ITEMS = [
    ("cbtt", "bctc_nam", "BCTC năm", 1),
    ("cbtt", "bctc_bn", "BCTC bán niên", 2),
    ("cbtt", "sd_von", "BC tình hình sử dụng vốn", 3),
    ("cbtt", "goc_lai", "BC tình hình thanh toán gốc lãi", 4),
    ("cbtt", "cam_ket", "BC thực hiện cam kết với nhà đầu tư", 5),
    ("ktdk", "bbkt", "BBKT sau đầu tư", 6),
    ("ktdk", "ubck", "BC gửi UBCK (TV, DLPH, Đại diện)", 7),
    ("ktdk", "dinh_gia", "Định giá TSBĐ", 8),
    ("ktdk", "cap_nhat_ls", "Cập nhật LS", 9),
]

roles_table = sa.table(
    "roles",
    sa.column("id", UUID(as_uuid=False)),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
)
compliance_table = sa.table(
    "compliance_items",
    sa.column("id", UUID(as_uuid=False)),
    sa.column("group_key", sa.String),
    sa.column("item_key", sa.String),
    sa.column("name", sa.String),
    sa.column("sort_order", sa.Integer),
)


def upgrade() -> None:
    op.bulk_insert(
        roles_table,
        [{"id": str(uuid.uuid4()), "name": name, "description": desc} for name, desc in ROLES],
    )
    op.bulk_insert(
        compliance_table,
        [
            {"id": str(uuid.uuid4()), "group_key": g, "item_key": k, "name": n, "sort_order": o}
            for g, k, n, o in COMPLIANCE_ITEMS
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM compliance_items")
    op.execute("DELETE FROM roles")
