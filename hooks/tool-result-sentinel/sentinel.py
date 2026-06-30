#!/usr/bin/env python3
r"""tool-result-sentinel/sentinel.py — PostToolUse hook (matcher: * / all tools).

GENERIC TOOL-RESULT BOUNDARY GUARD. Classifies EVERY tool result as
SUCCESS / FAILED / AMBIGUOUS and, on FAILED/AMBIGUOUS, injects a one-shot
"TOOL <name> returned a FAILURE/AMBIGUOUS result — do NOT treat as success."
so the agent cannot silently sail past a tool that quietly failed.

WHY THIS EXISTS / THE GAP IT FILLS (NON-DUPLICATIVE vs B1):
  * anti-degen/fingerprint.py only fires after the SAME (tool,args,output) repeats
    >=3 times — a stuck LOOP. It says nothing about a SINGLE call that failed.
  * claim-guard/claim-check.py runs at Stop, checks success *claims* against a
    Bash-only ledger. It never inspects MCP results and never fires mid-turn.
  * This hook is the per-call, all-tools classifier that catches the archetype
    where a tool (e.g. basic-memory) returns an error / "not connected" / times
    out and the agent keeps going as if it worked (the 4h-silent-memory-loss).

CLASSIFICATION (intentionally conservative — false positives are worse than misses):
  FAILED (high confidence):
    - MCP error envelope: isError == true, or success == false, or
      status in {error,failed}, or a non-empty `error` field, or interrupted.
    - A numeric exit/return code field present and != 0.
    - For MCP tools only: result text matches an INFRA-failure phrase
      (not connected / failed to connect / connection refused / server not
      running / timed out / MCP error / tool not found / ECONNREFUSED ...).
  AMBIGUOUS (medium):
    - empty-output-where-output-is-expected: an MCP "must-return-content" tool
      (decompile/disassemble/fetch/read_/get_/download/extract/convert/render)
      returned empty / None / "" / "[]" / "{}" / "null".
  SUCCESS: everything else -> silent (no I/O, no output).

  Deliberate restraint: Bash/PowerShell results are judged by STRUCTURE ONLY
  (exit code / interrupted) — never by text phrases — because normal command
  output legitimately contains the words "error"/"failed". list_/search_/find_/
  query/grep MCP tools are NOT in the empty-expected set (empty is a valid answer).

THROTTLE — once per identical failure: a per-session set of warned
fingerprints = sha256(tool_name, args_hash). A repeated identical failing call
is silent the 2nd time (the agent already got the message); a DIFFERENT failing
call (different tool or args) still warns.

HOOK LAW: inject-only (exit 0 + additionalContext); a failed tool is not a
dangerous op (AGENTS.md s6) so NO exit-2 block. FAIL-OPEN: every path wrapped in
try/except -> exit 0. Stdlib-only, no file I/O on the SUCCESS hot path.

Opt-out: TOOL_SENTINEL=off in env, or a hooks/tool-result-sentinel/.disabled file.

settings.json (PostToolUse, matcher "*"):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/tool-result-sentinel/sentinel.py",
   "timeout":8,"statusMessage":"Tool-result sentinel (failure boundary guard)"}
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
WARN_ROOT = Path(
    os.environ.get(
        "TOOL_SENTINEL_ROOT",
        str(Path(tempfile.gettempdir()) / "claude-tool-sentinel"),
    )
)
MAX_WARNED = 400  # cap the per-session warned-fingerprint list

# Tools judged by STRUCTURE only (their text output legitimately contains "error").
_STRUCTURAL_ONLY = {"Bash", "PowerShell"}

# MCP infra/transport failure phrases (applied to MCP results only).
_INFRA_FAIL = re.compile(
    r"(?:"
    r"not\s+connected"
    r"|failed\s+to\s+connect|could\s+not\s+connect|cannot\s+connect|unable\s+to\s+connect"
    r"|connection\s+(?:refused|reset|closed|error|timed?\s*out)"
    r"|econnrefused|etimedout|enotfound|econnreset"
    r"|server\s+(?:is\s+)?(?:not\s+running|not\s+responding|unavailable|unreachable)"
    r"|is\s+not\s+responding"
    r"|tim(?:ed|e)\s*[- ]?\s*out|timeout\s+(?:exceeded|of|after)"
    r"|mcp\s+error|tool\s+not\s+found|no\s+such\s+tool|unknown\s+tool"
    r"|no\s+tools?\s+available|service\s+unavailable|503\b"
    r"|internal\s+server\s+error|failed\s+to\s+(?:execute|invoke|call)"
    r")",
    re.IGNORECASE,
)

# MCP tools for which an EMPTY result is suspicious (they must return content).
_EXPECTS_CONTENT = re.compile(
    r"(?:decompile|disassemble|fetch|download|extract|convert|render"
    r"|read_|get_(?!.*list)|hexdump|dump_)",
    re.IGNORECASE,
)
# ... but these read patterns can legitimately be empty -> NOT empty-checked.
_EMPTY_OK = re.compile(
    r"(?:list_|search_|find_|query|grep|_list\b|enumerate|scan)", re.IGNORECASE
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _args_hash(tool_input) -> str:
    try:
        norm = json.dumps(
            tool_input,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=repr,
        )
    except Exception:
        norm = repr(tool_input)
    return _sha(norm)[:32]


def _warn_file(session_id: str) -> Path:
    WARN_ROOT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(session_id))[
        :80
    ]
    return WARN_ROOT / f"{safe or 'unknown'}.json"


def _already_warned(session_id: str, fp: str) -> bool:
    f = _warn_file(session_id)
    if not f.exists():
        return False
    try:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        return isinstance(data, list) and fp in data
    except Exception:
        return False


def _mark_warned(session_id: str, fp: str) -> None:
    f = _warn_file(session_id)
    data = []
    try:
        if f.exists():
            loaded = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, list):
                data = loaded
    except Exception:
        data = []
    if fp not in data:
        data.append(fp)
    if len(data) > MAX_WARNED:
        data = data[-MAX_WARNED:]
    try:
        f.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _gather_text(resp) -> str:
    """Flatten a tool_response into a searchable text blob (bounded)."""
    parts: list[str] = []

    def _walk(o, depth=0):
        if depth > 6 or len(parts) > 60:
            return
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for k in (
                "text",
                "stdout",
                "stderr",
                "message",
                "error",
                "detail",
                "content",
                "result",
                "output",
                "data",
                "body",
            ):
                if k in o:
                    _walk(o[k], depth + 1)
        elif isinstance(o, list):
            for item in o[:20]:
                _walk(item, depth + 1)

    try:
        _walk(resp)
    except Exception:
        pass
    return " ".join(parts)[:8000]


def _is_empty_result(resp) -> bool:
    if resp is None:
        return True
    if isinstance(resp, str):
        return resp.strip() in ("", "[]", "{}", "null", "None")
    if isinstance(resp, (list, dict)) and len(resp) == 0:
        return True
    if isinstance(resp, dict):
        # MCP shape {"content": []} or {"content": [{"text":""}]}
        c = resp.get("content")
        if c is not None:
            txt = _gather_text(c).strip()
            return txt in ("", "[]", "{}", "null", "None")
        # only-text shape
        if set(resp.keys()) <= {"type"}:
            return True
    return False


def _structural_failed(resp) -> tuple[bool, str]:
    """Structural FAILED signals usable for ANY tool (incl. Bash)."""
    if not isinstance(resp, dict):
        return False, ""
    # numeric exit/return codes
    for key in (
        "exit_code",
        "exitCode",
        "returncode",
        "return_code",
        "code",
        "status_code",
    ):
        val = resp.get(key)
        if val is not None:
            try:
                iv = int(val)
                if iv != 0:
                    return True, f"exit code {iv}"
                return False, ""  # explicit success exit code -> trust it
            except (TypeError, ValueError):
                pass
    if resp.get("isError") is True or resp.get("is_error") is True:
        return True, "isError=true"
    if resp.get("interrupted") is True:
        return True, "interrupted"
    if resp.get("success") is False or resp.get("ok") is False:
        return True, "success=false"
    st = str(resp.get("status") or "").lower()
    if st in ("error", "failed", "failure"):
        return True, f"status={st}"
    err = resp.get("error")
    if err and not isinstance(err, bool):
        es = str(err).strip()
        if es and es.lower() not in ("none", "null", "false", "0", ""):
            return True, "error field set"
    # nested wrappers
    for k in ("output", "result"):
        nested = resp.get(k)
        if isinstance(nested, dict):
            f, r = _structural_failed(nested)
            if f:
                return True, r
    return False, ""


def classify(tool_name: str, tool_input, resp) -> tuple[str, str]:
    """Return (verdict, reason). verdict in SUCCESS/FAILED/AMBIGUOUS."""
    # 1. Structural FAILED (all tools).
    failed, reason = _structural_failed(resp)
    if failed:
        return "FAILED", reason

    is_mcp = tool_name.startswith("mcp__")

    # 2. MCP-only: infra/transport failure phrases in the result text.
    if is_mcp:
        text = _gather_text(resp)
        if text and _INFRA_FAIL.search(text):
            m = _INFRA_FAIL.search(text)
            return "FAILED", f"infra-failure text: '{m.group(0)}'"

    # 3. AMBIGUOUS: empty where content is expected (MCP must-return-content tools).
    if (
        is_mcp
        and _EXPECTS_CONTENT.search(tool_name)
        and not _EMPTY_OK.search(tool_name)
    ):
        if _is_empty_result(resp):
            return "AMBIGUOUS", "empty result where content was expected"

    return "SUCCESS", ""


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("TOOL_SENTINEL", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        tool_name = str(data.get("tool_name") or "")
        if not tool_name:
            return 0
        tool_input = data.get("tool_input") or {}
        resp = data.get("tool_response")
        if resp is None:
            resp = data.get("tool_output")

        verdict, reason = classify(tool_name, tool_input, resp)
        if verdict == "SUCCESS":
            return 0  # hot path: no file I/O, no output

        session_id = str(data.get("session_id") or "unknown")
        fp = _sha(tool_name + "\x00" + _args_hash(tool_input))
        if _already_warned(session_id, fp):
            return 0  # throttle: once per identical failure
        _mark_warned(session_id, fp)

        if verdict == "FAILED":
            msg = (
                f"[tool-sentinel] TOOL `{tool_name}` returned a FAILED result "
                f"({reason}). Do NOT treat this as success: re-run, fix the "
                f"underlying cause, or surface the failure explicitly — do not "
                f"build on its (missing/garbage) output."
            )
        else:  # AMBIGUOUS
            msg = (
                f"[tool-sentinel] TOOL `{tool_name}` returned an AMBIGUOUS result "
                f"({reason}). Verify it actually did what you intended before "
                f"relying on it — an empty/odd result is not a confirmed success."
            )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": msg,
                    }
                }
            )
        )
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
