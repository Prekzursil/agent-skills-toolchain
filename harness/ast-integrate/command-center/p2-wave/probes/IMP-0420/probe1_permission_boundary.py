#!/usr/bin/env python3
"""IMP-0420 probe1: permission-boundary test per permission class.

Evidence required by the catalog: a unit declaring read-only permissions attempts
a write and is refused by the adapter, with the refusal recorded. Two independent
signals: (a) the typed refusal in the dispatch trace, (b) the marker file is
absent. A mutant that disables the allowlist must actually write, otherwise the
refusal arm measures a broken Write path.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_adapter import load_adapter  # noqa: E402

VOCAB = ("Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell")


def _unit(uid: str, perms: list[str], timeout: float = 8.0) -> dict:
    return {"id": uid, "tool_permissions": perms, "timeout_seconds": timeout}


def _call(tools, tool: str) -> None:
    if tool == "Read":
        tools.Read("seed.txt")
    elif tool == "Grep":
        tools.Grep("token", "seed.txt")
    elif tool == "Glob":
        tools.Glob("seed.txt")
    elif tool == "Write":
        tools.Write("marker.txt", "SHOULD-NOT-OR-SHOULD")
    elif tool == "Edit":
        tools.Edit("seed.txt", "edited")
    elif tool == "Bash":
        tools.Bash("echo granted-or-denied")
    elif tool == "PowerShell":
        tools.PowerShell("Write-Output 1")
    else:
        raise AssertionError(tool)


def _seed(root: Path) -> None:
    (root / "seed.txt").write_text("token-line\n", encoding="utf-8")


def _complement(tool: str) -> list[str]:
    if tool in {"Read", "Grep", "Glob"}:
        return ["Write"]
    return ["Read"]


def main() -> int:
    ca = load_adapter()
    adapter = ca.ClaudeAdapter()
    failures: list[str] = []
    matrix: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="imp0420-p1-") as td:
        base = Path(td)

        # --- evidence: read-only unit attempts Write ---
        ro_root = base / "readonly"
        ro_root.mkdir()
        marker = ro_root / "marker.txt"
        ro_unit = _unit("IMP-0420-EVIDENCE-READONLY", ["Read"])

        def _attempt_write(tools):
            return tools.Write("marker.txt", "planted-by-readonly-unit")

        refused = adapter.dispatch(
            ro_unit,
            _attempt_write,
            sandbox_root=ro_root,
            sentinel="SENTINEL:IMP-0420:WRITE-REFUSED",
        )
        refusals = [
            e
            for e in refused["dispatch_trace"]
            if e.get("event") == "tool-refused" and e.get("tool") == "Write"
        ]
        write_absent = not marker.exists()
        bound_excludes_write = "Write" not in refused["bound_tools"]
        if refused["result"]["outcome"] != "permission-denied":
            failures.append(f"readonly outcome={refused['result']['outcome']}")
        if not refusals:
            failures.append("readonly missing tool-refused Write in dispatch_trace")
        if not write_absent:
            failures.append("readonly Write produced a file — permissions documented, not enforced")
        if not bound_excludes_write:
            failures.append(f"readonly bound_tools still includes Write: {refused['bound_tools']}")

        # --- mutant control: same Write must succeed if allowlist is a no-op ---
        mut_root = base / "mutant"
        mut_root.mkdir()
        mut_marker = mut_root / "marker.txt"
        with patch.object(ca.PermissionAllowlist, "allows", return_value=True):
            mutant = adapter.dispatch(
                ro_unit,
                _attempt_write,
                sandbox_root=mut_root,
                sentinel="SENTINEL:IMP-0420:MUTANT-WRITE",
            )
        mutant_wrote = mut_marker.is_file() and mut_marker.stat().st_size > 0
        if not mutant_wrote:
            failures.append(
                "mutant allowlist-always-true did not write; refusal arm would be vacuous"
            )
        if mutant["result"]["outcome"] == "permission-denied":
            failures.append("mutant still permission-denied — patch missed the choke point")

        # --- both-states: granted Write succeeds ---
        ok_root = base / "granted-write"
        ok_root.mkdir()
        ok_marker = ok_root / "marker.txt"
        granted_write = adapter.dispatch(
            _unit("FIX-GRANT-WRITE", ["Write"]),
            lambda t: t.Write("marker.txt", "granted"),
            sandbox_root=ok_root,
        )
        if not (ok_marker.is_file() and ok_marker.read_text(encoding="utf-8") == "granted"):
            failures.append("granted Write did not persist bytes")
        if granted_write["state"] != "SUCCESS":
            failures.append(f"granted Write state={granted_write['state']}")

        # --- per-class granted/denied matrix ---
        for tool in VOCAB:
            d_root = base / f"deny-{tool.lower()}"
            g_root = base / f"grant-{tool.lower()}"
            d_root.mkdir()
            g_root.mkdir()
            _seed(d_root)
            _seed(g_root)
            denied = adapter.dispatch(
                _unit(f"FIX-DENY-{tool.upper()}", _complement(tool)),
                lambda t, tool=tool: _call(t, tool),
                sandbox_root=d_root,
            )
            granted = adapter.dispatch(
                _unit(f"FIX-GRANT-{tool.upper()}", [tool]),
                lambda t, tool=tool: _call(t, tool),
                sandbox_root=g_root,
            )
            denied_ok = denied["result"]["outcome"] == "permission-denied" and any(
                e.get("event") == "tool-refused" and e.get("tool") == tool
                for e in denied["dispatch_trace"]
            )
            granted_ok = granted["state"] == "SUCCESS" and granted["result"]["outcome"] == "completed"
            if tool == "Write":
                denied_ok = denied_ok and not (d_root / "marker.txt").exists()
                granted_ok = granted_ok and (g_root / "marker.txt").is_file()
            if tool == "Edit":
                denied_ok = denied_ok and (d_root / "seed.txt").read_text(encoding="utf-8") == "token-line\n"
                granted_ok = granted_ok and (g_root / "seed.txt").read_text(encoding="utf-8") == "edited"
            row = {
                "tool": tool,
                "denied_outcome": denied["result"]["outcome"],
                "granted_state": granted["state"],
                "denied_ok": denied_ok,
                "granted_ok": granted_ok,
            }
            matrix.append(row)
            if not denied_ok:
                failures.append(f"class {tool} DENIED arm failed: {denied['result']}")
            if not granted_ok:
                failures.append(f"class {tool} GRANTED arm failed: {granted['result']}")

        # --- Bash:python qualifier: python allowed, echo refused ---
        bq_root = base / "bash-python"
        bq_root.mkdir()
        bq_unit = _unit("FIX-BASH-PYTHON", ["Bash:python"])
        py_ok = adapter.dispatch(
            bq_unit,
            lambda t: t.Bash("python3 -c 'print(42)'"),
            sandbox_root=bq_root,
        )
        echo_no = adapter.dispatch(
            bq_unit,
            lambda t: t.Bash("echo should-be-refused"),
            sandbox_root=bq_root,
        )
        if py_ok["state"] != "SUCCESS":
            failures.append(f"Bash:python python3 refused: {py_ok['result']}")
        if echo_no["result"]["outcome"] != "permission-denied":
            failures.append(f"Bash:python echo leaked through: {echo_no['result']}")

    report = {
        "probe": "probe1-permission-boundary",
        "unit_id": "IMP-0420",
        "readonly_write_refused": bool(refusals),
        "readonly_file_absent": write_absent,
        "readonly_bound_tools": refused["bound_tools"],
        "mutant_wrote": mutant_wrote,
        "granted_write_ok": granted_write["state"] == "SUCCESS",
        "matrix": matrix,
        "bash_python_allows_python": py_ok["state"] == "SUCCESS",
        "bash_python_refuses_echo": echo_no["result"]["outcome"] == "permission-denied",
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    if failures:
        print("FAILED:IMP-0420-probe1 " + "; ".join(failures)[:800])
        return 1
    print(
        "SUCCESS:IMP-0420-probe1 permission-boundary "
        f"refused={bool(refusals)} file_absent={write_absent} "
        f"mutant_wrote={mutant_wrote} matrix={len(matrix)}/{len(VOCAB)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
