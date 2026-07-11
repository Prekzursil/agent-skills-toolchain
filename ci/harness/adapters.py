from __future__ import annotations

from typing import Any

try:
    from .models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope
except ImportError:  # Direct-script execution from dispatcher.py.
    from models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope


SUPPORTED_PROVIDERS = {"claude", "codex"}
_CONTEXT_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
}


def normalize_event(raw: dict[str, Any], *, provider: str, event_name: str) -> HookEvent:
    provider_name = str(provider or "").lower()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider_name}")

    data = raw if isinstance(raw, dict) else {}
    reported_event = str(data.get("hook_event_name") or event_name or "")
    tool_result = data.get("tool_response")
    if tool_result is None:
        tool_result = data.get("tool_output")
    if tool_result is None:
        tool_result = data.get("tool_result")

    transcript = data.get("agent_transcript_path")
    if transcript is None and reported_event in {"SubagentStart", "SubagentStop"}:
        transcript = data.get("transcript_path")

    return HookEvent(
        schema_version=1,
        provider=provider_name,
        event=str(event_name or reported_event),
        session_id=str(data.get("session_id") or "unknown"),
        turn_id=str(data.get("turn_id") or ""),
        cwd=str(data.get("cwd") or "."),
        permission_mode=str(data.get("permission_mode") or "default"),
        tool=ToolEnvelope(
            name=str(data.get("tool_name") or ""),
            id=str(data.get("tool_use_id") or data.get("tool_id") or ""),
            input=data.get("tool_input") if data.get("tool_input") is not None else {},
            result=tool_result,
        ),
        last_assistant_message=str(data.get("last_assistant_message") or ""),
        prompt=str(data.get("prompt") or ""),
        source=str(data.get("source") or ""),
        trigger=str(data.get("trigger") or ""),
        agent=AgentEnvelope(
            id=str(data.get("agent_id") or ""),
            type=str(data.get("agent_type") or ""),
            transcript_path=str(transcript or ""),
        ),
    )


def _message(result: HookResult) -> str:
    if result.additional_context:
        return "\n\n".join(x for x in result.additional_context if x)
    if result.continuation:
        return result.continuation
    return result.reason_code.replace("_", " ").strip() or "Blocked by lifecycle policy."


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

