from __future__ import annotations

from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str = "dep@example.com") -> str:
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "Passw0rd!",
        },
    )
    assert r.status_code == 201, r.text

    r2 = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "Passw0rd!",
        },
    )
    assert r2.status_code == 200, r2.text
    return r2.json()["access_token"]


def test_deposit_requires_auth(client: TestClient) -> None:
    r = client.post("/api/transactions/deposit", json={"amount": "10.00"})
    assert r.status_code == 401


def test_deposit_minimum_boundary(client: TestClient) -> None:
    token = _register_and_login(client)

    too_small = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "0.99"},
    )
    assert too_small.status_code == 400

    min_ok = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1.00"},
    )
    assert min_ok.status_code == 201, min_ok.text
    assert min_ok.json()["balance"] == "1.00"


def test_deposit_maximum_boundary(client: TestClient) -> None:
    token = _register_and_login(client)

    max_ok = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "10000.00"},
    )
    assert max_ok.status_code == 201, max_ok.text

    too_big = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "10000.01"},
    )
    assert too_big.status_code == 400


def test_deposit_accumulates_balance(client: TestClient) -> None:
    token = _register_and_login(client)

    r1 = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "10.00"},
    )
    assert r1.status_code == 201
    assert r1.json()["balance"] == "10.00"

    r2 = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "0.50"},
    )
    assert r2.status_code == 400

    r3 = client.post(
        "/api/transactions/deposit",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "5.25"},
    )
    assert r3.status_code == 201
    assert r3.json()["balance"] == "15.25"
