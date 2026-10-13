#!/usr/bin/env python3
"""
Chaos + discrimination self-test for claude-code-mcp-guard (G-3b/G-2c).

Runs guard.py as a subprocess with synthetic hook-stdin payloads (shapes per
PROBE-depth-dial.md par4 keysets) and records exit code + stdout per case.
Writes SELFTEST-EVIDENCE.md next to this script. Exit code 0 only if every
case matches its expectation.

Expected outcomes:
  DENY  = exit 0, stdout parses as JSON, hookSpecificOutput.permissionDecision == "deny"
  ALLOW = exit 0, stdout empty (silent allow / fail-open)
"""

import hashlib
import json
import os
import subprocess
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard.py")
EVIDENCE = os.path.join(HERE, "SELFTEST-EVIDENCE.md")

BASE_MAIN = {
    "session_id": "probe-root-session-0001",
    "transcript_path": "C:\\probe\\projects\\probe-root-session-0001.jsonl",
    "cwd": "C:\\Users\\Prekzursil",
    "hook_event_name": "PreToolUse",
    "permission_mode": "default",
    "prompt_id": "probe-prompt-1",
    "tool_use_id": "probe-tuu-0",
    "effort": "medium",
    "tool_name": "mcp__claude-code-mcp__claude_code",
    "tool_input": {"prompt": "probe"},
}
SUBAGENT_EXTRA = {
    "agent_id": "a56f73158ab7e18ea",   # literal shape captured by the probe (16 hex)
    "agent_type": "general-purpose",
}


def payload(**overrides):
    p = dict(BASE_MAIN)
    p.update(SUBAGENT_EXTRA)
    for k, v in overrides.items():
        if v is ...:  # sentinel: delete key
            p.pop(k, None)
        else:
            p[k] = v
    return p


def run_guard(stdin_text):
    p = subprocess.run(
        [sys.executable, GUARD],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


CASES = [
    # (id, description, stdin, expected)
    ("T01", "subagent x mcp__claude-code-mcp__ tool -> DENY",
     json.dumps(payload(tool_use_id="t01")), "DENY"),
    ("T02", "main (no agent_id) x mcp__claude-code-mcp__ tool -> silent allow",
     json.dumps(payload(tool_use_id="t02", agent_id=..., agent_type=...)), "ALLOW"),
    ("T03", "subagent x mcp__McpHub__claude-code-mcp__ tool -> DENY",
     json.dumps(payload(tool_use_id="t03", tool_name="mcp__McpHub__claude-code-mcp__claude_code")), "DENY"),
    ("T04", "main x mcp__McpHub__claude-code-mcp__ tool -> silent allow",
     json.dumps(payload(tool_use_id="t04", tool_name="mcp__McpHub__claude-code-mcp__claude_code",
                        agent_id=..., agent_type=...)), "ALLOW"),
    ("T05", "subagent x unrelated MCP tool (mcp__github__) -> silent allow",
     json.dumps(payload(tool_use_id="t05", tool_name="mcp__github__create_issue")), "ALLOW"),
    ("T06", "garbage stdin 'not-json{{{' -> fail open",
     "not-json{{{", "ALLOW"),
    ("T07", "empty stdin -> fail open",
     "", "ALLOW"),
    ("T08", "empty JSON object '{}' -> fail open",
     "{}", "ALLOW"),
    ("T09", "missing tool_name (subagent context) -> fail open",
     json.dumps(payload(tool_use_id="t09", tool_name=...)), "ALLOW"),
    ("T10", "tool_name null -> fail open",
     json.dumps(payload(tool_use_id="t10", tool_name=None)), "ALLOW"),
    ("T11", "JSON array payload (non-dict) -> fail open",
     "[1,2,3]", "ALLOW"),
    ("T12", "agent_id empty string x guarded tool -> treated as no signal, silent allow",
     json.dumps(payload(tool_use_id="t12", agent_id="")), "ALLOW"),
    ("T13", "near-miss server 'mcp__claude-code-mcp2__' (strict prefix) -> silent allow",
     json.dumps(payload(tool_use_id="t13", tool_name="mcp__claude-code-mcp2__claude_code")), "ALLOW"),
]


def classify(rc, out):
    if rc != 0:
        return "NONZERO-EXIT"
    if out == "":
        return "ALLOW"
    try:
        doc = json.loads(out)
        d = doc.get("hookSpecificOutput", {}).get("permissionDecision")
        if d == "deny":
            return "DENY"
        return "UNEXPECTED-OUTPUT: " + out[:200]
    except Exception:
        return "UNPARSEABLE-OUTPUT: " + out[:200]


def main():
    sha = hashlib.sha256(open(GUARD, "rb").read()).hexdigest()
    rows = []
    failures = []
    for cid, desc, stdin_text, expected in CASES:
        rc, out, err = run_guard(stdin_text)
        got = classify(rc, out)
        ok = got == expected
        if not ok:
            failures.append(cid)
        rows.append((cid, desc, expected, got, rc, ok, out[:160]))

    lines = []
    lines.append("# SELFTEST EVIDENCE -- claude-code-mcp-guard (G-3b/G-2c)")
    lines.append("")
    lines.append("- Date: %s" % datetime.datetime.now().isoformat(timespec="seconds"))
    lines.append("- guard.py sha256: `%s`" % sha)
    lines.append("- python: %s | runner: selftest.py (subprocess stdin pipe per case)"
                 % sys.version.split()[0])
    lines.append("- Signal contract: subagent context == `agent_id` non-empty string "
                 "in hook stdin (PROBE-depth-dial.md par4, measured 2.1.277, both states).")
    lines.append("- DENY = exit 0 + JSON `hookSpecificOutput.permissionDecision:\"deny\"`; "
                 "ALLOW = exit 0 + empty stdout.")
    lines.append("")
    lines.append("| id | case | expected | measured | exit | pass |")
    lines.append("|----|------|----------|----------|------|------|")
    for cid, desc, expected, got, rc, ok, _ in rows:
        lines.append("| %s | %s | %s | %s | %d | %s |" % (cid, desc, expected, got, rc, "PASS" if ok else "FAIL"))
    lines.append("")
    lines.append("## Deny-path output (T01, verbatim stdout)")
    lines.append("```")
    lines.append(rows[0][6] if rows else "(none)")
    lines.append("```")
    lines.append("")
    lines.append("## Literal shell pipe tests (appended after settings.json registration)")
    lines.append("UNKNOWN - not yet run")
    lines.append("")
    lines.append("## settings.json registration + validation")
    lines.append("UNKNOWN - not yet run")
    lines.append("")
    lines.append("## Verdict")
    if failures:
        lines.append("FAILED cases: %s" % ", ".join(failures))
    else:
        lines.append("ALL %d CASES PASS (discrimination + chaos fail-open)." % len(CASES))
    open(EVIDENCE, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    print("cases=%d failures=%d" % (len(CASES), len(failures)))
    for cid, desc, expected, got, rc, ok, _ in rows:
        print("%s %-6s expected=%s measured=%s exit=%d" % (cid, "PASS" if ok else "FAIL", expected, got, rc))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
