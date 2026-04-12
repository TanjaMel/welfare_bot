from pydantic import BaseModel


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    language: str
    phone_number: str


class UserRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    language: str
    phone_number: str