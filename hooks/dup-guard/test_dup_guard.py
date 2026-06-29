#!/usr/bin/env python3
"""Direct-invocation tests for dup-guard/guard.py.

Proves: writing a NEW file whose basename/symbol already exists FIRES; a genuinely
new name stays SILENT; overwrites and recurring basenames stay SILENT; throttle works.

Run:  python test_dup_guard.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "guard.py")


def run(payload, env_extra=None):
    env = dict(os.environ)
    env.setdefault("DUP_GUARD_ROOT", str(Path(tempfile.gettempdir()) / f"dg-{uuid.uuid4().hex}"))
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    assert p.returncode == 0, f"must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def setup_repo() -> Path:
    repo = Path(tempfile.gettempdir()) / f"dg-repo-{uuid.uuid4().hex}"
    (repo / "src" / "components").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "components" / "widget.py").write_text(
        "class Widget:\n    def render(self):\n        return 1\n", encoding="utf-8")
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    return repo


def main() -> int:
    repo = setup_repo()
    cwd = str(repo)
    cases = []
    sroot = str(Path(tempfile.gettempdir()) / f"dg-shared-{uuid.uuid4().hex}")
    env = {"DUP_GUARD_ROOT": sroot}

    # 1. New file, SAME basename elsewhere -> FIRES
    out = run({"session_id": "d1", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "lib" / "widget.py"), "content": "x=1\n"}}, env)
    cases.append(("new file w/ existing basename -> fires", fired(out), True, out))

    # 2. Throttle: same basename again (same session) -> SILENT
    out = run({"session_id": "d1", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "other" / "widget.py"), "content": "y=2\n"}}, env)
    cases.append(("throttle: 2nd same-basename -> silent", fired(out), False, out))

    # 3. Genuinely NEW basename -> SILENT
    out = run({"session_id": "d2", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "lib" / "sprocket_xyz.py"), "content": "z=3\n"}}, env)
    cases.append(("brand-new basename -> silent", fired(out), False, out))

    # 4. Primary-SYMBOL collision (different filename, same class) -> FIRES
    out = run({"session_id": "d3", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "lib" / "thing.py"),
                              "content": "class Widget:\n    pass\n"}}, env)
    cases.append(("symbol collision (class Widget) -> fires", fired(out), True, out))

    # 5. Overwrite of an EXISTING path -> SILENT
    out = run({"session_id": "d4", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "src" / "components" / "widget.py"),
                              "content": "class Widget:\n    pass\n"}}, env)
    cases.append(("overwrite existing path -> silent", fired(out), False, out))

    # 6. Recurring basename __init__.py in a new dir -> SILENT
    out = run({"session_id": "d5", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "pkg" / "__init__.py"), "content": "\n"}}, env)
    cases.append(("__init__.py recurring -> silent", fired(out), False, out))

    # 7. DUP_GUARD=off -> SILENT even on a collision
    out = run({"session_id": "d6", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "z" / "widget.py"), "content": "x=1\n"}},
              {"DUP_GUARD": "off", **env})
    cases.append(("DUP_GUARD=off -> silent", fired(out), False, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")
    print("\nFIRED-sample (case 1):")
    print(run({"session_id": "demo", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "demo" / "widget.py"), "content": "x=1\n"}},
              {"DUP_GUARD_ROOT": str(Path(tempfile.gettempdir()) / f"dg-demo-{uuid.uuid4().hex}")}))
    print("SILENT-sample (case 3): " + repr(run({"session_id": "demo2", "tool_name": "Write", "cwd": cwd,
               "tool_input": {"file_path": str(repo / "demo" / "totallynew.py"), "content": "x=1\n"}},
              {"DUP_GUARD_ROOT": str(Path(tempfile.gettempdir()) / f"dg-demo2-{uuid.uuid4().hex}")})))
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
