#!/usr/bin/env python3
"""The docs executable-claim gate must RUN on the event this repo actually uses.

WHAT WAS BROKEN
---------------
``ci/tests/test_docs_executable_claims.py`` shipped green, committed, and with
both-states controls -- and it executed on exactly ZERO of the commits that
shipped it. The only workflow that ran it was
``.github/workflows/skill-dual-write.yml``, which collects ``ci/tests`` as a
DIRECTORY (``python -m pytest ci/tests tools/d001-dual-write/tests -q``) and
whose ``on:`` block has ONE key, ``pull_request``, with no ``push:``. Every
commit in this program lands by pushing ``main`` directly, so the gate's silence
meant "never invoked", not "the docs agree with the tree".

``quality.yml`` is the workflow carrying ``push: branches: [main]``. It has no
tree-wide ``ci/tests`` step -- by its own doctrine at ``quality.yml:685``, *"a
suite that is not named here is dead weight that cannot catch a regression"* --
so the fix is a NAMED step there, and this file is what stops that step from
being deleted, renamed, weakened, moved into another job, or pushed below the
``setup python 3.12`` pivot (which repoints the default ``python`` and would
make a bare ``python -m pytest`` run on the wrong interpreter).

WHY THIS FILE IS NOT CIRCULAR
-----------------------------
A wiring assertion that lives only inside the step it pins cannot fail when that
step is deleted; it simply stops running. This file sits in ``ci/tests/``, which
``skill-dual-write.yml`` collects as a whole DIRECTORY on every
``pull_request``, so deleting the ``quality.yml`` step turns a DIFFERENT
workflow red. ``ci/tests/test_ci_wiring.py`` separately pins that the sweep
keeps covering this directory. Same construction, and the same reasoning, as
``ci/tests/test_wf_timeout_ci_wiring.py``.

RESIDUAL, disclosed inline and NOT closed here: a direct push to ``main`` that
deletes BOTH the ``quality.yml`` step and this file is caught by nothing,
because ``skill-dual-write.yml`` has no ``push:`` trigger either. That is one
strictly smaller hole than the one this file closes, and shrinking it further
means changing a shared workflow's blast radius. Settling experiment (owner
action): add ``push: branches: [main]`` to ``skill-dual-write.yml`` and confirm
its D-001 diff gate still behaves when ``--base origin/main --head HEAD`` spans
an empty range on a push event.

USE-VS-MENTION
--------------
The ``quality.yml`` step carries a long explanatory comment that names the very
commands it invokes. Every assertion below therefore matches against
comment-stripped lines, never the raw document, so prose can never satisfy a
test that a command is *invoked*. ``test_the_comment_stripper_actually_strips``
is the control for that stripper.

THE CONTROLS ARE NOT SYNTHETIC WHERE THEY DO NOT HAVE TO BE
-----------------------------------------------------------
``test_control_fires_on_a_workflow_with_no_push_trigger`` feeds the predicate
the REAL committed bytes of ``skill-dual-write.yml`` -- the actual workflow
whose missing ``push:`` is the defect -- so the trigger arm is proven to
discriminate between two real files rather than between a file and a mutation
of itself.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY = REPO_ROOT / ".github" / "workflows" / "quality.yml"
DUAL_WRITE = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
GATE_SUITE = REPO_ROOT / "ci" / "tests" / "test_docs_executable_claims.py"

EXPECTED_JOB = "test-python"
STEP_NAME = "gate-tests-coverage docs executable claims (README + roadmap)"
STEP_LINE = f"- name: {STEP_NAME}"

GATE_CMD = (
    "python -m pytest ci/tests/test_docs_executable_claims.py -q -p no:cacheprovider"
)
WIRING_CMD = (
    "python -m pytest ci/tests/test_docs_gate_ci_wiring.py -q -p no:cacheprovider"
)

# quality.yml:1444 -- "KEEP THE py3.12 STEPS LAST in this job -- this action
# repoints the default `python` to 3.12, so no 3.11 step may follow them."
PY312_PIVOT_LINE = "- name: setup python 3.12 for the py312-only trees"

# This file is only reachable at all because skill-dual-write.yml sweeps the
# directory it lives in. Pinning the sweep here keeps the anti-circularity
# argument in the module docstring true rather than merely asserted.
DUAL_WRITE_SWEEP = "run: python -m pytest ci/tests tools/d001-dual-write/tests -q"


# --------------------------------------------------------------------------
# text helpers (deliberately NOT a YAML parse: the assertions are about the
# literal command strings a runner executes, and a parse would happily
# normalise a changed flag into an equivalent-looking node)
# --------------------------------------------------------------------------
def strip_comments(text: str) -> str:
    """Drop full-line YAML comments; keep indentation and everything else."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def code_lines(text: str) -> list[str]:
    return [line.strip() for line in strip_comments(text).splitlines() if line.strip()]


