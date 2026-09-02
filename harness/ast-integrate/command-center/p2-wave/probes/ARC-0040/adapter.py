"""A6 adapter-level guards for measured cross-vendor dispatch failures.

Every dispatch return from dispatch() / _checked() goes through terminal()
and therefore emits SUCCESS:<id> or FAILED:<id> <reason>. Silence is not a
legal return. Guards are validated by both_states.py against reproductions,
not against descriptions.

This module is the probe-local adapter specified by ARC-0040. It is not a
claim that production Codex CLI already calls it (A6 DESIGN.json is absent).
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional

import jsonschema

UNIT_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
WIN_CREATEPROCESS_CAP = 32767
CONSERVATIVE_INLINE_THRESHOLD = 24000
ESTATE_OVERFLOW_PAYLOAD = 34472
DEFAULT_PREFIX = ("codex", "exec", "--ignore-user-config")

# Mini typed schema used by the both-states corpus. The estate file this
# stands in for is command-center/schema/work-result.schema.json.
MINI_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["unit_id", "state", "sentinel"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 3},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "minLength": 8},
    },
    "additionalProperties": True,
}

PROGRESS_MARKERS = frozenset({"PROGRESS"})


def terminal(uid: str, ok: bool, reason: Optional[str] = None) -> dict:
    """Single factory for dispatch terminal states. No other marker shape."""
    unit = uid if UNIT_RE.match(uid) else "UNKNOWN"
    if ok:
        marker = f"SUCCESS:{unit}"
        return {
            "ok": True,
            "marker": marker,
            "reason": None,
            "unit_id": unit,
            "guard": None,
        }
    why = (reason or "unclassified").strip() or "unclassified"
    marker = f"FAILED:{unit} {why}"
    guard = why.split()[0]
    return {
        "ok": False,
        "marker": marker,
        "reason": why,
        "unit_id": unit,
        "guard": guard,
    }


def utf16_len(text: str) -> int:
    """Windows CreateProcess counts UTF-16 code units, not Python len()."""
    return len(text.encode("utf-16-le")) // 2


def assemble_argv(request: dict) -> list[str]:
    prefix = request.get("argv_prefix")
    if isinstance(prefix, (list, tuple)) and prefix:
        argv = [str(x) for x in prefix]
    else:
        argv = list(DEFAULT_PREFIX)
    transport = str(request.get("transport") or "inline")
    if transport == "prompt-file":
        path = str(request.get("prompt_file") or "prompt.txt")
        argv.extend(["--prompt-file", path])
    else:
        argv.extend(["--prompt", str(request.get("prompt") or "")])
    extra = request.get("extra_argv")
    if isinstance(extra, (list, tuple)):
        argv.extend(str(x) for x in extra)
    return argv


def assembled_command_line(request: dict) -> str:
    return " ".join(assemble_argv(request))


def assembled_utf16(request: dict) -> int:
    return utf16_len(assembled_command_line(request))


def _unit_id(request: dict) -> str:
    raw = request.get("unit_id")
    if isinstance(raw, str) and UNIT_RE.match(raw.strip()):
        return raw.strip()
    return "UNKNOWN"


def _background_reason(request: dict) -> Optional[str]:
    """Flag/role only. Must not scan result body (use-vs-mention)."""
    if request.get("background") is True:
        return "fire-and-forget background=True"
    if request.get("wait") is False:
        return "fire-and-forget wait=False"
    argv = assemble_argv(request)
    extra = request.get("extra_argv") or []
    tokens = set(argv) | {str(x) for x in extra}
    if "--background" in tokens:
        return "fire-and-forget --background"
    role = str(request.get("result_role") or "")
    if role in {"job-receipt", "background-start"}:
        return "fire-and-forget result_role=" + role
    return None


def _arglimit_reason(request: dict) -> Optional[str]:
    n = assembled_utf16(request)
    transport = str(request.get("transport") or "inline")
    if transport != "prompt-file" and n > CONSERVATIVE_INLINE_THRESHOLD:
        return (
            f"win-arg-limit assembled_utf16={n} "
            f"threshold={CONSERVATIVE_INLINE_THRESHOLD} transport=inline"
        )
    if n > WIN_CREATEPROCESS_CAP:
        return (
            f"win-arg-limit assembled_utf16={n} "
            f"cap={WIN_CREATEPROCESS_CAP} transport={transport}"
        )
    return None


def _as_text(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return json.dumps(raw, sort_keys=True, separators=(",", ":"))
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _progress_marker(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    for key in ("kind", "type", "stream", "event"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip().upper() in PROGRESS_MARKERS:
            return True
    return False


def is_progress_stream(raw: Any) -> bool:
    if isinstance(raw, Mapping):
        return _progress_marker(dict(raw))
    text = _as_text(raw)
    if text is None:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    try:
        doc = json.loads(stripped)
    except json.JSONDecodeError:
        doc = None
    if isinstance(doc, dict) and _progress_marker(doc):
        return True
    lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if len(lines) < 1:
        return False
    parsed: list[Any] = []
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            return False
    return bool(parsed) and all(_progress_marker(p) for p in parsed)


def _body_reason(request: dict) -> Optional[str]:
    raw = request.get("body")
    if raw is None:
        return "severed-stream missing-body"
    if is_progress_stream(raw):
        return "severed-stream progress-only"
    text = _as_text(raw)
    if text is None or not text.strip():
        return "severed-stream empty-body"
    return None


def _schema_reason(request: dict) -> Optional[str]:
    """Typed schema is enforced even when MCP tools are active.

    The known typed-schema-times-active-MCP interaction is skipping this
    check. Skipping is forbidden here; mcp_tools_active is recorded, not a
    bypass.
    """
    schema = request.get("output_schema")
    if not isinstance(schema, dict):
        schema = MINI_OUTPUT_SCHEMA
    raw = request.get("body")
    if isinstance(raw, Mapping):
        doc: Any = dict(raw)
    else:
        text = _as_text(raw)
        try:
            doc = json.loads(text or "")
        except json.JSONDecodeError:
            mcp = "mcp-active" if request.get("mcp_tools_active") else "mcp-off"
            return f"schema-invalid unparseable {mcp}"
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(doc))
    if errors:
        mcp = "mcp-active" if request.get("mcp_tools_active") else "mcp-off"
        return f"schema-invalid {mcp} {errors[0].message}"
    return None


def _checked(request: dict, uid: str) -> dict:
    reason = _background_reason(request)
    if reason:
        return terminal(uid, False, reason)
    reason = _arglimit_reason(request)
    if reason:
        return terminal(uid, False, reason)
    reason = _body_reason(request)
    if reason:
        return terminal(uid, False, reason)
    reason = _schema_reason(request)
    if reason:
        return terminal(uid, False, reason)
    return terminal(uid, True)


def dispatch(request: dict) -> dict:
    uid = _unit_id(request)
    try:
        return _checked(request, uid)
    except Exception as exc:
        return terminal(uid, False, f"adapter-exception {type(exc).__name__}")
