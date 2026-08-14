#!/usr/bin/env python3
"""The rule-audit lane's ten gates must stay REACHABLE. Nothing pinned that.

WHAT IS BROKEN
--------------
``.github/workflows/rule-audit.yml`` is the ONLY thing in this repository that
invokes ``docs/rule-audit/ci_gate.py``, and through it the ten gates four audit
rounds, three adversarial rounds and three build rounds produced. Measured
before this file was written, with the search controlled in BOTH directions:

* ``grep -rn "rule-audit\\.yml|rule-audit/ci_gate|docs/rule-audit" ci/ .github/``
  returns exactly ONE hit outside the workflow itself -- ``hook-audit.yml:20``,
  which merely NAMES it in a prose comment listing sibling workflows. A mention
  is not a guard.
* POSITIVE CONTROL (the same search shape can find a real guard): the identical
  search for ``wf-timeout`` returns ``ci/tests/test_wf_timeout_ci_wiring.py``
  plus ``quality.yml``. So the silence above is real, not a broken matcher.
* NEGATIVE CONTROL: the same search for a bogus token returns nothing.

So deleting, renaming, or quietly weakening that one file removes every
rule-audit gate from CI and NOTHING goes red. That is precisely the defect the
lane was created to fix -- ``ci_gate.py``'s own docstring opens with *"A gate
nobody invokes is indistinguishable from one that does not exist"* -- and it
would recur silently, which is how the repo-vs-live rule drift grew from 28
files to 29 while 167 rules tests stayed green.

WHY THIS FILE IS NOT CIRCULAR
-----------------------------
A wiring assertion that lives inside the workflow it pins cannot fail when that
workflow is deleted; it simply stops running. This file lives in ``ci/tests/``,
which is reached two independent ways:

* ``skill-dual-write.yml`` collects ``ci/tests`` as a whole DIRECTORY on every
  ``pull_request`` (pinned below by ``test_this_file_is_itself_reachable``);
* ``quality.yml`` -- the workflow carrying ``push: branches: [main]`` -- names
  this suite in an explicit step, because ``quality.yml:685`` records that
  ``ci/tests/`` has NO tree-wide step and an unnamed suite there never runs.

Deleting ``rule-audit.yml`` therefore turns a DIFFERENT workflow red. Same
construction, and the same reasoning, as ``ci/tests/test_docs_gate_ci_wiring.py``
and ``ci/tests/test_wf_timeout_ci_wiring.py``.

RESIDUAL, disclosed inline and NOT closed here: a single direct push to ``main``
that deletes ``rule-audit.yml`` AND the ``quality.yml`` step AND this file is
caught by nothing, because ``skill-dual-write.yml`` has no ``push:`` trigger.
That is one strictly smaller hole than the one this file closes. Settling
experiment (owner action, shared blast radius, deliberately not taken by an
agent): add ``push: branches: [main]`` to ``skill-dual-write.yml`` and confirm
its D-001 diff gate still behaves when ``--base origin/main --head HEAD`` spans
an empty range on a push event.

USE-VS-MENTION
--------------
``rule-audit.yml`` opens with a ~70-line comment block that NAMES every gate
filename and names ``ci_gate.py`` itself. A raw-text search would therefore be
satisfied by prose alone. Every assertion below matches comment-stripped lines
by EXACT equality, never substring and never the raw document.
``test_a_commented_out_command_does_not_satisfy_the_gate`` is the control, and
it is run on the REAL file's bytes rather than a synthetic sample.

THE PREFIX TRAP THIS FILE DELIBERATELY AVOIDS
---------------------------------------------
``run: python docs/rule-audit/ci_gate.py`` is a strict PREFIX of
``run: python docs/rule-audit/ci_gate.py --self-test``, and the self-test line
comes FIRST in the file. A substring match -- or a ``str.replace(..., 1)`` in a
control -- silently hits the wrong line and the control then proves nothing.
Every match and every mutation here is line-wise and exact, and every mutation
helper asserts it actually changed something.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

RULE_AUDIT_WF = WORKFLOWS / "rule-audit.yml"
QUALITY = WORKFLOWS / "quality.yml"
DUAL_WRITE = WORKFLOWS / "skill-dual-write.yml"

GATE_DIR = REPO_ROOT / "docs" / "rule-audit"
GATE_SCRIPT = GATE_DIR / "ci_gate.py"

# Exact, comment-stripped lines. Equality, not substring -- see the prefix trap above.
GATE_CMD = "run: python docs/rule-audit/ci_gate.py"
SELFTEST_CMD = "run: python docs/rule-audit/ci_gate.py --self-test"

# The workflow's two pip dependencies, each load-bearing for a DIFFERENT gate:
#
#   tiktoken -- measured by BUILD-R1 under WSL Ubuntu 24.04 with HOME redirected to an empty
#     dir: without it, rule_audit.py --self-test fails 2/19 controls (Counter degrades to
#     "ESTIMATE chars/4") and r2_control_count_gate + r2_failclosed_mutation cascade red.
#   pytest   -- r6_wiring_redproof.py drives THIS suite as a subprocess; with no pytest on
#     the runner it cannot run at all, and the red-proof for the reachability guard would
#     silently stop being executed.
#
# Checked as "a `run: pip install` line that PINS this package", not as one exact string:
# the exact-equality discipline elsewhere in this file exists to dodge the prefix trap
# between the two ci_gate.py invocations, and it buys nothing here -- while an exact match
# would turn adding a third package into a spurious red.
REQUIRED_PINS = ("tiktoken==", "pytest==")

# The step in quality.yml that puts THIS suite on the push path.
THIS_SUITE_CMD = "python -m pytest ci/tests/test_rule_audit_ci_wiring.py -q"

# The premise of the anti-circularity argument above, asserted rather than assumed.
DUAL_WRITE_SWEEP = "run: python -m pytest ci/tests tools/d001-dual-write/tests -q"


# --------------------------------------------------------------------------
# text helpers -- deliberately NOT a YAML parse. The assertions are about the
# literal command strings a runner executes; a parse would happily normalise a
# changed flag into an equivalent-looking node. Duplicated from the sibling
# wiring suites ON PURPOSE: importing one lane's gate into another couples them,
# and a shared helper that regressed would take both guards down together.
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


# --------------------------------------------------------------------------
# the CI_PLAN reader -- AST, not import
# --------------------------------------------------------------------------
def ci_plan_scripts(gate_source: str) -> list[str]:
    """The script filename from every ``CI_PLAN`` entry, read statically.

    AST rather than ``import ci_gate`` on purpose: importing it executes
    ``import rule_audit``, which pulls in tiktoken and walks rule trees. This
    suite is stdlib-only and must stay that way -- ``quality.yml`` runs it with
    no install step.
    """
    names: list[str] = []
    for node in ast.parse(gate_source).body:
        target = None
        if isinstance(node, ast.AnnAssign):
            target = getattr(node.target, "id", None)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = getattr(node.targets[0], "id", None)
        if target != "CI_PLAN" or not isinstance(node.value, ast.List):
            continue
        for entry in node.value.elts:
            if not isinstance(entry, ast.Tuple) or len(entry.elts) < 2:
                continue
            argv = entry.elts[1]
            if isinstance(argv, ast.List) and argv.elts:
                first = argv.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.append(first.value)
    return names


# --------------------------------------------------------------------------
# the predicate -- pure, so a MUTATED or a DIFFERENT workflow can be fed to it
# --------------------------------------------------------------------------
def wiring_violations(rule_audit_text: str, quality_text: str) -> list[str]:
    """Every way the rule-audit gates could be committed yet never execute."""
    bad: list[str] = []
    stripped = strip_comments(rule_audit_text)
    lines = code_lines(rule_audit_text)

    # The headline regression, named explicitly rather than left to surface as a
    # FileNotFoundError traceback. A guard should say WHAT is gone, not just die.
    if not rule_audit_text.strip():
        bad.append(
            "workflow-missing: .github/workflows/rule-audit.yml is absent or empty, so "
            "every rule-audit gate has left CI entirely"
        )

    for label, cmd in (
        ("gate", GATE_CMD),
        ("selftest", SELFTEST_CMD),
    ):
        if cmd not in lines:
            bad.append(f"{label}-command-missing: no run line invoking {cmd!r}")

    installs = [ln for ln in lines if ln.startswith("run: pip install")]
    for pin in REQUIRED_PINS:
        if not any(pin in ln for ln in installs):
            bad.append(
                f"dependency-unpinned: no `run: pip install` line pins {pin!r}, so a gate "
                "that needs it cannot run on a runner"
            )

    events = _event_keys(stripped)
    if "push" not in events:
        bad.append(
            "not-push-triggered: rule-audit.yml has no `push:` event, so the gates "
            f"never run on a direct push to main (events: {sorted(events)})"
        )
    elif "main" not in _event_body(stripped, "push"):
        bad.append("push-not-on-main: the `push:` event does not target `main`")

    if THIS_SUITE_CMD not in code_lines(quality_text):
        bad.append(
            "wiring-suite-not-named: quality.yml does not invoke "
            f"{THIS_SUITE_CMD!r}, so this guard itself never runs on a push to main "
            "and deleting rule-audit.yml becomes undetectable on the path this "
            "program actually uses"
        )

    return bad


# --------------------------------------------------------------------------
# fixtures-free readers (module-level state would hide a mid-run edit)
# --------------------------------------------------------------------------
def rule_audit_text() -> str:
    # Absent -> "" rather than an exception, so the predicate reports a NAMED
    # `workflow-missing` violation instead of every test dying on a traceback.
    if not RULE_AUDIT_WF.is_file():
        return ""
    return RULE_AUDIT_WF.read_text(encoding="utf-8")


def quality_text() -> str:
    return QUALITY.read_text(encoding="utf-8")


def dual_write_text() -> str:
    return DUAL_WRITE.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# mutation helpers -- each asserts it actually changed something, so a control
# can never quietly become a no-op that "passes"
# --------------------------------------------------------------------------
def _drop_exact_lines(text: str, *drop: str) -> str:
    kept = [ln for ln in text.splitlines() if ln.strip() not in drop]
    assert len(kept) < len(text.splitlines()), (
        f"control precondition failed: none of {drop!r} is in the document"
    )
    return "\n".join(kept)


def _comment_out_exact_lines(text: str, *targets: str) -> str:
    out, hits = [], 0
    for ln in text.splitlines():
        if ln.strip() in targets:
            hits += 1
            out.append(f"{ln[: len(ln) - len(ln.lstrip())]}# {ln.strip()}")
        else:
            out.append(ln)
    assert hits == len(targets), (
        f"control precondition failed: matched {hits} of {len(targets)} target lines"
    )
    return "\n".join(out)


# --------------------------------------------------------------------------
# detector controls FIRST -- a green below means nothing until these pass
# --------------------------------------------------------------------------
def test_the_comment_stripper_actually_strips() -> None:
    """Control for every use-vs-mention assertion in this file."""
    sample = f"  # {GATE_CMD}\n  {GATE_CMD}\n\n"
    lines = code_lines(sample)
    assert lines == [GATE_CMD], lines


def test_the_event_reader_agrees_with_the_real_workflows() -> None:
    """Shape control: the reader must find the collection it claims to read.

    The manifest-DICT trap -- four probes once agreed on "3 and 3" because they
    all counted the wrong collection one level up. A reader that silently
    returns an empty set makes every downstream check inert while looking
    clean, so assert it is non-trivial and that it can also say NO.
    """
    events = _event_keys(strip_comments(rule_audit_text()))
    assert events, "no `on:` event keys parsed out of rule-audit.yml"
    assert "push" in events, events
    assert _event_keys("jobs:\n  x:\n") == set(), (
        "the event reader invents keys for a document with no `on:` block"
    )


def test_the_ci_plan_reader_is_not_inert() -> None:
    """Fail closed on an empty read: 'no gates' and 'reader broke' look identical."""
    scripts = ci_plan_scripts(GATE_SCRIPT.read_text(encoding="utf-8"))
    assert len(scripts) >= 8, (
        f"CI_PLAN reader found only {len(scripts)} gates ({scripts}); the plan has "
        "never been that small, so the reader -- not the plan -- is what changed"
    )
    assert ci_plan_scripts("OTHER = [1, 2]\n") == [], (
        "the CI_PLAN reader returns entries for a source with no CI_PLAN, so a "
        "non-empty result proves nothing"
    )


def test_the_gate_the_workflow_invokes_exists() -> None:
    """A workflow pointing at a moved file fails at run time, in CI, on someone else."""
    assert GATE_SCRIPT.is_file(), f"missing {GATE_SCRIPT}"


def test_every_gate_the_plan_invokes_exists() -> None:
    """CI_PLAN naming a deleted script is a red runner, not a caught regression."""
    missing = [
        name
        for name in ci_plan_scripts(GATE_SCRIPT.read_text(encoding="utf-8"))
        if not (GATE_DIR / name).is_file()
    ]
    assert missing == [], f"CI_PLAN names scripts that do not exist: {missing}"


# --------------------------------------------------------------------------
# the wiring assertion
# --------------------------------------------------------------------------
def test_the_rule_audit_gates_are_actually_reachable() -> None:
    violations = wiring_violations(rule_audit_text(), quality_text())
    assert violations == [], (
        "the rule-audit lane's gates are committed but not reachable:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_this_file_is_itself_reachable() -> None:
    """The anti-circularity premise, asserted rather than assumed.

    This file can fail a build on a pull request only because
    skill-dual-write.yml sweeps the whole directory. If that sweep goes away,
    the docstring above becomes a false claim.
    """
    assert DUAL_WRITE_SWEEP in code_lines(dual_write_text()), (
        "skill-dual-write.yml no longer sweeps ci/tests as a directory, so this "
        "wiring test loses one of its two independent paths to running"
    )


# --------------------------------------------------------------------------
# both-states controls: each arm must FIRE on a known-broken input
# --------------------------------------------------------------------------
def test_the_workflow_file_exists() -> None:
    """The bluntest form of the claim, stated on its own so a failure is legible."""
    assert RULE_AUDIT_WF.is_file(), (
        f"missing {RULE_AUDIT_WF} -- the only file in this repo that invokes the "
        "rule-audit lane's ten gates"
    )


def test_control_fires_when_the_whole_workflow_is_deleted() -> None:
    """The headline regression: rule-audit.yml removed, all ten gates gone."""
    found = wiring_violations("", quality_text())
    for arm in (
        "workflow-missing",
        "gate-command-missing",
        "selftest-command-missing",
        "not-push-triggered",
    ):
        assert any(v.startswith(arm) for v in found), (arm, found)


def test_control_fires_when_only_the_gate_step_is_deleted() -> None:
    """Subtler: the workflow survives, the blocking gate quietly does not."""
    broken = _drop_exact_lines(rule_audit_text(), GATE_CMD)
    found = wiring_violations(broken, quality_text())
    assert any(v.startswith("gate-command-missing") for v in found), found
    assert not any(v.startswith("selftest-command-missing") for v in found), (
        "control: the self-test line must survive this mutation -- if it did not, "
        "the prefix trap struck and this control is measuring the wrong line"
    )


def test_control_fires_when_the_self_test_is_dropped() -> None:
    """The gate's own both-states control is what stops it becoming a no-op."""
    broken = _drop_exact_lines(rule_audit_text(), SELFTEST_CMD)
    found = wiring_violations(broken, quality_text())
    assert any(v.startswith("selftest-command-missing") for v in found), found
    assert not any(v.startswith("gate-command-missing") for v in found), (
        "control: the bare gate line must survive this mutation (prefix trap)"
    )


