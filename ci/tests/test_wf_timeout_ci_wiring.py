"""The H6 red-proof must be EXECUTED by CI, not merely committed.

``tools/wf-timeout`` ships design item H6 -- per-agent timeout + stall heartbeat, the
barrier-deadlock escape (``docs/audit-design-2026-07-13/B2-RFC-operational.md:377``,
wave item W1.5 at ``B3-migration-verification.md:150``) -- together with the executable
proof that B3:156 demands verbatim: *"H6 proven to break a synthetic barrier hang."*

KNOWN-BROKEN PRE-STATE, measured before this file existed: a scan of all 88 text files
under ``.github/`` and ``ci/`` found **zero** occurrences of ``wf-timeout``, ``wf_gate``,
``h6_extract``, ``h6_harness`` or ``test_h6_timeout`` (detector control on the same scan:
``pytest`` matched 40 files, an absent-needle matched 0).  Nothing ran the red-proof.  By
``quality.yml``'s own doctrine, *"a suite that is not named here is dead weight that
cannot catch a regression"* -- so the proof existed and proved nothing.

WHY THIS FILE IS NOT CIRCULAR.  A wiring assertion that lives inside the very step it
pins cannot fail when that step is deleted -- it simply stops running.  This file sits in
``ci/tests/``, which ``.github/workflows/skill-dual-write.yml`` collects as a whole
DIRECTORY (``python -m pytest ci/tests tools/d001-dual-write/tests -q``) on every
``pull_request``.  Deleting the ``quality.yml`` step therefore turns a *different*
workflow red.  ``ci/tests/test_ci_wiring.py`` separately pins that the sweep keeps
covering this directory, so the outer wiring cannot rot silently either.

USE-VS-MENTION.  The ``quality.yml`` step carries a long explanatory comment that names
``wf_gate.py`` in prose.  Every assertion below therefore matches against the set of
comment-stripped, whitespace-stripped ``run`` lines -- never against the raw document --
so a comment mentioning a command can never satisfy a test that the command is invoked.
``test_the_comment_stripper_actually_strips`` is the control for that stripper.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY = REPO_ROOT / ".github" / "workflows" / "quality.yml"
DUAL_WRITE = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

TOOL_DIR = REPO_ROOT / "tools" / "wf-timeout"
GATE = TOOL_DIR / "wf_gate.py"
EXTRACT = TOOL_DIR / "h6_extract.py"
HARNESS = TOOL_DIR / "h6_harness.mjs"
RED_PROOF = TOOL_DIR / "test_h6_timeout.py"
HELPER_TEMPLATE = (
    REPO_ROOT
    / "skills"
    / "workflow-authoring"
    / "templates"
    / "h6-timeout-heartbeat.md"
)

STEP_NAME = "gate-tests-coverage wf-timeout (H6 red-proof + workflow-lint invocation)"
WORKING_DIR = "working-directory: tools/wf-timeout"

# The exact command lines.  Order matters for the last two: --self-test is the
# both-states control that licenses the bare invocation's green.
COV_CMD = (
    "pytest --cov=wf_gate --cov=h6_extract --cov-branch "
    "--cov-report=term-missing --cov-fail-under=100"
)
SELF_TEST_CMD = "python wf_gate.py --self-test"
GATE_CMD = "python wf_gate.py"

# The suite hard-FAILS without node (test_h6_timeout.py resolves it with shutil.which
# and refuses to skip), so the node setup is part of the contract, not hygiene.
SETUP_NODE = (
    "- uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0"
)

DUAL_WRITE_SWEEP = "run: python -m pytest ci/tests tools/d001-dual-write/tests -q"


def quality_text() -> str:
    return QUALITY.read_text(encoding="utf-8")


def code_lines(text: str) -> list[str]:
    """Whitespace-stripped lines with full-line YAML comments removed.

    Deliberately NOT a YAML parse: the assertions below are about the literal
    command strings a runner will execute, and a parse would happily normalise a
    changed flag into an equivalent-looking node.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def quality_code_lines() -> list[str]:
    return code_lines(quality_text())


