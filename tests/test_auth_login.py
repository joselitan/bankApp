from __future__ import annotations


def _register(client, email: str, password: str = "Passw0rd!"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "User", "password": password},
    )


def test_login_happy_path_returns_token(client) -> None:
    r = _register(client, "login@example.com")
    assert r.status_code == 201

    r2 = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "Passw0rd!"},
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_lockout_after_3_failures(client) -> None:
    r = _register(client, "lock@example.com")
    assert r.status_code == 201

    for _ in range(3):
        bad = client.post(
            "/api/auth/login",
            json={"email": "lock@example.com", "password": "wrongpass!1"},
        )
        assert bad.status_code == 401

    # 4th attempt in lockout window should be blocked
    locked = client.post(
        "/api/auth/login",
        json={"email": "lock@example.com", "password": "wrongpass!1"},
    )
    assert locked.status_code == 423, locked.text

    # Still locked even with correct password (during window)
    ok = client.post("/api/auth/login", json={"email": "lock@example.com", "password": "Passw0rd!"})
    assert ok.status_code == 423


def test_me_requires_auth(client) -> None:
    r = client.get("/api/accounts/me")
    assert r.status_code == 401
