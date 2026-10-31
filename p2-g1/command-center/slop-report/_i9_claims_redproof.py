"""INTEGRATE round 2 -- the BEHAVIOURAL red proof for `gate-published-claims`.

`_i5_ci_wiring_verify.py` proves the step is wired and that its commands exit 0. That is a
weaker claim than it looks: a step that runs `python -c pass` satisfies it. This asks the
question that decides whether the step earns its slot in CI --

    if a committed document publishes a number its own committed receipt refutes,
    does THE WIRED STEP, as extracted from the committed workflow blob, go red?
    and would anything ALREADY in CI have caught it?

Everything runs in a fresh LF clone. Working-tree green != clone green != CI green.

  R0  PRECONDITION. The clone, the step and the gate must all exist, or this ABORTS without
      filing a reading. Round 1 of this lane filed a T1 datum against a gate that was not in
      the clone at all; a missing instrument must abort, never produce a number.
  R1  BASELINE. The extracted step is rc 0 on the untouched clone -- wiring it does not red
      main.
  R2  RED. Inject one doc publishing `partition_total: false` against a receipt that says
      true, COMMIT it in the clone, re-run the extracted step -> must be rc 1 AND must name
      the injected document. rc 1 alone is not enough: a gate that fails for an unrelated
      reason would also produce it.
  R3  NEGATIVE / the other half of both-states. The SAME injection shape carrying the
      CORRECT value must leave the gate green. Without this, R2 could just mean "the gate
      fires on any new document", which would make it a nuisance rather than a detector.
  R4  BLINDNESS. Against the identical injected clone, run every OTHER gate CI already had:
      `ruff check .`, `ruff format --check .` at the pin, and the extracted
      `gate-published-commands` block. If they are all green, the defect ships without this
      step -- which is the state the repo was in five minutes ago. If any of them goes red,
      this step is redundant and should not have been added.
  R5  SOURCE INTEGRITY. The source worktree's porcelain status must be byte-identical before
      and after. Round 7 confirmed a clone-run that silently wrote its receipt back into the
      source tree, so "I ran it in a clone" is itself a claim needing evidence.
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
UNDER_TEST = "gate-published-claims"
PREEXISTING = "gate-published-commands"
OUT = ROOT / "command-center/slop-report/_i9_claims_redproof.out.json"

# The injected claim. `partition_total` is a real leaf key in the committed receipt
# _r5_reclassify.out.json, whose value is true. The doc names the receipt on the same line so
# the comparison is scoped to it rather than to every receipt in the directory. The word
# REFUTED is deliberately ABSENT -- it is the suppression marker, and including it would
# silence the very violation this fixture exists to produce.
INJECT_BAD = (
    "# Injected fixture\n\n"
    "The classifier reported `partition_total: false` in `_r5_reclassify.out.json`.\n"
)
INJECT_GOOD = (
    "# Injected fixture\n\n"
    "The classifier reported `partition_total: true` in `_r5_reclassify.out.json`.\n"
)
INJECT_REL = "command-center/slop-report/SLOP-REDPROOF-INJECTED.md"


def run(cmd, cwd):
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def extract(wf_text: str, prefix: str) -> list[str]:
    doc = yaml.safe_load(wf_text)
    for step in doc["jobs"][JOB]["steps"]:
        if str(step.get("name", "")).startswith(prefix):
            return [
                ln.strip() for ln in str(step.get("run", "")).splitlines() if ln.strip()
            ]
    return []


def exec_block(cmds: list[str], cwd: str) -> dict:
    rows = []
    for cmd in cmds:
        parts = cmd.split()
        if parts and parts[0].startswith("python"):
            parts[0] = sys.executable
        r = run(parts, cwd)
        rows.append({"cmd": cmd, "rc": r["rc"], "out": r["out"], "err": r["err"]})
    return {
        "rows": [{"cmd": x["cmd"], "rc": x["rc"]} for x in rows],
        "rc": max([x["rc"] for x in rows], default=-1),
        "text": "\n".join(x["out"] + x["err"] for x in rows),
    }


def commit_all(clone: str, msg: str) -> int:
    run(["git", "add", "-A"], clone)
    return run(
        [
            "git",
            "-c",
            "user.email=redproof@local",
            "-c",
            "user.name=redproof",
            "commit",
            "-q",
            "-m",
            msg,
        ],
        clone,
    )["rc"]


def porcelain() -> str:
    return run(["git", "status", "--porcelain", "-uall"], str(ROOT))["out"]


def lane_porcelain() -> list[str]:
    """Porcelain restricted to THIS lane's directory, minus this probe's own outputs.

    See R5 below for why the repo-wide form was abandoned.
    """
    return sorted(
        ln
        for ln in porcelain().splitlines()
        if "command-center/slop-report/" in ln and "_i9_" not in ln
    )


def sig(p: Path) -> dict:
    """size + mtime to the nanosecond -- enough to catch any write, cheap, no hashing."""
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {"exists": True, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def main() -> int:
    res: dict = {"repo_root": str(ROOT).replace("\\", "/")}
    src_before = porcelain()
    lane_before = lane_porcelain()
    # The ONLY file the claims gate can write. If a clone-run reached back into the source
    # -- the round-7 defect -- this is the artifact that would move.
    gate_out = ROOT / "command-center/slop-report/_r6_transcript.out.json"
    gate_sig_before = sig(gate_out)

    wf_text = run(["git", "cat-file", "-p", f"HEAD:{WF_REL}"], str(ROOT))["out"]
    under = extract(wf_text, UNDER_TEST)
    pre = extract(wf_text, PREEXISTING)
    res["step_under_test"] = {"prefix": UNDER_TEST, "commands": under}
    res["preexisting_step"] = {"prefix": PREEXISTING, "commands": pre}

    # ---- R0 preconditions: abort rather than file a reading ------------------------
    if not under:
        res["verdict"] = f"ABORTED: {UNDER_TEST} is not in the committed workflow"
        OUT.write_text(
            json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
        )
        print(json.dumps(res, indent=1, sort_keys=True))
        print("FAILED:i9-redproof step not wired at HEAD -- nothing to red-proof")
        return 1

    tmp = tempfile.mkdtemp(prefix="i9_redproof_")
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
            res["verdict"] = "ABORTED: clone failed"
            res["clone_err"] = c["err"][:400]
            OUT.write_text(
                json.dumps(res, indent=1, sort_keys=True),
                encoding="utf-8",
                newline="\n",
            )
            print("FAILED:i9-redproof clone failed -- refusing to file a reading")
            return 1
        res["clone_head"] = run(["git", "rev-parse", "HEAD"], clone)["out"].strip()
        gate_in_clone = os.path.join(
            clone, "command-center/slop-report/_r6_transcript.py"
        )
        res["R0_gate_present_in_clone"] = os.path.exists(gate_in_clone)
        if not res["R0_gate_present_in_clone"]:
            res["verdict"] = "ABORTED: gate absent from the clone"
            OUT.write_text(
                json.dumps(res, indent=1, sort_keys=True),
                encoding="utf-8",
                newline="\n",
            )
            print("FAILED:i9-redproof gate missing in clone")
            return 1

        # ---- R1 baseline ------------------------------------------------------------
        base = exec_block(under, clone)
        res["R1_baseline"] = {"rc": base["rc"], "rows": base["rows"]}

        # ---- R3 negative: the CORRECT value must stay green -------------------------
        good = os.path.join(clone, INJECT_REL)
        with open(good, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(INJECT_GOOD)
        commit_all(clone, "inject a doc publishing the CORRECT value")
        g = exec_block(under, clone)
        res["R3_correct_value_is_green"] = {"rc": g["rc"]}

        # ---- R2 red: same shape, wrong value ----------------------------------------
        with open(good, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(INJECT_BAD)
        commit_all(clone, "inject a doc publishing a number the receipt refutes")
        bad = exec_block(under, clone)
        named = os.path.basename(INJECT_REL) in bad["text"]
        res["R2_red"] = {
            "rc": bad["rc"],
            "names_the_injected_doc": named,
            "tail": bad["text"].strip().splitlines()[-3:],
        }

        # ---- R4 blindness: every OTHER gate CI already had, same injected clone ------
        blind = {}
        pre_res = exec_block(pre, clone) if pre else {"rc": -1, "rows": []}
        blind[PREEXISTING] = pre_res["rc"]
        for label, cmd in (
            ("ruff check .", ["ruff", "check", "."]),
            ("ruff format --check .", ["ruff", "format", "--check", "."]),
        ):
            r = run(cmd, clone)
            blind[label] = r["rc"]
        res["R4_preexisting_ci_on_the_same_injection"] = blind
        res["R4_all_preexisting_are_blind"] = all(v == 0 for v in blind.values())
        res["R4_ruff_version"] = run(["ruff", "--version"], clone)["out"].strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- R5, SECOND VERSION. The first one was my own detector failure, not a finding.
    # It compared the FULL repo porcelain before against after and came back false. That
    # cannot distinguish "the clone wrote into the source" (a real defect) from "a sibling
    # lane touched the shared tree while I ran" -- and round 7 already recorded that
    # equality against a moving value is not an invariant. Diagnosed rather than assumed
    # (`_i9_r5_diag.out.json`): in a 12s window with HEAD stationary, the only line that
    # moved was `M command-center/mcp-audit/_r2_dod_check.py`, another lane's file, while
    # the gate's own output was identical to the nanosecond. H1 refuted, H2 confirmed.
    #
    # The replacement is scoped to what a clone-run could actually have touched, so a
    # sibling editing mcp-audit can no longer refute a true conclusion.
    src_after = porcelain()
    gate_sig_after = sig(gate_out)
    lane_after = lane_porcelain()
    res["R5_gate_output_untouched"] = gate_sig_before == gate_sig_after
    res["R5_gate_output_sig"] = {"before": gate_sig_before, "after": gate_sig_after}
    res["R5_lane_porcelain_unchanged"] = lane_before == lane_after
    res["R5_lane_delta"] = sorted(set(lane_after) ^ set(lane_before))
    # Kept, not deleted: the wide reading and the reason it is not gating.
    res["R5_repo_wide_unchanged_REFUTED_moving_value"] = src_before == src_after
    res["R5_foreign_churn_during_run"] = sorted(
        ln
        for ln in (set(src_after.splitlines()) ^ set(src_before.splitlines()))
        if "command-center/slop-report/" not in ln
    )

    checks = {
        "R0_instrument_present": res.get("R0_gate_present_in_clone", False),
        "R1_baseline_green": res["R1_baseline"]["rc"] == 0,
        "R2_injection_turns_it_red": res["R2_red"]["rc"] != 0,
        "R2_failure_names_the_injected_doc": res["R2_red"]["names_the_injected_doc"],
        "R3_correct_value_stays_green": res["R3_correct_value_is_green"]["rc"] == 0,
        "R4_preexisting_ci_is_blind": res["R4_all_preexisting_are_blind"],
        "R5_gate_output_in_source_untouched": res["R5_gate_output_untouched"],
        "R5_lane_worktree_untouched": res["R5_lane_porcelain_unchanged"],
    }
    res["checks"] = checks
    res["verdict"] = "CLAIMS-GATE-RED-PROVEN" if all(checks.values()) else "FAILED"

    OUT.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {k: v for k, v in res.items() if k != "step_under_test"},
            indent=1,
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:i9-redproof"
        if res["verdict"] == "CLAIMS-GATE-RED-PROVEN"
        else "FAILED:i9-redproof see checks"
    )
    return 0 if res["verdict"] == "CLAIMS-GATE-RED-PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main())
