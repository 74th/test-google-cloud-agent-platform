from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError as PydanticValidationError

from .adapter import ClaudeAgentAdapter, new_correlation_id
from .credentials import GoogleIDTokenProvider
from .errors import ValidationError
from .models import TargetConfig
from .registry import GcloudRegistryClient, RegistryResolver
from .runner import ValidationRunner

app = FastAPI(title="20260823 governed Agent Runtime MCP client")


class RuntimeRequest(BaseModel):
    class_method: str
    input: dict[str, Any] | None = None


def _tool_spec() -> dict[str, Any]:
    with open(os.getenv("TOOL_SPEC_PATH", "toolspec.json"), encoding="utf-8") as handle:
        return json.load(handle)["tools"][0]


def build_runner() -> ValidationRunner:
    project = os.getenv("REGISTRY_PROJECT", "nnyn-dev")
    location = os.getenv("REGISTRY_LOCATION", "us-central1")
    tool = _tool_spec()
    targets: dict[str, TargetConfig] = {
        "cloud-run": TargetConfig(
            name="cloud-run",
            service_id=os.getenv("CLOUD_RUN_REGISTRY_SERVICE_ID", "mcp-20260823-cloud-run"),
            allowed_hosts=frozenset(filter(None, os.getenv("CLOUD_RUN_ALLOWED_HOSTS", "").split(","))),
            audience=os.getenv("CLOUD_RUN_AUTH_AUDIENCE", ""),
        ),
        "gke": TargetConfig(
            name="gke",
            service_id=os.getenv("GKE_REGISTRY_SERVICE_ID", "mcp-20260823-gke"),
            allowed_hosts=frozenset(filter(None, os.getenv("GKE_ALLOWED_HOSTS", "").split(","))),
            audience=os.getenv("GKE_AUTH_AUDIENCE", ""),
        ),
    }
    diagnostic_hosts = frozenset(filter(None, os.getenv("GKE_HTTP_DIAGNOSTIC_ALLOWED_HOSTS", "").split(",")))
    diagnostic_audience = os.getenv("GKE_HTTP_DIAGNOSTIC_AUTH_AUDIENCE", "")
    if diagnostic_hosts and diagnostic_audience:
        targets["gke-http-diagnostic"] = TargetConfig(
            name="gke-http-diagnostic",
            service_id=os.getenv("GKE_HTTP_DIAGNOSTIC_REGISTRY_SERVICE_ID", "mcp-20260823-gke-http-diagnostic"),
            allowed_hosts=diagnostic_hosts,
            audience=diagnostic_audience,
            allowed_schemes=frozenset({"http"}),
        )
    missing = [name for name in ("cloud-run",) if not targets[name].allowed_hosts or not targets[name].audience]
    if missing:
        raise RuntimeError(f"missing reviewed target configuration: {','.join(missing)}")
    resolver = RegistryResolver(GcloudRegistryClient(), project, location, targets, {name: tool for name in targets})
    return ValidationRunner(resolver, ClaudeAgentAdapter(GoogleIDTokenProvider(os.getenv("MCP_CALLER_SERVICE_ACCOUNT"))))


def _request_parts(request: RuntimeRequest | str | dict[str, Any], expected: str) -> tuple[str, str]:
    try:
        normalized = request if isinstance(request, RuntimeRequest) else RuntimeRequest.model_validate_json(request) if isinstance(request, str) else RuntimeRequest.model_validate(request)
    except PydanticValidationError as error:
        raise HTTPException(400, "invalid Agent Runtime request") from error
    if normalized.class_method != expected:
        raise HTTPException(400, f"class_method must be {expected}")
    payload = normalized.input or {}
    target = payload.get("target")
    message = payload.get("message")
    if target not in {"cloud-run", "gke", "gke-http-diagnostic"} or not isinstance(message, str) or not message.strip():
        raise HTTPException(400, "input.target and non-empty input.message are required")
    if re.search(r"https?://", message, re.IGNORECASE) or payload.get("url") is not None:
        raise HTTPException(400, "endpoint URLs are not accepted")
    return target, message.strip()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _invoke(request: RuntimeRequest | str | dict[str, Any], method: str) -> tuple[str, dict[str, Any]]:
    target, message = _request_parts(request, method)
    correlation_id = new_correlation_id()
    try:
        result, evidence = await build_runner().run(target, message, correlation_id=correlation_id)
        sanitized = evidence.sanitized()
        print(json.dumps({"event": "runtime_mcp_invocation", **sanitized}, ensure_ascii=False), flush=True)
        return result, sanitized
    except ValidationError as error:
        print(json.dumps({"event": "runtime_mcp_failure", "correlation_id": correlation_id, "target": target, "stage": error.stage.value, "error": str(error)}, ensure_ascii=False), flush=True)
        raise HTTPException(422, {"correlation_id": correlation_id, "stage": error.stage.value, "error": str(error)}) from error


@app.post("/api/reasoning_engine")
async def reasoning_engine(request: RuntimeRequest | str | dict[str, Any]) -> dict[str, Any]:
    output, evidence = await _invoke(request, "query")
    return {"output": output, "correlation_id": evidence["correlation_id"], "validation": evidence}


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: RuntimeRequest | str | dict[str, Any]) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        try:
            output, evidence = await _invoke(request, "stream_query")
            yield json.dumps({"output": output, "correlation_id": evidence["correlation_id"], "validation": evidence}, ensure_ascii=False) + "\n"
        except HTTPException as error:
            yield json.dumps({"error": error.detail}, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
