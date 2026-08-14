"""Red-proof for the interpreter-floor gate's WIRING -- the half that makes it reachable.

WHY THIS FILE EXISTS. `command-center/ci/interpreter_floor_gate.py` was written, reviewed and
committed, and then sat for two rounds doing nothing at all, because no workflow invoked it.
Its own docstring said so in capitals: "NOT WIRED INTO CI". A committed detector that nothing
runs is indistinguishable from no detector, and this repo has already paid for that shape twice
-- once with a rail-count producer that was fixed but never invoked, once here.

So the wiring is now an ASSERTION rather than a claim, and the assertion is only credible if
each of its codes has been SEEN to fire:

  * ``test_the_real_repository_is_green`` is the HEALTHY control. Without it a checker that is
    permanently red would satisfy every mutation below and prove nothing.
  * ``test_mutation_turns_the_wiring_red`` is the BROKEN direction: one scratch copy per
    mutation, exactly ONE wire cut, and the specific code must appear. Every case is
    ``exclusive`` -- the cut wire must be the ONLY code that fires, which is what separates a
    targeted rule from one that reddens whenever anything is touched.
  * ``test_every_invariant_has_a_red_proof`` closes the last hole: a code in ``WIRING_CHECKS``
    with no mutation here is a code nobody has ever seen fire.

``mut_w4b`` exists because the first version of this checker would have passed it. The rule was
a substring test for ``main`` over the raw ``on:`` block, and that block carries a COMMENT
explaining why ``pull_request`` has no ``branches: [main]`` filter -- so deleting the real
``branches: [main]`` from ``push`` left the checker green, satisfied by its own documentation.
The record is kept rather than quietly deleted.

Run (there is no repo-wide pytest autodiscovery; ``.github/workflows/skill-dual-write.yml``
collects ``ci/tests`` as a directory, and ``.github/workflows/interpreter-floor.yml`` runs the
gate's own ``--verify-wiring`` on push)::

    python -m pytest ci/tests/test_interpreter_floor_wiring.py -q
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "command-center" / "ci" / "interpreter_floor_gate.py"
WORKFLOW_REL = ".github/workflows/interpreter-floor.yml"

sys.path.insert(0, str(GATE.parent))
import interpreter_floor_gate as floor  # noqa: E402


def _scratch(tmp_path: Path) -> Path:
    """Copy ONLY what ``wiring_violations`` reads, file by file.

    Not ``shutil.copytree`` over the repository: a blanket recursive copy on Windows aborts the
    moment it meets a reserved device name, and it would drag in whatever a sibling agent is
    mid-write. The checker reads ``.github/workflows/*.yml`` and the gate path those name, so
    that is the whole fixture.
    """
    root = tmp_path / "repo"
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    for src in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        shutil.copy2(src, wf / src.name)
    dst = root / "command-center" / "ci"
    dst.mkdir(parents=True)
    shutil.copy2(GATE, dst / GATE.name)
    return root


def _wf(root: Path) -> Path:
    return root / WORKFLOW_REL


def mut_w1_delete_workflow(root: Path) -> None:
    """The whole wiring file is removed -- the exact state this suite was written to prevent."""
    _wf(root).unlink()


def mut_w2_drop_selftest(root: Path) -> None:
    """The gate still runs, but its both-states control no longer does."""
    p = _wf(root)
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "python command-center/ci/interpreter_floor_gate.py --self-test",
            'python -c "pass"',
        ),
        encoding="utf-8",
    )


def mut_w3_move_gate(root: Path) -> None:
    """The workflow still names the gate; the gate has moved. Reachable-looking and broken."""
    gate = root / "command-center" / "ci" / GATE.name
    gate.rename(gate.with_name("interpreter_floor_gate_moved.py"))


def mut_w4_drop_push(root: Path) -> None:
    """No longer runs on push to main, so a defect lands and only a later PR notices."""
    p = _wf(root)
    p.write_text(
        p.read_text(encoding="utf-8").replace("  push:\n    branches: [main]\n", "", 1),
        encoding="utf-8",
    )


def mut_w4b_drop_branches_only(root: Path) -> None:
    """`push:` kept, `branches: [main]` deleted.

    The mutation the first version of this checker could not see: the surviving comment in the
    same block contains the word ``main``, so a substring test over the raw block stayed green.
    """
    p = _wf(root)
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "  push:\n    branches: [main]\n", "  push:\n", 1
        ),
        encoding="utf-8",
    )


def mut_w5_drop_pull_request(root: Path) -> None:
    """No longer runs on pull requests, so a defect is only caught after it is already on main."""
    p = _wf(root)
    p.write_text(
        p.read_text(encoding="utf-8").replace("  pull_request:\n", "", 1),
        encoding="utf-8",
    )


#: (mutation, the code it must produce). Every case is exclusive: that code and nothing else.
MUTATIONS: tuple[tuple[Callable[[Path], None], str], ...] = (
    (mut_w1_delete_workflow, "W1-no-workflow-invokes-gate"),
    (mut_w2_drop_selftest, "W2-invoked-without-self-test"),
    (mut_w3_move_gate, "W3-gate-path-does-not-exist"),
    (mut_w4_drop_push, "W4-not-run-on-push-to-main"),
    (mut_w4b_drop_branches_only, "W4-not-run-on-push-to-main"),
    (mut_w5_drop_pull_request, "W5-not-run-on-pull-request"),
)


def test_the_real_repository_is_green() -> None:
    """HEALTHY control. A permanently-red checker would pass every mutation below."""
    assert floor.wiring_violations(REPO_ROOT) == []


def test_the_scratch_copy_is_green(tmp_path: Path) -> None:
    """The fixture itself is clean, so a red below is the MUTATION and not the copy."""
    assert floor.wiring_violations(_scratch(tmp_path)) == []


@pytest.mark.parametrize(
    ("mutate", "code"), MUTATIONS, ids=[m.__name__ for m, _ in MUTATIONS]
)
def test_mutation_turns_the_wiring_red(
    mutate: Callable[[Path], None], code: str, tmp_path: Path
) -> None:
    root = _scratch(tmp_path)
    mutate(root)
    got = floor.wiring_violations(root)
    assert got == [code], f"{mutate.__name__}: expected exactly [{code}], got {got}"


def test_every_invariant_has_a_red_proof() -> None:
    """A code with no mutation is a code nobody has ever seen fire."""
    proven = {code for _, code in MUTATIONS}
    assert proven == set(floor.WIRING_CHECKS), (
        f"unproven: {sorted(set(floor.WIRING_CHECKS) - proven)};"
        f" stale: {sorted(proven - set(floor.WIRING_CHECKS))}"
    )


def test_the_workflow_runs_the_sweep_not_only_the_self_test() -> None:
    """A self-test-only wiring would be green forever while checking no repository file.

    ``--self-test`` builds its own fixtures in a temp dir, so it passes on a tree where every
    tracked file is broken. The sweep is the step that reads this repository, and it is a
    distinct invocation from the control that precedes it.
    """
    text = (REPO_ROOT / WORKFLOW_REL).read_text(encoding="utf-8")
    invocations = [
        ln.split("interpreter_floor_gate.py", 1)[1].strip()
        for ln in text.splitlines()
        if "run: python command-center/ci/interpreter_floor_gate.py" in ln
    ]
    assert "--self-test" in invocations, invocations
    assert "--verify-wiring" in invocations, invocations
    assert any(a in ("", "--report") for a in invocations), invocations
