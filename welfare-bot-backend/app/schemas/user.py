from __future__ import annotations
from pydantic import BaseModel

class UserBase(BaseModel):
    first_name: str
    last_name: str
    language: str
    phone_number: str


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int

    class Config:
        from_attributes = True  # ВАЖНО