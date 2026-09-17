from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession
from app.core.limiter import limiter
from app.schemas.auth import CurrentUser as CurrentUserOut
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: DbSession):
    user = auth_service.authenticate(db, payload.email, payload.password)
    access, refresh = auth_service.issue_tokens(db, user)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DbSession):
    access, refresh_token = auth_service.rotate_refresh_token(db, payload.refresh_token)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.post("/logout")
def logout(payload: RefreshRequest, db: DbSession):
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=CurrentUserOut)
def me(user: CurrentUser):
    return CurrentUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=user.role_names(),
        must_reset_password=user.must_reset_password,
    )
