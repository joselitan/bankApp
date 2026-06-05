from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session as session_module
from app.models.audit_log import AuditLog


def _register(client: TestClient, email: str) -> None:
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "Passw0rd!",
        },
    )
    assert r.status_code == 201, r.text


def _login(client: TestClient, email: str, password: str) -> TestClient:
    r = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    return r


def _audit_actions() -> list[str]:
    # Use the same SessionLocal that tests bind to a temp DB in conftest.
    with session_module.SessionLocal() as db:
        return [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id)).all()]


def test_audit_log_register_and_login_success(client: TestClient) -> None:
    _register(client, "audit1@example.com")
    r = _login(client, "audit1@example.com", "Passw0rd!")
    assert r.status_code == 200, r.text

    actions = _audit_actions()
    assert "register_success" in actions
    assert "login_success" in actions


def test_audit_log_login_failure_unknown_user(client: TestClient) -> None:
    r = _login(client, "nosuch@example.com", "Passw0rd!")
    assert r.status_code == 401

    actions = _audit_actions()
    assert "login_failure" in actions


def test_audit_log_deposit_and_transfer(client: TestClient) -> None:
    _register(client, "sender_audit@example.com")
    _register(client, "recv_audit@example.com")

    token_sender = _login(client, "sender_audit@example.com", "Passw0rd!").json()["access_token"]

    dep = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token_sender}"},
        json={"amount": "10.00"},
    )
    assert dep.status_code == 201, dep.text

    tr = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token_sender}"},
        json={"to_email": "recv_audit@example.com", "amount": "1.00"},
    )
    assert tr.status_code == 201, tr.text

    actions = _audit_actions()
    assert "deposit" in actions
    assert "transfer" in actions
