"""Run the four query operations locally or through the deployed API as JSON Lines."""
from __future__ import annotations
import argparse, asyncio, json, time, uuid
from collections.abc import AsyncIterator
from typing import Any
import httpx

METHODS = ("query", "async_query", "stream_query", "async_stream_query")

def emit(**value: Any) -> None: print(json.dumps(value, ensure_ascii=False, default=str))

async def local(base_url: str, method: str, verification_id: str) -> AsyncIterator[dict[str, Any]]:
    endpoint = "/api/reasoning_engine" if method in ("query", "async_query") else "/api/stream_reasoning_engine"
    started = time.monotonic()
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        async with client.stream("POST", endpoint, json={"class_method": method, "input": {"verification_id": verification_id}}) as response:
            response.raise_for_status()
            if method in ("query", "async_query"):
                yield {"response": json.loads(await response.aread()), "elapsed_ms": round((time.monotonic()-started)*1000, 1)}
            else:
                async for line in response.aiter_lines():
                    if line: yield {"response": json.loads(line), "elapsed_ms": round((time.monotonic()-started)*1000, 1)}

async def deployed_rest(resource: str, location: str, method: str, verification_id: str) -> AsyncIterator[dict[str, Any]]:
    import google.auth
    from google.auth.transport.requests import Request
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"]); credentials.refresh(Request())
    suffix = "query" if method in ("query", "async_query") else "streamQuery"
    url = f"https://{location}-aiplatform.googleapis.com/v1/{resource}:{suffix}"
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=90) as client:
        async with client.stream("POST", url, headers={"Authorization": f"Bearer {credentials.token}"}, json={"class_method": method, "input": {"verification_id": verification_id}}) as response:
            response.raise_for_status()
            if method in ("query", "async_query"):
                yield {"response": json.loads(await response.aread()), "elapsed_ms": round((time.monotonic()-started)*1000, 1)}
                return
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line = line.removeprefix("data: ")
                if line and line != "[DONE]" and not line.startswith(("event:", "id:", ":")):
                    yield {"response": json.loads(line), "elapsed_ms": round((time.monotonic()-started)*1000, 1)}

async def run(args: argparse.Namespace) -> None:
    for method in (METHODS if args.operation == "all" else (args.operation,)):
        verification_id = f"verify-{uuid.uuid4()}"
        emit(event="attempt_started", target=args.target, operation=method, verification_id=verification_id)
        try:
            iterator = local(args.base_url, method, verification_id) if args.target == "local" else deployed_rest(args.agent_resource, args.location, method, verification_id)
            index = 0
            async for result in iterator:
                index += 1; emit(event="response", target=args.target, operation=method, verification_id=verification_id, sequence=index, **result)
            emit(event="attempt_completed", target=args.target, operation=method, verification_id=verification_id, success=True)
        except Exception as exc: emit(event="attempt_completed", target=args.target, operation=method, verification_id=verification_id, success=False, error_type=type(exc).__name__)

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--target", choices=("local","deployed"), default="local"); p.add_argument("--operation", choices=(*METHODS,"all"), default="all"); p.add_argument("--base-url", default="http://127.0.0.1:8080"); p.add_argument("--agent-resource"); p.add_argument("--location")
    args=p.parse_args()
    if args.target == "deployed" and (not args.agent_resource or not args.location): p.error("deployed には --agent-resource と --location が必要です。")
    asyncio.run(run(args))
if __name__ == "__main__": main()
