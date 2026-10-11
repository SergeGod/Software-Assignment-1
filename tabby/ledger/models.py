"""Request and response shapes for the ledger API (validated by Pydantic)."""

from typing import Literal

from pydantic import BaseModel, Field

from tabby.accounts.models import UserOut


class CategoryOut(BaseModel):
    id: int
    name: str


class SpendingOut(BaseModel):
    category_id: int
    name: str
    total_cents: int


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    member_ids: list[int] = []


class MemberIn(BaseModel):
    user_id: int


class GroupOut(BaseModel):
    id: int
    name: str
    created_at: str


class GroupDetailOut(GroupOut):
    members: list[UserOut]


class Participant(BaseModel):
    user_id: int
    # Ignored for 'equal', a weight for 'shares', cents owed for 'exact'.
    value: int = Field(default=1, ge=0)


class ExpenseIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, le=100_000_000)
    payer_id: int
    split_type: Literal["equal", "shares", "exact"]
    category_id: int
    participants: list[Participant] = Field(min_length=1)


class ExpenseOut(BaseModel):
    id: int
    payer_id: int
    description: str
    amount_cents: int
    split_type: str
    category_id: int
    created_at: str
    shares: dict[int, int]
