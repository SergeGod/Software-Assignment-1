"""Request and response shapes for the accounts API (validated by Pydantic)."""

from pydantic import BaseModel, Field


class SignUpIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LogInIn(BaseModel):
    username: str = Field(max_length=30)
    password: str = Field(max_length=128)


class FriendIn(BaseModel):
    username: str = Field(max_length=30)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
