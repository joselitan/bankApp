from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transactions import DepositRequest, TransferRequest
from app.services.audit import log_action

router = APIRouter()

MIN_DEPOSIT = Decimal("1.00")
MAX_DEPOSIT = Decimal("10000.00")

MIN_TRANSFER = Decimal("0.01")
DAILY_TRANSFER_LIMIT = Decimal("5000.00")


def _get_my_account(db: Session, user_id: int) -> Account:
    acct = db.scalar(select(Account).where(Account.user_id == user_id))
    if acct is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return acct


@router.post("/deposit", status_code=201)
def deposit(
    payload: DepositRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    amount = payload.amount
    if amount < MIN_DEPOSIT:
        raise HTTPException(status_code=400, detail="Minimum deposit is 1.00")
    if amount > MAX_DEPOSIT:
        raise HTTPException(status_code=400, detail="Maximum deposit is 10000.00")

    try:
        acct = _get_my_account(db, user.id)
        acct.balance = (acct.balance or Decimal("0.00")) + amount
        db.add(Transaction(account_id=acct.id, type="deposit", amount=amount))
        log_action(db, action="deposit", user_id=user.id, request=request, amount=amount)
        db.commit()
        db.refresh(acct)
        return {"deposited": str(amount), "balance": str(acct.balance)}
    except Exception:
        db.rollback()
        raise


@router.post("/transfer", status_code=201)
def transfer(
    payload: TransferRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    amount = payload.amount
    if amount < MIN_TRANSFER:
        raise HTTPException(status_code=400, detail="Minimum transfer is 0.01")

    to_email = payload.to_email.lower().strip()

    try:
        sender = db.get(User, user.id)
        recipient = db.scalar(select(User).where(User.email == to_email))

        if recipient is None:
            log_action(
                db,
                action="transfer_failure",
                user_id=user.id,
                request=request,
                amount=amount,
                details="recipient_not_found",
            )
            raise HTTPException(status_code=400, detail="Invalid recipient")

        if recipient.id == sender.id:
            log_action(
                db,
                action="transfer_failure",
                user_id=user.id,
                request=request,
                amount=amount,
                details="self_transfer",
            )
            raise HTTPException(status_code=400, detail="Cannot transfer to self")

        sender_acct = _get_my_account(db, sender.id)
        recipient_acct = _get_my_account(db, recipient.id)

        if sender_acct.balance < amount:
            log_action(
                db,
                action="transfer_failure",
                user_id=user.id,
                request=request,
                amount=amount,
                details="insufficient_funds",
            )
            raise HTTPException(status_code=400, detail="Insufficient funds")

        # Daily outgoing limit (UTC day)
        today = datetime.now(timezone.utc).date().isoformat()
        outgoing_sum = (
            db.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(Transaction.account_id == sender_acct.id)
                .where(Transaction.type == "transfer_out")
                .where(func.date(Transaction.created_at) == today)
            )
            or 0
        )

        if Decimal(str(outgoing_sum)) + amount > DAILY_TRANSFER_LIMIT:
            log_action(
                db,
                action="transfer_failure",
                user_id=user.id,
                request=request,
                amount=amount,
                details="daily_limit",
            )
            raise HTTPException(status_code=400, detail="Daily transfer limit exceeded")

    # Atomic update (BAN-16): single commit at the end.
        sender_acct.balance -= amount
        recipient_acct.balance += amount

        db.add(
            Transaction(
                account_id=sender_acct.id,
                type="transfer_out",
                amount=amount,
                description=f"to={to_email}",
            )
        )
        db.add(
            Transaction(
                account_id=recipient_acct.id,
                type="transfer_in",
                amount=amount,
                description=f"from={sender.email}",
            )
        )

        log_action(
            db,
            action="transfer",
            user_id=user.id,
            request=request,
            amount=amount,
            details=f"to={to_email}",
        )
        db.commit()
        return {"transferred": str(amount), "to": to_email}
    except Exception:
        db.rollback()
        raise
