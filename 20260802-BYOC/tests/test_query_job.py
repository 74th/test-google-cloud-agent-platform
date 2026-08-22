import json
from datetime import UTC, datetime

from scripts.query_job import build_log_filter, evaluate_evidence, safe_log_summary


def log(event, request_id="request-1", **fields):
    return {"event": event, "request_id": request_id, **fields}


def evidence(marker="marker-1", *, failed=False):
    processing_event = "query_failed" if failed else "query_completed"
    processing = log(processing_event, verification_id=marker, error_type="RuntimeError" if failed else None)
    processing = {key: value for key, value in processing.items() if value is not None}
    return {
        "root_received": [log("http_received", method="POST", path="/")],
        "root_completed": [log("http_completed", method="POST", path="/", status=500 if failed else 200)],
        "marker_events": [processing],
        "search_complete": True,
        "marker": marker,
    }


def test_log_filter_contains_agent_and_bounded_window():
    started = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
    ended = datetime(2026, 8, 21, 0, 5, tzinfo=UTC)
    filter_ = build_log_filter("projects/p/locations/l/reasoningEngines/123", started, ended)
    assert "reasoning_engine_id=\"123\"" in filter_
    assert started.isoformat() in filter_
    assert ended.isoformat() in filter_
    assert 'textPayload:"http_received"' in filter_


def test_success_evaluation_has_all_four_stages_and_no_secret():
    result = evaluate_evidence(
        log_evidence=evidence(),
        status_history=[{"state": "SUCCEEDED"}],
        output={"uri": "gs://bucket/output.json", "exists": True, "size": 12},
    )
    assert result["result"] == "動作確認"
    assert set(result["stages"]) == {"http_delivery", "processing", "job_terminal_state", "gcs_output"}
    assert "secret-value" not in json.dumps(result)


def test_root_delivery_with_processing_failure_is_not_success():
    result = evaluate_evidence(
        log_evidence=evidence(failed=True),
        status_history=[{"state": "FAILED"}],
        output={"uri": "gs://bucket/output.json", "exists": False},
    )
    assert result["result"] == "配送確認・動作未確認"
    assert result["stages"]["processing"]["state"] == "failure"


def test_missing_root_log_is_unreached():
    result = evaluate_evidence(
        log_evidence={"root_received": [], "marker_events": [], "search_complete": True},
        status_history=[{"state": "RUNNING"}],
        output={"uri": "gs://bucket/output.json", "exists": False},
    )
    assert result["result"] == "未到達"


def test_status_field_is_normalized_for_agent_platform_results():
    from scripts.query_job import safe_status

    assert safe_status({"status": "RUNNING", "operation_name": "operations/1"}) == {
        "state": "RUNNING",
        "operation_name": "operations/1",
    }


def test_missing_cloud_evidence_is_undetermined_and_log_summary_is_allowlisted():
    result = evaluate_evidence(
        log_evidence=None,
        status_history=[{"state": "SUCCEEDED"}],
        output=None,
        log_error="PermissionDenied",
    )
    assert result["result"] == "判定不能"
    summary = safe_log_summary({"text_payload": '{"event":"query_completed","secret":"do-not-persist"}'})
    serialized = json.dumps(summary)
    assert "do-not-persist" not in serialized
    assert summary["event"] == "query_completed"
