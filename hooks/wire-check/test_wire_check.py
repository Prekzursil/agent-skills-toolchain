#!/usr/bin/env python3
"""Direct-invocation tests for wire-check/check.py.

Builds throwaway git repos and pipes Stop-hook stdin to prove the hook FIRES on a
session-added unreferenced symbol, a _v2-with-no-v1 file, and an unlinked route, while
staying SILENT when the symbol IS referenced, when nothing changed, and outside git.

Run:  python test_wire_check.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "check.py")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd),
                           "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, timeout=30)


def new_repo() -> Path:
    repo = Path(tempfile.gettempdir()) / f"wc-{uuid.uuid4().hex}"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    (repo / "README.md").write_text("# baseline\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "baseline")
    return repo


def run(cwd, env_extra=None) -> str:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    payload = {"session_id": "wc-" + uuid.uuid4().hex[:8], "cwd": str(cwd),
               "transcript_path": ""}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=40)
    assert p.returncode == 0, f"must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def main() -> int:
    cases = []

    # 1. Added unreferenced exported symbol -> FIRES
    repo = new_repo()
    (repo / "feature.py").write_text("def orphan_widget():\n    return 1\n", encoding="utf-8")
    out = run(repo)
    cases.append(("added unreferenced symbol -> fires", fired(out), True, out))

    # 2. Added symbol that IS referenced elsewhere -> SILENT
    repo = new_repo()
    (repo / "main.py").write_text("def used():\n    return 0\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main")
    (repo / "feature2.py").write_text("def wired_thing():\n    return 1\n", encoding="utf-8")
    # reference it from a modified tracked file
    (repo / "main.py").write_text("def used():\n    return 0\n\nx = wired_thing()\n", encoding="utf-8")
    out = run(repo)
    cases.append(("added symbol that is referenced -> silent", fired(out), False, out))

    # 3. _v2 file with no live v1 -> FIRES
    repo = new_repo()
    (repo / "coupons_v2.py").write_text("X = 1\n", encoding="utf-8")
    out = run(repo)
    cases.append(("coupons_v2 with no v1 -> fires", fired(out), True, out))

    # 4. _v2 file WHEN v1 exists & referenced -> SILENT (normal migration)
    repo = new_repo()
    (repo / "coupons.py").write_text("def coupons():\n    return 1\n", encoding="utf-8")
    (repo / "use.py").write_text("from coupons import coupons\ncoupons()\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "v1")
    (repo / "coupons_v2.py").write_text("Y = 2\n", encoding="utf-8")
    out = run(repo)
    cases.append(("coupons_v2 WITH live v1 -> silent", fired(out), False, out))

    # 5. Unlinked route -> FIRES
    repo = new_repo()
    (repo / "routes.js").write_text(
        "router.get('/checkout_xyz', checkoutHandler)\nfunction checkoutHandler(){ return ok(); }\n"
        "checkoutHandler();\n", encoding="utf-8")
    out = run(repo)
    cases.append(("unlinked route -> fires", fired(out), True, out))

    # 6. No changes vs HEAD -> SILENT
    repo = new_repo()
    out = run(repo)
    cases.append(("clean repo (no diff) -> silent", fired(out), False, out))

    # 7. Not a git repo -> SILENT
    nongit = Path(tempfile.gettempdir()) / f"wc-nogit-{uuid.uuid4().hex}"
    nongit.mkdir(parents=True, exist_ok=True)
    (nongit / "feature.py").write_text("def orphan():\n    return 1\n", encoding="utf-8")
    out = run(nongit)
    cases.append(("non-git dir -> silent", fired(out), False, out))

    # 8. WIRE_CHECK=off -> SILENT despite dead symbol
    repo = new_repo()
    (repo / "feature.py").write_text("def orphan_widget2():\n    return 1\n", encoding="utf-8")
    out = run(repo, {"WIRE_CHECK": "off"})
    cases.append(("WIRE_CHECK=off -> silent", fired(out), False, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")

    print("\nFIRED-sample (case 1):")
    repo = new_repo()
    (repo / "feature.py").write_text("def orphan_widget():\n    return 1\n", encoding="utf-8")
    print(run(repo))
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
