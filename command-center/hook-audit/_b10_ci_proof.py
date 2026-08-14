#!/usr/bin/env python
"""_b10_ci_proof.py -- will `.github/workflows/hook-audit.yml` be green on a runner?

Working-tree green is not clone green and not CI green. This program has already shipped that
mistake (3,910 passed in a working tree vs 31 collection errors from a fresh clone of the same
commit), so the four wired commands are executed HERE the way the runner will execute them:

  * from a FRESH CLONE of HEAD -- so anything living only in this dirty worktree is absent,
  * with HOME and USERPROFILE redirected to a nonexistent directory -- so `~/.claude`, which
    the runner does not have, is not silently supplying an answer,
  * capturing each child's REAL exit code, never through a pipe (a pipeline reports the LAST
    command's status, which turns a red gate green).

CONTROLS, because four green commands prove nothing on their own:
  C1 REDIRECTION BITES -- `Path.home()` must MOVE and `<home>/.claude` must report False inside
     the clone. A redirection that does not take effect makes every later "runner-safe" claim
     meaningless.
  C2 THE GATE CAN STILL FAIL IN THE CLONE -- one citation's expected value is mutated in the
     clone and the gate must go RED, then the file is restored and it must go GREEN again.
     Without this, "the gate passed on a runner" is indistinguishable from "the gate cannot
     fail on a runner" -- which is precisely the shape of the no-op discovered while writing
     the workflow (`pytest` on a standalone script: zero tests collected, exit 0).
  C3 THE CLONE IS REAL -- the four wired files must exist in it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)

WIRED = [
    ["python", "command-center/hook-audit/check_citations.py", "--self-test"],
    ["python", "command-center/hook-audit/test_citation_gate.py"],
    ["python", "command-center/hook-audit/check_citations.py"],
    [
        "python",
        "-m",
        "pytest",
        "command-center/hook-audit/test_hook_predeploy_gate.py",
        "-q",
    ],
]
NEEDED = [
    "command-center/hook-audit/check_citations.py",
    "command-center/hook-audit/test_citation_gate.py",
    "command-center/hook-audit/test_hook_predeploy_gate.py",
    "command-center/hook-audit/hook_predeploy_gate.py",
]


def runner_env(fake_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    return env


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    return p.returncode, (tail[-1][:200] if tail else "")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="b10ci_"))
    clone = tmp / "clone"
    fake_home = tmp / "nohome"
    out: dict = {"probe": "_b10_ci_proof.py", "controls": {}, "wired": []}
    try:
        subprocess.run(
            ["git", "clone", "--no-hardlinks", "--quiet", str(REPO), str(clone)],
            check=True,
            capture_output=True,
        )
        out["clone_head"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()[:12]

        env = runner_env(fake_home)
        rc, home_line = run(
            [
                "python",
                "-c",
                "from pathlib import Path; print(Path.home(), (Path.home()/'.claude').exists())",
            ],
            clone,
            env,
        )
        c1 = (
            rc == 0
            and str(fake_home) in home_line
            and home_line.strip().endswith("False")
        )
        out["controls"]["C1_redirection_bites"] = c1
        out["controls"]["C1_observed"] = home_line

        c3 = all((clone / n).exists() for n in NEEDED)
        out["controls"]["C3_clone_has_wired_files"] = c3
        if not (c1 and c3):
            print(f"CONTROL C1 redirection bites = {c1}  ({home_line})")
            print(f"CONTROL C3 clone has files   = {c3}")
            print("FAILED:ci-proof control failed -- no runner verdict published")
            return 2

        for cmd in WIRED:
            rc, tail = run(cmd, clone, env)
            out["wired"].append({"cmd": " ".join(cmd[1:]), "rc": rc, "tail": tail})
            print(f"rc={rc}  {' '.join(cmd[1:])}\n      {tail}")

        # C2: the gate must still be able to FAIL inside the clone.
        doc = clone / "docs" / "hook-audit" / "BUILD-R2.md"
        original = doc.read_text(encoding="utf-8")
        mutated = re.sub(
            r"(id=R2-fmt-files[^>]*?value=)2595", r"\g<1>9999", original, count=1
        )
        if mutated == original:
            out["controls"]["C2_gate_can_fail_in_clone"] = False
            print("CONTROL C2 = FAIL (mutation anchor not found)")
            print("FAILED:ci-proof could not mutate a citation -- control inert")
            return 2
        doc.write_text(mutated, encoding="utf-8", newline="")
        rc_hot, tail_hot = run(WIRED[2], clone, env)
        doc.write_text(original, encoding="utf-8", newline="")
        rc_cold, _ = run(WIRED[2], clone, env)
        c2 = rc_hot != 0 and rc_cold == 0
        out["controls"]["C2_gate_can_fail_in_clone"] = c2
        out["controls"]["C2_rc_mutated"] = rc_hot
        out["controls"]["C2_rc_restored"] = rc_cold
        print(f"CONTROL C1 redirection bites          = {c1}")
        print(
            f"CONTROL C2 gate goes RED when mutated = {c2} (rc {rc_hot} mutated / {rc_cold} restored)"
        )
        print(f"CONTROL C3 clone has the wired files  = {c3}")
        print(f"      C2 mutated-run tail: {tail_hot}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    all_green = all(w["rc"] == 0 for w in out["wired"])
    out["all_wired_commands_green"] = all_green
    out["verdict"] = (
        "RUNNER-GREEN"
        if (all_green and out["controls"]["C2_gate_can_fail_in_clone"])
        else "RUNNER-RED"
    )
    (HERE / "B10-CI-PROOF.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    if out["verdict"] != "RUNNER-GREEN":
        print(f"FAILED:ci-proof {out['verdict']}")
        return 1
    print(
        f"SUCCESS:ci-proof 4/4 wired commands green in a fresh clone at {out['clone_head']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
