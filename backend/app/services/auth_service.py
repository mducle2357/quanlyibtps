from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User

settings = get_settings()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    generic_error = "Email hoặc mật khẩu không đúng."
    if not user or user.sso_subject is not None:
        raise UnauthorizedError(generic_error)
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(generic_error)
    if not user.is_active:
        raise UnauthorizedError("Tài khoản đã bị vô hiệu hóa.")
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    roles = user.role_names()
    access = create_access_token(user.id, roles)
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
            created_at=datetime.now(timezone.utc),
        )
    )
    return access, refresh


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[str, str]:
    payload = decode_token(raw_refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Refresh token không hợp lệ hoặc đã hết hạn.")
    token_hash = hash_refresh_token(raw_refresh_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not stored or stored.revoked_at is not None or stored.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")
    user = db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.")
    stored.revoked_at = datetime.now(timezone.utc)
    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
