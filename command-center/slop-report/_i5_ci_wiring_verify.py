"""INTEGRATE / step I5 -- the end-to-end check that FAILS if the wiring is removed.

I3 proved the GATE has teeth. This proves the WIRING is real, which is a different claim:
a gate that exists in the repo but is invoked by no workflow is exactly the "reachable?"
question this lane was sent to answer, and the repo already has one of those (the
hook-audit citation gate is referenced only by prose and hardcodes a Windows path, so no
runner can execute it).

So this does not read the workflow for a string. It PARSES the YAML, finds the step by
name, extracts the literal `run:` script the runner would execute, and EXECUTES it in a
fresh LF clone at HEAD -- the same bytes CI checks out.

  W1  the step exists under jobs.<job>.steps and carries a run: script  -> else FAIL
  W2  every command in that run: block executes at rc 0 in a fresh clone -> else FAIL
  W3  CONTROL, the state that must be distinguishable: the SAME parser run against a copy
      of the workflow with that step deleted must report MISSING. A checker that cannot
      tell "wired" from "not wired" is measuring the file's existence, not the wiring.
  W4  CONTROL: the run: block must actually invoke the gate script, not merely be present.
      A step renamed to match while running `echo ok` would pass W1+W2 and prove nothing.

Working-tree green != clone green != CI green, so W2 runs in a clone, never here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
WF_REL = ".github/workflows/no-runtime-junk.yml"
JOB = "no-runtime-junk"
STEP_PREFIX = "gate-published-commands"
GATE_REL = "command-center/slop-report/check_published_commands.py"
OUT = ROOT / "command-center/slop-report/_i5_ci_wiring_verify.out.json"


def find_step(wf_text: str):
    """-> the step dict whose name starts with STEP_PREFIX, or None."""
    doc = yaml.safe_load(wf_text)
    for step in doc["jobs"][JOB]["steps"]:
        if str(step.get("name", "")).startswith(STEP_PREFIX):
            return step
    return None


def run(cmd, cwd):
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def main() -> int:
    res: dict = {}
    # Read the COMMITTED blob, not the worktree. A wiring that exists only on this disk is
    # the exact defect this lane exists to close, and reading the worktree would certify it.
    wf_text = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-p", f"HEAD:{WF_REL}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    res["source"] = f"HEAD:{WF_REL} (committed blob, not the worktree)"
    res["worktree_matches_head"] = (
        subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--", WF_REL],
            capture_output=True,
            text=True,
        ).stdout.strip()
        == ""
    )

    # ---- W1: the step is wired -------------------------------------------------------
    step = find_step(wf_text)
    res["W1_step_found"] = step is not None
    if step is None:
        res["verdict"] = "NOT-WIRED"
        OUT.write_text(
            json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
        )
        print(json.dumps(res, indent=1, sort_keys=True))
        print(
            f"FAILED:i5 no step named {STEP_PREFIX}* under jobs.{JOB} -- the gate is unreachable"
        )
        return 1
    script = str(step.get("run", ""))
    cmds = [ln.strip() for ln in script.splitlines() if ln.strip()]
    res["W1_step_name"] = step["name"]
    res["W1_commands"] = cmds

    # ---- W4: the step must invoke the gate, not merely be named after it -------------
    res["W4_invokes_the_gate"] = any(GATE_REL in c for c in cmds)
    res["W4_runs_the_selftest"] = any("--self-test" in c for c in cmds)

    tmp = tempfile.mkdtemp(prefix="i5_wiring_")
    try:
        clone = os.path.join(tmp, "c")
        c = run(
            [
                "git",
                "clone",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "--single-branch",
                str(ROOT),
                clone,
            ],
            tmp,
        )
        if c["rc"] != 0:
            raise SystemExit(f"clone failed: {c['err'][:300]}")
        res["clone_head"] = run(["git", "rev-parse", "HEAD"], clone)["out"].strip()

        # ---- W2: execute the literal run: block the runner would execute -------------
        executed = []
        for cmd in cmds:
            parts = cmd.split()
            if parts and parts[0].startswith("python"):
                parts[0] = sys.executable
            r = run(parts, clone)
            executed.append(
                {"cmd": cmd, "rc": r["rc"], "tail": r["out"].strip().splitlines()[-1:]}
            )
        res["W2_executed"] = executed
        res["W2_all_green"] = all(e["rc"] == 0 for e in executed)

        # ---- W3: both-states control -- delete the step, the parser must notice ------
        doc = yaml.safe_load(wf_text)
        doc["jobs"][JOB]["steps"] = [
            s
            for s in doc["jobs"][JOB]["steps"]
            if not str(s.get("name", "")).startswith(STEP_PREFIX)
        ]
        res["W3_unwired_step_found"] = find_step(yaml.safe_dump(doc)) is not None
        res["W3_states_distinguishable"] = (
            res["W1_step_found"] and not res["W3_unwired_step_found"]
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    checks = {
        "W1_step_is_wired": res["W1_step_found"],
        "W2_wired_commands_all_pass_in_a_clone": res["W2_all_green"],
        "W3_unwired_state_is_detected": res["W3_states_distinguishable"],
        "W4_step_actually_invokes_the_gate": res["W4_invokes_the_gate"],
        "W4_step_runs_the_selftest_first": res["W4_runs_the_selftest"],
    }
    res["checks"] = checks
    res["verdict"] = "WIRING-PROVEN" if all(checks.values()) else "FAILED"

    OUT.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=1, sort_keys=True))
    print(f"\nwrote {OUT}")
    return 0 if res["verdict"] == "WIRING-PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main())
