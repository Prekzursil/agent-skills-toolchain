"""D7 -- adding a CI gate must not break the live charter-consistency gate.

``.quality/charter_check.sh`` runs inside quality.yml's ``lint`` job and does a
BIDIRECTIONAL one-in / one-out check:

  forward  every ``- slug: <s>`` in .quality/charter.yml needs a ``gate-<s>``
           marker in .github/workflows/quality.yml
  reverse  every ``gate-<s>`` marker in quality.yml must map back to a slug

So pasting a ``gate-skill-dual-write:`` job into quality.yml WITHOUT adding the
matching charter slug makes the script exit 1 -- which turns the EXISTING lint
job red.  That is strictly worse than the older "the ci/checks/ directory does
not exist" finding, and it is what these tests pin, both states.

The shipped wiring avoids the trap entirely by living in its own workflow file
(the ``no-runtime-junk.yml`` precedent): ``charter_check.sh`` reads ONLY
quality.yml, so a separate workflow carries no charter obligation.  Two
independent signals for that: the script's own ``workflow=`` assignment, and
the fact that ``no-runtime-junk.yml`` already ships a ``gate-no-runtime-junk``
job while main's charter check is green.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER = REPO_ROOT / ".quality" / "charter.yml"
CHECK = REPO_ROOT / ".quality" / "charter_check.sh"
QUALITY = REPO_ROOT / ".github" / "workflows" / "quality.yml"
LANE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

R2_JOB_YAML = """
  gate-skill-dual-write:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python ci/check_skill_dual_write.py --base origin/main --head HEAD
"""


def find_bash() -> str | None:
    """Git Bash on Windows -- NOT ``bash`` from PATH.

    On this class of box ``bash`` on PATH resolves to WSL's
    ``C:/WINDOWS/system32/bash.exe``, which rejects Windows paths.  Preferring
    the Git Bash binary is the difference between measuring the script and
    measuring the wrong interpreter.
    """
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("bash")


BASH = find_bash()
requires_bash = pytest.mark.skipif(BASH is None, reason="no bash interpreter found")


def build_tree(tmp_path: Path, *, include_lane_workflow: bool = True) -> Path:
    """Byte-exact copy of the charter + quality.yml (LF preserved)."""
    root = tmp_path / "tree"
    (root / ".quality").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    shutil.copyfile(CHARTER, root / ".quality" / "charter.yml")
    shutil.copyfile(CHECK, root / ".quality" / "charter_check.sh")
    shutil.copyfile(QUALITY, root / ".github" / "workflows" / "quality.yml")
    if include_lane_workflow and LANE_WORKFLOW.is_file():
        shutil.copyfile(
            LANE_WORKFLOW, root / ".github" / "workflows" / "skill-dual-write.yml"
        )
    return root


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, str(root / ".quality" / "charter_check.sh")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def append(path: Path, text: str) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


@requires_bash
def test_d7_known_good_shipped_wiring_keeps_the_charter_green(tmp_path: Path) -> None:
    """The gate ships as its own workflow file; charter_check stays at exit 0."""
    root = build_tree(tmp_path)
    assert (root / ".github" / "workflows" / "skill-dual-write.yml").is_file()
    proc = run_check(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "charter_check: OK" in proc.stdout


@requires_bash
def test_d7_known_broken_r2_job_in_quality_yml_turns_the_lint_job_red(
    tmp_path: Path,
) -> None:
    """Reverse scan: a gate-* job with no charter slug -> exit 1."""
    root = build_tree(tmp_path)
    append(root / ".github" / "workflows" / "quality.yml", R2_JOB_YAML)
    proc = run_check(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "gate-skill-dual-write" in proc.stderr
    assert "charter_check: FAILED" in proc.stderr


@requires_bash
def test_d7_alternative_quality_yml_job_plus_charter_slug_is_green(
    tmp_path: Path,
) -> None:
    """Option GOOD-A: the job is legal only when its slug lands in the SAME change."""
    root = build_tree(tmp_path)
    append(root / ".github" / "workflows" / "quality.yml", R2_JOB_YAML)
    append(
        root / ".quality" / "charter.yml",
        '  - slug: skill-dual-write\n    tools: ["python 3.11"]\n'
        "    enforces: >-\n      D-001 dual-write gate.\n",
    )
    proc = run_check(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_bash
def test_d7_forward_scan_charter_slug_without_a_marker_also_fails(
    tmp_path: Path,
) -> None:
    """The mirror-image trap: do NOT add a slug for a gate that lives elsewhere."""
    root = build_tree(tmp_path)
    append(
        root / ".quality" / "charter.yml",
        '  - slug: skill-dual-write\n    tools: ["python 3.11"]\n'
        "    enforces: >-\n      D-001 dual-write gate.\n",
    )
    proc = run_check(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "has no matching" in proc.stderr


@requires_bash
def test_d7_detector_sanity_baseline_without_the_lane_workflow_is_also_green(
    tmp_path: Path,
) -> None:
    """Anchors the known-good leg to main's own state, not to this lane's change."""
    root = build_tree(tmp_path, include_lane_workflow=False)
    assert run_check(root).returncode == 0


def test_charter_check_reads_only_quality_yml() -> None:
    """Static corroboration of the runtime result above (second signal)."""
    text = CHECK.read_text(encoding="utf-8")
    assert 'workflow="$here/.github/workflows/quality.yml"' in text
    others = [
        line
        for line in text.splitlines()
        if "workflows/" in line and "quality.yml" not in line
    ]
    assert others == [], others
