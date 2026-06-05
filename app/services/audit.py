from __future__ import annotations

from decimal import Decimal

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    user_id: int | None,
    request: Request | None = None,
    amount: Decimal | None = None,
    details: str | None = None,
) -> None:
    ip = None
    if request is not None:
        # Best-effort; behind proxies you'd use X-Forwarded-For.
        ip = request.client.host if request.client else None

    db.add(
        AuditLog(
            action=action,
            user_id=user_id,
            amount=amount,
            ip_address=ip,
            details=details,
        )
    )
