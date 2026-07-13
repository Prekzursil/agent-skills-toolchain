from __future__ import annotations

import json
from pathlib import Path

from harness.adapters import normalize_event, render_output
from harness.models import HookResult


def test_claude_and_codex_events_normalize_to_one_contract(tmp_path):
    common = {
        "session_id": "session-1",
        "turn_id": "turn-2",
        "cwd": str(tmp_path),
        "permission_mode": "bypassPermissions",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_use_id": "tool-3",
        "tool_input": {"command": "pytest -q"},
        "tool_response": {"exit_code": 0, "output": "12 passed"},
    }

    claude = normalize_event(common, provider="claude", event_name="PostToolUse")
    codex = normalize_event(common, provider="codex", event_name="PostToolUse")

    assert claude.to_dict() == codex.to_dict() | {"provider": "claude"}
    assert codex.provider == "codex"
    assert codex.tool.name == "Bash"
    assert codex.tool.id == "tool-3"
    assert codex.tool.input == {"command": "pytest -q"}
    assert codex.tool.result["exit_code"] == 0


def test_normalizer_supports_codex_subagent_transcript_field(tmp_path):
    event = normalize_event(
        {
            "session_id": "s",
            "cwd": str(tmp_path),
            "agent_id": "a",
            "agent_type": "reviewer",
            "agent_transcript_path": "C:/tmp/agent.jsonl",
            "last_assistant_message": "SUCCESS:review",
        },
        provider="codex",
        event_name="SubagentStop",
    )

    assert event.agent.id == "a"
    assert event.agent.type == "reviewer"
    assert event.agent.transcript_path == "C:/tmp/agent.jsonl"
    assert event.last_assistant_message == "SUCCESS:review"


def test_context_and_denial_render_in_native_shape_without_unsupported_fields():
    injected = HookResult.success(
        action="inject", additional_context=["ACTIVE GOAL: ship it"]
    )
    denied = HookResult.success(
        action="block",
        reason_code="secret_literal",
        additional_context=["Secret-bearing command blocked."],
    )

    for provider in ("claude", "codex"):
        context = render_output(injected, provider=provider, event_name="PreToolUse")
        block = render_output(denied, provider=provider, event_name="PreToolUse")
        assert context == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "ACTIVE GOAL: ship it",
            }
        }
        assert block["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert block["hookSpecificOutput"]["permissionDecisionReason"] == (
            "Secret-bearing command blocked."
        )
        assert "suppressOutput" not in json.dumps(context)
        assert "suppressOutput" not in json.dumps(block)


def test_permission_request_denial_uses_decision_object():
    result = HookResult.success(
        action="block", reason_code="irreversible", additional_context=["Blocked."]
    )
    rendered = render_output(result, provider="codex", event_name="PermissionRequest")

    assert rendered == {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": "Blocked."},
        }
    }


def test_noop_stop_renders_empty_json_because_plain_text_is_invalid():
    assert render_output(HookResult.success(), provider="codex", event_name="Stop") == {}


def test_core_result_schema_is_closed_and_contains_no_provider_wire_fields():
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "hook-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "status",
        "action",
        "reason_code",
        "additional_context",
        "continuation",
    }
    assert set(schema["required"]) == {
        "status",
        "action",
        "reason_code",
        "additional_context",
    }
    forbidden = {"hookSpecificOutput", "decision", "systemMessage", "suppressOutput"}
    assert forbidden.isdisjoint(schema["properties"])
