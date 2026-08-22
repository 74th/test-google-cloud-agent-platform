from fastapi.testclient import TestClient

from agent_service import app as runtime


def test_health_and_query_contract(monkeypatch):
    async def fake_invoke(message):
        assert message == "hello"
        return "answer"

    monkeypatch.setattr(runtime, "invoke", fake_invoke)
    client = TestClient(runtime.app)
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"message": "hello"}})
    assert response.status_code == 200
    assert response.json() == {"output": "answer"}


def test_invalid_and_empty_messages_are_rejected():
    client = TestClient(runtime.app)
    assert client.post("/api/reasoning_engine", json={"class_method": "query", "input": {}}).status_code == 422
    assert client.post("/api/reasoning_engine", json={"class_method": "wrong", "input": {"message": "x"}}).status_code == 400


def test_stream_contract(monkeypatch):
    async def fake_stream(message):
        assert message == "hello"
        yield {"output": "chunk"}

    monkeypatch.setattr(runtime, "stream_invoke", fake_stream)
    response = TestClient(runtime.app).post(
        "/api/stream_reasoning_engine",
        json={"class_method": "stream_query", "input": {"message": "hello"}},
    )
    assert response.status_code == 200
    assert response.text == '{"output": "chunk"}\n'
