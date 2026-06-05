from __future__ import annotations

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str = "acct@example.com") -> None:
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "Passw0rd!",
        },
    )
    assert r.status_code == 201, r.text


def _login(client: TestClient, email: str = "acct@example.com") -> str:
    r = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "Passw0rd!",
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert token
    return token


def test_accounts_me_requires_auth(client: TestClient) -> None:
    r = client.get("/api/accounts/me")
    assert r.status_code == 401


def test_accounts_me_returns_account_number_and_balance(client: TestClient) -> None:
    _register(client)
    token = _login(client)

    r = client.get(
        "/api/accounts/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert "account_number" in data
    assert data["account_number"]

    assert data["balance"] == "0.00"
    assert data["recent_transactions"] == []


def test_accounts_me_includes_recent_transactions_after_deposit(client: TestClient) -> None:
    _register(client)
    token = _login(client)

    dep = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "25.50"},
    )
    assert dep.status_code == 201, dep.text

    r = client.get(
        "/api/accounts/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["balance"] == "25.50"
    txns = data["recent_transactions"]
    assert isinstance(txns, list)
    assert len(txns) >= 1

    t0 = txns[0]
    assert t0["type"] == "deposit"
    assert t0["amount"] == "25.50"
    assert "created_at" in t0
