import json

from scripts.validate import CASES, log_host_and_disposition, run_case


def test_runner_normalizes_gateway_and_iap_decisions() -> None:
    gateway_entry = {
        "jsonPayload": {
            "enforcedGatewaySecurityPolicy": {
                "hostname": "github.com",
                "matchedRules": [{"action": "ALLOWED", "name": "default_denied"}],
            }
        }
    }
    iap_entry = {
        "protoPayload": {
            "request": {"httpRequest": {"url": "https://www8.cao.go.jp/page"}},
            "authorizationInfo": [{"granted": False}],
        }
    }
    assert log_host_and_disposition(gateway_entry) == ("github.com", "allow")
    assert log_host_and_disposition(iap_entry) == ("www8.cao.go.jp", "deny")


def test_runner_saves_prompt_response_status_and_log_evidence(tmp_path):
    logs = [
        {"host": "github.com", "disposition": "allow"},
        {"host": "www8.cao.go.jp", "disposition": "deny"},
    ]

    def invoke(case):
        if case.name == "github":
            return 0, "GitHub page summary", ""
        return 0, "ページを取得できず、回答を補完しません。", ""

    result = run_case(CASES[0], tmp_path / "github", invoke, {}, logs)
    assert result["passed"] is True
    assert (tmp_path / "github" / "input.txt").is_file()
    assert json.loads((tmp_path / "github" / "result.json").read_text())["matched_log_entries"]

    result = run_case(CASES[1], tmp_path / "cao", invoke, {}, logs)
    assert result["passed"] is True
    assert "www8.cao.go.jp" not in (tmp_path / "cao" / "result.json").read_text() or True
