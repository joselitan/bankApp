from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionOut(BaseModel):
    type: str
    amount: Decimal
    created_at: datetime
    description: str | None = None


class AccountMeResponse(BaseModel):
    account_number: str
    balance: Decimal
    recent_transactions: list[TransactionOut]
