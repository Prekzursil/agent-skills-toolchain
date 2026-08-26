from __future__ import annotations

from typing import Any

try:
    from .models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope
except ImportError:  # pragma: no cover - direct-script import
    from models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope


# `grok` (xAI Grok CLI) added 2026-08-07. Its hooks were previously registered
# with `--provider claude`, so every Grok turn was attributed to claude in the
# ledger. Adding it to the argparse `choices` alone is NOT sufficient: this set
# is the second gate — normalize_event/render_output raise on a non-member and
# dispatcher.main() swallows that ValueError (`except Exception: return 0`), so
# a half-fix makes every Grok hook a SILENT no-op instead of a mislabelled
# record. Both gates move together.
SUPPORTED_PROVIDERS = {"claude", "codex", "grok"}
_CONTEXT_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    # PostToolUseFailure IS a member of the host's hookSpecificOutput union and
    # does accept additionalContext, so the failure channel stays in-band.
    "PostToolUseFailure",
}

# Events that FIRE as hook inputs but have NO additionalContext-bearing member
# in the host's hookSpecificOutput output union, so an inject rendered as
# {"hookSpecificOutput": {"hookEventName": <name>, "additionalContext": ...}}
# is rejected instead of injected.
_NO_NATIVE_CONTEXT_EVENTS = {
    "PostCompact",
    "TaskCompleted",
    "TaskCreated",
    "TeammateIdle",
    "PermissionDenied",
    "ConfigChange",
}

_AGENT_EVENTS = {
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
}

_RESULT_ALIASES = (
    "tool_response",
    "tool_output",
    "tool_result",
    "error",
    "tool_error",
    "error_message",
    "errorMessage",
    "permission_decision_reason",
    "permissionDecisionReason",
    "reason",
    "failure",
    "result",
)


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def normalize_event(
    raw: dict[str, Any], *, provider: str, event_name: str
) -> HookEvent:
    provider_name = str(provider or "").lower()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider_name}")

    data = raw if isinstance(raw, dict) else {}
    reported_event = str(data.get("hook_event_name") or event_name or "")
    tool_result = _first_present(data, _RESULT_ALIASES)

    transcript = data.get("agent_transcript_path")
    if transcript is None and reported_event in _AGENT_EVENTS:
        transcript = data.get("transcript_path")

    agent_id = _first_present(
        data, ("agent_id", "task_id", "taskId", "teammate_id", "teammateId")
    )
    agent_type = _first_present(
        data,
        (
            "agent_type",
            "task_type",
            "task_name",
            "taskName",
            "teammate",
            "teammate_name",
        ),
    )
    agent_parent_id = _first_present(
        data,
        (
            "parent_task_id",
            "parentTaskId",
            "parent_agent_id",
            "parentAgentId",
            "parent_id",
            "parentId",
        ),
    )
    last_message = _first_present(
        data, ("last_assistant_message", "summary", "task_summary", "taskSummary")
    )

    return HookEvent(
        schema_version=1,
        provider=provider_name,
        event=str(event_name or reported_event),
        session_id=str(data.get("session_id") or "unknown"),
        # Claude reports prompt_id rather than turn_id on its base hook payload,
        # so prompt_id is the canonical fallback when the host leaves turn_id blank.
        turn_id=str(_first_present(data, ("turn_id", "prompt_id", "promptId")) or ""),
        cwd=str(data.get("cwd") or "."),
        permission_mode=str(data.get("permission_mode") or "default"),
        tool=ToolEnvelope(
            name=str(_first_present(data, ("tool_name", "toolName")) or ""),
            id=str(
                _first_present(data, ("tool_use_id", "tool_id", "toolUseId", "toolId"))
                or ""
            ),
            input=(
                _first_present(data, ("tool_input", "toolInput"))
                if _first_present(data, ("tool_input", "toolInput")) is not None
                else {}
            ),
            result=tool_result,
        ),
        last_assistant_message=str(last_message or ""),
        prompt=str(data.get("prompt") or ""),
        source=str(data.get("source") or ""),
        trigger=str(
            data.get("trigger")
            or (
                "stop_hook_active"
                if str(data.get("stop_hook_active", "")).lower() in {"true", "1"}
                else ""
            )
        ),
        transcript_path=str(data.get("transcript_path") or ""),
        agent=AgentEnvelope(
            id=str(agent_id or ""),
            type=str(agent_type or ""),
            transcript_path=str(transcript or ""),
            parent_id=str(agent_parent_id or ""),
        ),
    )


def _message(result: HookResult) -> str:
    if result.additional_context:
        return "\n\n".join(x for x in result.additional_context if x)
    if result.continuation:
        return result.continuation
    return (
        result.reason_code.replace("_", " ").strip() or "Blocked by lifecycle policy."
    )


def render_output(
    result: HookResult, *, provider: str, event_name: str
) -> dict[str, Any]:
    provider_name = str(provider).lower()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider_name}")

    message = _message(result)

    if result.action == "block":
        if event_name == "PreToolUse":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": message,
                }
            }
        if event_name == "PermissionRequest":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "deny", "message": message},
                }
            }
        return {"decision": "block", "reason": message}

    if result.action == "continue":
        return {"decision": "block", "reason": result.continuation or message}

    if result.action == "inject" and message:
        if event_name in _NO_NATIVE_CONTEXT_EVENTS:
            return {"systemMessage": message}
        if event_name in _CONTEXT_EVENTS:
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message,
                }
            }
        if event_name in {"Stop", "SubagentStop"} and provider_name in {
            "claude",
            "grok",
        }:
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message,
                }
            }
        return {"systemMessage": message}

    return {}
