"""Prove the P2NEXT blast-radius sweep is CALLED by CI, not merely committed.

`_k4_tree_survey.py` was tracked, fail-closed and correct for a full round while **nothing
invoked it** -- `git grep` found it referenced only inside its own docstring. That is the
failure mode this repo has shipped repeatedly: a fixed script that nothing runs is not a fix.
Round 4 of the lane disclosed the gap it closes as a prospective residual ("a NEW owner-facing
page could assert the retracted rail verdict tomorrow and C6 would not scan it"), and a survey
run once by hand cannot close a prospective residual, because the next page is written after
the survey ran.

These tests fail if the wiring is removed. They are collected by `skill-dual-write.yml`'s
`python -m pytest ci/tests ...` directory sweep; `quality.yml` has NO tree-wide `ci/tests` step
(quality.yml:685 says so outright), so a wiring test placed here runs via that sweep and not via
quality.yml autodiscovery.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "p2next-rail-count.yml"
SURVEY = REPO_ROOT / "command-center" / "p2-next" / "_k4_tree_survey.py"

SELF_TEST_CMD = "python command-center/p2-next/_k4_tree_survey.py --self-test"
GATE_CMD = "python command-center/p2-next/_k4_tree_survey.py --check"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_workflow_and_the_survey_both_exist() -> None:
    # Known-broken: deleting either half leaves the other a dangling reference.
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert SURVEY.is_file(), f"missing {SURVEY}"


def test_workflow_actually_runs_the_tree_survey() -> None:
    """The whole point. Known-broken: the survey existed and CI never called it."""
    text = workflow_text()
    assert GATE_CMD in text, (
        "the blast-radius sweep is not invoked by CI; a committed gate nobody runs "
        "is the exact defect this step exists to prevent"
    )


def test_workflow_runs_the_survey_self_test_too() -> None:
    """Known-broken: a gate that has never failed is indistinguishable from a no-op.

    `ci-hygiene.md` §1. The survey's own suite carries 2 cases that expect a HIT, so
    running it is what makes the gate's silence mean something.
    """
    assert SELF_TEST_CMD in workflow_text()


def test_the_self_test_runs_before_the_gate() -> None:
    """Order is load-bearing: a self-test after the gate proves nothing about that run."""
    text = workflow_text()
    assert text.index(SELF_TEST_CMD) < text.index(GATE_CMD)


def test_ci_runs_the_non_writing_form() -> None:
    """CI must not be able to launder the receipt it verifies.

    Known-broken: `main()` wrote K4-TREE-SURVEY.json on EVERY run, including the verifying
    one -- the same shape round 2 of this lane had to fix in `vendor_satisfiability.py`.
    A bare `_k4_tree_survey.py` in CI would re-derive AND rewrite; `--check` derives and
    asserts only. This asserts the gate step carries `--check` and is not the bare form.
    """
    steps = [
        ln.strip()
        for ln in workflow_text().splitlines()
        if "_k4_tree_survey.py" in ln and ln.strip().startswith("run:")
    ]
    assert steps, "no run: step invokes the survey"
    for step in steps:
        assert "--check" in step or "--self-test" in step, (
            f"CI invokes the WRITING form of the survey: {step!r}"
        )


def test_the_survey_supports_the_flags_the_workflow_passes() -> None:
    """A wiring test that only greps YAML would pass against a survey that rejects the flag.

    So this EXECUTES both invocations. Known-broken: the workflow could name `--check`
    while the script's argparse does not define it, which fails only on the runner.
    """
    for flag, label in (("--self-test", "self-test"), ("--check", "check")):
        proc = subprocess.run(
            [sys.executable, str(SURVEY), flag],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=180,
        )
        # argparse rejects an unknown flag with exit 2 and an "unrecognized arguments" stderr.
        # The survey's own broken-detector path also returns 2, so assert on the message, not
        # only the code -- otherwise the two are indistinguishable.
        err = proc.stderr.decode("utf-8", "replace")
        assert "unrecognized arguments" not in err, (
            f"{label}: survey rejects {flag}: {err}"
        )
        assert proc.returncode in (0, 1), (
            f"{label}: unexpected exit {proc.returncode}; stderr={err[:400]}"
        )
