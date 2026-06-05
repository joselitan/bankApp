from __future__ import annotations

from sqlalchemy import select

from app.db import session as session_module
from app.models.account import Account
from app.models.user import User


def test_register_success_creates_user_and_default_account(client) -> None:
    payload = {
        "email": "a@example.com",
        "full_name": "Alice A",
        "password": "Passw0rd!",
    }
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()

    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]
    assert "account_number" in data

    # Verify DB: 1 user, 1 savings account, hashed password stored
    db = session_module.SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == payload["email"]))
        assert user is not None
        assert user.password_hash != payload["password"]
        assert len(user.password_hash) > 20

        acct = db.scalar(select(Account).where(Account.user_id == user.id))
        assert acct is not None
        assert acct.name == "Savings"
        assert str(acct.balance) in {"0.00", "0"}
    finally:
        db.close()


def test_register_password_policy(client) -> None:
    payload = {
        "email": "b@example.com",
        "full_name": "Bob B",
        "password": "short",
    }
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 400
    assert "Password must be" in r.json()["detail"]


def test_register_duplicate_email(client) -> None:
    payload = {
        "email": "dup@example.com",
        "full_name": "Dup",
        "password": "Passw0rd!",
    }
    r1 = client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409
