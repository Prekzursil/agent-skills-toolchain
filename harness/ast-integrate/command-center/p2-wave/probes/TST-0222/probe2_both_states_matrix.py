#!/usr/bin/env python3
"""Probe 2: both-states Write control plus full vocabulary grant/deny matrix.

Catalog tests_required:
  * a unit declaring Write succeeds at the same call
  * every tool in the permission vocabulary, granted and denied
Independent JS signal: tools/lib/workspace.mjs denies the same Write.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.lib.workspace_permissions import (  # noqa: E402
    PERMISSION_VOCABULARY,
    PathContainmentError,
    PermissionSession,
    ToolPermissionError,
    evaluate,
)

JS = REPO / "tools" / "lib" / "workspace.mjs"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0222-probe2 {msg}")
    return 1


def seed_tree(root: Path) -> None:
    (root / "readable.txt").write_text("matrix-read-ok\nfind-me\n", encoding="utf-8")
    (root / "edit-me.txt").write_text("before\n", encoding="utf-8")
    (root / "glob-a.txt").write_text("a\n", encoding="utf-8")
    (root / "nested").mkdir(parents=True, exist_ok=True)
    (root / "nested" / "glob-b.txt").write_text("b\n", encoding="utf-8")


def invoke_granted(sess: PermissionSession, tool: str, root: Path) -> object:
    if tool == "Read":
        return sess.invoke("Read", path="readable.txt")
    if tool == "Grep":
        return sess.invoke("Grep", path="readable.txt", pattern="find-me")
    if tool == "Glob":
        return sess.invoke("Glob", pattern="*.txt")
    if tool == "Write":
        return sess.invoke("Write", path="granted-write.txt", contents="granted\n")
    if tool == "Edit":
        return sess.invoke("Edit", path="edit-me.txt", contents="after\n")
    if tool == "Bash":
        marker = root / "bash-ran.txt"
        return sess.invoke(
            "Bash",
            command=[
                sys.executable,
                "-c",
                f"open({str(marker)!r}, 'w', encoding='utf-8').write('bash-ok\\n')",
            ],
        )
    if tool == "PowerShell":
        return sess.invoke("PowerShell", command=["Write-Output", "ok"])
    raise AssertionError(tool)


def side_effect_denied(tool: str, root: Path) -> bool:
    if tool == "Write":
        return not (root / "denied-matrix-write.txt").exists()
    if tool == "Edit":
        return (root / "edit-me.txt").read_text(encoding="utf-8") == "before\n"
    if tool == "Bash":
        return not (root / "bash-denied.txt").exists()
    return True


def invoke_denied(sess: PermissionSession, tool: str, root: Path) -> None:
    if tool == "Read":
        sess.invoke("Read", path="readable.txt")
    elif tool == "Grep":
        sess.invoke("Grep", path="readable.txt", pattern="find-me")
    elif tool == "Glob":
        sess.invoke("Glob", pattern="*.txt")
    elif tool == "Write":
        sess.invoke("Write", path="denied-matrix-write.txt", contents="nope\n")
    elif tool == "Edit":
        sess.invoke("Edit", path="edit-me.txt", contents="mutated\n")
    elif tool == "Bash":
        marker = root / "bash-denied.txt"
        sess.invoke(
            "Bash",
            command=[
                sys.executable,
                "-c",
                f"open({str(marker)!r}, 'w', encoding='utf-8').write('should-not\\n')",
            ],
        )
    elif tool == "PowerShell":
        sess.invoke("PowerShell", command=["Write-Output", "nope"])
    else:
        raise AssertionError(tool)


def run_js_denied_write(root: Path) -> dict:
    proc = subprocess.run(
        [
            "node",
            str(JS),
            "--root",
            str(root),
            "--declared",
            "Read,Grep",
            "--tool",
            "Write",
            "--path",
            "js-denied.txt",
            "--contents",
            "NO-JS",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    payload = None
    for line in text.splitlines():
        if line.startswith("{"):
            payload = json.loads(line)
            break
    if not isinstance(payload, dict):
        raise RuntimeError(f"workspace.mjs produced no JSON: {text[-1000:]}")
    payload["exit_code"] = proc.returncode
    payload["raw_tail"] = text[-1500:]
    return payload


def main() -> int:
    if not JS.is_file():
        return fail("tools/lib/workspace.mjs is absent")
    with TemporaryDirectory(prefix="tst0222-p2-") as tmp:
        root = Path(tmp)
        seed_tree(root)

        both = PermissionSession(["Read", "Grep", "Write"], root)
        if evaluate(both.declared, "Write") != "grant":
            return fail("evaluate() denied Write for a unit that declares it")
        written = both.invoke("Write", path="same-call.txt", contents="both-states-ok\n")
        same = root / "same-call.txt"
        if not same.is_file() or same.read_text(encoding="utf-8") != "both-states-ok\n":
            return fail("granted Write did not persist bytes")
        if written.bytes_written != len("both-states-ok\n"):
            return fail("granted Write bytes_written drifted")

        prefix_root = root / "tools" / "lib"
        prefix_root.mkdir(parents=True)
        contained = PermissionSession(["Write"], prefix_root)
        try:
            contained.invoke("Write", path="../libextra/escape.txt", contents="escaped\n")
            return fail("prefix-escape sibling write was allowed")
        except PathContainmentError:
            pass
        if (root / "tools" / "libextra" / "escape.txt").exists():
            return fail("prefix-escape write landed")

        matrix: list[dict] = []
        for tool in PERMISSION_VOCABULARY:
            denied_declared = [item for item in PERMISSION_VOCABULARY if item != tool]
            denied_sess = PermissionSession(denied_declared, root)
            granted_sess = PermissionSession([tool], root)
            if evaluate(denied_sess.declared, tool) != "deny":
                return fail(f"evaluate grant leak for denied {tool}")
            if evaluate(granted_sess.declared, tool) != "grant":
                return fail(f"evaluate deny leak for granted {tool}")

            spawn_before = denied_sess.spawn_count
            err: ToolPermissionError | None = None
            try:
                invoke_denied(denied_sess, tool, root)
            except ToolPermissionError as exc:
                err = exc
            if err is None:
                return fail(f"denied {tool} did not raise ToolPermissionError")
            if err.code != "tool-permission-denied" or err.tool != tool:
                return fail(f"denied {tool} typed error drifted: {err!r}")
            if denied_sess.spawn_count != spawn_before:
                return fail(f"denied {tool} spawned")
            if not side_effect_denied(tool, root):
                return fail(f"denied {tool} produced a filesystem side effect")

            try:
                result = invoke_granted(granted_sess, tool, root)
            except ToolPermissionError as exc:
                return fail(f"granted {tool} raised {exc}")
            granted_ok = bool(getattr(result, "granted", False))
            if tool == "Write" and not (root / "granted-write.txt").is_file():
                return fail("granted Write file missing")
            if tool == "Edit" and (root / "edit-me.txt").read_text(encoding="utf-8") != "after\n":
                return fail("granted Edit did not change bytes")
            if tool == "Bash" and not (root / "bash-ran.txt").is_file():
                return fail("granted Bash did not run")
            if tool == "PowerShell" and result.reason not in {None, "interpreter-absent"}:
                return fail(f"granted PowerShell unexpected reason {result.reason!r}")
            matrix.append(
                {
                    "tool": tool,
                    "denied_error": err.code,
                    "denied_side_effect": False,
                    "granted": granted_ok,
                    "granted_reason": getattr(result, "reason", None),
                }
            )

        if len(matrix) != len(PERMISSION_VOCABULARY):
            return fail("matrix length drifted")

        js_root = root / "js-workspace"
        js_root.mkdir()
        js_payload = run_js_denied_write(js_root)
        if js_payload.get("exit_code") != 0:
            return fail(f"workspace.mjs exit {js_payload.get('exit_code')} {js_payload.get('raw_tail')}")
        if js_payload.get("code") != "tool-permission-denied":
            return fail(f"JS denial code {js_payload.get('code')!r}")
        if js_payload.get("exists_after"):
            return fail("JS denied Write created the file")
        if (js_root / "js-denied.txt").exists():
            return fail("JS target exists after denial")

        payload = {
            "probe": "probe2-both-states-matrix",
            "unit_id": "TST-0222",
            "pass": True,
            "vocabulary": list(PERMISSION_VOCABULARY),
            "both_states_write_granted": True,
            "granted_write_path": "same-call.txt",
            "prefix_escape_blocked": True,
            "matrix": matrix,
            "js_independent": {
                "code": js_payload.get("code"),
                "exists_after": js_payload.get("exists_after"),
                "evaluation_site": js_payload.get("evaluation_site"),
            },
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"both_states_write=True matrix={len(matrix)}/"
            f"{len(PERMISSION_VOCABULARY)} js_denied=tool-permission-denied"
        )
        print("SUCCESS:TST-0222-probe2 granted Write control; vocabulary matrix")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
