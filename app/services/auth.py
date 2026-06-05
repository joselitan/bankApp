from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, is_password_valid, verify_password
from app.models.user import User
from app.services.audit import log_action

LOCKOUT_THRESHOLD = 3
LOCKOUT_MINUTES = 10


class DuplicateEmailError(Exception):
    pass


class PasswordPolicyError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AccountLockedError(Exception):
    pass


def register_user(db: Session, *, email: str, full_name: str, password: str) -> User:
    if not is_password_valid(password):
        raise PasswordPolicyError(
            "Password must be at least 8 characters and include at least 1 digit "
            "and 1 special character."
        )

    u = User(email=email.lower(), full_name=full_name, password_hash=hash_password(password))
    db.add(u)
    try:
        db.flush()  # assigns id; may raise on unique constraint
    except IntegrityError as e:
        raise DuplicateEmailError("email already exists") from e
    return u


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    request: Request | None = None,
) -> User:
    email_norm = email.lower()
    user = db.scalar(select(User).where(User.email == email_norm))

    # Generic error to avoid leaking existence
    generic = InvalidCredentialsError("invalid credentials")

    if user is None:
        # Log as unknown user_id
        if request is not None:
            log_action(
                db,
                action="login_failure",
                user_id=None,
                request=request,
                details=f"email={email_norm}",
            )
        raise generic

    # Use naive UTC timestamps for SQLite compatibility.
    now = datetime.utcnow()
    if user.locked_until is not None and user.locked_until > now:
        if request is not None:
            log_action(db, action="login_locked", user_id=user.id, request=request)
        raise AccountLockedError("account locked")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            # Lock is effective for subsequent attempts (4th+); keep 3rd as generic invalid creds.
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)

        # Persist counters/lock within the current transaction scope.
        db.add(user)
        db.flush()

        if request is not None:
            log_action(db, action="login_failure", user_id=user.id, request=request)

        # If lockout was triggered, the *next* attempt should be blocked.
        raise generic

    # success
    user.failed_login_attempts = 0
    user.locked_until = None
    if request is not None:
        log_action(db, action="login_success", user_id=user.id, request=request)

    return user
