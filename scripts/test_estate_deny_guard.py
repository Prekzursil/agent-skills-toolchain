#!/usr/bin/env python3
"""Offline tests for estate-deny-guard.py (no live rotate/force/public actions)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "estate-deny-guard.py")
SHELL = os.path.join(HERE, "cursor-hooks", "shell-guard.ps1")


def run_py(runtime, payload):
    raw = json.dumps(payload)
    p = subprocess.run(
        [sys.executable, GUARD, "--runtime", runtime],
        input=raw.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    out = p.stdout.decode("utf-8")
    if out.startswith("\ufeff"):
        raise SystemExit("BOM on python stdout")
    return p.returncode, out


def run_shell(payload_obj):
    raw = json.dumps(payload_obj)
    # UTF-8 BOM prefix — the Cursor stdin bug class
    stdin = b"\xef\xbb\xbf" + raw.encode("utf-8")
    p = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            SHELL,
        ],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    return p.returncode, p.stdout


def expect_contains(label, hay, needle):
    if needle not in hay:
        raise SystemExit(f"FAIL {label}: expected {needle!r} in {hay!r}")
    print(f"PASS {label}")


def main():
    rc, out = run_py(
        "claude",
        {"tool_input": {"command": "git push --force origin main"}},
    )
    assert rc == 0
    data = json.loads(out)
    expect_contains(
        "claude-force",
        data["hookSpecificOutput"]["permissionDecision"],
        "deny",
    )

    rc, out = run_py(
        "grok",
        {"toolInput": {"command": "aws iam create-access-key --user-name x"}},
    )
    data = json.loads(out)
    expect_contains("grok-rotate", data.get("decision", ""), "deny")

    rc, out = run_py("cursor", {"command": "git status"})
    data = json.loads(out)
    expect_contains("cursor-allow", data.get("permission", ""), "allow")

    rc, out = run_py(
        "cursor",
        {
            "command": "gh repo edit Prekzursil/agent-skills-toolchain --visibility public"
        },
    )
    data = json.loads(out)
    expect_contains("cursor-public", data.get("permission", ""), "deny")

    rc, out = run_py(
        "claude",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": r"C:\Users\Prekzursil\.agents\local.json"},
        },
    )
    data = json.loads(out)
    expect_contains(
        "claude-secret-write",
        data["hookSpecificOutput"]["permissionDecision"],
        "deny",
    )

    rc, out = run_py(
        "claude", {"tool_input": {"file_path": r"src\tokenizer.py"}}
    )
    if out.strip():
        raise SystemExit(f"FAIL tokenizer should allow (empty stdout), got {out!r}")
    print("PASS tokenizer-allow")

    rc, stdout = run_shell({"command": "git status"})
    if stdout[:1] == b"\xff" or stdout[:3] == b"\xef\xbb\xbf":
        raise SystemExit(f"FAIL shell BOM/UTF16 stdout head={stdout[:12]!r}")
    text = stdout.decode("ascii")
    data = json.loads(text)
    expect_contains("shell-allow", data.get("permission", ""), "allow")

    rc, stdout = run_shell({"command": "git push --force origin main"})
    text = stdout.decode("ascii")
    data = json.loads(text)
    expect_contains("shell-deny-force", data.get("permission", ""), "deny")

    print("ALL-PASS")


if __name__ == "__main__":
    main()
