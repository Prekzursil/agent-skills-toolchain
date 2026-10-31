"""INTEGRATE -- the end-to-end check that FAILS if the wiring is removed.

I3 proved the GATE has teeth. This proves the WIRING is real, which is a different claim: a
gate that exists in the repo but is invoked by no workflow is exactly the "reachable?"
question this lane was sent to answer, and the repo already has one of those (the hook-audit
citation gate is referenced only by prose, so no runner executes it).

So this does not read the workflow for a string. It PARSES the YAML, finds each step by
name, extracts the literal `run:` script the runner would execute, and EXECUTES it in a
fresh LF clone at HEAD -- the same bytes CI checks out.

  W1  the step exists under jobs.<job>.steps and carries a run: script  -> else FAIL
  W2  every command in that run: block executes at rc 0 in a fresh clone -> else FAIL
  W3  CONTROL, the state that must be distinguishable: the SAME parser run against a copy
      of the workflow with that step deleted must report MISSING. A checker that cannot
      tell "wired" from "not wired" is measuring the file's existence, not the wiring.
  W4  CONTROL: the run: block must actually invoke the gate script, not merely be present.
      A step renamed to match while running `echo ok` would pass W1+W2 and prove nothing.
  W5  NEW (INTEGRATE round 2). PORTABILITY. Every script a wired step invokes must resolve
      its repo root DYNAMICALLY. Round 7 confirmed the concrete failure: round 6 shipped a
      gate binding `REPO = "C:/Users/Prekzursil/source/ast-integrate"`, so a copy of it
      placed in a fresh clone silently re-measured the SOURCE tree and wrote its receipt
      back into it -- a clone-run manufacturing the very confidence the clone exists to
      establish. W1-W4 are all GREEN in that state, because the step is wired and the
      command exits 0; only a portability check separates "runs" from "runs on the runner".

      Decided by AST over ASSIGNMENT targets, never a regex over the file. ~70 scripts in
      this directory contain that literal and most are only MENTIONING it in a docstring --
      including both gates' own paragraphs warning about it. A regex calls those violations;
      counting the FIELD instead of the document is the use-vs-mention rule this lane has
      paid for four times.

Working-tree green != clone green != CI green, so W2 runs in a clone, never here.

SCOPE CHANGE, disclosed rather than silently superseding a sibling: SLOP-INTEGRATE-R1.md
published `WIRING-PROVEN 5/5` for the ONE step wired at that rev. This file now verifies
TWO steps, so the check count is larger and R1's 5/5 is correct AT ITS REV for its step, not
a number to compare against this run.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Resolved from THIS FILE, never a literal. The previous version of this line was
# `ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")` -- the wiring verifier carried
# the exact defect class it now checks for, which is the third occurrence in this lane.
_HERE = Path(__file__).resolve().parent
_R = subprocess.run(
    ["git", "-C", str(_HERE), "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
ROOT = Path(
    _R.stdout.strip() if _R.returncode == 0 and _R.stdout.strip() else _HERE.parents[1]
)

WF_REL = ".github/workflows/no-runtime-junk.yml"
JOB = "no-runtime-junk"
OUT = ROOT / "command-center/slop-report/_i5_ci_wiring_verify.out.json"

STEPS = [
    {
        "prefix": "gate-published-commands",
        "gate": "command-center/slop-report/check_published_commands.py",
        "requires_selftest": True,
    },
    {
        "prefix": "gate-published-claims",
        "gate": "command-center/slop-report/_r6_transcript.py",
        "requires_selftest": False,
    },
]

# W5 both-states fixtures, both REAL committed files rather than synthetic strings.
PORTABLE_CONTROL = "command-center/slop-report/check_published_commands.py"
HARDCODED_CONTROL = "command-center/slop-report/_r5_reclassify.py"

ABS_LITERAL = re.compile(r"^(?:[A-Za-z]:[\\/]|/(?:home|Users|c)/)")


def binds_absolute_path(src: str) -> list[str]:
    """Names ASSIGNED an absolute-path string literal. AST, so docstrings do not count.

    Catches `X = "C:/..."`, `X: str = "C:/..."` and `X = Path("C:/...")`. A module that only
    NAMES the path in prose has no such assignment and is correctly silent.
    """
    found: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ["<unparseable>"]

    def literal_of(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Call) and node.args:
            return literal_of(node.args[0])
        return None

    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        val = literal_of(node.value) if node.value is not None else None
        if val and ABS_LITERAL.match(val):
            for t in targets:
                if isinstance(t, ast.Name):
                    found.append(f"{t.id} = {val!r}")
    return found


def find_step(wf_text: str, prefix: str):
    doc = yaml.safe_load(wf_text)
    for step in doc["jobs"][JOB]["steps"]:
        if str(step.get("name", "")).startswith(prefix):
            return step
    return None


def run(cmd, cwd):
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def main() -> int:
    res: dict = {"repo_root": str(ROOT).replace("\\", "/")}
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
    if not wf_text.strip():
        res["verdict"] = "ABORTED: workflow blob is empty at HEAD"
        print(json.dumps(res, indent=1, sort_keys=True))
        print("FAILED:i5 no committed workflow to read -- refusing to file a reading")
        return 1

    checks: dict = {}
    per_step: dict = {}

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

        for spec in STEPS:
            pfx, gate_rel = spec["prefix"], spec["gate"]
            s: dict = {}
            step = find_step(wf_text, pfx)
            s["W1_step_found"] = step is not None
            if step is None:
                s["verdict"] = "NOT-WIRED"
                per_step[pfx] = s
                checks[f"{pfx}:W1_step_is_wired"] = False
                continue
            script = str(step.get("run", ""))
            cmds = [ln.strip() for ln in script.splitlines() if ln.strip()]
            s["W1_step_name"] = step["name"]
            s["W1_commands"] = cmds

            # W4: the step must invoke the gate, not merely be named after it.
            s["W4_invokes_the_gate"] = any(gate_rel in cmd for cmd in cmds)
            s["W4_runs_the_selftest"] = any("--self-test" in cmd for cmd in cmds)

            # W2: execute the literal run: block the runner would execute.
            executed = []
            for cmd in cmds:
                parts = cmd.split()
                if parts and parts[0].startswith("python"):
                    parts[0] = sys.executable
                r = run(parts, clone)
                executed.append(
                    {
                        "cmd": cmd,
                        "rc": r["rc"],
                        "tail": r["out"].strip().splitlines()[-1:],
                    }
                )
            s["W2_executed"] = executed
            s["W2_all_green"] = all(e["rc"] == 0 for e in executed)

            # W3: both-states -- delete the step, the parser must notice.
            doc = yaml.safe_load(wf_text)
            doc["jobs"][JOB]["steps"] = [
                st
                for st in doc["jobs"][JOB]["steps"]
                if not str(st.get("name", "")).startswith(pfx)
            ]
            s["W3_unwired_step_found"] = find_step(yaml.safe_dump(doc), pfx) is not None
            s["W3_states_distinguishable"] = (
                s["W1_step_found"] and not s["W3_unwired_step_found"]
            )

            # W5: the invoked gate must be clone-valid. Read the CLONE's bytes.
            gate_path = os.path.join(clone, gate_rel)
            if not os.path.exists(gate_path):
                s["W5_gate_present_in_clone"] = False
                s["W5_binds_absolute"] = ["<gate absent from clone>"]
            else:
                s["W5_gate_present_in_clone"] = True
                with open(gate_path, encoding="utf-8") as fh:
                    s["W5_binds_absolute"] = binds_absolute_path(fh.read())
            s["W5_portable"] = (
                s["W5_gate_present_in_clone"] and not s["W5_binds_absolute"]
            )

            checks[f"{pfx}:W1_step_is_wired"] = s["W1_step_found"]
            checks[f"{pfx}:W2_wired_commands_all_pass_in_a_clone"] = s["W2_all_green"]
            checks[f"{pfx}:W3_unwired_state_is_detected"] = s[
                "W3_states_distinguishable"
            ]
            checks[f"{pfx}:W4_step_actually_invokes_the_gate"] = s[
                "W4_invokes_the_gate"
            ]
            if spec["requires_selftest"]:
                checks[f"{pfx}:W4_step_runs_the_selftest_first"] = s[
                    "W4_runs_the_selftest"
                ]
            checks[f"{pfx}:W5_invoked_gate_is_clone_valid"] = s["W5_portable"]
            per_step[pfx] = s

        # W5 both-states control, on REAL committed files. Without the known-bad arm a
        # green W5 could mean "the predicate never fires", which is the inert-control shape
        # this lane has now measured four times.
        def _read(rel: str) -> str:
            p = os.path.join(clone, rel)
            return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

        good = binds_absolute_path(_read(PORTABLE_CONTROL))
        bad = binds_absolute_path(_read(HARDCODED_CONTROL))
        res["W5_control"] = {
            "known_good": {"file": PORTABLE_CONTROL, "binds": good},
            "known_bad": {"file": HARDCODED_CONTROL, "binds": bad},
            "mentions_are_not_bindings": (
                "C:/Users/Prekzursil" in _read(PORTABLE_CONTROL) and not good
            ),
        }
        checks["W5_control_known_good_is_silent"] = not good
        checks["W5_control_known_bad_fires"] = bool(bad)
        checks["W5_control_ignores_a_docstring_mention"] = res["W5_control"][
            "mentions_are_not_bindings"
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    res["per_step"] = per_step
    res["checks"] = checks
    res["n_checks"] = len(checks)
    res["verdict"] = "WIRING-PROVEN" if checks and all(checks.values()) else "FAILED"

    OUT.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=1, sort_keys=True))
    print(f"\nwrote {OUT}")
    return 0 if res["verdict"] == "WIRING-PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main())
