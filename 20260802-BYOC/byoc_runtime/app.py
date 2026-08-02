"""FastAPI implementation of the Agent Platform BYOC runtime contract."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from .agent import DummyAgent
from .logging import event
from .models import STREAM_METHODS, UNARY_METHODS, RuntimeRequest, json_response, request_metadata

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
            event("http_completed", request_id=request_id, started=started, path=request.url.path, status=response.status_code)

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


def normalize_payload(payload: RuntimeRequest | str) -> RuntimeRequest:
    if isinstance(payload, RuntimeRequest):
        return payload
    try:
        return RuntimeRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid runtime request.") from exc


@app.post("/api/reasoning_engine")
async def reasoning_engine(payload: RuntimeRequest | str, request: Request) -> dict[str, str]:
    payload = normalize_payload(payload)
    validate_endpoint(payload, UNARY_METHODS)
    request_id, started = request.state.request_id, request.state.started
    metadata = request_metadata(payload)
    event("query_started", request_id=request_id, started=started, **metadata)
    try:
        output = await getattr(agent, payload.class_method)()
    except Exception as exc:
        event("query_failed", request_id=request_id, started=started, severity="ERROR", error_type=type(exc).__name__, **metadata)
        raise HTTPException(500, "Query processing failed.") from exc
    event("query_completed", request_id=request_id, started=started, status="success", **metadata)
    return json_response(output)


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
