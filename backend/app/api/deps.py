from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Thiếu hoặc sai định dạng token xác thực.")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Token không hợp lệ hoặc đã hết hạn.")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise UnauthorizedError("Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: str) -> Callable[[CurrentUser], User]:
    def _dep(user: CurrentUser) -> User:
        if not set(user.role_names()) & set(allowed):
            raise ForbiddenError("Bạn không có quyền thực hiện thao tác này.")
        return user

    return _dep


# Convenience role gates matching the permission table in prompt §2.
require_admin = require_roles("Admin")
require_manager_up = require_roles("Admin", "Manager")
require_staff_up = require_roles("Admin", "Manager", "Staff")
require_any = require_roles("Admin", "Manager", "Staff", "Viewer")
