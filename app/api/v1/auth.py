from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.models.account import Account
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.services.accounts import generate_account_number
from app.services.audit import log_action
from app.services.auth import (
    AccountLockedError,
    DuplicateEmailError,
    InvalidCredentialsError,
    PasswordPolicyError,
    authenticate_user,
    register_user,
)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    try:
        with db.begin():
            user = register_user(
                db,
                email=payload.email,
                full_name=payload.full_name,
                password=payload.password,
            )

            # Create default Savings account (BAN-10). Must be in same transaction.
            acct = Account(
                user_id=user.id,
                name="Savings",
                account_number=generate_account_number(),
                balance=Decimal("0.00"),
            )
            db.add(acct)

            log_action(db, action="register_success", user_id=user.id, request=request)

        return RegisterResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            account_number=acct.account_number,
        )

    except PasswordPolicyError as e:
        with db.begin():
            log_action(db, action="register_failure", user_id=None, request=request, details=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    except DuplicateEmailError as e:
        with db.begin():
            log_action(
                db,
                action="register_failure",
                user_id=None,
                request=request,
                details="duplicate_email",
            )
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = authenticate_user(
            db,
            email=payload.email,
            password=payload.password,
            request=request,
        )
        db.commit()

        return TokenResponse(access_token=create_access_token(str(user.id)))

    except AccountLockedError:
        db.rollback()
        raise HTTPException(status_code=423, detail="Account locked")

    except InvalidCredentialsError:
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
def logout() -> dict:
    # JWT-only MVP: client discards token.
    return {"logged_out": True}