def test_a_commented_out_command_does_not_satisfy_the_gate() -> None:
    """USE-VS-MENTION, on the real file's bytes.

    rule-audit.yml's own header comment already names ci_gate.py in prose. This
    proves prose cannot stand in for an invocation: comment out the two real run
    lines and both arms must fire even though the strings remain in the document.
    """
    broken = _comment_out_exact_lines(rule_audit_text(), GATE_CMD, SELFTEST_CMD)
    assert "ci_gate.py" in broken, (
        "precondition: the text should still mention the gate"
    )
    found = wiring_violations(broken, quality_text())
    assert any(v.startswith("gate-command-missing") for v in found), found
    assert any(v.startswith("selftest-command-missing") for v in found), found


def test_control_fires_on_a_workflow_with_no_push_trigger() -> None:
    """Two-hypothesis control on two REAL files, not a self-mutation.

    H1 (the arm reads the trigger): rule-audit.yml -- which has ``push:`` --
    stays silent on that arm while skill-dual-write.yml -- which does not --
    fires. H2 (the arm merely notices a document was parsed): both look the
    same. Only H1 produces the asymmetry below, and skill-dual-write.yml's
    missing ``push:`` is a real, load-bearing property of this repo.
    """
    dual = dual_write_text()
    assert "push" not in _event_keys(strip_comments(dual)), (
        "precondition: skill-dual-write.yml gained a `push:` trigger, so it is no "
        "longer a known-broken example. Re-point this control."
    )
    assert any(
        v.startswith("not-push-triggered")
        for v in wiring_violations(dual, quality_text())
    )
    assert not any(
        v.startswith("not-push-triggered")
        for v in wiring_violations(rule_audit_text(), quality_text())
    ), "control: the arm fired on rule-audit.yml, which does have a push trigger"


