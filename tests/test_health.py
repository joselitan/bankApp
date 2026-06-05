def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ping(client) -> None:
    r = client.get("/api/ping")
    assert r.status_code == 200
    assert r.json() == {"pong": True}
