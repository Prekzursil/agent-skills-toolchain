"""End-to-end proof that the P2NEXT blast-radius sweep is WIRED and NECESSARY.

The claim under test is not "the survey passes today". It is the two-part integration claim:

  1. Without this wiring the defect ships GREEN -- the pre-existing p2next CI is BLIND to a NEW
     owner-facing page asserting the retracted rail verdict, because every check it runs reads a
     DECLARED document set (`rail_count_gate.py`'s `SECONDARY_DOCS`).
  2. The check that PROVES the wiring exists goes RED the moment the wiring is removed --
     otherwise "it is wired" is an unfalsifiable sentence in a document.

Four legs, each failing a different way if the integration is decorative:

  0  GOOD state, post-integration clone   -> survey GREEN, gate GREEN, wiring test PASSES
  A  a NEW live page asserts DOWN         -> survey RED, and rail_count_gate GREEN (BLIND)
                                             Leg A without its blind measurement would prove the
                                             survey works, not that it was needed.
  B  the SAME sentence in a round artifact -> survey GREEN (use-vs-mention: a page whose job is to
                                             record a retracted verdict is not asserting it). Without
                                             B, leg A is indistinguishable from "the word DOWN is bad".
  C  the workflow steps deleted            -> the wiring test FAILS. This is the control for the
                                             integration itself.

NOTHING IS WRITTEN TO THE REAL REPO. The clone lives under the system temp dir.

Run:  python command-center/p2-next/_l1_redproof.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: The files this lane adds or changes, committed into the clone so it represents the
#: POST-integration state exactly as CI will see it.
LANE_FILES = [
    "command-center/p2-next/_k4_tree_survey.py",
    ".github/workflows/p2next-rail-count.yml",
    "ci/tests/test_p2next_tree_survey_wiring.py",
]

SURVEY = ["python", "command-center/p2-next/_k4_tree_survey.py", "--check"]
RAIL_GATE = ["python", "command-center/p2-next/rail_count_gate.py"]
WIRING_TEST = [
    "python",
    "-m",
    "pytest",
    "ci/tests/test_p2next_tree_survey_wiring.py",
    "-q",
]

#: Deliberately carries NO digits. `rail_count_gate.py`'s C2 checks unit COUNTS; a number in the
#: injected sentence would confound "the gate is blind to the state assertion" with "the gate saw
#: a wrong count". This isolates the one variable under test.
INJECTED = "The cross-vendor review rail is DOWN and cannot be used.\n"


def run(cmd: list[str], cwd: Path) -> dict:
    real = [sys.executable] + cmd[1:] if cmd[0] == "python" else cmd
    proc = subprocess.run(real, cwd=cwd, capture_output=True, timeout=900)
    return {
        "cmd": " ".join(cmd),
        "rc": proc.returncode,
        "tail": proc.stdout.decode("utf-8", "replace").strip().splitlines()[-3:],
    }


def commit(clone: Path, paths: list[str], msg: str) -> bool:
    """-> True if a commit was made, False if there was nothing staged to commit.

    A no-op is NOT an error here, and treating it as one is a defect this lane has already
    shipped once (`48252d5e`: a before/after probe that went red the moment its own fix was
    committed). Once these lane files are committed upstream, the clone ALREADY carries them --
    which is the post-integration state this probe wants. `git commit` then exits 1 with
    "nothing to commit", and failing on that would make the probe red exactly when its subject
    is correct. So: stage, and commit only if staging produced something.
    """
    subprocess.run(["git", "add", "--"] + paths, cwd=clone, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=clone)
    if staged.returncode == 0:  # nothing staged
        return False
    subprocess.run(
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
        cwd=clone,
        check=True,
    )
    return True


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="p2next-l1-"))
    clone = tmp / "clone"
    results: dict[str, object] = {}
    ok = True
    try:
        # Windows-style path on purpose: MSYS rewrites a /c/... argument and the clone then
        # silently does not happen, which reads downstream as a failing probe.
        r = subprocess.run(
            ["git", "clone", "--no-hardlinks", "-q", str(REPO), str(clone)],
            cwd=tmp,
            capture_output=True,
        )
        if r.returncode != 0:
            print(f"FAILED:l1-redproof clone rc={r.returncode}")
            return 2

        for rel in LANE_FILES:
            dst = clone / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        made = commit(clone, LANE_FILES, "wire the blast-radius sweep into CI")
        results["lane_files_needed_a_commit"] = made
        print(
            f"  lane files: {'committed into the clone' if made else 'ALREADY at clone HEAD'} "
            "-- either way the clone is the post-integration state"
        )
        # CONTROL: whichever path was taken, the wiring MUST be present in the clone before any
        # leg runs. Without this, a silent copy failure would read as "leg C cannot find the
        # wiring" and be reported as a probe error rather than a missing integration.
        wf_text = (clone / ".github/workflows/p2next-rail-count.yml").read_text(
            encoding="utf-8"
        )
        if "_k4_tree_survey.py" not in wf_text:
            print("FAILED:l1-redproof the clone does not carry the wiring under test")
            return 2

        # --- leg 0: the good state -------------------------------------------------------
        leg0 = {
            "survey": run(SURVEY, clone),
            "rail_gate": run(RAIL_GATE, clone),
            "wiring_test": run(WIRING_TEST, clone),
        }
        good = all(v["rc"] == 0 for v in leg0.values())
        ok = ok and good
        results["0_good"] = leg0
        print(
            f"  {'ok ' if good else 'BAD'} 0 GOOD state: survey rc={leg0['survey']['rc']} "
            f"gate rc={leg0['rail_gate']['rc']} wiring-test rc={leg0['wiring_test']['rc']} (want 0/0/0)"
        )

        # --- leg A: a NEW owner-facing page, outside every declared set ------------------
        newpage = clone / "command-center" / "NEW-OWNER-PAGE.md"
        newpage.write_text(
            "# Wave status\n\n" + INJECTED, encoding="utf-8", newline="\n"
        )
        commit(clone, ["command-center/NEW-OWNER-PAGE.md"], "a new owner-facing page")
        lega = {"survey": run(SURVEY, clone), "rail_gate": run(RAIL_GATE, clone)}
        a_good = lega["survey"]["rc"] == 1 and lega["rail_gate"]["rc"] == 0
        ok = ok and a_good
        results["a_new_live_page"] = lega
        print(
            f"  {'ok ' if a_good else 'BAD'} A new live page asserts DOWN: survey rc="
            f"{lega['survey']['rc']} (want 1 = RED), rail_count_gate rc={lega['rail_gate']['rc']} "
            "(want 0 = BLIND, which is why the sweep was needed)"
        )

        # --- leg B: the same sentence where recording it is the page's JOB ---------------
        subprocess.run(
            ["git", "rm", "-q", "command-center/NEW-OWNER-PAGE.md"],
            cwd=clone,
            check=True,
        )
        hist = clone / "command-center" / "p2-next" / "P2NEXT-HISTORICAL-PROBE.md"
        hist.write_text(
            "# What round 3 believed\n\n" + INJECTED, encoding="utf-8", newline="\n"
        )
        # `git rm` has ALREADY staged the deletion; re-adding that path is an invalid pathspec
        # (measured: exit 128, "did not match any files"). Only the new file needs staging.
        commit(
            clone,
            ["command-center/p2-next/P2NEXT-HISTORICAL-PROBE.md"],
            "move the same sentence into a round artifact",
        )
        legb = {"survey": run(SURVEY, clone)}
        b_good = legb["survey"]["rc"] == 0
        ok = ok and b_good
        results["b_historical_is_not_a_claim"] = legb
        print(
            f"  {'ok ' if b_good else 'BAD'} B same sentence in a round artifact: survey rc="
            f"{legb['survey']['rc']} (want 0 -- use-vs-mention, not 'the word DOWN is bad')"
        )

        # --- leg C: the integration removed ----------------------------------------------
        wf = clone / ".github" / "workflows" / "p2next-rail-count.yml"
        text = wf.read_text(encoding="utf-8")
        stripped = "\n".join(
            ln for ln in text.splitlines() if "_k4_tree_survey.py" not in ln
        )
        if stripped == text:
            print("FAILED:l1-redproof leg C could not find the wiring to remove")
            return 2
        wf.write_text(stripped + "\n", encoding="utf-8", newline="\n")
        legc = {"wiring_test": run(WIRING_TEST, clone)}
        c_good = legc["wiring_test"]["rc"] != 0
        ok = ok and c_good
        results["c_wiring_removed"] = legc
        print(
            f"  {'ok ' if c_good else 'BAD'} C wiring steps deleted: wiring test rc="
            f"{legc['wiring_test']['rc']} (want non-zero -- the check must FAIL when the "
            "integration is missing)"
        )

        (REPO / "command-center/p2-next/L1-REDPROOF.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8", newline="\n"
        )
        if not ok:
            print("FAILED:l1-redproof a leg did not discriminate")
            return 1
        print(
            "SUCCESS:l1-redproof the sweep goes red on a page the pre-existing p2next CI ships "
            "green, and its wiring test goes red when the wiring is removed"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
