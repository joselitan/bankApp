from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.accounts import AccountMeResponse, TransactionOut

router = APIRouter()


@router.get("/me", response_model=AccountMeResponse)
def get_my_account(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccountMeResponse:
    acct = db.scalar(select(Account).where(Account.user_id == user.id))
    # For MVP assumptions: exactly one account.
    if acct is None:
        raise HTTPException(status_code=404, detail="Account not found")

    txns = (
        db.execute(
            select(Transaction)
            .where(Transaction.account_id == acct.id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    return AccountMeResponse(
        account_number=acct.account_number,
        balance=acct.balance,
        recent_transactions=[
            TransactionOut(
                type=t.type,
                amount=t.amount,
                created_at=t.created_at,
                description=t.description,
            )
            for t in txns
        ],
    )
