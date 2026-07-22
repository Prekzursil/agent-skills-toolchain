"""D4 -- the gate must actually be EXECUTED, not merely committed.

This repository has no repo-wide test autodiscovery.  ``quality.yml`` runs a
short, explicit list of per-package ``run:`` blocks; dropping a file into a
directory does NOT get it executed, and the ``ci/checks/`` path an earlier
proposal targeted does not exist on any branch.  A check runs here only when a
workflow step invokes it by an explicit path -- the ``ci/gen_hooks.py`` /
``.quality/charter_check.sh`` precedent.

These tests assert the structural link between this suite and the workflow step
that runs it, so moving or renaming either side fails loudly instead of quietly
un-wiring the gate.  The both-states proof for D4 (break an assertion -> the CI
command goes RED; revert -> GREEN) is run against the workflow's own command
line and recorded in the lane evidence.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
GUARD = REPO_ROOT / "ci" / "check_skill_dual_write.py"
APPLIER = REPO_ROOT / "tools" / "d001-dual-write" / "d001_apply.py"

SELFTEST_MARKER = "python -m pytest ci/tests tools/d001-dual-write/tests"
GATE_MARKER = "python ci/check_skill_dual_write.py"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_file_exists() -> None:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"


def test_guard_and_applier_paths_referenced_by_the_workflow_exist() -> None:
    assert GUARD.is_file()
    assert APPLIER.is_file()


def test_workflow_selftest_step_covers_this_test_directory() -> None:
    """If these tests move, the workflow must move with them."""
    rel = Path(__file__).resolve().parent.relative_to(REPO_ROOT).as_posix()
    assert rel == "ci/tests"
    assert SELFTEST_MARKER in workflow_text()


def test_workflow_selftest_step_covers_the_applier_test_directory() -> None:
    rel = APPLIER.parent.joinpath("tests").relative_to(REPO_ROOT).as_posix()
    assert rel == "tools/d001-dual-write/tests"
    assert rel in workflow_text()


def test_workflow_invokes_the_guard_by_explicit_path() -> None:
    text = workflow_text()
    assert GATE_MARKER in text
    assert "--base origin/main --head HEAD" in text


def test_workflow_job_carries_a_gate_marker_name() -> None:
    assert "name: gate-skill-dual-write" in workflow_text()


def test_workflow_pins_every_action_by_sha() -> None:
    """Repo policy: all actions are SHA-pinned (supply-chain hardening)."""
    uses = [
        line.split("uses:", 1)[1].strip()
        for line in workflow_text().splitlines()
        if "uses:" in line
    ]
    assert uses, "workflow declares no actions"
    for ref in uses:
        action, _, sha = ref.partition("@")
        sha = sha.split()[0]
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), (
            f"{action} is not SHA-pinned: {ref}"
        )


def test_workflow_fetches_main_so_the_three_dot_base_resolves() -> None:
    text = workflow_text()
    assert "fetch-depth: 0" in text
    assert "refs/remotes/origin/main" in text
