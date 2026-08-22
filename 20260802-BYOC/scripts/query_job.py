"""Start, monitor, and collect safe evidence for a long-running query job."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "CANCELED"})
SUCCESS_STATES = frozenset({"SUCCEEDED", "SUCCESS", "COMPLETED", "DONE"})
FAILURE_STATES = frozenset({"FAILED", "CANCELLED", "CANCELED", "ERROR"})
LOG_EVENTS = frozenset({"http_received", "http_completed", "query_started", "query_completed", "query_failed"})


def write(path: Path, value: dict[str, Any]) -> None:
    """Append one JSON object without serializing arbitrary SDK objects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _value(value: object, key: str, default: object = None) -> object:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _payload(entry: object) -> dict[str, Any]:
    payload = _value(entry, "payload")
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


def safe_log_summary(entry: object) -> dict[str, Any]:
    """Keep only lifecycle fields; never persist a log message or request body."""
    payload = _payload(entry)
    summary: dict[str, Any] = {
        "timestamp": _iso(_value(entry, "timestamp")) or payload.get("timestamp"),
        "severity": _value(entry, "severity") or payload.get("severity"),
        "event": payload.get("event"),
        "request_id": payload.get("request_id"),
        "path": payload.get("path"),
        "method": payload.get("method"),
        "status": payload.get("status"),
        "class_method": payload.get("class_method"),
        "verification_id": payload.get("verification_id"),
        "error_type": payload.get("error_type"),
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
    events = " OR ".join(f'textPayload:"{event}"' for event in sorted(LOG_EVENTS))
    return (
        f'timestamp >= "{started_at.astimezone(UTC).isoformat()}" '
        f'AND timestamp <= "{ended_at.astimezone(UTC).isoformat()}" '
        f'AND ({resources}) AND ({events})'
    )


def collect_log_evidence(client: object, *, agent_resource: str, marker: str,
                         started_at: datetime, ended_at: datetime) -> dict[str, Any]:
    filter_ = build_log_filter(agent_resource, started_at, ended_at)
    entries = client.list_entries(filter_=filter_, page_size=1000)
    summaries = [safe_log_summary(entry) for entry in entries]
    summaries = [
        item for item in summaries
        if item.get("event") in LOG_EVENTS and (
            item.get("verification_id") == marker
            or item.get("path") == "/"
            or item.get("request_id")
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
    return {
        "agent_resource": agent_resource,
        "marker": marker,
        "window": {"started_at": started_at.isoformat(), "ended_at": ended_at.isoformat()},
        "filter": filter_,
        "entries": summaries,
        "root_received": root_received,
        "root_completed": root_completed,
        "marker_events": marker_events,
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
    return result


def gcs_output_summary(client: object, uri: str) -> dict[str, Any]:
    """Check output metadata only; never download potentially sensitive content."""
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("output URI must be a gs:// URI")
    bucket_name, object_name = parsed.netloc, parsed.path.lstrip("/")
    blob = client.bucket(bucket_name).blob(object_name)
    if not blob.exists():
        return {"uri": uri, "accessible": True, "exists": False}
    blob.reload()
    return {
        "uri": uri,
        "accessible": True,
        "exists": True,
        "size": int(blob.size or 0),
        "updated": _iso(blob.updated),
        "content_type": blob.content_type,
    }


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
                      output_error: str | None = None) -> dict[str, Any]:
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
    states = {item["state"] for item in stages.values()}
    if states == {"success"}:
        result = "動作確認"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--agent-resource", required=True)
    parser.add_argument("--output-gcs-uri", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--log-grace-seconds", type=int, default=60)
    parser.add_argument("--result", type=Path, default=Path("results/query-job.jsonl"))
    args = parser.parse_args()

    import agentplatform
    from google.cloud import logging as cloud_logging
    from google.cloud import storage

    marker = f"query-job-{uuid.uuid4()}"
    attempt_id = marker
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=args.timeout_seconds)
    monotonic_deadline = time.monotonic() + args.timeout_seconds
    log_started = started - timedelta(minutes=1)
    client = agentplatform.Client(project=args.project, location=args.location)
    response = client.agent_engines.run_query_job(
        name=args.agent_resource,
        config={"query": json.dumps({"input": {"verification_id": marker}}), "output_gcs_uri": args.output_gcs_uri},
    )
    job_name = _job_name(response)
    if not job_name:
        raise RuntimeError("run_query_job response did not include a job name")

    write(args.result, {
        "event": "attempt_started", "attempt_id": attempt_id, "marker": marker,
        "agent_resource": args.agent_resource, "job_name": job_name,
        "started_at": started.isoformat(), "deadline_at": deadline.isoformat(),
        "output_gcs_uri": args.output_gcs_uri,
        "log_window": {"started_at": log_started.isoformat(), "ended_at": None},
    })

    status_history: list[dict[str, Any]] = []
    timed_out = False
    while time.monotonic() < monotonic_deadline:
        status = client.agent_engines.check_query_job(name=job_name, config={"retrieve_result": True})
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
        try:
            cancellation = client.agent_engines.cancel_query_job(
                name=args.agent_resource, config={"operation_name": job_name},
            )
            write(args.result, {"event": "cancel_requested", "attempt_id": attempt_id,
                                "job_name": job_name, "status": safe_status(cancellation)})
        except Exception as exc:
            write(args.result, {"event": "cancel_failed", "attempt_id": attempt_id,
                                "job_name": job_name, "error_type": type(exc).__name__})

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
        output = gcs_output_summary(storage.Client(project=args.project), args.output_gcs_uri)
        write(args.result, {"event": "gcs_output", "attempt_id": attempt_id, **output})
    except Exception as exc:
        output_error = type(exc).__name__
        write(args.result, {"event": "gcs_output", "attempt_id": attempt_id,
                            "uri": args.output_gcs_uri, "error_type": output_error})

    evaluation = evaluate_evidence(
        log_evidence=log_evidence, status_history=status_history, output=output,
        log_error=log_error, output_error=output_error,
    )
    write(args.result, {"event": "evaluation", "attempt_id": attempt_id, "marker": marker,
                        "job_name": job_name, "ended_at": ended.isoformat(),
                        "log_window": {"started_at": log_started.isoformat(), "ended_at": log_ended.isoformat()},
                        **evaluation})


if __name__ == "__main__":
    main()
