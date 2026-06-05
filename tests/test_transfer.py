from __future__ import annotations

from fastapi.testclient import TestClient


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


def _login(client: TestClient, email: str) -> str:
    r = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "Passw0rd!",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _deposit(client: TestClient, token: str, amount: str) -> None:
    r = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": amount},
    )
    assert r.status_code == 201, r.text


def _me(client: TestClient, token: str) -> dict:
    r = client.get(
        "/api/accounts/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_transfer_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/api/transactions/transfer",
        json={"to_email": "b@example.com", "amount": "1.00"},
    )
    assert r.status_code == 401


def test_transfer_happy_path_moves_money(client: TestClient) -> None:
    _register(client, "a@example.com")
    _register(client, "b@example.com")

    token_a = _login(client, "a@example.com")
    token_b = _login(client, "b@example.com")

    _deposit(client, token_a, "100.00")

    r = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"to_email": "b@example.com", "amount": "25.50"},
    )
    assert r.status_code == 201, r.text

    a = _me(client, token_a)
    b = _me(client, token_b)
    assert a["balance"] == "74.50"
    assert b["balance"] == "25.50"


def test_transfer_rejects_self_transfer(client: TestClient) -> None:
    _register(client, "self@example.com")
    token = _login(client, "self@example.com")
    _deposit(client, token, "10.00")

    r = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token}"},
        json={"to_email": "self@example.com", "amount": "1.00"},
    )
    assert r.status_code == 400

    me = _me(client, token)
    assert me["balance"] == "10.00"


def test_transfer_rejects_unknown_recipient(client: TestClient) -> None:
    _register(client, "sender@example.com")
    token = _login(client, "sender@example.com")
    _deposit(client, token, "10.00")

    r = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token}"},
        json={"to_email": "nosuch@example.com", "amount": "1.00"},
    )
    assert r.status_code == 400

    me = _me(client, token)
    assert me["balance"] == "10.00"


def test_transfer_rejects_insufficient_funds_and_does_not_move_money(client: TestClient) -> None:
    _register(client, "low@example.com")
    _register(client, "recv@example.com")

    token_low = _login(client, "low@example.com")
    token_recv = _login(client, "recv@example.com")

    # No deposit for low funds user
    r = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token_low}"},
        json={"to_email": "recv@example.com", "amount": "5.00"},
    )
    assert r.status_code == 400

    low = _me(client, token_low)
    recv = _me(client, token_recv)
    assert low["balance"] == "0.00"
    assert recv["balance"] == "0.00"


def test_transfer_daily_limit_enforced_and_atomic(client: TestClient) -> None:
    _register(client, "limit@example.com")
    _register(client, "sink@example.com")

    token_a = _login(client, "limit@example.com")
    token_b = _login(client, "sink@example.com")

    # Put enough funds to exceed daily limit.
    _deposit(client, token_a, "6000.00")

    # First transfer within limit.
    ok = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"to_email": "sink@example.com", "amount": "4000.00"},
    )
    assert ok.status_code == 201, ok.text

    # Second transfer would exceed daily 5000.00 limit.
    blocked = client.post(
        "/api/transactions/transfer",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"to_email": "sink@example.com", "amount": "1500.01"},
    )
    assert blocked.status_code == 400

    # Assert atomicity: balances reflect only the first transfer.
    a = _me(client, token_a)
    b = _me(client, token_b)
    assert a["balance"] == "2000.00"
    assert b["balance"] == "4000.00"
