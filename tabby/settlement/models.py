"""Request and response shapes for the settlement API (validated by Pydantic)."""

from pydantic import BaseModel, Field


class BalanceOut(BaseModel):
    user_id: int
    balance_cents: int  # positive: is owed money, negative: owes money


class TransferOut(BaseModel):
    from_user_id: int
    to_user_id: int
    amount_cents: int


class SettlementOut(BaseModel):
    balances: list[BalanceOut]
    transfers: list[TransferOut]


class PaymentIn(BaseModel):
    to_user_id: int
    amount_cents: int = Field(gt=0, le=100_000_000)


class PaymentOut(BaseModel):
    id: int
    from_user_id: int
    to_user_id: int
    amount_cents: int
    created_at: str
