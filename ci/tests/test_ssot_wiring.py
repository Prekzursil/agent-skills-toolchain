"""Both-states proof for the SSOT lane's wiring, and for the drift gate it wires in.

WHY THIS FILE EXISTS. The SSOT lane classified 25 checkouts, wrote a one-sentence rule and
built a drift gate -- and shipped all three unreachable. The rule lived in ``docs/``, which
nothing loads; the gate was a script nothing invoked. This suite is what turns "committed"
into "wired", and it is what makes the wiring CREDIBLE: a green checker proves nothing until
each of its codes has been shown to fire in the broken state.

  * ``test_the_real_repository_is_green`` is the HEALTHY control. Without it, a checker that
    is permanently red would still satisfy every mutation below.
  * ``test_mutation_turns_the_gate_red`` is the BROKEN direction: one scratch copy per
    mutation, exactly one wire cut, and the specific code must appear. Most are ``exclusive``
    -- the cut wire must be the ONLY code that fires, which is what separates a targeted rule
    from one that reddens whenever anything is touched.
  * ``test_every_invariant_has_a_red_proof`` closes the last hole: a code in ``CHECKS`` with
    no mutation is a code nobody has ever seen fire.
  * The ``drift gate`` tests drive ``ssot_drift_gate.py`` itself against a SYNTHETIC git repo
    built in ``tmp_path``. They are what make the gate's verdict portable: the gate's real
    target is a Windows path on one machine, so without these its logic would be unproven
    anywhere else, including on this CI runner.

One mutation exists because this checker's OWN first run was wrong, and the record is kept
rather than quietly deleted: ``W4-gate-unreferenced`` fired against a ``CLAUDE.md`` that DID
reference the gate. The original path regex required an entire backtick span to be the path,
so ``python command-center/ssot/ssot_drift_gate.py`` -- an invocation, the commonest way to
name a gate -- did not count. ``mut_w3_dangling_path`` proves the widened rule still bites.

Run (there is no repo-wide pytest autodiscovery; ``.github/workflows/skill-dual-write.yml``
runs ``pytest ci/tests`` as a directory AND names this file explicitly)::

    python -m pytest ci/tests/test_ssot_wiring.py -q
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "command-center" / "ssot" / "ssot_wiring_check.py"
GATE = REPO_ROOT / "command-center" / "ssot" / "ssot_drift_gate.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

# The explicit step in the workflow. The directory glob above it already collects this file,
# but the workflow's own comments record that the glob is one refactor away from not
# containing a given file -- so the explicit name is the durable wire, and this pins it.
WORKFLOW_STEP_MARKER = "python -m pytest ci/tests/test_ssot_wiring.py -q"

sys.path.insert(0, str(CHECKER.parent))
import ssot_wiring_check as wiring  # noqa: E402

# Everything the checker reads. Copied file-by-file rather than with ``shutil.copytree`` over
# the repository: a blanket recursive copy on Windows aborts mid-tree the moment it meets a
# reserved device name, and it would also drag in whatever a sibling agent is writing.
COPY_PATHS = (
    "CLAUDE.md",
    "docs/ssot/SSOT-CLONE-INVENTORY.md",
    "command-center/ssot/ssot_drift_gate.py",
    # W3 resolves every path the block names, and the block names the checker itself.
    # Omitting this from the scratch copy made the UNMUTATED copy red -- caught by
    # test_the_scratch_copy_is_green_before_mutation, which exists for exactly that.
    "command-center/ssot/ssot_wiring_check.py",
    # Round 4 added two more receipts to the block. Same trap as above, caught the same way:
    # the scratch copy went red on W3 the moment CLAUDE.md named a file the copy did not
    # carry. W3 only tests `.exists()`, so the bytes need not be importable here.
    "command-center/ssot/apply_severed_resolution.py",
    "command-center/ssot/redproof_severed.py",
    # W7 reads the measured artifact the block's counts claim to summarise. Same trap as
    # the two lines above, and it sprang a THIRD time: adding W7 without this entry made
    # the UNMUTATED scratch copy red, which then cascaded into all six exclusivity
    # assertions failing. Caught by test_the_scratch_copy_is_green_before_mutation before
    # CI ever saw it -- the control earning its place for the third round running.
    "command-center/ssot/population-classified.json",
    ".github/workflows/skill-dual-write.yml",
)


def _scratch(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in COPY_PATHS:
        src = REPO_ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return root


def _codes(root: Path) -> set[str]:
    return {code for code, _ in wiring.run(root)}


def _sub(path: Path, old: str, new: str) -> None:
    """Replace ``old`` with ``new``, asserting the anchor was actually present.

    A mutation whose anchor silently misses would leave the tree HEALTHY and the test would
    then be asserting that a green checker is red -- it would fail, but for the wrong
    reason, and the diagnostic would point at the checker instead of at this file.
    """
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor absent in {path.name}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Mutations: each cuts exactly one wire.
# --------------------------------------------------------------------------------------


def mut_w1_no_block(root: Path) -> None:
    _sub(root / "CLAUDE.md", wiring.BLOCK_START, "<!-- removed -->")


def mut_w2_sentence_drift(root: Path) -> None:
    _sub(
        root / "CLAUDE.md", "the only checkout you", "an entirely optional checkout you"
    )


def mut_w3_dangling_path(root: Path) -> None:
    _sub(
        root / "CLAUDE.md",
        "command-center/ssot/ssot_wiring_check.py",
        "command-center/ssot/ssot_wiring_check_RENAMED.py",
    )


def mut_w4_gate_unreferenced(root: Path) -> None:
    _sub(
        root / "CLAUDE.md",
        "command-center/ssot/ssot_drift_gate.py",
        "docs/ssot/SSOT-CLONE-INVENTORY.md",
    )


def mut_w5_gate_no_entry_point(root: Path) -> None:
    _sub(
        root / "command-center/ssot/ssot_drift_gate.py",
        'if __name__ == "__main__":',
        'if __name__ == "__never__":',
    )


def mut_w6_ci_unwired(root: Path) -> None:
    wf = root / ".github/workflows/skill-dual-write.yml"
    _sub(wf, "python -m pytest ci/tests tools/d001-dual-write/tests -q", "true")
    _sub(wf, WORKFLOW_STEP_MARKER, "true")


def mut_inventory_deleted(root: Path) -> None:
    (root / "docs/ssot/SSOT-CLONE-INVENTORY.md").unlink()


# --- W7 mutations ---------------------------------------------------------------------
# Four shapes, because W7 guards four different ways the counts can stop being true: the
# prose drifts off the measurement, the arithmetic stops closing, the sentence carrying a
# number disappears, or the artifact the numbers summarise is gone. Each must fire W7 and
# nothing else -- otherwise it stays unproven that W7 is what noticed.
POPULATION_JSON = "command-center/ssot/population-classified.json"


def mut_w7_population_drift(root: Path) -> None:
    _sub(
        root / "CLAUDE.md",
        "**178 checkouts across 168 object stores**",
        "**179 checkouts across 168 object stores**",
    )


def mut_w7_arithmetic_does_not_close(root: Path) -> None:
    """Round 4's actual defect, reconstructed: a kind split that does not add up.

    That round shipped `9 + 168 = 177` against a population of 178 and every reader went
    past it, because nothing added it up. This is the mutation that would have caught it.
    """
    _sub(root / "CLAUDE.md", "9 + 168 + 1 = 178", "9 + 168 + 1 = 177")


def mut_w7_claim_sentence_deleted(root: Path) -> None:
    """Deleting the sentence must not be quieter than getting its number wrong."""
    _sub(root / "CLAUDE.md", "5 have no remote at all.**", "some have no remote.**")


def mut_w7_artifact_absent(root: Path) -> None:
    """W3 resolves only `.md`/`.py`, so before W7 nothing required this file to exist."""
    (root / POPULATION_JSON).unlink()


def mut_w7_artifact_disagrees_with_itself(root: Path) -> None:
    """Break the artifact's own accounting without touching a single word of prose.

    Prose measured against a ruler whose own arithmetic does not close would be certified
    against a broken instrument, so W7 checks the artifact against itself first.
    """
    path = root / POPULATION_JSON
    pc = json.loads(path.read_text(encoding="utf-8"))
    pc["kind_arithmetic"]["severed_worktrees"] = 0
    pc["kind_arithmetic"]["sum"] = 177
    pc["kind_arithmetic"]["closes"] = False
    path.write_text(json.dumps(pc, indent=2), encoding="utf-8")


MUTATIONS: tuple[tuple[str, Callable[[Path], None], set[str], bool], ...] = (
    (
        "W1-claude-md-no-ssot-block",
        mut_w1_no_block,
        {"W1-claude-md-no-ssot-block"},
        True,
    ),
    ("W2-rule-sentence-drift", mut_w2_sentence_drift, {"W2-rule-sentence-drift"}, True),
    (
        "W3-referenced-path-missing",
        mut_w3_dangling_path,
        {"W3-referenced-path-missing"},
        True,
    ),
    ("W4-gate-unreferenced", mut_w4_gate_unreferenced, {"W4-gate-unreferenced"}, True),
    (
        "W5-gate-not-runnable",
        mut_w5_gate_no_entry_point,
        {"W5-gate-not-runnable"},
        True,
    ),
    ("W6-ci-suite-unwired", mut_w6_ci_unwired, {"W6-ci-suite-unwired"}, True),
    # Deliberately NON-exclusive: deleting the inventory cuts two wires at once, and a rule
    # that only ever fires one code at a time would be hiding one of them.
    (
        "inventory-deleted",
        mut_inventory_deleted,
        {"W2-rule-sentence-drift", "W3-referenced-path-missing"},
        False,
    ),
    ("W7-population-drift", mut_w7_population_drift, {"W7-count-drift"}, True),
    (
        "W7-arithmetic-does-not-close",
        mut_w7_arithmetic_does_not_close,
        {"W7-count-drift"},
        True,
    ),
    (
        "W7-claim-sentence-deleted",
        mut_w7_claim_sentence_deleted,
        {"W7-count-drift"},
        True,
    ),
    ("W7-artifact-absent", mut_w7_artifact_absent, {"W7-count-drift"}, True),
    (
        "W7-artifact-disagrees-with-itself",
        mut_w7_artifact_disagrees_with_itself,
        {"W7-count-drift"},
        True,
    ),
)


# --------------------------------------------------------------------------------------
# The checker: healthy control, then the broken direction.
# --------------------------------------------------------------------------------------


def test_the_real_repository_is_green() -> None:
    """HEALTHY control. A permanently-red checker would pass every mutation below."""
    assert wiring.run(REPO_ROOT) == []


def test_the_scratch_copy_is_green_before_mutation(tmp_path: Path) -> None:
    """The scratch copy must reproduce the real repo's verdict, or no mutation means anything."""
    assert _codes(_scratch(tmp_path)) == set()