def _on_block(stripped: str) -> str:
    """The body of the top-level ``on:`` key, comments already removed."""
    lines = stripped.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == "on:"), None)
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line[:1].isspace():
            break
        body.append(line)
    return "\n".join(body)


def _event_keys(stripped: str) -> set[str]:
    return {
        m.group(1)
        for line in _on_block(stripped).splitlines()
        if (m := re.fullmatch(r"  ([a-z_]+):\s*", line))
    }


def _event_body(stripped: str, event: str) -> str:
    """The sub-block under one event key inside ``on:``."""
    lines = _on_block(stripped).splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.rstrip() == f"  {event}:"), None
    )
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("    "):
            break
        body.append(line)
    return "\n".join(body)


def _job_of(stripped: str, needle: str) -> str | None:
    """Which ``jobs:`` entry contains the first line holding ``needle``."""
    job: str | None = None
    in_jobs = False
    for line in stripped.splitlines():
        if line.rstrip() == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if m := re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line):
            job = m.group(1)
        if needle in line:
            return job
    return None


# --------------------------------------------------------------------------
# the predicate -- pure, so a MUTATED or a DIFFERENT workflow can be fed to it
# --------------------------------------------------------------------------
def wiring_violations(quality_text: str) -> list[str]:
    """Every way the docs gate could be committed yet not actually execute."""
    bad: list[str] = []
    stripped = strip_comments(quality_text)
    lines = code_lines(quality_text)

    if STEP_LINE not in lines:
        bad.append(f"step-missing: no step named {STEP_NAME!r}")
    else:
        job = _job_of(stripped, STEP_LINE)
        if job != EXPECTED_JOB:
            bad.append(f"step-in-wrong-job: step sits in {job!r}, not {EXPECTED_JOB!r}")
        if PY312_PIVOT_LINE in lines and lines.index(STEP_LINE) > lines.index(
            PY312_PIVOT_LINE
        ):
            bad.append(
                "after-py312-pivot: the step follows the setup-python 3.12 action, "
                "so its bare `python` is the 3.12 interpreter, not the job's 3.11"
            )

    for label, cmd in (("gate", GATE_CMD), ("wiring", WIRING_CMD)):
        if cmd not in lines:
            bad.append(f"{label}-command-missing: no run line invoking {cmd!r}")

    events = _event_keys(stripped)
    if "push" not in events:
        bad.append(
            "not-push-triggered: this workflow has no `push:` event, so a suite "
            f"named in it never runs on a direct push (events: {sorted(events)})"
        )
    elif "main" not in _event_body(stripped, "push"):
        bad.append("push-not-on-main: the `push:` event does not target `main`")

    return bad


# --------------------------------------------------------------------------
# fixtures-free readers (module-level state would hide a mid-run edit)
# --------------------------------------------------------------------------
def quality_text() -> str:
    return QUALITY.read_text(encoding="utf-8")


def dual_write_text() -> str:
    return DUAL_WRITE.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# detector controls FIRST -- a green below means nothing until these pass
# --------------------------------------------------------------------------
def test_the_comment_stripper_actually_strips() -> None:
    """Control for every use-vs-mention assertion in this file."""
    sample = f"  # {GATE_CMD}\n  run: {GATE_CMD}\n\n"
    lines = code_lines(sample)
    assert lines == [f"run: {GATE_CMD}"]
    assert GATE_CMD not in lines, "a commented-out command survived the stripper"


def test_the_job_and_event_readers_agree_with_the_real_workflow() -> None:
    """Shape control: the readers must find the collections they claim to read.

    The manifest-DICT trap -- four probes once agreed on "3 and 3" because they
    all counted the wrong collection. A reader that silently returns nothing
    makes every downstream check inert while looking clean, so assert the
    collections are non-trivial before trusting any verdict built on them.
    """
    stripped = strip_comments(quality_text())
    assert _event_keys(stripped), "no `on:` event keys parsed out of quality.yml"
    assert _job_of(stripped, "runs-on: ubuntu-latest") is not None, (
        "the job reader found no job for a line that appears in every job"
    )
    assert _job_of(stripped, "a-string-that-is-not-in-quality-yml") is None, (
        "the job reader returns a job for an absent needle, so a match proves nothing"
    )


