"""Executable semantics of the ARC-0088 hook contract.

A hook file on disk is not wiring. Wiring is a live invocation that
produces two independent signals: the dispatcher's own fire record and
an externally observable side effect written by the hook process.

Exit 2 is reserved for irreversible danger. Every other guidance path
injects and does not block. Internal errors, timeouts, and illegal
block attempts fail open (session continues, process exit 0).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

UNIT_ID = "ARC-0088"
SENTINEL = "SUCCESS:ARC-0088"

# Event names observed on this worktree's hook fixtures (PreToolUse,
# SessionStart) plus the remaining host-client events named in sibling
# catalogs. _USER-PROMPTS.md:10797-10822 is ABSENT; this list is
# reconstructed, not quoted from that source.
EVENT_TYPES: tuple[str, ...] = (
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Notification",
    "UserPromptSubmit",
    "SessionStart",
    "SessionEnd",
    "Stop",
    "SubagentStop",
    "PreCompact",
    "PermissionRequest",
)

STDIN_REQUIRED_FIELDS: tuple[str, ...] = (
    "session_id",
    "transcript_path",
    "cwd",
    "hook_event_name",
    "permission_mode",
)

EVENT_EXTRA_FIELDS: dict[str, tuple[str, ...]] = {
    "PreToolUse": ("tool_name", "tool_input"),
    "PostToolUse": ("tool_name", "tool_input", "tool_response"),
    "PostToolUseFailure": ("tool_name", "tool_input", "error"),
    "PermissionRequest": ("tool_name", "tool_input"),
    "UserPromptSubmit": ("prompt",),
    "Notification": ("message",),
    "SessionStart": ("source",),
    "SessionEnd": ("reason",),
    "Stop": ("stop_hook_active",),
    "SubagentStop": ("stop_hook_active",),
    "PreCompact": ("trigger",),
}

BLOCKING_EVENTS = frozenset({"PreToolUse", "PermissionRequest"})

IRREVERSIBLE_DANGER_CLASSES = frozenset(
    {
        "irreversible_fs_destroy",
        "production_datastore_destroy",
        "credential_exfil_untrusted_network",
        "destructive_force_push_protected_branch",
    }
)

NON_DANGEROUS_CONDITIONS = (
    "style_warning",
    "budget_advisory",
    "unknown_tool_name",
    "missing_additional_context",
    "linter_finding",
    "secret_scan_advisory",
)

EXIT_OK = 0
EXIT_BLOCK = 2
TIMEOUT_MS_DEFAULT = 60_000
SIDE_EFFECT_ENV = "ARC0088_SIDE_EFFECT"
FIRE_LOG_NAME = "dispatcher-fire.jsonl"


def default_stdin(
    event: str, cwd: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": "arc0088-session",
        "transcript_path": "/tmp/arc0088-transcript.jsonl",
        "cwd": cwd,
        "hook_event_name": event,
        "permission_mode": "default",
    }
    for field in EVENT_EXTRA_FIELDS.get(event, ()):
        if field == "tool_input":
            payload[field] = {}
        elif field == "stop_hook_active":
            payload[field] = False
        else:
            payload[field] = field
    if extra:
        payload.update(extra)
    return payload


def validate_stdin(payload: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not isinstance(payload, dict):
        return ["stdin-not-object"]
    for field in STDIN_REQUIRED_FIELDS:
        if field not in payload:
            errs.append(f"missing:{field}")
    event = str(payload.get("hook_event_name") or "")
    if event and event not in EVENT_TYPES:
        errs.append(f"unknown-event:{event}")
    for field in EVENT_EXTRA_FIELDS.get(event, ()):
        if field not in payload:
            errs.append(f"missing-event-field:{field}")
    return errs


def parse_json_stdout(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def extract_inject(doc: dict[str, Any] | None) -> str | None:
    if not doc:
        return None
    ctx = doc.get("additionalContext")
    if isinstance(ctx, str) and ctx.strip():
        return ctx
    nested = doc.get("hookSpecificOutput")
    if isinstance(nested, dict):
        ctx = nested.get("additionalContext")
        if isinstance(ctx, str) and ctx.strip():
            return ctx
    return None


def extract_danger_claim(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    danger = doc.get("danger")
    if isinstance(danger, dict):
        return danger
    if doc.get("decision") == "block" and isinstance(doc.get("reason"), dict):
        return doc["reason"]
    return None


def may_block(event: str, claim: dict[str, Any] | None) -> bool:
    if event not in BLOCKING_EVENTS:
        return False
    if not isinstance(claim, dict):
        return False
    if claim.get("irreversible") is not True:
        return False
    if str(claim.get("class") or "") not in IRREVERSIBLE_DANGER_CLASSES:
        return False
    if not str(claim.get("target") or "").strip():
        return False
    return True


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    hooks = doc.get("hooks") if isinstance(doc, dict) else None
    if not isinstance(hooks, list):
        return []
    return [item for item in hooks if isinstance(item, dict)]


def command_list(spec: dict[str, Any]) -> list[str]:
    cmd = spec.get("command")
    if isinstance(cmd, list) and all(isinstance(x, str) and x for x in cmd):
        return list(cmd)
    if isinstance(cmd, str) and cmd.strip():
        return [str(spec.get("interpreter") or sys.executable), cmd]
    return []


def wiring_proof(
    *,
    manifest_present: bool,
    file_present: bool,
    dispatcher_record_observed: bool,
    side_effect_observed: bool,
) -> dict[str, Any]:
    """Manifest/file presence is recorded and is never sufficient."""
    return {
        "manifest_present": bool(manifest_present),
        "file_present": bool(file_present),
        "dispatcher_record_observed": bool(dispatcher_record_observed),
        "side_effect_observed": bool(side_effect_observed),
        "wired": bool(dispatcher_record_observed and side_effect_observed),
        "insufficient_alone": ["manifest_present", "file_present"],
        "required_signals": ["dispatcher_record", "side_effect"],
    }


def _append_fire_record(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def invoke(
    spec: dict[str, Any] | None,
    payload: dict[str, Any],
    workdir: Path,
    *,
    registered: bool,
    file_present: bool,
    manifest_present: bool,
) -> dict[str, Any]:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    invocation_id = uuid.uuid4().hex
    event = str(payload.get("hook_event_name") or "")
    hook_id = str((spec or {}).get("id") or payload.get("hook_id") or "unregistered")
    fire_log = workdir / FIRE_LOG_NAME
    side_path = workdir / "side-effects" / invocation_id
    timeout_ms = int((spec or {}).get("timeout_ms") or TIMEOUT_MS_DEFAULT)
    stdin_errs = validate_stdin(payload)
    base: dict[str, Any] = {
        "unit_id": UNIT_ID,
        "hook_id": hook_id,
        "event": event,
        "invocation_id": invocation_id,
        "registered": registered,
        "raw_exit": None,
        "process_exit": EXIT_OK,
        "session_continue": True,
        "blocked": False,
        "inject": None,
        "fail_open_reason": None,
        "block_refused_reason": None,
        "timeout": False,
        "dispatcher_record_path": str(fire_log),
        "side_effect_path": str(side_path),
        "stdin_errors": stdin_errs,
    }

    def finish(*, dispatcher_observed: bool, side_observed: bool) -> dict[str, Any]:
        base["wiring"] = wiring_proof(
            manifest_present=manifest_present,
            file_present=file_present,
            dispatcher_record_observed=dispatcher_observed,
            side_effect_observed=side_observed,
        )
        return base

    if stdin_errs:
        base["fail_open_reason"] = "invalid-stdin:" + ",".join(stdin_errs)
        return finish(dispatcher_observed=False, side_observed=False)

    if not registered or spec is None:
        base["fail_open_reason"] = "not-registered"
        return finish(dispatcher_observed=False, side_observed=False)

    cmd = command_list(spec)
    if not cmd:
        base["fail_open_reason"] = "missing-command"
        return finish(dispatcher_observed=False, side_observed=False)

    env = os.environ.copy()
    env[SIDE_EFFECT_ENV] = str(side_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload),
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=max(timeout_ms, 1) / 1000.0,
            env=env,
            check=False,
        )
        raw_exit = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        base["timeout"] = True
        base["fail_open_reason"] = "timeout"
        record = {
            "invocation_id": invocation_id,
            "hook_id": hook_id,
            "event": event,
            "timeout": True,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
        _append_fire_record(fire_log, record)
        side_observed = side_path.is_file() and side_path.stat().st_size > 0
        return finish(dispatcher_observed=True, side_observed=side_observed)
    except OSError as exc:
        base["fail_open_reason"] = f"spawn-error:{type(exc).__name__}"
        return finish(dispatcher_observed=False, side_observed=False)

    parsed = parse_json_stdout(stdout)
    inject = extract_inject(parsed)
    claim = extract_danger_claim(parsed)
    base["raw_exit"] = raw_exit
    base["inject"] = inject
    record = {
        "invocation_id": invocation_id,
        "hook_id": hook_id,
        "event": event,
        "raw_exit": raw_exit,
        "timeout": False,
        "elapsed_ms": int((time.time() - started) * 1000),
        "stderr_bytes": len(stderr.encode("utf-8")),
    }
    _append_fire_record(fire_log, record)
    side_observed = side_path.is_file() and side_path.stat().st_size > 0

    if raw_exit == EXIT_BLOCK:
        if may_block(event, claim):
            base["blocked"] = True
            base["process_exit"] = EXIT_BLOCK
            base["session_continue"] = False
        else:
            base["blocked"] = False
            base["process_exit"] = EXIT_OK
            base["session_continue"] = True
            reason = (
                "exit-2-not-irreversible-danger"
                if event in BLOCKING_EVENTS
                else "exit-2-event-cannot-block"
            )
            base["block_refused_reason"] = reason
            if inject is None:
                base["inject"] = "block-refused:" + reason
    elif raw_exit != EXIT_OK:
        base["process_exit"] = EXIT_OK
        base["session_continue"] = True
        base["fail_open_reason"] = f"hook-nonzero-exit:{raw_exit}"
    else:
        base["process_exit"] = EXIT_OK
        base["session_continue"] = True

    return finish(dispatcher_observed=True, side_observed=side_observed)


def fire_event(
    manifest_path: Path,
    payload: dict[str, Any],
    workdir: Path,
    hook_id: str,
) -> dict[str, Any]:
    manifest_present = manifest_path.is_file()
    hooks = load_manifest(manifest_path) if manifest_present else []
    spec = next((h for h in hooks if str(h.get("id") or "") == hook_id), None)
    registered = bool(
        spec
        and spec.get("enabled") is not False
        and str(spec.get("event") or "") == str(payload.get("hook_event_name") or "")
    )
    script = ""
    if spec:
        cmd = command_list(spec)
        script = cmd[-1] if cmd else ""
    file_present = bool(script) and Path(script).is_file()
    return invoke(
        spec,
        payload,
        workdir,
        registered=registered,
        file_present=file_present,
        manifest_present=manifest_present,
    )
