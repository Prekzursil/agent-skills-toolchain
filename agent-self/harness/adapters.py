from __future__ import annotations

from typing import Any

try:
    from .models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope
except ImportError:  # pragma: no cover - direct-script import
    from models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope


SUPPORTED_PROVIDERS = {"claude", "codex"}
_CONTEXT_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    # Post-cutoff native events whose handlers inject context. Registering them
    # here makes an inject render as native additionalContext (not a bare
    # systemMessage) so the PostCompact re-anchor, the Agent-Teams lifecycle
    # watchers (TaskCompleted/TaskCreated/TeammateIdle) and the failure channel
    # (PostToolUseFailure/PermissionDenied) surface their context in-band.
    # ConfigChange is intentionally NOT here: a config-drift sentinel is a
    # system-level notice, so its inject renders as systemMessage.
    "PostCompact",
    "TaskCompleted",
    "TaskCreated",
    "TeammateIdle",
    "PostToolUseFailure",
    "PermissionDenied",
}

# Native events that carry an agent/teammate identity in their payload. Their
# transcript, when present under the generic `transcript_path` key, is mapped
# onto the agent envelope (SubagentStart/Stop already did this).
_AGENT_EVENTS = {
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
}

# Payload aliases that all mean "the outcome/result of this event". The
# failure channel (PostToolUseFailure/PermissionDenied) reports the error or
# the denial reason under one of these; mapping it onto the EXISTING
# tool.result field lets the verification / anti-degeneration modules observe
# a failure without any new HookEvent field.
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
    # Result resolution keeps the historical order (tool_response/output/result
    # first) so existing normalization is unchanged; the failure-channel aliases
    # only fill in when no standard result key is present.
    tool_result = _first_present(data, _RESULT_ALIASES)

    transcript = data.get("agent_transcript_path")
    if transcript is None and reported_event in _AGENT_EVENTS:
        transcript = data.get("transcript_path")

    # Agent/teammate/task identity: an Agent-Teams task or teammate event names
    # its actor under task_* / teammate_* keys; map those onto the existing
    # agent envelope so the subagent/lifecycle modules recognize them.
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
    # D17-F4 · the spawning task/agent. The child aliases above were already
    # accepted while every parent spelling was dropped on the floor, so a host
    # that DID report the edge still produced an unjoinable completion record.
    # Task lineage wins over agent lineage when a host sends both.
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

    # A task summary is the closest existing analogue to an assistant message,
    # so a TaskCompleted/TeammateIdle summary maps onto last_assistant_message
    # when the host did not provide one directly.
    last_message = _first_present(
        data, ("last_assistant_message", "summary", "task_summary", "taskSummary")
    )

    return HookEvent(
        schema_version=1,
        provider=provider_name,
        event=str(event_name or reported_event),
        session_id=str(data.get("session_id") or "unknown"),
        turn_id=str(data.get("turn_id") or ""),
        cwd=str(data.get("cwd") or "."),
        permission_mode=str(data.get("permission_mode") or "default"),
        tool=ToolEnvelope(
            # Accept the camelCase spellings too. Every other envelope field here was
            # already alias-tolerant; the tool name and input were the sole exception, and
            # they are the fields the destructive-command guard reads. Measured 2026-07-26
            # with HARNESS_LIFECYCLE_GUARD=1: `rm -rf /tmp/victim` as tool_name/tool_input
            # was denied, the same command as toolName/toolInput normalized to an empty
            # tool and was ALLOWED. A safety guard must not fail open on payload casing.
            name=str(data.get("tool_name") or data.get("toolName") or ""),
            id=str(
                data.get("tool_use_id")
                or data.get("tool_id")
                or data.get("toolUseId")
                or data.get("toolId")
                or ""
            ),
            # `is not None` preserved rather than collapsed to `or`: an intentional empty
            # dict is a real payload and must not fall through to the alias.
            input=(
                data.get("tool_input")
                if data.get("tool_input") is not None
                else (
                    data.get("toolInput") if data.get("toolInput") is not None else {}
                )
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
    """Translate the core result into current provider-native hook JSON."""
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
        if event_name in _CONTEXT_EVENTS:
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message,
                }
            }
        if event_name in {"Stop", "SubagentStop"} and provider_name == "claude":
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message,
                }
            }
        return {"systemMessage": message}

    return {}
