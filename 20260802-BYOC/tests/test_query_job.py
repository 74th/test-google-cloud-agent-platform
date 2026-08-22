import json
from datetime import UTC, datetime

import pytest

from scripts.query_job import (
    _call_api,
    build_log_filter,
    effective_timeout_seconds,
    evaluate_evidence,
    query_payload,
    safe_log_summary,
)


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
    assert 'jsonPayload.event="http_received"' in filter_
    assert "proxy-container" in filter_


def test_query_payload_and_long_running_timeout_are_explicit():
    assert json.loads(query_payload("marker-1", 960)) == {
        "input": {"verification_id": "marker-1", "delay_seconds": 960}
    }
    assert effective_timeout_seconds(10, None) == 900
    assert effective_timeout_seconds(10, 120) == 120
    assert effective_timeout_seconds(960, None) == 1560
    assert effective_timeout_seconds(960, 60) == 1560


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


def test_proxy_log_summary_is_allowlisted_and_preserves_permission_classification():
    summary = safe_log_summary({
        "severity": "ERROR",
        "labels": {"container_name": "proxy-container"},
        "jsonPayload": {
            "stage": "gcs_input",
            "error_code": 403,
            "permission_name": "serviceusage.services.use",
            "message": "Authorization: Bearer secret https://example.test/?token=secret",
        },
    })
    serialized = json.dumps(summary)
    assert summary["container_name"] == "proxy-container"
    assert summary["permission_name"] == "serviceusage.services.use"
    assert "secret" not in serialized
    assert "message" not in summary


def test_evaluation_includes_gcs_input_and_proxy_failure_stage():
    log_evidence = {
        "root_received": [],
        "marker_events": [],
        "proxy_errors": [{"container_name": "proxy-container", "error_code": 403}],
        "search_complete": True,
    }
    result = evaluate_evidence(
        log_evidence=log_evidence,
        status_history=[{"state": "FAILED", "result": "container terminated"}],
        input={"uri": "gs://bucket/input.json", "exists": True},
        output={"uri": "gs://bucket/output.json", "exists": False},
    )
    assert result["result"] == "GCS入力取得失敗"
    assert result["stages"]["gcs_input"]["state"] == "failure"


def test_api_call_prints_before_after_and_complete_response(capsys):
    response = _call_api(
        "test.example.get",
        lambda: {"state": "RUNNING", "nested": [1, {"value": "full"}]},
        request={"name": "operations/1"},
    )

    assert response["nested"][1]["value"] == "full"
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["phase"] for record in records] == ["before", "after"]
    assert records[0]["state"] == "calling"
    assert records[0]["request"] == {"name": "operations/1"}
    assert records[1]["state"] == "completed"
    assert records[1]["response"] == {"state": "RUNNING", "nested": [1, {"value": "full"}]}
    assert records[0]["call_id"] == records[1]["call_id"]


def test_api_trace_can_summarize_non_serializable_log_entries(capsys):
    _call_api("logging.list_entries", lambda: [object()], response_for_trace=lambda values: {"count": len(values)})
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[-1]["response"] == {"count": 1}


def test_api_call_prints_failed_after_state(capsys):
    with pytest.raises(RuntimeError, match="api failed"):
        _call_api("test.example.fail", lambda: (_ for _ in ()).throw(RuntimeError("api failed")))

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert records[0]["state"] == "calling"
    assert records[1]["state"] == "failed"
    assert records[1]["error"] == {
        "type": "RuntimeError",
        "message": "api failed",
        "repr": "RuntimeError('api failed')",
    }
