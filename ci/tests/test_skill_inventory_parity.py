"""Both-states proof for ``ci/check_skill_inventory_parity.py``.

A green checker proves nothing until each of its rules has been SEEN TO FIRE, so
every rule here is exercised in both directions: a known-BAD tree that must go
red, and the known-GOOD twin that must stay silent.  Four of the controls run
against the REAL repository rather than a synthetic fixture, because the defect
this gate exists to catch is live at HEAD and a synthetic reproduction of it
would only demonstrate self-consistency:

  * ``test_real_repo_is_green_with_the_committed_baseline``    the adoptable state.
  * ``test_real_repo_without_pins_reports_the_measured_15``    the same tree, pins
    removed, must report exactly the 15 asymmetric skills -- the RED state.
  * ``test_the_two_surfaces_reconcile_to_the_plans_twelve``    the arithmetic that
    settles which reading of "the set of skills" the plan section used.
  * ``test_dual_write_strict_parity_is_blind_to_that_asymmetry``  the control that
    justifies the arm existing at all.  Two hypotheses, distinguishable outcomes:
    H1 "the existing gate already covers inventory" predicts it goes red on this
    tree; H2 "it is diff-scoped and cannot see a standing asymmetry" predicts
    green.  It is green.  That is a scope statement about the neighbour gate, NOT
    a defect in it -- it is correct for the job it claims.

WHY THE MANIFEST SURFACE IS TESTED SEPARATELY.  A first version of this gate
compared DIRECTORY presence only.  It was green on ``microsoft-foundry`` --
whose projection copy holds 42 of 204 files and no ``SKILL.md`` -- and that green
was used to conclude the plan's count had gone stale.  The conclusion was wrong:
a directory detector answering a loadable-skill question.  ``crcp-health`` is the
control in the other direction (asset-only in BOTH roots, correctly silent), and
both are pinned as real-repo assertions below so the pair cannot regress.

The two enumerations (``os`` walk vs ``git ls-tree``) are asserted to AGREE at
HEAD on BOTH surfaces, which is the second mechanically independent signal behind
every count this suite reports.

Run (there is no repo-wide pytest autodiscovery)::

    python -m pytest ci/tests/test_skill_inventory_parity.py -q

NOT WIRED INTO CI.  Unlike ``test_skill_render_traps.py`` this file asserts no
workflow markers, because the gate is deliberately unwired: the private-repo
Actions minute allowance is exhausted, so a workflow edit could not be verified.
When it is wired, add the marker assertions then -- do not add them before, or
the suite pins a wire that does not exist.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "ci" / "check_skill_inventory_parity.py"
DUAL_WRITE = REPO_ROOT / "ci" / "check_skill_dual_write.py"
BASELINE = REPO_ROOT / "ci" / "skill-inventory-baseline.txt"

#: Measured at HEAD on 2026-08-14 by BOTH enumerations, on both surfaces.
#: The asymmetry the 2026-08-28 SSOT fold (15905d35) RECONCILED. Kept as the
#: historical record the real-repo controls below used to pin: 11 canonical-only
#: + 3 projection-only + 1 manifest-canonical-only = the "measured 15". Every one
#: of these is now symmetric across both roots, and ci/skill-inventory-baseline.txt
#: (shrink-only) correspondingly holds zero pins.
RECONCILED_CANONICAL_ONLY = (
    "claim-verify-gate",
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
    "qdx-rush",
)
RECONCILED_PROJECTION_ONLY = (
    "harness-module-authoring",
    "patent-fto-search",
    "social-corpus-extraction",
)
#: Directory in both roots, SKILL.md was only in the canonical one.
RECONCILED_PARTIAL = ("microsoft-foundry",)
#: Asset-only in BOTH roots: symmetric on both surfaces, must stay silent.
MEASURED_SYMMETRIC_ASSET_ONLY = "crcp-health"

sys.path.insert(0, str(GATE.parent))
import check_skill_inventory_parity as gate  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
def build_skill_tree(
    root: Path,
    canonical: dict[str, str | None] | None = None,
    projection: dict[str, str | None] | None = None,
    baseline: str | None = "",
) -> Path:
    """Materialise a two-root skill tree.

    A value is the SKILL.md body; ``None`` builds an ASSET-ONLY directory (one
    ``notes.md``, no ``SKILL.md``) -- the shape that separates the two surfaces.
    """
    for sub, skills in (
        (gate.CANONICAL_ROOT, canonical or {}),
        (gate.PROJECTION_ROOT, projection or {}),
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)
        for name, body in skills.items():
            skill_dir = root / sub / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            if body is None:
                (skill_dir / "notes.md").write_text("asset", encoding="utf-8")
            else:
                (skill_dir / gate.MANIFEST).write_text(body, encoding="utf-8")
    if baseline is not None:
        (root / "ci").mkdir(parents=True, exist_ok=True)
        (root / "ci" / "skill-inventory-baseline.txt").write_text(
            baseline, encoding="utf-8"
        )
    return root


def run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )


# --------------------------------------------------------------------------- #
# R1 unpinned-asymmetry (directory surface) -- both states                      #
# --------------------------------------------------------------------------- #
def test_known_good_symmetric_tree_is_silent(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path, canonical={"a": "x", "b": "x"}, projection={"a": "x", "b": "x"}
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr
    assert f"SUCCESS:{gate.MARKER}" in result.stdout


def test_known_bad_canonical_only_skill_fires(tmp_path: Path) -> None:
    """The control: the same tree minus one projection copy MUST go red."""
    build_skill_tree(tmp_path, canonical={"a": "x", "b": "x"}, projection={"a": "x"})
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_UNPINNED in result.stdout
    assert "b" in result.stdout
    assert f"FAILED:{gate.MARKER} violations=1" in result.stdout


def test_known_bad_projection_only_skill_fires(tmp_path: Path) -> None:
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={"a": "x", "b": "x"})
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_UNPINNED in result.stdout
    assert gate.KIND_PROJECTION_ONLY in result.stdout


def test_a_pin_makes_the_known_bad_tree_green(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x", "b": "x"},
        projection={"a": "x"},
        baseline="# reason\ncanonical-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# R2 partial-projection (manifest surface) -- both states                       #
# --------------------------------------------------------------------------- #
def test_partial_projection_fires_when_only_one_root_has_skill_md(
    tmp_path: Path,
) -> None:
    """The microsoft-foundry shape: directory in BOTH roots, SKILL.md in one.

    A directory-only comparison calls this symmetric.  It is not: the projection
    copy cannot be selected by any loader.
    """
    build_skill_tree(
        tmp_path, canonical={"a": "x", "b": "x"}, projection={"a": "x", "b": None}
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_PARTIAL in result.stdout
    assert gate.KIND_MANIFEST_CANONICAL_ONLY in result.stdout


def test_partial_projection_fires_in_the_other_direction(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path, canonical={"a": "x", "b": None}, projection={"a": "x", "b": "x"}
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.KIND_MANIFEST_PROJECTION_ONLY in result.stdout


def test_asset_only_in_both_roots_is_symmetric(tmp_path: Path) -> None:
    """The crcp-health control: no SKILL.md on EITHER side is not an asymmetry."""
    build_skill_tree(
        tmp_path, canonical={"a": "x", "b": None}, projection={"a": "x", "b": None}
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr


def test_a_pin_makes_the_partial_projection_green(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x", "b": "x"},
        projection={"a": "x", "b": None},
        baseline="skill-md-canonical-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# R3 direction-mismatch, R4 stale-baseline, R5 unknown-baseline                 #
# --------------------------------------------------------------------------- #
def test_direction_mismatch_fires_when_a_skill_swaps_roots(tmp_path: Path) -> None:
    """The set-difference is unchanged in SIZE; only the direction moved.

    A gate that compared counts, or that only asked "is this name asymmetric",
    would stay quiet here while the authoritative copy was being deleted.
    """
    build_skill_tree(
        tmp_path,
        canonical={"a": "x"},
        projection={"a": "x", "b": "x"},
        baseline="canonical-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_DIRECTION in result.stdout


def test_direction_mismatch_fires_across_the_two_surfaces(tmp_path: Path) -> None:
    """Pinned as a missing DIRECTORY, but the directory arrived without SKILL.md.

    The pin must not silently absorb a different defect than the one it records.
    """
    build_skill_tree(
        tmp_path,
        canonical={"a": "x", "b": "x"},
        projection={"a": "x", "b": None},
        baseline="canonical-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_DIRECTION in result.stdout


def test_stale_pin_fires_once_the_skill_is_reconciled(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x", "b": "x"},
        projection={"a": "x", "b": "x"},
        baseline="canonical-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_STALE in result.stdout


def test_unknown_pin_fires_when_the_skill_is_gone(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x"},
        projection={"a": "x"},
        baseline="canonical-only:retired\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_VIOLATION, result.stdout + result.stderr
    assert gate.RULE_UNKNOWN in result.stdout


# --------------------------------------------------------------------------- #
# fail-closed surface -- exit 2, never a pass                                   #
# --------------------------------------------------------------------------- #
def test_empty_walk_is_a_configuration_error_not_a_pass(tmp_path: Path) -> None:
    """The no-op-gate shape: both roots exist, neither holds a skill."""
    build_skill_tree(tmp_path, canonical={}, projection={})
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert "empty walk" in result.stderr
    assert f"SUCCESS:{gate.MARKER}" not in result.stdout


def test_one_empty_root_is_a_configuration_error(tmp_path: Path) -> None:
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={})
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr


def test_empty_manifest_surface_is_a_configuration_error(tmp_path: Path) -> None:
    """Directories on both sides, zero SKILL.md anywhere.

    The manifest surface fails independently of the directory surface: a broken
    SKILL.md read would otherwise produce two empty sets whose difference is
    empty, i.e. a clean verdict from a measurement that never happened.
    """
    build_skill_tree(tmp_path, canonical={"a": None}, projection={"a": None})
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert gate.MANIFEST in result.stderr


def test_missing_root_is_a_configuration_error(tmp_path: Path) -> None:
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={"a": "x"})
    result = run_gate("--repo", str(tmp_path), "--projection-root", "does-not-exist")
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert "does not exist" in result.stderr


def test_identical_roots_are_a_configuration_error(tmp_path: Path) -> None:
    """The ONLY shape that could fail silently GREEN, so it is refused outright."""
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={"a": "x"})
    result = run_gate(
        "--repo",
        str(tmp_path),
        "--canonical-root",
        gate.CANONICAL_ROOT,
        "--projection-root",
        gate.CANONICAL_ROOT,
    )
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert "same directory" in result.stderr


def test_missing_baseline_is_a_configuration_error(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path, canonical={"a": "x"}, projection={"a": "x"}, baseline=None
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert "cannot read baseline" in result.stderr


@pytest.mark.parametrize(
    "line", ["nonsense\n", "canonical-only:\n", "sideways-only:a\n", "a\n"]
)
def test_malformed_baseline_line_is_a_configuration_error(
    tmp_path: Path, line: str
) -> None:
    build_skill_tree(
        tmp_path, canonical={"a": "x"}, projection={"a": "x"}, baseline=line
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr


def test_duplicate_pin_is_a_configuration_error(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x"},
        projection={"a": "x"},
        baseline="canonical-only:b\nprojection-only:b\n",
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_CONFIG, result.stdout + result.stderr
    assert "pinned twice" in result.stderr


# --------------------------------------------------------------------------- #
# enumeration semantics                                                         #
# --------------------------------------------------------------------------- #
def test_an_empty_directory_is_not_a_skill(tmp_path: Path) -> None:
    """git cannot represent an empty directory, so counting one here would
    manufacture an asymmetry that the committed tree does not have."""
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={"a": "x"})
    (tmp_path / gate.CANONICAL_ROOT / "hollow").mkdir()
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr


def test_a_loose_file_under_a_root_is_not_a_skill(tmp_path: Path) -> None:
    build_skill_tree(tmp_path, canonical={"a": "x"}, projection={"a": "x"})
    (tmp_path / gate.PROJECTION_ROOT / "SKILLS-MANIFEST.md").write_text(
        "x", encoding="utf-8"
    )
    result = run_gate("--repo", str(tmp_path))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr


def test_no_baseline_flag_can_only_add_violations(tmp_path: Path) -> None:
    build_skill_tree(
        tmp_path,
        canonical={"a": "x", "b": "x"},
        projection={"a": "x"},
        baseline="canonical-only:b\n",
    )
    pinned = run_gate("--repo", str(tmp_path))
    unpinned = run_gate("--repo", str(tmp_path), "--no-baseline")
    assert pinned.returncode == gate.EXIT_OK, pinned.stdout + pinned.stderr
    assert unpinned.returncode == gate.EXIT_VIOLATION


# --------------------------------------------------------------------------- #
# REAL-REPO controls                                                            #
# --------------------------------------------------------------------------- #
def test_the_two_enumerations_agree_at_head() -> None:
    """Second mechanically independent signal: os walk vs git ls-tree."""
    for root in (gate.CANONICAL_ROOT, gate.PROJECTION_ROOT):
        walk = gate.inventory_from_worktree(REPO_ROOT, root)
        tree = gate.inventory_from_git(REPO_ROOT, root, "HEAD")
        assert walk.dirs == tree.dirs, (
            f"{root} dirs: worktree-only={sorted(walk.dirs - tree.dirs)} "
            f"git-only={sorted(tree.dirs - walk.dirs)}"
        )
        assert walk.manifests == tree.manifests, (
            f"{root} {gate.MANIFEST}: "
            f"worktree-only={sorted(walk.manifests - tree.manifests)} "
            f"git-only={sorted(tree.manifests - walk.manifests)}"
        )


def test_real_repo_is_green_with_the_committed_baseline() -> None:
    assert BASELINE.is_file()
    result = run_gate("--repo", str(REPO_ROOT))
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr
    assert f"SUCCESS:{gate.MARKER}" in result.stdout


def _real_repo_unpinned() -> dict[str, object]:
    """The live tree with the baseline ignored.

    Until 2026-08-28 this was the RED state (15 violations). The SSOT fold made
    both roots symmetric, so the unpinned run is now GREEN and identical to the
    pinned one — asserted below rather than assumed, because a tree that drifts
    back into asymmetry must fail here first.
    """
    result = run_gate("--repo", str(REPO_ROOT), "--no-baseline", "--json")
    assert result.returncode == gate.EXIT_OK, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_real_repo_without_pins_reports_zero_asymmetry() -> None:
    """The measured state of the live tree, with nothing grandfathered.

    Replaces ``test_real_repo_without_pins_reports_the_measured_15``: the 15 it
    pinned (``RECONCILED_*`` above) are all symmetric since 15905d35, and the
    shrink-only baseline carries zero pins to match.
    """
    payload = _real_repo_unpinned()
    asymmetric = payload["summary"]["asymmetric"]
    assert asymmetric[gate.KIND_CANONICAL_ONLY] == []
    assert asymmetric[gate.KIND_PROJECTION_ONLY] == []
    assert asymmetric[gate.KIND_MANIFEST_CANONICAL_ONLY] == []
    assert asymmetric[gate.KIND_MANIFEST_PROJECTION_ONLY] == []
    assert payload["violations"] == []
    assert payload["summary"]["pinned"] == 0
    assert payload["summary"]["canonical_dirs"] == payload["summary"]["projection_dirs"]

    # The baseline file itself agrees: comments only, no grandfathered skill.
    pins = [
        line
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert pins == []


def test_every_reconciled_skill_is_now_symmetric() -> None:
    """The plan's 12 + 3 reconciled to zero, and stays zero.

    History: the plan recorded 12 canonical-only + 3 projection-only. On the
    DIRECTORY surface alone the pre-fold repo showed 11 + 3; adding the
    manifest-surface row (microsoft-foundry) reproduced the plan's 12 exactly, so
    the plan was measuring loadable skills and was never stale. All 15 are now
    present on both surfaces of both roots, checked by name so a regression names
    the skill rather than a count.
    """
    for root in (gate.CANONICAL_ROOT, gate.PROJECTION_ROOT):
        inventory = gate.inventory_from_worktree(REPO_ROOT, root)
        for name in (
            *RECONCILED_CANONICAL_ONLY,
            *RECONCILED_PROJECTION_ONLY,
            *RECONCILED_PARTIAL,
        ):
            assert name in inventory.dirs, f"{root}: {name} directory missing"
            assert name in inventory.manifests, f"{root}: {name} SKILL.md missing"

    # And the independent SKILL.md-only measurement agrees: no canonical-side
    # manifest is missing from the projection, and vice versa.
    canonical = {
        p.parent.name
        for p in (REPO_ROOT / gate.CANONICAL_ROOT).glob(f"*/{gate.MANIFEST}")
    }
    projection = {
        p.parent.name
        for p in (REPO_ROOT / gate.PROJECTION_ROOT).glob(f"*/{gate.MANIFEST}")
    }
    assert canonical == projection, (
        f"canonical-only={sorted(canonical - projection)} "
        f"projection-only={sorted(projection - canonical)}"
    )


def test_an_asset_only_directory_in_both_roots_stays_silent_in_the_real_repo() -> None:
    """crcp-health: the negative control for the manifest rule, on live data."""
    payload = _real_repo_unpinned()
    for names in payload["summary"]["asymmetric"].values():
        assert MEASURED_SYMMETRIC_ASSET_ONLY not in names
    for root in (gate.CANONICAL_ROOT, gate.PROJECTION_ROOT):
        inventory = gate.inventory_from_worktree(REPO_ROOT, root)
        assert MEASURED_SYMMETRIC_ASSET_ONLY in inventory.dirs
        assert MEASURED_SYMMETRIC_ASSET_ONLY not in inventory.manifests


def test_dual_write_strict_parity_is_blind_to_that_asymmetry() -> None:
    """H1 vs H2 control -- see this module's docstring.

    ``--base HEAD --head HEAD`` is an empty range, which is the point: the
    neighbour gate's verdict is a function of the RANGE, so it reports OK
    regardless of what the tree holds.  When this control was written the tree
    held 15 asymmetric skills and the inventory arm reported them while the range
    arm said OK — the measurement that shows an inventory arm is a different
    check.  Since 15905d35 the tree is symmetric, so both arms now agree on OK;
    the blindness itself is still proven on a constructed asymmetric tree by the
    fixture tests above.  Here we pin that the two arms agree on the live tree.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(DUAL_WRITE),
            "--base",
            "HEAD",
            "--head",
            "HEAD",
            "--strict-parity",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK:" in result.stdout

    inventory = run_gate("--repo", str(REPO_ROOT), "--no-baseline")
    assert inventory.returncode == gate.EXIT_OK, inventory.stdout + inventory.stderr
    assert f"SUCCESS:{gate.MARKER}" in inventory.stdout
