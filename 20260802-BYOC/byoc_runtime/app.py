"""FastAPI implementation of the Agent Platform BYOC runtime contract."""

from __future__ import annotations

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

from .agent import DummyAgent
from .logging import event
from .models import (
    LongRunningRequest,
    RuntimeRequest,
    STREAM_METHODS,
    UNARY_METHODS,
    json_response,
    request_metadata,
)

app = FastAPI(title="BYOC query operation verifier")
agent = DummyAgent()


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
    safe_errors = exc.errors()
    event(
        "invalid_request",
        request_id=getattr(request.state, "request_id", "unknown"),
        started=getattr(request.state, "started", time.monotonic()),
        severity="WARNING",
        error_locations=[".".join(str(part) for part in item["loc"]) for item in safe_errors],
        error_types=[item["type"] for item in safe_errors],
    )
    return JSONResponse(status_code=422, content={"detail": "Invalid runtime request."})


def validate_endpoint(payload: RuntimeRequest, allowed: frozenset[str]) -> None:
    if payload.class_method not in allowed:
        raise HTTPException(status_code=400, detail="class_method is not supported by this endpoint.")


def normalize_payload(payload: Any) -> RuntimeRequest:
    if isinstance(payload, RuntimeRequest):
        return payload
    try:
        return RuntimeRequest.model_validate_json(payload) if isinstance(payload, str) else RuntimeRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid runtime request.") from exc


def normalize_root_payload(payload: Any) -> tuple[RuntimeRequest, bool]:
    """Normalize GCS query-job input without weakening the normal API contract."""
    raw = payload
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Invalid runtime request.") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Invalid runtime request.")

    has_operation = "class_method" in raw or "classMethod" in raw
    try:
        if has_operation:
            request = RuntimeRequest.model_validate(raw)
            return request, False
        long_request = LongRunningRequest.model_validate(raw)
        return RuntimeRequest(class_method=long_request.class_method or "query", input=long_request.input), True
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid long-running query input.") from exc


async def _run_unary(payload: Any, request: Request, *, root: bool) -> dict[str, str]:
    try:
        payload, long_running = normalize_root_payload(payload) if root else (normalize_payload(payload), False)
    except HTTPException as exc:
        raw = payload if isinstance(payload, dict) else {}
        input_value = raw.get("input") if isinstance(raw, dict) else None
        event(
            "request_shape_invalid",
            request_id=request.state.request_id,
            started=request.state.started,
            severity="WARNING",
            endpoint="/" if root else "/api/reasoning_engine",
            top_level_keys=sorted(str(key) for key in raw)[:16],
            input_type=type(input_value).__name__,
            status=exc.status_code,
        )
        raise
    validate_endpoint(payload, UNARY_METHODS)
    request_id, started = request.state.request_id, request.state.started
    metadata = request_metadata(payload)
    if not long_running:
        metadata.pop("delay_seconds", None)
    event("query_started", request_id=request_id, started=started, **metadata)
    try:
        method = getattr(agent, payload.class_method)
        output = await method(payload.input.delay_seconds) if long_running else await method()
    except Exception as exc:
        event("query_failed", request_id=request_id, started=started, severity="ERROR", error_type=type(exc).__name__, **metadata)
        raise HTTPException(500, "Query processing failed.") from exc
    event("query_completed", request_id=request_id, started=started, status="success", **metadata)
    return json_response(output)


@app.post("/")
async def root_endpoint(payload: Any = Body(None), request: Request = None) -> dict[str, str]:
    return await _run_unary(payload, request, root=True)


@app.post("/api/reasoning_engine")
async def reasoning_engine(payload: RuntimeRequest | str, request: Request) -> dict[str, str]:
    return await _run_unary(payload, request, root=False)


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(payload: RuntimeRequest | str, request: Request) -> StreamingResponse:
    payload = normalize_payload(payload)
    validate_endpoint(payload, STREAM_METHODS)
    request_id, started = request.state.request_id, request.state.started
    metadata = request_metadata(payload)

    async def ndjson() -> AsyncIterator[str]:
        event("query_started", request_id=request_id, started=started, **metadata)
        try:
            async for chunk in getattr(agent, payload.class_method)():
                event("query_chunk", request_id=request_id, started=started, **metadata)
                yield json.dumps(json_response(chunk)) + "\n"
        except Exception as exc:
            event("query_failed", request_id=request_id, started=started, severity="ERROR", error_type=type(exc).__name__, **metadata)
            raise
        else:
            event("query_completed", request_id=request_id, started=started, status="success", **metadata)

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")


def run() -> None:
    uvicorn.run("byoc_runtime.app:app", host="0.0.0.0", port=8080)