def test_control_fires_when_push_stops_targeting_main() -> None:
    broken = rule_audit_text().replace("branches: [main]", "branches: [release]", 1)
    assert broken != rule_audit_text(), "control precondition: no branches line found"
    found = wiring_violations(broken, quality_text())
    assert any(v.startswith("push-not-on-main") for v in found), found


def test_control_fires_when_quality_stops_naming_this_suite() -> None:
    """If quality.yml drops this suite, the guard leaves the push path."""
    broken_quality = _drop_exact_lines(quality_text(), THIS_SUITE_CMD)
    found = wiring_violations(rule_audit_text(), broken_quality)
    assert any(v.startswith("wiring-suite-not-named") for v in found), found


def test_control_fires_when_a_pinned_dependency_is_dropped() -> None:
    """Both pins, one at a time, on the real file's bytes."""
    text = rule_audit_text()
    installs = [
        ln for ln in text.splitlines() if ln.strip().startswith("run: pip install")
    ]
    assert installs, (
        "control precondition: rule-audit.yml has no `run: pip install` line"
    )

    for pin in REQUIRED_PINS:
        broken = "\n".join(ln for ln in text.splitlines() if pin not in ln)
        assert broken != text, f"control precondition: no line carries {pin!r}"
        found = wiring_violations(broken, quality_text())
        assert any(v.startswith("dependency-unpinned") and pin in v for v in found), (
            pin,
            found,
        )
