"""HTTP implementation of the Agent Platform custom container contract.

Exposes two independent paths on the same container:

- ``/api/reasoning_engine`` / ``/api/stream_reasoning_engine`` — the
  synchronous Agent Platform contract, answered by a direct WebFetch
  handler with no model in the loop (see ``adapter.py``).
- ``/`` (root) — the contract Agent Engine's ``run_query_job`` delivers a
  long-running job through: a GCS input object is POSTed here, and the
  response (or, per the query-job design, no synchronous response at all) is
  written back to a GCS output object by the platform. This handler never
  calls a model either; the failure this repository reproduces occurs in the
  platform's own query-job delivery path (GCS input fetch through the Agent
  Gateway-associated Runtime) before any request reaches this process.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from .adapter import AgentInvocationError, invoke, stream_invoke
from .logging import event
from .models import MessageRequest, QueryJobRequest, json_response

app = FastAPI(title="20260912 Agent Gateway + BYOC long-running query verification")


@app.middleware("http")
async def lifecycle(request: Request, call_next):
    request_id, started = str(uuid.uuid4()), time.monotonic()
    request.state.request_id, request.state.started = request_id, started
    event("http_received", request_id=request_id, started=started, path=request.url.path, method=request.method)
    response = await call_next(request)

    original_body = response.body_iterator

    async def body_with_completion() -> AsyncIterator[bytes]:
        try:
            async for chunk in original_body:
                yield chunk
        finally:
            event("http_completed", request_id=request_id, started=started, path=request.url.path,
                  method=request.method, status=response.status_code)

    response.body_iterator = body_with_completion()
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    event(
        "invalid_request",
        request_id=getattr(request.state, "request_id", "unknown"),
        started=getattr(request.state, "started", time.monotonic()),
        severity="WARNING",
        error_locations=[".".join(str(part) for part in item["loc"]) for item in exc.errors()],
    )
    return JSONResponse(status_code=422, content={"detail": "Invalid runtime request."})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _normalize_message_request(payload: MessageRequest | str | dict[str, Any]) -> MessageRequest:
    try:
        if isinstance(payload, MessageRequest):
            return payload
        if isinstance(payload, str):
            return MessageRequest.model_validate_json(payload)
        return MessageRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(400, "Agent Platform リクエストを解析できません。") from exc


@app.post("/api/reasoning_engine")
async def reasoning_engine(payload: MessageRequest | str | dict[str, Any], request: Request) -> dict[str, str]:
    normalized = _normalize_message_request(payload)
    if normalized.class_method != "query":
        raise HTTPException(400, "class_method は 'query' で指定してください。")
    request_id, started = request.state.request_id, request.state.started
    event("query_started", request_id=request_id, started=started, class_method="query")
    try:
        output = await invoke(normalized.input.message)
    except AgentInvocationError as exc:
        event("query_failed", request_id=request_id, started=started, severity="ERROR", class_method="query")
        raise HTTPException(422, str(exc)) from exc
    event("query_completed", request_id=request_id, started=started, class_method="query")
    return {"output": output}


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(payload: MessageRequest | str | dict[str, Any], request: Request) -> StreamingResponse:
    normalized = _normalize_message_request(payload)
    if normalized.class_method != "stream_query":
        raise HTTPException(400, "class_method は 'stream_query' で指定してください。")
    message = normalized.input.message
    request_id, started = request.state.request_id, request.state.started

    async def ndjson() -> AsyncIterator[str]:
        event("query_started", request_id=request_id, started=started, class_method="stream_query")
        try:
            async for chunk in stream_invoke(message):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"
        except AgentInvocationError as exc:
            event("query_failed", request_id=request_id, started=started, severity="ERROR", class_method="stream_query")
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"
            return
        event("query_completed", request_id=request_id, started=started, class_method="stream_query")

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


def _normalize_query_job_payload(payload: Any) -> QueryJobRequest:
    raw = payload
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, "Invalid long-running query input.") from exc
    if not isinstance(raw, dict):
        raise HTTPException(422, "Invalid long-running query input.")
    try:
        return QueryJobRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid long-running query input.") from exc


@app.post("/")
async def root_endpoint(payload: Any = Body(None), request: Request = None) -> dict[str, str]:
    """The long-running query-job delivery contract.

    If this handler runs at all, the query-job's GCS input successfully
    reached the application container -- i.e. the Agent Gateway-associated
    proxy path did not block or fail the platform's own input delivery.
    """
    try:
        job = _normalize_query_job_payload(payload)
    except HTTPException as exc:
        event(
            "request_shape_invalid",
            request_id=request.state.request_id,
            started=request.state.started,
            severity="WARNING",
            status=exc.status_code,
        )
        raise
    request_id, started = request.state.request_id, request.state.started
    event(
        "query_started",
        request_id=request_id,
        started=started,
        class_method="query_job",
        verification_id=job.input.verification_id,
        delay_seconds=job.input.delay_seconds,
    )
    try:
        await asyncio.sleep(job.input.delay_seconds)
    except Exception as exc:
        event(
            "query_failed",
            request_id=request_id,
            started=started,
            severity="ERROR",
            class_method="query_job",
            verification_id=job.input.verification_id,
            error_type=type(exc).__name__,
        )
        raise HTTPException(500, "Query processing failed.") from exc
    event(
        "query_completed",
        request_id=request_id,
        started=started,
        class_method="query_job",
        verification_id=job.input.verification_id,
    )
    return json_response("OK")


def run() -> None:
    uvicorn.run("byoc_runtime.app:app", host="0.0.0.0", port=8080)
