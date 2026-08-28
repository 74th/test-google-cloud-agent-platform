import json

from scripts.validate import CASES, log_host_and_disposition, mcp_e2e_passed, response_matches, run_case


def test_runner_normalizes_gateway_and_iap_decisions() -> None:
    gateway_entry = {
        "jsonPayload": {
            "enforcedGatewaySecurityPolicy": {
                "hostname": "github.com",
                "matchedRules": [{"action": "ALLOWED", "name": "default_denied"}],
            }
        }
    }
    authz_denied_gateway_entry = {
        "jsonPayload": {
            "authzPolicyInfo": {"result": "DENIED"},
            "enforcedGatewaySecurityPolicy": {
                "hostname": "www8.cao.go.jp",
                "matchedRules": [{"action": "ALLOWED", "name": "default_denied"}],
            },
        }
    }
    iap_entry = {
        "protoPayload": {
            "request": {"httpRequest": {"url": "https://www8.cao.go.jp/page"}},
            "authorizationInfo": [{"granted": False}],
        }
    }
    assert log_host_and_disposition(gateway_entry) == ("github.com", "allow")
    assert log_host_and_disposition(authz_denied_gateway_entry) == ("www8.cao.go.jp", "deny")
    assert log_host_and_disposition(iap_entry) == ("www8.cao.go.jp", "deny")


def test_runner_saves_prompt_response_status_and_log_evidence(tmp_path):
    logs = [
        {"host": "github.com", "disposition": "allow"},
        {"host": "www8.cao.go.jp", "disposition": "deny"},
    ]

    def invoke(case):
        if case.name == "github":
            return 0, "GitHub 74th のページを要約しました。", "GatewayWebFetch response host=github.com status=200"
        return 0, "ページを取得できません。回答を補完しません。", "GatewayWebFetch error host=www8.cao.go.jp type=HTTPError"

    context = {
        "verification_id": "fixture-1",
        "caller": "operator@example.com",
        "runtime_effective_identity": "agents.global.proj-1.system.id.goog/resources/aiplatform/projects/1/locations/us-central1/reasoningEngines/2",
        "gateway_id": "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress",
    }
    result = run_case(CASES[0], tmp_path / "github", invoke, {"text": "default_action: DENY\n  - host: github.com"}, logs, context)
    assert result["passed"] is True
    assert (tmp_path / "github" / "input.txt").is_file()
    assert json.loads((tmp_path / "github" / "result.json").read_text())["matched_log_entries"]

    result = run_case(CASES[1], tmp_path / "cao", invoke, {"text": "default_action: DENY\n  - host: github.com"}, logs, context)
    assert result["passed"] is True
    assert json.loads((tmp_path / "cao" / "result.json").read_text())["matched_log_entries"]


def test_runner_rejects_unrelated_or_incomplete_responses():
    assert response_matches(CASES[0], "GitHub 74th のページを要約しました。")
    assert not response_matches(CASES[0], "処理が完了しました。")
    assert response_matches(CASES[1], "ページを取得できませんでした。祝日一覧は補完しません。")
    assert not response_matches(CASES[1], "2027年の祝日:\n- 1月1日")


def test_runner_requires_correlation_for_pass(tmp_path):
    logs = [{"host": "github.com", "disposition": "allow"}]
    result = run_case(CASES[0], tmp_path / "github", lambda _: (0, "GitHub 74th の要約です。", "fetch ok"), {"text": "default_action: DENY"}, logs)
    assert result["passed"] is False
    assert result["correlation_complete"] is False


def test_mcp_e2e_is_gated_by_all_execution_layers():
    base = {
        "registry_service_id": "service",
        "interface_resolution": "resolved",
        "selected_tool": "GatewayWebFetch",
        "gateway_decision": "allow",
        "endpoint_authorization": "allow",
        "server_side_mcp_log": "event",
    }
    assert mcp_e2e_passed(base)
    assert not mcp_e2e_passed({**base, "server_side_mcp_log": None})
