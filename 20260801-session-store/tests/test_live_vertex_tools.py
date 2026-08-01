"""Vertex AI 上の Claude Agent SDK が custom MCP ツールと人間役の回答を扱う統合テスト。"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

import pytest

from claude_agent_sdk import create_sdk_mcp_server, tool

from claude_session_store.claude import AgentSdkRunner
from claude_session_store.config import Settings
from claude_session_store.models import StoredConversation
from claude_session_store.session_store import GoogleSessionStore


pytestmark = pytest.mark.live_vertex


def _json_value(value: Any) -> Any:
    """Vertex SDK のイベントを比較可能な JSON 値へ変換する。"""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _write_comparison_outputs(session_name: str, claude_session_id: str, store: GoogleSessionStore,
                              initial_response: str, resumed_response: str) -> None:
    """クラウドイベントと SDK ローカルトランスクリプトを tmp/ に別々に保存する。"""
    output_dir = Path("tmp") / claude_session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    events = [_json_value(event) for event in store.events.list(name=session_name)]
    session_store_path = output_dir / "session-store-events.json"
    session_store_path.write_text(json.dumps(events, ensure_ascii=False, indent=2, default=str) + "\n")

    transcript_paths = list((Path.home() / ".claude" / "projects").rglob(f"{claude_session_id}.jsonl"))
    assert len(transcript_paths) == 1, f"ローカルトランスクリプトが一意に見つかりません: {transcript_paths}"
    transcript_output_path = output_dir / "claude-transcript.jsonl"
    shutil.copyfile(transcript_paths[0], transcript_output_path)

    result_output_path = output_dir / "claude-final-responses.json"
    result_output_path.write_text(json.dumps({
        "initial_execution_result": initial_response,
        "resumed_execution_result": resumed_response,
    }, ensure_ascii=False, indent=2) + "\n")

    (output_dir / "comparison.json").write_text(json.dumps({
        "session_store_session_name": session_name,
        "claude_session_id": claude_session_id,
        "session_store_event_count": len(events),
        "session_store_events_file": session_store_path.name,
        "claude_transcript_file": transcript_output_path.name,
        "claude_final_responses_file": result_output_path.name,
        "note": "Session Store はアダプターが保存した会話要約と管理情報、ローカルトランスクリプトは SDK の詳細イベントを含む。",
    }, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_VERTEX_TESTS") != "1",
    reason="Vertex AI の課金対象テスト。RUN_LIVE_VERTEX_TESTS=1 を指定した場合だけ実行する。",
)
def test_live_tool_call_and_human_question():
    """tool/human 会話を Session Store に保存・取得し、同じ Claude session を再開する。"""
    tool_calls: list[str] = []
    human_answers = ["human-initial-answer", "human-resumed-answer"]
    nonce = secrets.token_urlsafe(18)

    @tool(
        "ask_human",
        "Ask a human operator one concise question and return the operator's answer.",
        {"question": str},
    )
    async def ask_human(arguments: dict[str, str]) -> dict[str, object]:
        tool_calls.append(arguments["question"])
        return {"content": [{"type": "text", "text": human_answers[len(tool_calls) - 1]}]}

    settings = Settings.from_env()
    runner, store = AgentSdkRunner(settings), GoogleSessionStore(settings)
    session_name = store.create_session()
    mcp_servers = {"human": create_sdk_mcp_server("human", "1.0.0", tools=[ask_human])}
    try:
        initial_prompt = (
            "必ず ask_human ツールを一度呼び、質問には verification-question を含めてください。"
            "ツール結果を受け取った後、Claude 自身の最終回答として "
            "`execution-result: <ツール結果>` の形式で実行結果を返してください。"
        )
        claude_session_id, tool_call_response = asyncio.run(runner.run(
            initial_prompt, mcp_servers=mcp_servers,
            allowed_tools=["mcp__human__ask_human"], max_turns=5,
        ))
        assert human_answers[0] in tool_call_response
        store.append_tool_interaction(session_name, "ask_human", {"question": tool_calls[0]}, human_answers[0])
        reported_session_id, initial_response = asyncio.run(runner.run(
            "直前に実行した ask_human の結果を確認し、Claude 自身の最終回答として "
            "`execution-result: <ツール結果>` の形式で報告してください。新しい tool call は行わないでください。",
            resume=claude_session_id,
            mcp_servers=mcp_servers, allowed_tools=["mcp__human__ask_human"], max_turns=5,
        ))
        assert reported_session_id == claude_session_id
        assert f"execution-result: {human_answers[0]}" in initial_response
        store.append_conversation(session_name, StoredConversation(
            claude_session_id, nonce, initial_prompt, initial_response,
        ))

        restored = store.retrieve_conversation(session_name)
        assert restored.claude_session_id == claude_session_id
        assert restored.user_prompt == initial_prompt
        assert restored.assistant_response == initial_response

        resumed_session_id, resumed_tool_call_response = asyncio.run(runner.run(
            "同じ ask_human ツールを一度呼び、質問には resumed-verification-question を含めてください。"
            "ツール結果を受け取った後、Claude 自身の最終回答として "
            "`execution-result: <ツール結果>` の形式で実行結果を返してください。",
            resume=restored.claude_session_id, mcp_servers=mcp_servers,
            allowed_tools=["mcp__human__ask_human"], max_turns=5,
        ))
        assert resumed_session_id == claude_session_id
        assert human_answers[1] in resumed_tool_call_response
        store.append_tool_interaction(session_name, "ask_human", {"question": tool_calls[1]}, human_answers[1])
        final_session_id, resumed_response = asyncio.run(runner.run(
            "直前に実行した ask_human の結果を確認し、Claude 自身の最終回答として "
            "`execution-result: <ツール結果>` の形式で報告してください。新しい tool call は行わないでください。",
            resume=restored.claude_session_id,
            mcp_servers=mcp_servers, allowed_tools=["mcp__human__ask_human"], max_turns=5,
        ))
        assert final_session_id == claude_session_id
        assert f"execution-result: {human_answers[1]}" in resumed_response
        assert len(tool_calls) == 2
        assert "verification-question" in tool_calls[0]
        assert "resumed-verification-question" in tool_calls[1]
        _write_comparison_outputs(session_name, claude_session_id, store, initial_response, resumed_response)
    finally:
        store.delete_session(session_name)
