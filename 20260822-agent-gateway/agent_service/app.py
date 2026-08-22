"""HTTP implementation of the Agent Platform custom container contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from .adapter import AgentInvocationError, invoke, stream_invoke

app = FastAPI(title="20260822 Agent Gateway egress validation")


class RuntimeRequest(BaseModel):
    class_method: str
    input: dict[str, Any] | None = None


def _normalize_request(request: RuntimeRequest | str | dict[str, Any]) -> RuntimeRequest:
    if isinstance(request, RuntimeRequest):
        return request
    try:
        if isinstance(request, str):
            return RuntimeRequest.model_validate_json(request)
        return RuntimeRequest.model_validate(request)
    except ValidationError as exc:
        raise HTTPException(400, "Agent Platform リクエストを解析できません。") from exc


def _message(request: RuntimeRequest | str | dict[str, Any], expected_method: str) -> object:
    normalized = _normalize_request(request)
    if normalized.class_method != expected_method:
        raise HTTPException(400, f"class_method は {expected_method!r} で指定してください。")
    return (normalized.input or {}).get("message")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/reasoning_engine")
async def reasoning_engine(request: RuntimeRequest | str | dict[str, Any]) -> dict[str, str]:
    try:
        return {"output": await invoke(_message(request, "query"))}
    except AgentInvocationError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: RuntimeRequest | str | dict[str, Any]) -> StreamingResponse:
    message = _message(request, "stream_query")

    async def ndjson() -> AsyncIterator[str]:
        try:
            async for chunk in stream_invoke(message):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"
        except AgentInvocationError as exc:
            yield json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(ndjson(), media_type="application/x-ndjson")
