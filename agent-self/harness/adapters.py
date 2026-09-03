from __future__ import annotations

from typing import Any

try:
    from .models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope
except ImportError:  # pragma: no cover - direct-script import
    from models import AgentEnvelope, HookEvent, HookResult, ToolEnvelope


# Runtime providers accepted by the shared dispatcher. `grok` (xAI Grok CLI) was
# added on the live tree 2026-08-07 and ported 2026-09-02; `cyberstrike` lands
# here as a DISPATCH-ONLY provider on 2026-09-02 per the plugin-bridge contract:
# normalize into the shared HookEvent, but do NOT infer hook registration support
# from this set. Adding a provider to argparse `choices` alone is NOT sufficient:
# this set is the second gate — normalize_event/render_output raise on a
# non-member and dispatcher.main() swallows that ValueError (`except Exception:
# return 0`), so a half-fix makes every hook a SILENT no-op instead of a
# mislabelled or translated record. Both gates move together.
SUPPORTED_PROVIDERS = {"claude", "codex", "grok", "cyberstrike"}
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
# is rejected instead of injected. Verified 2026-07-27 against the installed
# claude 2.1.220 binary: its output union has literals for PreToolUse,
# UserPromptSubmit, UserPromptExpansion, SessionStart, Setup, SubagentStart,
# PostToolUse, PostToolUseFailure, PostToolBatch, Stop, SubagentStop,
# PermissionDenied, Notification, PermissionRequest, Elicitation,
# ElicitationResult, CwdChanged, FileChanged, WorktreeCreate and MessageDisplay
# — and nothing else:
#   * PostCompact / TaskCompleted / TaskCreated / TeammateIdle have no member at
#     all, so the union fails to parse, the validator returns a validationError
#     and the host degrades the ENTIRE hook payload to plainText + a non-blocking
#     hook error. The context is not injected; the whole output is discarded.
#   * PermissionDenied's member is {hookEventName, retry?: boolean} only — the
#     object is non-strict, so additionalContext is silently STRIPPED (the host
#     logs "unrecognized keys (ignored): hookSpecificOutput.additionalContext").
# Both failure shapes lose the context, so these render as systemMessage, which
# every provider surfaces. ConfigChange was already excluded for the same
# reason (a config-drift sentinel is a system-level notice). The replica of the
# union that pins this lives in tests/test_native_events.py
# (HOST_HOOK_SPECIFIC_OUTPUT_UNION).
_NO_NATIVE_CONTEXT_EVENTS = {
    "PostCompact",
    "TaskCompleted",
    "TaskCreated",
    "TeammateIdle",
    "PermissionDenied",
    "ConfigChange",
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
        # `turn_id` is NOT part of the claude base hook payload: its builder emits
        # {session_id, transcript_path, cwd, prompt_id, permission_mode, agent_id,
        # agent_type, effort} and names the turn `prompt_id` (only MessageDisplay
        # carries a literal turn_id). Reading turn_id alone left it "" on every
        # claude event, and an empty turn DISABLES the turn filter in
        # ledger._receipts / _has_legacy_verification / last_mutation_seq —
        # measured 2026-07-27 on the live ledger, 112076/112076 claude tool_result
        # records had turn_id == "" against 16970/16971 populated for codex, i.e.
        # turn scoping was 100% inert on claude. prompt_id is the provider's
        # canonical turn identity, so it is the fallback; codex keeps winning with
        # its own turn_id. models.HookEvent.evidence_turn_id still covers the case
        # where neither key is present (session-derived token).
        turn_id=str(_first_present(data, ("turn_id", "prompt_id", "promptId")) or ""),
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
    if provider_name == "cyberstrike":
        # The CyberStrike bridge consumes the provider-neutral HookResult
        # contract directly and performs its own Node-side validation/translation.
        return result.to_dict()

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
            # Never emit hookSpecificOutput for an event the host's output union
            # cannot carry it on — the payload would be dropped, not injected.
            return {"systemMessage": message}
        if event_name in _CONTEXT_EVENTS:
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": message,
                }
            }
        # grok rides the claude branch, NOT the codex fallthrough. Two reasons,
        # both measured against the shipped grok.exe (2026-08-07):
        #   1. Grok's command-hook output vocabulary is {additionalContext,
        #      decision, continue, stopReason, hookSpecificOutput} —
        #      `systemMessage` is absent, so the codex fallthrough below would be
        #      parsed and then DROPPED. Its own docs give the Stop example
        #      verbatim: {"hookSpecificOutput":{"hookEventName":"Stop",
        #      "additionalContext":"..."}}.
        #   2. Grok's hooks were already registered as `--provider claude`, so this
        #      keeps the emitted wire bytes byte-identical to what Grok has been
        #      receiving all along. The provider rename is an ATTRIBUTION fix; it
        #      must not silently change Grok's runtime behaviour.
        # Caveat (grok-only): on Grok an additionalContext on Stop is "non-error
        # feedback" that keeps the agent working and counts toward its
        # 8-continuation cap, whereas on claude it is inert injected context.
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
