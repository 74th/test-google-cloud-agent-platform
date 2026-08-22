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
async def test_root_and_unary_endpoints_have_identical_success_responses(client, monkeypatch):
    async def fast(): return "OK"
    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    payload = {"class_method": "query", "input": {"verification_id": "same-1"}}

    root_response = await client.post("/", json=payload)
    unary_response = await client.post("/api/reasoning_engine", json=payload)

    assert root_response.status_code == unary_response.status_code == 200
    assert root_response.json() == unary_response.json() == {"output": "OK"}


@pytest.mark.asyncio
async def test_root_accepts_gcs_query_input_without_operation_name(client, monkeypatch):
    delays = []

    async def fast(delay_seconds):
        delays.append(delay_seconds)
        return "OK"

    monkeypatch.setattr("byoc_runtime.app.agent.query", fast)
    response = await client.post("/", json={"input": {"verification_id": "gcs-1", "delay_seconds": 960}})
    assert response.status_code == 200
    assert response.json() == {"output": "OK"}
    assert delays == [960]


@pytest.mark.asyncio
async def test_root_rejects_missing_or_invalid_long_running_input(client):
    missing = await client.post("/", json={"input": {}})
    negative = await client.post("/", json={"input": {"verification_id": "gcs-2", "delay_seconds": -1}})
    too_long = await client.post("/", json={"input": {"verification_id": "gcs-3", "delay_seconds": 3601}})
    unsupported = await client.post("/", json={"class_method": "stream_query", "input": {"verification_id": "gcs-4"}})
    assert [response.status_code for response in (missing, negative, too_long)] == [422, 422, 422]
    assert unsupported.status_code == 400


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
async def test_root_invalid_payload_logs_lifecycle_without_body_or_secret(client, caplog, monkeypatch):
    from byoc_runtime.logging import logger

    monkeypatch.setattr(logger, "propagate", True)
    response = await client.post(
        "/",
        json={"class_method": "query", "input": {"verification_id": "bad value!", "secret": "do-not-log"}},
    )

    assert response.status_code == 422
    messages = "\n".join(record.message for record in caplog.records)
    assert '"event": "http_received"' in messages
    assert '"event": "http_completed"' in messages
    assert "bad value" not in messages
    assert "do-not-log" not in messages


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