def test_the_comment_stripper_actually_strips() -> None:
    """Control for every use-vs-mention assertion in this file.

    If the stripper ever stops removing comments, the tests below would start
    passing on prose alone -- exactly the failure mode they exist to prevent.
    """
    sample = "  # python wf_gate.py --self-test\n  run: python wf_gate.py\n\n"
    lines = code_lines(sample)
    assert lines == ["run: python wf_gate.py"]
    assert SELF_TEST_CMD not in lines, "a commented-out command survived the stripper"


def test_the_artifacts_the_step_invokes_all_exist() -> None:
    """A step pointing at a moved file fails at run time, in CI, on someone else."""
    for path in (GATE, EXTRACT, HARNESS, RED_PROOF, HELPER_TEMPLATE):
        assert path.is_file(), f"missing {path.relative_to(REPO_ROOT).as_posix()}"


def test_quality_declares_the_wf_timeout_step_by_name() -> None:
    assert f"- name: {STEP_NAME}" in quality_code_lines()


def test_the_step_runs_the_h6_red_proof_at_full_coverage() -> None:
    """KNOWN-BROKEN pre-state: no workflow named tools/wf-timeout at all."""
    lines = quality_code_lines()
    assert WORKING_DIR in lines
    assert COV_CMD in lines, (
        "the H6 red-proof is not executed with the 100% threshold; a weakened "
        "or absent pytest line lets the barrier-hang control rot"
    )


def test_the_step_invokes_the_linter_over_real_source() -> None:
    """workflow_lint had 110 tests and a 100% lane, and linted nothing."""
    lines = quality_code_lines()
    assert GATE_CMD in lines, "wf_gate.py is never invoked; the linter is a no-op again"


def test_the_gate_self_test_runs_before_the_bare_invocation() -> None:
    """A green from a gate that has never gone red is indistinguishable from a no-op."""
    lines = quality_code_lines()
    assert SELF_TEST_CMD in lines
    assert lines.index(SELF_TEST_CMD) < lines.index(GATE_CMD), (
        "--self-test must run BEFORE the bare gate, so its red-on-bad proof is "
        "what licenses the bare invocation's green"
    )


def test_node_is_set_up_in_the_same_job_before_the_step() -> None:
    """test_h6_timeout.py FAILS without node rather than skipping, by design."""
    text = quality_text()
    assert "\n  test-python:\n" in text, "the host job was renamed or removed"
    job = text.split("\n  test-python:\n", 1)[1].split("\n  test-platform:", 1)[0]
    lines = code_lines(job)
    assert SETUP_NODE in lines, (
        "no SHA-pinned setup-node in the job that runs the proof"
    )
    assert lines.index(SETUP_NODE) < lines.index(f"- name: {STEP_NAME}")


def test_every_action_in_the_quality_workflow_is_sha_pinned() -> None:
    """Repo policy, restated here because this file adds an action to that workflow."""
    refs = [
        line.split("uses:", 1)[1].strip()
        for line in quality_code_lines()
        if "uses:" in line
    ]
    assert refs, "the workflow declares no actions -- the detector is broken"
    for ref in refs:
        action, _, sha = ref.partition("@")
        sha = sha.split()[0]
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), (
            f"{action} is not SHA-pinned: {ref}"
        )


def test_this_file_is_swept_by_the_independent_dual_write_workflow() -> None:
    """The anti-circularity guarantee, asserted rather than assumed.

    If this file were only reachable from the step it pins, deleting that step
    would delete its own alarm.
    """
    rel = Path(__file__).resolve().parent.relative_to(REPO_ROOT).as_posix()
    assert rel == "ci/tests"
    assert DUAL_WRITE.is_file()
    assert DUAL_WRITE_SWEEP in code_lines(DUAL_WRITE.read_text(encoding="utf-8"))
