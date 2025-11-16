def test_health_endpoint_returns_ok(client) -> None:
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "app_version" in payload

