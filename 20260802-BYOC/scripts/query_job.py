"""Start, monitor, and collect evidence for a long-running query job.

The result file remains sanitized, while API call traces written to stdout
include the complete request/response representation for interactive
debugging. Do not redirect stdout to a shared or publicly accessible file.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

TERMINAL_STATES = frozenset({"SUCCEEDED", "SUCCESS", "COMPLETED", "DONE", "FAILED", "CANCELLED", "CANCELED", "ERROR"})
SUCCESS_STATES = frozenset({"SUCCEEDED", "SUCCESS", "COMPLETED", "DONE"})
FAILURE_STATES = frozenset({"FAILED", "CANCELLED", "CANCELED", "ERROR"})
LOG_EVENTS = frozenset({"http_received", "http_completed", "query_started", "query_completed", "query_failed"})
CONTAINER_NAMES = frozenset({"proxy-container", "job-container"})
T = TypeVar("T")


def write(path: Path, value: dict[str, Any]) -> None:
    """Append one JSON object without serializing arbitrary SDK objects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _jsonable(value: object) -> object:
    """Convert SDK responses to a JSON value without dropping fields."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, bytes):
        return {"__type__": "bytes", "value": value.hex()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]

    for method_name in ("to_dict", "to_api_repr"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return _jsonable(method())
            except Exception:
                pass

    protobuf = getattr(value, "_pb", None)
    if protobuf is not None:
        try:
            from google.protobuf.json_format import MessageToDict

            return _jsonable(MessageToDict(protobuf, preserving_proto_field_name=True))
        except Exception:
            pass

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return {
            "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "attributes": _jsonable(attributes),
        }
    return {"__type__": f"{type(value).__module__}.{type(value).__qualname__}", "repr": repr(value)}


def _print_api_trace(*, call_id: str, api: str, phase: str, state: str,
                     started_at: str, request: object = None, response: object = None,
                     error: BaseException | None = None, duration_ms: float | None = None) -> None:
    """Print one complete API call state transition as a JSON Lines record."""
    record: dict[str, object] = {
        "event": "api_call",
        "call_id": call_id,
        "api": api,
        "phase": phase,
        "state": state,
        "started_at": started_at,
    }
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if phase == "before":
        record["request"] = _jsonable(request)
    elif phase == "after":
        if error is not None:
            record["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "repr": repr(error),
            }
        else:
            record["response"] = _jsonable(response)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)


def _call_api(api: str, operation: Callable[[], T], *, request: object = None,
              response_for_trace: Callable[[T], object] | None = None) -> T:
    """Run an API call while printing before/after state and its full response."""
    call_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    _print_api_trace(
        call_id=call_id, api=api, phase="before", state="calling",
        started_at=started_at, request=request,
    )
    try:
        response = operation()
    except Exception as exc:
        _print_api_trace(
            call_id=call_id, api=api, phase="after", state="failed",
            started_at=started_at, error=exc,
            duration_ms=round((time.monotonic() - started) * 1000, 1),
        )
        raise
    try:
        traced_response = response_for_trace(response) if response_for_trace else response
    except Exception as trace_error:
        traced_response = {
            "__trace_serialization_error__": {
                "type": type(trace_error).__name__,
                "message": str(trace_error),
            },
            "response": response,
        }
    _print_api_trace(
        call_id=call_id, api=api, phase="after", state="completed",
        started_at=started_at, response=traced_response,
        duration_ms=round((time.monotonic() - started) * 1000, 1),
    )
    return response


def _value(value: object, key: str, default: object = None) -> object:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        camel = key.split("_")[0] + "".join(part.title() for part in key.split("_")[1:])
        return value.get(camel, default)
    return getattr(value, key, default)


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _payload(entry: object) -> dict[str, Any]:
    for key in ("payload", "json_payload", "jsonPayload"):
        payload = _value(entry, key)
        if isinstance(payload, dict):
            return payload
    text_payload = _value(entry, "text_payload") or _value(entry, "textPayload")
    if isinstance(text_payload, str):
        try:
            parsed = json.loads(text_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _safe_text(value: object) -> str:
    """Retain useful error classification while removing secrets and URLs."""
    text = str(value)
    text = re.sub(r"(?i)(authorization|x-goog-.*?token|access_token)=?[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"https?://[^\s]+", "[URL]", text)
    text = re.sub(r"\bgs://[^\s]+", "[GCS_URI]", text)
    return text[:240]


def safe_log_summary(entry: object) -> dict[str, Any]:
    """Keep only lifecycle fields; never persist a log message or request body."""
    payload = _payload(entry)
    labels = _value(entry, "labels", {})
    if not isinstance(labels, dict):
        labels = {}
    container_name = (
        payload.get("container_name") or payload.get("containerName")
        or labels.get("container_name") or labels.get("containerName")
    )
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    status = payload.get("status") or payload.get("http_status") or payload.get("httpStatus")
    http_request = _value(entry, "http_request")
    status = status or _value(http_request, "status")
    error_code = payload.get("error_code") or payload.get("errorCode") or error.get("code")
    error_type = payload.get("error_type") or payload.get("errorType") or error.get("type")
    permission_name = (
        payload.get("permission_name") or payload.get("permissionName")
        or payload.get("permission") or error.get("permission")
    )
    summary: dict[str, Any] = {
        "timestamp": _iso(_value(entry, "timestamp")) or payload.get("timestamp"),
        "severity": _value(entry, "severity") or payload.get("severity"),
        "event": payload.get("event"),
        "container_name": container_name,
        "stage": payload.get("stage") or payload.get("processing_stage") or payload.get("processingStage"),
        "request_id": payload.get("request_id"),
        "path": payload.get("path"),
        "method": payload.get("method"),
        "status": status,
        "error_code": error_code,
        "class_method": payload.get("class_method"),
        "verification_id": payload.get("verification_id"),
        "error_type": error_type,
        "permission_name": permission_name,
    }
    return {key: value for key, value in summary.items() if value is not None}


def _resource_id(agent_resource: str) -> str:
    return agent_resource.rstrip("/").rsplit("/", 1)[-1]


def build_log_filter(agent_resource: str, started_at: datetime, ended_at: datetime) -> str:
    """Build a bounded query for the agent resource and lifecycle events.

    Agent Platform log resource labels have changed between releases, so the
    resource-name alternatives are intentionally explicit. The caller still
    stores this exact filter as part of the evidence window.
    """
    resource_id = _resource_id(agent_resource)
    resources = " OR ".join(
        (
            f'resource.labels.reasoning_engine_id="{resource_id}"',
            f'resource.labels.agent_engine_id="{resource_id}"',
            f'labels."agentplatform.googleapis.com/agent_resource"="{agent_resource}"',
            f'textPayload:"{agent_resource}"',
        )
    )
    events = " OR ".join(
        [*(f'jsonPayload.event="{event}"' for event in sorted(LOG_EVENTS)),
         *(f'textPayload:"{event}"' for event in sorted(LOG_EVENTS))]
    )
    container_filter = " OR ".join(f'labels.container_name="{name}"' for name in sorted(CONTAINER_NAMES))
    return (
        f'timestamp >= "{started_at.astimezone(UTC).isoformat()}" '
        f'AND timestamp <= "{ended_at.astimezone(UTC).isoformat()}" '
        f'AND ({resources}) AND (({events}) OR httpRequest.status >= 400 OR severity >= ERROR OR ({container_filter}))'
    )


def collect_log_evidence(client: object, *, agent_resource: str, marker: str,
                         started_at: datetime, ended_at: datetime) -> dict[str, Any]:
    filter_ = build_log_filter(agent_resource, started_at, ended_at)
    entries = _call_api(
        "google.cloud.logging.Client.list_entries",
        lambda: list(client.list_entries(filter_=filter_, page_size=1000)),
        request={"filter_": filter_, "page_size": 1000},
        response_for_trace=lambda values: {"count": len(values)},
    )
    summaries = [safe_log_summary(entry) for entry in entries]
    summaries = [
        item for item in summaries
        if (item.get("event") in LOG_EVENTS or item.get("container_name") in CONTAINER_NAMES
            or item.get("status") is not None or item.get("error_code") is not None) and (
            item.get("verification_id") == marker
            or item.get("path") == "/"
            or item.get("request_id")
            or item.get("container_name") in CONTAINER_NAMES
        )
    ]
    root_received = [
        item for item in summaries
        if item.get("event") == "http_received" and item.get("method") == "POST" and item.get("path") == "/"
    ]
    root_completed = [
        item for item in summaries
        if item.get("event") == "http_completed" and item.get("method") == "POST" and item.get("path") == "/"
    ]
    marker_events = [item for item in summaries if item.get("verification_id") == marker]
    root_request_ids = {item.get("request_id") for item in root_received} | {
        item.get("request_id") for item in root_completed
    }
    marker_request_ids = {item.get("request_id") for item in marker_events}
    proxy_errors = [
        item for item in summaries
        if item.get("container_name") == "proxy-container"
        and (item.get("error_type") or item.get("error_code") or item.get("permission_name")
             or item.get("severity") in {"ERROR", "CRITICAL"})
    ]
    return {
        "agent_resource": agent_resource,
        "marker": marker,
        "window": {"started_at": started_at.isoformat(), "ended_at": ended_at.isoformat()},
        "filter": filter_,
        "entries": summaries,
        "root_received": root_received,
        "root_completed": root_completed,
        "marker_events": marker_events,
        "proxy_errors": proxy_errors,
        "containers": sorted({item["container_name"] for item in summaries if item.get("container_name")} ),
        "related_request_ids": sorted(root_request_ids & marker_request_ids),
        "search_complete": True,
    }


def safe_status(status: object) -> dict[str, Any]:
    state = str(_value(status, "state") or _value(status, "status") or "UNKNOWN").upper()
    result: dict[str, Any] = {"state": state}
    for key in ("name", "job_name", "operation_name"):
        value = _value(status, key)
        if value:
            result[key] = str(value)
    output_uri = _value(status, "output_gcs_uri")
    if output_uri:
        result["output_gcs_uri"] = str(output_uri)
    error = _value(status, "error")
    if isinstance(error, dict):
        code = error.get("code") or error.get("status") or error.get("http_status")
        message = error.get("message") or error.get("detail")
    else:
        code = getattr(error, "code", None) if error else None
        message = getattr(error, "message", None) if error else None
    result_value = _value(status, "result")
    if state in FAILURE_STATES and result_value and not message:
        message = result_value
    if code is not None:
        result["error_code"] = str(code)
    if message:
        result["error_message"] = _safe_text(message)
    if state in SUCCESS_STATES and result_value is not None:
        result["result_available"] = True
    return result


def gcs_output_summary(client: object, uri: str) -> dict[str, Any]:
    """Check output metadata only; never download potentially sensitive content."""
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("output URI must be a gs:// URI")
    bucket_name, object_name = parsed.netloc, parsed.path.lstrip("/")
    blob = client.bucket(bucket_name).blob(object_name)
    request = {"bucket": bucket_name, "object": object_name}
    exists = _call_api(
        "google.cloud.storage.Blob.exists",
        blob.exists,
        request=request,
    )
    if not exists:
        return {"uri": uri, "accessible": True, "exists": False}
    _call_api(
        "google.cloud.storage.Blob.reload",
        blob.reload,
        request=request,
        response_for_trace=lambda _response: {
            "size": int(blob.size or 0),
            "updated": _iso(blob.updated),
            "content_type": blob.content_type,
        },
    )
    return {
        "uri": uri,
        "accessible": True,
        "exists": True,
        "size": int(blob.size or 0),
        "updated": _iso(blob.updated),
        "content_type": blob.content_type,
    }


gcs_object_summary = gcs_output_summary


def _stage(state: str, evidence: list[dict[str, Any]] | None = None, reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"state": state}
    if evidence:
        result["evidence"] = evidence
    if reason:
        result["reason"] = reason
    return result


def evaluate_evidence(*, log_evidence: dict[str, Any] | None,
                      status_history: list[dict[str, Any]],
                      output: dict[str, Any] | None,
                      log_error: str | None = None,
                      output_error: str | None = None,
                      input: dict[str, Any] | None = None,
                      input_error: str | None = None) -> dict[str, Any]:
    """Evaluate independent evidence stages without treating missing proof as success."""
    if log_error:
        http_delivery = _stage("unknown", reason=f"Cloud Logging collection failed: {log_error}")
        processing = _stage("unknown", reason="HTTP evidence is unavailable")
    else:
        log_evidence = log_evidence or {}
        roots = log_evidence.get("root_received", [])
        completed = [item for item in log_evidence.get("marker_events", []) if item.get("event") == "http_completed"]
        root_request_ids = {item.get("request_id") for item in roots}
        related = [item for item in log_evidence.get("marker_events", []) if item.get("request_id") in root_request_ids]
        failed = [item for item in related if item.get("event") == "query_failed"]
        processed = [item for item in related if item.get("event") == "query_completed"]
        proxy_errors = log_evidence.get("proxy_errors", [])
        if roots:
            http_delivery = _stage("success", roots)
        else:
            http_delivery = _stage("failure", reason="対象時間範囲に POST / の受信ログなし")
        if failed:
            processing = _stage("failure", failed, "ルート要求の処理失敗")
        elif processed:
            processing = _stage("success", processed)
        elif roots:
            processing = _stage("unknown", reason="POST / は受信したが、マーカーと対応する処理完了がない")
        else:
            processing = _stage("unknown", reason="対応する処理イベントなし")

    latest_state = status_history[-1].get("state", "UNKNOWN") if status_history else "UNKNOWN"
    if latest_state in SUCCESS_STATES:
        terminal = _stage("success", [{"state": latest_state}])
    elif latest_state in FAILURE_STATES:
        terminal = _stage("failure", [{"state": latest_state}], "ジョブが成功終端していない")
    else:
        terminal = _stage("unknown", [{"state": latest_state}], "監視期限までに成功・失敗終端を確認できない")

    if output_error:
        gcs = _stage("unknown", reason=f"GCS output collection failed: {output_error}")
    elif output and output.get("exists"):
        gcs = _stage("success", [output])
    elif output:
        gcs = _stage("failure", [output], "期待する GCS 出力が存在しない")
    else:
        gcs = _stage("unknown", reason="GCS 出力証跡なし")

    stages = {
        "http_delivery": http_delivery,
        "processing": processing,
        "job_terminal_state": terminal,
        "gcs_output": gcs,
    }
    if input is not None or input_error:
        if proxy_errors if not log_error else False:
            gcs_input = _stage("failure", proxy_errors, "proxy による GCS 入力取得または配送前処理が失敗")
        elif input_error:
            gcs_input = _stage("unknown", reason=f"GCS input collection failed: {input_error}")
        elif input and input.get("exists"):
            gcs_input = _stage("success", [input])
        elif input:
            gcs_input = _stage("failure", [input], "入力オブジェクトが存在しない")
        else:
            gcs_input = _stage("unknown", reason="GCS 入力証跡なし")
        stages = {"gcs_input": gcs_input, **stages}
    states = {item["state"] for item in stages.values()}
    if states == {"success"}:
        result = "動作確認"
    elif stages.get("gcs_input", {}).get("state") == "failure" and http_delivery["state"] != "success":
        result = "GCS入力取得失敗"
    elif http_delivery["state"] == "success" and "failure" in states:
        result = "配送確認・動作未確認"
    elif http_delivery["state"] == "failure" and not log_error and log_evidence and log_evidence.get("search_complete"):
        result = "未到達"
    else:
        result = "判定不能"
    return {"result": result, "stages": stages}


def _job_name(response: object) -> str | None:
    for key in ("job_name", "name", "operation_name"):
        value = _value(response, key)
        if value:
            return str(value)
    return None


def query_payload(marker: str, delay_seconds: int) -> str:
    """Return the exact JSON written by the SDK to the GCS input object."""
    from byoc_runtime.models import QueryInput

    validated = QueryInput(verification_id=marker, delay_seconds=delay_seconds)
    return json.dumps({"input": validated.model_dump()}, ensure_ascii=False, separators=(",", ":"))


def effective_timeout_seconds(delay_seconds: int, requested: int | None) -> int:
    """Keep the long-running observation window at least 10 minutes past processing."""
    base = requested or 900
    return max(base, delay_seconds + 600) if delay_seconds > 900 else base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--agent-resource", required=True)
    parser.add_argument("--output-gcs-uri", required=True)
    parser.add_argument("--delay-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--log-grace-seconds", type=int, default=60)
    parser.add_argument("--cancel-on-timeout", action="store_true",
                        help="明示した場合だけ監視期限でキャンセルを要求する")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--result", type=Path, default=Path("results/query-job.jsonl"))
    args = parser.parse_args()

    from byoc_runtime.models import QueryInput

    QueryInput(verification_id="query-job-marker", delay_seconds=args.delay_seconds)
    timeout_seconds = effective_timeout_seconds(args.delay_seconds, args.timeout_seconds)

    import agentplatform
    from google.cloud import logging as cloud_logging
    from google.cloud import storage
    from scripts.preflight import check_gcs_object_access, check_service_usage

    marker = f"query-job-{uuid.uuid4()}"
    attempt_id = marker
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=timeout_seconds)
    monotonic_deadline = time.monotonic() + timeout_seconds
    log_started = started - timedelta(minutes=1)
    client = agentplatform.Client(project=args.project, location=args.location)
    storage_client = storage.Client(project=args.project)
    if not args.skip_preflight:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            preflight = {
                "gcs_output": check_gcs_object_access(storage_client, args.output_gcs_uri),
                "service_usage": check_service_usage(AuthorizedSession(credentials), args.project),
            }
            write(args.result, {"event": "preflight", "attempt_id": attempt_id, **preflight})
        except Exception as exc:
            write(args.result, {"event": "preflight", "attempt_id": attempt_id,
                                "ok": False, "error_type": type(exc).__name__})
    run_config = {
        "query": query_payload(marker, args.delay_seconds),
        "output_gcs_uri": args.output_gcs_uri,
    }
    response = _call_api(
        "agentplatform.Client.agent_engines.run_query_job",
        lambda: client.agent_engines.run_query_job(name=args.agent_resource, config=run_config),
        request={"name": args.agent_resource, "config": run_config},
    )
    job_name = _job_name(response)
    if not job_name:
        raise RuntimeError("run_query_job response did not include a job name")

    input_gcs_uri = _value(response, "input_gcs_uri")
    output_gcs_uri = _value(response, "output_gcs_uri") or args.output_gcs_uri
    if not input_gcs_uri:
        raise RuntimeError("run_query_job response did not include input_gcs_uri")

    write(args.result, {
        "event": "attempt_started", "attempt_id": attempt_id, "marker": marker,
        "agent_resource": args.agent_resource, "job_name": job_name,
        "started_at": started.isoformat(), "deadline_at": deadline.isoformat(),
        "delay_seconds": args.delay_seconds,
        "input_gcs_uri": str(input_gcs_uri),
        "output_gcs_uri": str(output_gcs_uri),
        "log_window": {"started_at": log_started.isoformat(), "ended_at": None},
    })

    status_history: list[dict[str, Any]] = []
    timed_out = False
    while time.monotonic() < monotonic_deadline:
        check_config = {"retrieve_result": True}
        status = _call_api(
            "agentplatform.Client.agent_engines.check_query_job",
            lambda: client.agent_engines.check_query_job(name=job_name, config=check_config),
            request={"name": job_name, "config": check_config},
        )
        snapshot = safe_status(status)
        status_history.append(snapshot)
        write(args.result, {"event": "status", "attempt_id": attempt_id, "marker": marker,
                            "job_name": job_name, "checked_at": datetime.now(UTC).isoformat(), **snapshot})
        if snapshot["state"] in TERMINAL_STATES:
            break
        time.sleep(min(args.interval_seconds, max(0, int(monotonic_deadline - time.monotonic()))))
    else:
        timed_out = True
        write(args.result, {"event": "deadline_exceeded", "attempt_id": attempt_id,
                            "marker": marker, "job_name": job_name, "at": datetime.now(UTC).isoformat()})
        if args.cancel_on_timeout:
            try:
                cancel_config = {"operation_name": job_name}
                cancellation = _call_api(
                    "agentplatform.Client.agent_engines.cancel_query_job",
                    lambda: client.agent_engines.cancel_query_job(
                        name=args.agent_resource, config=cancel_config,
                    ),
                    request={"name": args.agent_resource, "config": cancel_config},
                )
                write(args.result, {"event": "cancel_requested", "attempt_id": attempt_id,
                                    "job_name": job_name, "status": safe_status(cancellation)})
            except Exception as exc:
                write(args.result, {"event": "cancel_failed", "attempt_id": attempt_id,
                                    "job_name": job_name, "error_type": type(exc).__name__})
        else:
            write(args.result, {"event": "cancel_skipped", "attempt_id": attempt_id,
                                "job_name": job_name, "reason": "cancel_on_timeout_not_set"})

    ended = datetime.now(UTC)
    if args.log_grace_seconds:
        time.sleep(args.log_grace_seconds)
    log_ended = datetime.now(UTC)
    log_evidence = None
    log_error = None
    try:
        log_evidence = collect_log_evidence(
            cloud_logging.Client(project=args.project), agent_resource=args.agent_resource,
            marker=marker, started_at=log_started, ended_at=log_ended,
        )
        write(args.result, {"event": "log_evidence", "attempt_id": attempt_id, **log_evidence})
    except Exception as exc:
        log_error = type(exc).__name__
        write(args.result, {"event": "log_evidence", "attempt_id": attempt_id,
                            "agent_resource": args.agent_resource, "marker": marker,
                            "error_type": log_error, "search_complete": False})

    output = None
    output_error = None
    try:
        output = gcs_output_summary(storage_client, str(output_gcs_uri))
        write(args.result, {"event": "gcs_output", "attempt_id": attempt_id, **output})
    except Exception as exc:
        output_error = type(exc).__name__
        write(args.result, {"event": "gcs_output", "attempt_id": attempt_id,
                            "uri": str(output_gcs_uri), "error_type": output_error})

    input_summary = None
    input_error = None
    try:
        input_summary = gcs_object_summary(storage_client, str(input_gcs_uri))
        write(args.result, {"event": "gcs_input", "attempt_id": attempt_id, **input_summary})
    except Exception as exc:
        input_error = type(exc).__name__
        write(args.result, {"event": "gcs_input", "attempt_id": attempt_id,
                            "uri": str(input_gcs_uri), "error_type": input_error})

    evaluation = evaluate_evidence(
        log_evidence=log_evidence, status_history=status_history, output=output,
        log_error=log_error, output_error=output_error, input=input_summary, input_error=input_error,
    )
    write(args.result, {"event": "evaluation", "attempt_id": attempt_id, "marker": marker,
                        "job_name": job_name, "ended_at": ended.isoformat(),
                        "log_window": {"started_at": log_started.isoformat(), "ended_at": log_ended.isoformat()},
                        **evaluation})


if __name__ == "__main__":
    main()