@pytest.mark.parametrize(
    ("name", "mutate", "expected", "exclusive"),
    MUTATIONS,
    ids=[m[0] for m in MUTATIONS],
)
def test_mutation_turns_the_gate_red(
    tmp_path: Path,
    name: str,
    mutate: Callable[[Path], None],
    expected: set[str],
    exclusive: bool,
) -> None:
    root = _scratch(tmp_path)
    mutate(root)
    codes = _codes(root)
    assert expected <= codes, f"{name}: expected {expected}, got {codes}"
    if exclusive:
        assert codes == expected, (
            f"{name}: fired beyond the cut wire: {codes - expected}"
        )


def test_every_invariant_has_a_red_proof() -> None:
    """A code with no mutation is a code nobody has ever watched fire."""
    proven: set[str] = set()
    for _, _, expected, _ in MUTATIONS:
        proven |= expected
    declared = {code for code, _ in wiring.CHECKS}
    assert declared <= proven, f"codes with no red-proof: {sorted(declared - proven)}"


def test_the_workflow_names_this_suite_explicitly() -> None:
    """The durable wire. The directory glob collects this file today; this pins it."""
    assert WORKFLOW_STEP_MARKER in WORKFLOW.read_text(encoding="utf-8")


def test_checker_fails_closed_on_a_wrong_root(tmp_path: Path) -> None:
    """An empty --root must exit 3, never read as 'all wires intact'."""
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "FAILED:ssot-wiring-check" in proc.stdout