def test_the_gate_suite_the_step_invokes_exists() -> None:
    """A step pointing at a moved file fails at run time, in CI, on someone else."""
    assert GATE_SUITE.is_file(), f"missing {GATE_SUITE}"


# --------------------------------------------------------------------------
# the wiring assertion
# --------------------------------------------------------------------------
def test_quality_actually_runs_the_docs_executable_claim_gate() -> None:
    violations = wiring_violations(quality_text())
    assert violations == [], (
        "the docs executable-claim gate is committed but not reachable on a "
        "push to main:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_this_file_is_itself_reachable() -> None:
    """The anti-circularity premise, asserted rather than assumed.

    This file can only fail a build because skill-dual-write.yml sweeps the
    whole directory. If that sweep goes away, deleting the quality.yml step
    becomes undetectable and the docstring above becomes a false claim.
    """
    assert DUAL_WRITE_SWEEP in code_lines(dual_write_text()), (
        "skill-dual-write.yml no longer sweeps ci/tests as a directory, so this "
        "wiring test cannot fail when the quality.yml step is deleted"
    )


# --------------------------------------------------------------------------
# both-states controls: each arm must FIRE on a known-broken input
# --------------------------------------------------------------------------
def _without_lines(text: str, *drop: str) -> str:
    kept = [ln for ln in text.splitlines() if ln.strip() not in drop]
    assert len(kept) < len(text.splitlines()), (
        f"control precondition failed: none of {drop!r} is in the document"
    )
    return "\n".join(kept)


def test_control_fires_when_the_step_is_deleted() -> None:
    """The exact regression this file exists to catch, on real bytes."""
    broken = _without_lines(quality_text(), STEP_LINE, GATE_CMD, WIRING_CMD, "run: |")
    found = wiring_violations(broken)
    assert any(v.startswith("step-missing") for v in found), found
    assert any(v.startswith("gate-command-missing") for v in found), found


def test_control_fires_when_only_the_command_is_weakened() -> None:
    """Step name intact, invocation silently retargeted -- the subtler shape."""
    broken = quality_text().replace(
        GATE_CMD, "python -m pytest ci/tests/test_docs_executable_claims.py --co -q", 1
    )
    found = wiring_violations(broken)
    assert any(v.startswith("gate-command-missing") for v in found), found
    assert not any(v.startswith("step-missing") for v in found), (
        "control: the step name should still be present in this mutation"
    )


def test_control_fires_when_the_step_moves_below_the_py312_pivot() -> None:
    """The trap this lane nearly walked into, made permanent."""
    text = quality_text()
    assert PY312_PIVOT_LINE in code_lines(text), (
        "control precondition: the py3.12 pivot step is gone from quality.yml, "
        "so this arm can no longer discriminate. Re-derive the ordering "
        "constraint before deleting this control."
    )
    assert wiring_violations(text) == [], "precondition: the real file is clean"

    step_block = f"      {STEP_LINE}\n        run: |\n          {GATE_CMD}\n          {WIRING_CMD}\n"
    moved = text.replace(step_block, "", 1)
    assert moved != text, "control precondition: the step block was not found verbatim"
    moved = moved.rstrip("\n") + "\n" + step_block

    found = wiring_violations(moved)
    assert any(v.startswith("after-py312-pivot") for v in found), found


def test_control_fires_on_a_workflow_with_no_push_trigger() -> None:
    """Two-hypothesis control on two REAL files, not a self-mutation.

    H1 (the arm reads the trigger): quality.yml -- which has `push:` -- stays
    silent on that arm, while skill-dual-write.yml -- which does not -- fires.
    H2 (the arm merely notices that a workflow was parsed): both look the same.
    Only H1 produces the asymmetry below, and skill-dual-write.yml's missing
    `push:` IS the defect that made the docs gate unreachable.
    """
    dual = dual_write_text()
    assert "push" not in _event_keys(strip_comments(dual)), (
        "precondition: skill-dual-write.yml gained a `push:` trigger, so it is "
        "no longer a known-broken example. Re-point this control."
    )
    found = wiring_violations(dual)
    assert any(v.startswith("not-push-triggered") for v in found), found
    assert not any(
        v.startswith("not-push-triggered") for v in wiring_violations(quality_text())
    ), "control: the arm fired on quality.yml, which does have a push trigger"


def test_control_fires_when_push_stops_targeting_main() -> None:
    broken = quality_text().replace("branches: [main]", "branches: [release]", 1)
    found = wiring_violations(broken)
    assert any(v.startswith("push-not-on-main") for v in found), found
