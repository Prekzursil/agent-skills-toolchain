"""BUILD R2 -- did THIS ROUND's three commits add any gate failure?

Round 1 answered this question and published the answer as the current state of main; the
number was already wrong (D1). So this asks a narrower question that does NOT rot: not "is
main green today" -- that moves hourly -- but "does the failing set at MY LAST COMMIT contain
anything MY COMMITS introduced". Both revs are pinned, so the answer is fixed forever.

Reads the two rev-anchored receipts produced by `_r2_gate_now.py --rev … --out …`:
  before = 61e69cf2  (parent of this round's first commit)
  after   = ebcd0bc1  (this round's last commit)
`git log 61e69cf2..ebcd0bc1` is exactly the three commits of this round -- no sibling commit is
interleaved -- so the delta is wholly attributable and per-file attribution is exact.

Controls: both receipts must report all_controls_pass, and the widened-vs-as-is states must
still be distinguishable. A "0 new failures" reading taken from a probe whose controls failed
is worth nothing.
"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
HERE = pathlib.Path(__file__).parent
OUT = pathlib.Path(__file__).with_suffix(".out.json")
BEFORE_REV = "61e69cf2"
AFTER_REV = "ebcd0bc1"


def main():
    before = json.loads(
        (HERE / "_r2_postgate_before.out.json").read_text(encoding="utf-8")
    )
    after = json.loads(
        (HERE / "_r2_postgate_after.out.json").read_text(encoding="utf-8")
    )

    changed = [
        p
        for p in subprocess.run(
            ["git", "-C", str(REPO), "diff", "--name-only", BEFORE_REV, AFTER_REV],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if p.strip()
    ]
    commits = [
        ln
        for ln in subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "log",
                "--format=%h %s",
                f"{BEFORE_REV}..{AFTER_REV}",
            ],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if ln.strip()
    ]

    fb = set(before["A_as_is"]["failing_files"])
    fa = set(after["A_as_is"]["failing_files"])
    new_failures = sorted(fa - fb)
    fixed = sorted(fb - fa)
    mine_in_failset = sorted(fa & set(changed))

    out = {
        "before_rev": before["rev_measured"],
        "after_rev": after["rev_measured"],
        "commits_in_range": commits,
        "range_is_only_this_round": len(commits) == 3,
        "files_changed_by_this_round": len(changed),
        "before": {
            "check_rc": before["A_as_is"]["check_rc"],
            "format_rc": before["A_as_is"]["format_rc"],
            "n_would_reformat": before["A_as_is"]["n_would_reformat"],
            "considered": before["blast_radius_widen"]["considered_as_is"],
        },
        "after": {
            "check_rc": after["A_as_is"]["check_rc"],
            "format_rc": after["A_as_is"]["format_rc"],
            "n_would_reformat": after["A_as_is"]["n_would_reformat"],
            "considered": after["blast_radius_widen"]["considered_as_is"],
        },
        "new_failures_introduced": new_failures,
        "failures_removed": fixed,
        "failing_files_touched_by_this_round": mine_in_failset,
        "considered_delta": after["blast_radius_widen"]["considered_as_is"]
        - before["blast_radius_widen"]["considered_as_is"],
        "controls_before": before["controls"],
        "controls_after": after["controls"],
    }

    checks = {
        "controls_pass_before": before["all_controls_pass"],
        "controls_pass_after": after["all_controls_pass"],
        "range_isolated_to_this_round": len(commits) == 3,
        "no_new_failures": new_failures == [],
        "no_failing_file_is_mine": mine_in_failset == [],
        "lint_not_worsened": after["A_as_is"]["check_rc"]
        <= before["A_as_is"]["check_rc"],
        "ruff_saw_the_new_files": out["considered_delta"] > 0,
    }
    out["checks"] = checks
    out["verdict"] = (
        "THIS-ROUND-ADDED-ZERO-GATE-FAILURES" if all(checks.values()) else "REGRESSION"
    )
    out["scope_note"] = (
        "Scoped deliberately: this says the three commits of round 2 introduce no failure "
        "between two PINNED revs. It does NOT say main is green -- at ebcd0bc1 the gate is "
        f"red on {after['A_as_is']['n_would_reformat']} sibling-owned files. For today's "
        "state run `python command-center/slop-report/_r2_gate_now.py`."
    )

    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"].startswith("THIS-ROUND") else 1


if __name__ == "__main__":
    sys.exit(main())
