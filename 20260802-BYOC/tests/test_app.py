import json

import httpx
import pytest

from byoc_runtime.app import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_unary_endpoint(client, monkeypatch):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    response = await client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"verification_id": "test-1"}})
    assert response.json() == {"output": "OK"}


@pytest.mark.asyncio
async def test_stream_endpoint(client, monkeypatch):
    async def stream():
        yield "Streaming OK"
        yield "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.stream_query", stream)
    response = await client.post("/api/stream_reasoning_engine", json={"class_method": "stream_query", "input": {"verification_id": "test-2"}})
    assert [json.loads(line) for line in response.text.splitlines()] == [{"output": "Streaming OK"}, {"output": "OK"}]


@pytest.mark.asyncio
async def test_invalid_operation_and_payload_are_safe_4xx(client):
    invalid_endpoint = await client.post("/api/reasoning_engine", json={"class_method": "stream_query", "input": {"verification_id": "test-3"}})
    invalid_payload = await client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"verification_id": "bad value!"}})
    assert invalid_endpoint.status_code == 400
    assert invalid_payload.status_code == 422
    assert "bad value" not in invalid_payload.text


@pytest.mark.asyncio
async def test_agent_platform_wrapped_input_is_accepted(client, monkeypatch):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    response = await client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"input": {"verification_id": "wrapped-1"}}})
    assert response.json() == {"output": "OK"}


@pytest.mark.asyncio
async def test_agent_platform_camel_case_method_is_accepted(client, monkeypatch):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    response = await client.post("/api/reasoning_engine", json={"classMethod": "query", "input": {"verification_id": "camel-1"}})
    assert response.json() == {"output": "OK"}


@pytest.mark.asyncio
async def test_agent_platform_json_string_payload_is_accepted(client, monkeypatch):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    payload = json.dumps({"class_method": "query", "input": {"verification_id": "string-1"}})
    response = await client.post("/api/reasoning_engine", json=payload)
    assert response.json() == {"output": "OK"}


@pytest.mark.asyncio
async def test_logs_include_lifecycle_without_secret(client, monkeypatch, caplog):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    from byoc_runtime.logging import logger
    monkeypatch.setattr(logger, "propagate", True)
    await client.post("/api/reasoning_engine", json={"class_method": "query", "input": {"verification_id": "trace-1", "secret": "nope"}})
    messages = "\n".join(record.message for record in caplog.records)
    for name in ("http_received", "query_started", "query_completed", "http_completed"):
        assert name in messages
    assert "nope" not in messages
