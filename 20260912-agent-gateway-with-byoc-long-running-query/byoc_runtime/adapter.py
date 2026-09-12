"""Direct URL-fetch handler.

No LLM is involved: this is a WebFetch tool, not an agent. `invoke()` pulls
every http(s) URL out of the request message and fetches it directly from
this container, so the Runtime's own egress path (and therefore Agent
Gateway) sees the real destination. This is enough to exercise and observe
Agent Gateway's allow/deny behavior without depending on a model.
"""

from __future__ import annotations

import asyncio
import re
import sys
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

MAX_MESSAGE_LENGTH = 4_000
MAX_SNIPPET_CHARS = 500
DOWNLOAD_CAP_BYTES = 120_000
URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)\]]+")


class AgentInvocationError(RuntimeError):
    """An error safe to return to a caller without disclosing credentials."""


def validate_message(message: object) -> str:
    if not isinstance(message, str) or not message.strip():
        raise AgentInvocationError("input.message は空でない文字列で指定してください。")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise AgentInvocationError("input.message は4000文字以下で指定してください。")
    return message.strip()


def extract_urls(message: str) -> list[str]:
    return URL_PATTERN.findall(message)


def _fetch_url(url: str) -> dict[str, Any]:
    host = urlparse(url).hostname or "unknown"
    print(f"WebFetch request host={host}", file=sys.stderr, flush=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "20260912-agent-gateway-byoc-longrunning-webfetch/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(DOWNLOAD_CAP_BYTES + 1)
            if len(data) > DOWNLOAD_CAP_BYTES:
                data = data[:DOWNLOAD_CAP_BYTES]
            charset = response.headers.get_content_charset() or "utf-8"
            final_host = urlparse(response.geturl()).hostname or "unknown"
            text = data.decode(charset, errors="replace")
            print(
                f"WebFetch response host={host} final_host={final_host} "
                f"status={response.status} bytes={len(data)}",
                file=sys.stderr,
                flush=True,
            )
            return {
                "url": url,
                "ok": True,
                "status": response.status,
                "bytes": len(data),
                "snippet": text[:MAX_SNIPPET_CHARS],
            }
    except urllib.error.HTTPError as exc:
        print(f"WebFetch response host={host} status={exc.code}", file=sys.stderr, flush=True)
        return {"url": url, "ok": False, "error_type": type(exc).__name__, "detail": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        print(f"WebFetch error host={host} type={type(exc).__name__} reason={reason}", file=sys.stderr, flush=True)
        return {"url": url, "ok": False, "error_type": type(exc).__name__, "detail": str(reason)}


def format_report(urls: list[str], results: list[dict[str, Any]]) -> str:
    if not urls:
        return "メッセージ内に http:// または https:// で始まるURLが見つかりませんでした。"
    lines: list[str] = []
    for result in results:
        if result["ok"]:
            lines.append(
                f"[取得成功] {result['url']} (HTTP {result['status']}, {result['bytes']} バイト)\n"
                f"内容の冒頭: {result['snippet']!r}"
            )
        else:
            lines.append(
                f"[取得失敗] {result['url']} -- {result['error_type']}: {result['detail']}"
            )
    return "\n\n".join(lines)


async def invoke(message: object) -> str:
    """Fetch every URL found in the message directly; no model call involved."""
    text = validate_message(message)
    urls = extract_urls(text)
    results = await asyncio.gather(*(asyncio.to_thread(_fetch_url, url) for url in urls))
    return format_report(urls, list(results))


async def stream_invoke(message: object) -> AsyncIterator[dict[str, str]]:
    """Expose the same report as a single NDJSON-compatible stream chunk."""
    yield {"output": await invoke(message)}
