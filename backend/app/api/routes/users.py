from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_admin
from app.core.errors import NotFoundError, ValidationAppError
from app.core.security import hash_password, verify_password
from app.models.user import ALL_ROLES, Role, User, UserRole
from app.schemas.user import (
    AdminResetPassword,
    ChangePassword,
    UserCreate,
    UserOut,
    UserSetActive,
    UserUpdateRoles,
)
from app.services.audit_service import record_create, record_field_changes

router = APIRouter(prefix="/users", tags=["users"])
Admin = Annotated[User, Depends(require_admin)]
MODULE = "users"


def _roles_by_name(db: DbSession, names: list[str]) -> list[Role]:
    invalid = set(names) - set(ALL_ROLES)
    if invalid:
        raise ValidationAppError(f"Role không hợp lệ: {', '.join(invalid)}")
    return db.query(Role).filter(Role.name.in_(names)).all()


def _get_or_404(db: DbSession, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("Không tìm thấy người dùng.")
    return user


def _out(user: User) -> UserOut:
    # Not model_validate(user): the ORM's `roles` relationship (list[UserRole])
    # has the same attribute name as the schema's `roles: list[str]` field, so
    # from_attributes would try to validate UserRole objects as strings.
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=user.role_names(),
        must_reset_password=user.must_reset_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession, _admin: Admin):
    users = db.query(User).order_by(User.created_at).all()
    return [_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: DbSession, admin: Admin):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise ValidationAppError("Email đã được sử dụng.")
    roles = _roles_by_name(db, payload.roles)
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        must_reset_password=True,
    )
    db.add(user)
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    record_create(db, user_id=admin.id, module=MODULE, record_id=user.id, snapshot={"email": user.email, "roles": payload.roles})
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/{user_id}/roles", response_model=UserOut)
def update_roles(user_id: str, payload: UserUpdateRoles, db: DbSession, admin: Admin):
    user = _get_or_404(db, user_id)
    before = sorted(user.role_names())
    roles = _roles_by_name(db, payload.roles)
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    record_field_changes(
        db, user_id=admin.id, module=MODULE, record_id=user.id,
        before={"roles": ",".join(before)}, after={"roles": ",".join(sorted(payload.roles))},
    )
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/{user_id}/active", response_model=UserOut)
def set_active(user_id: str, payload: UserSetActive, db: DbSession, admin: Admin):
    user = _get_or_404(db, user_id)
    before = user.is_active
    user.is_active = payload.is_active
    record_field_changes(
        db, user_id=admin.id, module=MODULE, record_id=user.id,
        before={"is_active": before}, after={"is_active": payload.is_active},
    )
    db.commit()
    db.refresh(user)
    return _out(user)


@router.post("/{user_id}/reset-password")
def admin_reset_password(user_id: str, payload: AdminResetPassword, db: DbSession, admin: Admin):
    user = _get_or_404(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = True
    record_field_changes(
        db, user_id=admin.id, module=MODULE, record_id=user.id,
        before={"password": "***"}, after={"password": "*** (reset by admin)"},
    )
    db.commit()
    return {"ok": True}


@router.post("/me/change-password")
def change_own_password(payload: ChangePassword, db: DbSession, user: CurrentUser):
    if not verify_password(payload.current_password, user.password_hash):
        raise ValidationAppError("Mật khẩu hiện tại không đúng.")
    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = False
    record_field_changes(
        db, user_id=user.id, module=MODULE, record_id=user.id,
        before={"password": "***"}, after={"password": "*** (self change)"},
    )
    db.commit()
    return {"ok": True}
