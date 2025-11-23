from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.v1.endpoints import assist as assist_router
from app.services.conversational import ChatResponse


def test_chat_endpoint(monkeypatch, client: TestClient) -> None:
    mock_response = ChatResponse(
        reply="Hello!",
        language="en",
        safety_passed=True,
        metadata={"model": "mock", "backend": "indicbartss", "output_tokens": 12},
    )
    monkeypatch.setattr(assist_router.agent, "respond", Mock(return_value=mock_response))

    payload = {
        "message": "Hi",
        "system_prompt": "Be kind",
        "history": [{"role": "user", "content": "Previous question"}],
    }
    resp = client.post("/api/v1/assist/chat", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Hello!"
    assert body["metadata"]["model"] == "mock"
    assert resp.headers["X-Assistant-Model"] == "mock"


def test_assistant_bootstrap_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/assist/session/bootstrap")
    assert resp.status_code == 200
    body = resp.json()
    assert "languages" in body
    assert "suggestion_prompts" in body


def test_chat_stream_headers(monkeypatch, client: TestClient) -> None:
    mock_response = ChatResponse(
        reply="Streamed hello!",
        language="hi",
        safety_passed=True,
        metadata={"model": "mock", "backend": "indicbartss", "input_tokens": 5},
    )
    monkeypatch.setattr(assist_router.agent, "respond", Mock(return_value=mock_response))
    payload = {"message": "नमस्ते", "history": []}
    resp = client.post("/api/v1/assist/chat/stream", json=payload)
    assert resp.status_code == 200
    assert resp.headers["X-Assistant-Model"] == "mock"
    assert resp.headers["X-Assistant-Backend"] == "indicbartss"
