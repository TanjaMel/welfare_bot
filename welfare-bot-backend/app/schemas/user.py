from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    first_name: str
    last_name: str
    language: str
    phone_number: str


class UserCreate(UserBase):
    pass


class UserRegister(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    language: str = "fi"
    email: str
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    email: str
    password: str


class UserRead(UserBase):
    id: int
    email: str | None = None
    role: str = "user"
    timezone: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead