from decimal import Decimal

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class TransferRequest(BaseModel):
    to_email: str
    amount: Decimal = Field(gt=0)