# --------------------------------------------------------------------------------------
# The drift gate itself, against a synthetic repo. Portable proof of a Windows-only gate.
# --------------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _synthetic_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo shaped like the executed checkout: one EXECUTED dir, one CONTROL dir."""
    repo = tmp_path / "executed"
    (repo / "tools/mcp/cloud-hub").mkdir(parents=True)
    (repo / "command-center").mkdir(parents=True)
    _git(repo.parent, "init", "--quiet", str(repo))
    _git(repo, "config", "user.email", "ssot@example.invalid")
    _git(repo, "config", "user.name", "ssot test")
    (repo / "tools/mcp/cloud-hub/server.py").write_text("v = 1\n", encoding="utf-8")
    (repo / "command-center/notes.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _run_gate(
    repo: Path, ref: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    # cwd defaults to the repo on purpose: the gate writes
    # command-center/ssot/drift-gate.json relative to the working directory, and a test must
    # never overwrite the committed receipt. The misconfiguration case passes an explicit cwd
    # because its --executed path deliberately does not exist, and spawning a process into a
    # non-existent cwd raises WinError 267 before the gate ever runs.
    return subprocess.run(
        [sys.executable, str(GATE), "--executed", str(repo), "--ref", ref],
        capture_output=True,
        text=True,
        cwd=str(cwd if cwd is not None else repo),
    )


def test_drift_gate_detects_a_stale_executed_checkout(tmp_path: Path) -> None:
    """THE point of the gate: an executed dir behind the reference must exit 1."""
    repo, base = _synthetic_repo(tmp_path)
    (repo / "tools/mcp/cloud-hub/server.py").write_text("v = 2\n", encoding="utf-8")
    (repo / "command-center/notes.md").write_text("churn\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "advance")

    proc = _run_gate(repo, base)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAILED:ssot-drift-gate drift=" in proc.stdout
    assert "tools/mcp/cloud-hub/server.py" in proc.stdout
    # The positive control must have PASSED here, or the exit 1 proves nothing.
    assert "control PASS" in proc.stdout


def test_drift_gate_reports_clean_at_parity(tmp_path: Path) -> None:
    """The other state. Without this, a gate hardcoded to exit 1 would pass the test above."""
    repo, base = _synthetic_repo(tmp_path)
    proc = _run_gate(repo, base)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SUCCESS:ssot-drift-gate drift=0" in proc.stdout


def test_drift_gate_fails_closed_when_it_cannot_see_a_difference(
    tmp_path: Path,
) -> None:
    """An empty commit puts HEAD off the reference while every diff is legitimately 0.

    The gate cannot tell that apart from a blind differ, so it must refuse to certify the
    fleet rather than report clean. Exit 3, not 0 -- this is the branch that stops the gate
    from being an inert control that passes and gets recorded as diligence.
    """
    repo, base = _synthetic_repo(tmp_path)
    _git(repo, "commit", "--quiet", "--allow-empty", "-m", "empty")
    proc = _run_gate(repo, base)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "FAILED:ssot-drift-gate detector-broken" in proc.stdout


def test_drift_gate_reports_misconfiguration_rather_than_clean(tmp_path: Path) -> None:
    """A non-existent executed checkout is exit 2, never a silent green."""
    proc = _run_gate(tmp_path / "nope", "HEAD", cwd=tmp_path)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "FAILED:ssot-drift-gate executed checkout absent" in proc.stdout
