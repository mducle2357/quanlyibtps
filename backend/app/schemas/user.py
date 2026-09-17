from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(min_length=1)


class UserUpdateRoles(BaseModel):
    roles: list[str] = Field(min_length=1)


class UserSetActive(BaseModel):
    is_active: bool


class AdminResetPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    must_reset_password: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
