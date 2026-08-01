"""HTTP implementation of the Google Cloud Agent Platform runtime contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from .adapter import AgentInvocationError, invoke, stream_invoke

app = FastAPI(title="Kanazawa timetable Claude agent")


class RuntimeRequest(BaseModel):
    class_method: str
    input: dict[str, Any] | None = None


def _normalize_request(request: RuntimeRequest | str) -> RuntimeRequest:
    if isinstance(request, RuntimeRequest):
        return request
    try:
        return RuntimeRequest.model_validate_json(request)
    except ValidationError as exc:
        raise HTTPException(400, "Agent Platform リクエストを解析できません。") from exc


def _message(request: RuntimeRequest | str, expected_method: str) -> object:
    request = _normalize_request(request)
    if request.class_method != expected_method:
        raise HTTPException(400, f"class_method は {expected_method!r} で指定してください。")
    return (request.input or {}).get("message")


@app.post("/api/reasoning_engine")
async def reasoning_engine(request: RuntimeRequest | str) -> dict[str, str]:
    try:
        return {"output": await invoke(_message(request, "query"))}
    except AgentInvocationError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: RuntimeRequest | str) -> StreamingResponse:
    try:
        message = _message(request, "stream_query")

        async def ndjson() -> AsyncIterator[str]:
            async for chunk in stream_invoke(message):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"

        return StreamingResponse(ndjson(), media_type="application/x-ndjson")
    except AgentInvocationError as exc:
        raise HTTPException(422, str(exc)) from exc
