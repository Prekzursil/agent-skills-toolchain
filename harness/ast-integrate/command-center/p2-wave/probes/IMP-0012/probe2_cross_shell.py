#!/usr/bin/env python3
"""Probe 2: two parent shells agree on the child-reported interpreter path.

Catalog names pwsh7 and Git Bash. This Linux worktree has neither. The two
parent shells that ARE present (GNU bash and dash) launch the same entrypoint
through the explicit argv launcher. The child's own reported executable must
match the resolved interpreter, and both parents must agree.

Also: bare invocation is refused; OS shebang-exec of .sh is the wrong-reason
control that still succeeds on Linux.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.interpreters import lint_entrypoints, which_family  # noqa: E402
from plugin.launcher import (  # noqa: E402
    BareInvocationError,
    launch_entrypoint,
    launch_from_parent_shell,
    refuse_bare_invocation,
)

ART = REPO / "command-center/receipts/IMP-0012.json"


def _realpath(path: str) -> str:
    return str(Path(path).resolve())


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0012-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0012" not in text:
        print("FAILED:IMP-0012-probe2 sentinel absent")
        return 1

    bash = shutil.which("bash")
    other = shutil.which("dash") or shutil.which("sh")
    if not bash or not other:
        print(f"FAILED:IMP-0012-probe2 need two parent shells bash={bash} other={other}")
        return 1
    if _realpath(bash) == _realpath(other) and Path(bash).name == Path(other).name:
        print("FAILED:IMP-0012-probe2 two parent shells collapsed to one binary")
        return 1

    rows = lint_entrypoints()
    agreements = []
    for row in rows:
        eid = row["id"]
        direct = launch_entrypoint(eid)
        if direct["exit_code"] != 0 or not direct["exe_agrees"]:
            print("FAILED:IMP-0012-probe2 direct launch", json.dumps(direct, default=str)[:1500])
            return 1
        from_bash = launch_from_parent_shell(bash, eid)
        from_other = launch_from_parent_shell(other, eid)
        if from_bash["exit_code"] != 0 or from_other["exit_code"] != 0:
            print("FAILED:IMP-0012-probe2 parent-shell launch", from_bash, from_other)
            return 1
        a = (from_bash.get("launch") or {}).get("resolved_interpreter")
        b = (from_other.get("launch") or {}).get("resolved_interpreter")
        ca = (from_bash.get("launch") or {}).get("child_exe")
        cb = (from_other.get("launch") or {}).get("child_exe")
        if not a or not b or _realpath(a) != _realpath(b):
            print(f"FAILED:IMP-0012-probe2 shells disagree id={eid} bash={a} other={b}")
            return 1
        if _realpath(ca) != _realpath(a) or _realpath(cb) != _realpath(b):
            print(f"FAILED:IMP-0012-probe2 child exe mismatch id={eid} {ca} {cb} {a} {b}")
            return 1
        agreements.append(
            {
                "id": eid,
                "family": row["interpreter"],
                "parent_bash": bash,
                "parent_other": other,
                "resolved": _realpath(a),
                "child_exe": _realpath(ca),
            }
        )
        print(
            f"id={eid} family={row['interpreter']} bash_parent={bash} other_parent={other} "
            f"resolved={_realpath(a)} child={_realpath(ca)} agree=True"
        )

    try:
        refuse_bare_invocation("scripts/longrun.sh")
        refused = False
        refuse_text = "not raised"
    except BareInvocationError as exc:
        refused = True
        refuse_text = str(exc)
    if not refused:
        print("FAILED:IMP-0012-probe2 bare invocation was not refused")
        return 1

    script = REPO / "scripts" / "longrun.sh"
    os.chmod(script, 0o755)
    os_bare = subprocess.run(
        [str(script)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if os_bare.returncode != 0 or "IMP-0012-CHILD" not in (os_bare.stdout or ""):
        print("FAILED:IMP-0012-probe2 OS-bare shebang control did not run", os_bare)
        return 1

    launcher_bare = subprocess.run(
        [sys.executable, str(REPO / "tools/plugin/launcher.py"), "--bare", "scripts/longrun.sh"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if launcher_bare.returncode == 0 or "REFUSED:bare-invocation" not in (
        (launcher_bare.stdout or "") + (launcher_bare.stderr or "")
    ):
        print("FAILED:IMP-0012-probe2 launcher did not refuse --bare")
        return 1

    print(
        json.dumps(
            {
                "agreements": agreements,
                "bare_refused": True,
                "os_shebang_succeeded_for_wrong_reason": True,
                "parent_shells": {"catalog_named": ["pwsh7", "Git Bash"], "present": [bash, other]},
                "pass": True,
                "probe": "probe2-cross-shell",
                "pwsh_on_path": bool(which_family("pwsh")),
                "unit_id": "IMP-0012",
            }
        )
    )
    print(f"bare_refused=True os_shebang_wrong_reason=True refuse={refuse_text}")
    print("SUCCESS:IMP-0012-probe2 cross-shell interpreter agreement and bare-invocation refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
