from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.v1.endpoints import assist as assist_router
from app.services.conversational import ChatResponse


def test_chat_endpoint(monkeypatch, client: TestClient) -> None:
    mock_response = ChatResponse(
        reply="Hello!",
        language="en",
        safety_passed=True,
        metadata={"model": "mock"},
    )
    monkeypatch.setattr(assist_router.agent, "respond", Mock(return_value=mock_response))

    resp = client.post("/api/v1/assist/chat", json={"message": "Hi"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Hello!"


def test_assistant_bootstrap_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/assist/session/bootstrap")
    assert resp.status_code == 200
    body = resp.json()
    assert "languages" in body
    assert "suggestion_prompts" in body
