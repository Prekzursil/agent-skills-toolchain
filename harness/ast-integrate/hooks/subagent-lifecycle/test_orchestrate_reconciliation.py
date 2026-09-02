"""Regression: /orchestrate must reconcile reviewer severities deterministically.

`agent-self/config/commands/orchestrate.md` demands ONE terminal recommendation
(`SHIP / NEEDS WORK / BLOCKED`) but its aggregation rules said only "pass each
output forward" and "aggregate results" / "combine outputs into single report".
For a change that logs an access token the two reviewers disagree by design --
`agents/code-reviewer.md` lists "Exposed secrets in logs" under Security
(CRITICAL); `agents/security-reviewer.md` rates "Logging passwords/secrets"
MEDIUM -- and the command reverses their order between the `feature` and
`security` chains while calling the LAST one "Final approval". The same evidence
therefore had no stable disposition: a CRITICAL secret exposure could be
downgraded purely by chain order.

This suite pins (a) that the collision premise is still real, so the rules are
not guarding a problem that no longer exists, (b) that the deterministic rules
are present and order-independent, and (c) the SCOPE boundary: `stop.py`
validates ONE subagent's output shape and is deliberately blind to its siblings,
so the arbitration belongs in the command and must not migrate into the hook.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ORCHESTRATE = REPO / "agent-self" / "config" / "commands" / "orchestrate.md"
# The repo-root twin. These two were byte-identical before this change; the
# deploy paths differ (bootstrap-codespace.sh copies commands/, bootstrap.ps1
# copies agent-self/config/), so a rule that lands in only one of them is live
# on one box and absent on the other.
ORCHESTRATE_ROOT = REPO / "commands" / "orchestrate.md"
CODE_REVIEWER = REPO / "agents" / "code-reviewer.md"
SECURITY_REVIEWER = REPO / "agents" / "security-reviewer.md"


def _load_stop():
    """Import `stop` the way its sibling suite does, and for the same reason.

    Six hook dirs ship a DIFFERENT `_common.py` under one flat `sys.modules`
    key (#214), so a plain `spec_from_file_location` on stop.py picks up
    whichever `_common` collection order happened to import first -- measured
    here as `ImportError: cannot import name 'emit_context' from '_common'
    (hooks/bg-registry/_common.py)` during the whole-tree `pytest hooks/` run,
    while the single-file run passed. Pin this directory at sys.path[0] and drop
    both cached names first.
    """
    if sys.path[:1] != [str(HERE)]:
        sys.path.insert(0, str(HERE))
    for name in ("stop", "_common"):
        sys.modules.pop(name, None)
    # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import -- fixed internal hook module, not untrusted input
    return importlib.import_module("stop")


@pytest.fixture(scope="module")
def doc() -> str:
    return ORCHESTRATE.read_text(encoding="utf-8")


# --- the premise is still live ------------------------------------------------


def test_the_two_reviewers_still_disagree_about_secrets_in_logs():
    """Detector control. If this ever goes green-by-agreement, the reconciliation
    rules are no longer guarding THIS collision and should be re-justified."""
    code = CODE_REVIEWER.read_text(encoding="utf-8")
    security = SECURITY_REVIEWER.read_text(encoding="utf-8")
    assert re.search(r"Exposed secrets in logs", code)
    row = re.search(r"\|\s*Logging passwords/secrets\s*\|\s*(\w+)\s*\|", security)
    assert row, "security-reviewer no longer rates 'Logging passwords/secrets'"
    assert row.group(1) == "MEDIUM"


def test_the_chains_still_run_the_reviewers_in_opposite_orders(doc):
    """The order-sensitivity the rules neutralise is still structurally present."""
    assert "planner -> tdd-guide -> code-reviewer -> security-reviewer" in doc
    assert "security-reviewer -> code-reviewer -> architect" in doc


# --- the rules ----------------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        "**R1 — Highest severity wins.**",
        "**R2 — Position confers no authority.**",
        "**R3 — Deterministic terminal mapping.**",
        "**R4 — Disagreements are reported, not silently resolved.**",
        "**R5 — A missing or unparseable reviewer result is not an approval.**",
    ],
)
def test_every_reconciliation_rule_is_present(doc, rule):
    assert rule in doc


def test_severity_order_is_stated_explicitly(doc):
    assert "CRITICAL > HIGH > MEDIUM > LOW" in doc


def test_critical_maps_to_blocked(doc):
    """The terminal mapping must be a table lookup, not prose judgement."""
    assert re.search(r"\|\s*CRITICAL\s*\|\s*`BLOCKED`\s*\|", doc)
    assert re.search(r"\|\s*HIGH\s*\|\s*`NEEDS WORK`\s*\|", doc)


def test_last_reviewer_is_explicitly_not_the_authority(doc):
    flat = " ".join(doc.split())  # the sentence wraps, so compare unwrapped
    assert "A later reviewer NEVER downgrades an earlier one" in flat
    assert (
        '"Final approval" in the chain descriptions means *last to run*, '
        "not *authoritative*" in flat
    )


def test_parallel_merge_points_at_the_same_rules(doc):
    """Parallel phases have no order at all, so an order-dependent merge there is
    undefined rather than merely unstable."""
    merge = doc.split("### Merge Results", 1)
    assert len(merge) == 2
    assert "R1-R5" in merge[1]


def test_final_report_recommendation_is_derived_from_the_table(doc):
    assert "derived from the R3 table, not from prose" in doc


def test_aggregate_step_no_longer_stands_alone(doc):
    """The bare 'Aggregate results into final report' line was the whole rule."""
    assert "4. **Aggregate results** into final report\n" not in doc


# --- scope boundary -----------------------------------------------------------


def test_stop_hook_validates_one_subagent_and_does_not_arbitrate():
    """stop.py is a per-subagent shape validator by design: it sees ONE agent_type
    and ONE transcript. Both reviewer outputs pass their own contract
    independently -- that is correct, not a bug, and the doc says so."""
    stop = _load_stop()
    contract = {"required_keywords": ["severity:", "recommendation:"]}
    assert stop.validate_contract(
        "severity: CRITICAL\nrecommendation: BLOCK", contract
    ) == (True, "")
    assert stop.validate_contract(
        "severity: MEDIUM\nrecommendation: PROCEED", contract
    ) == (True, "")


def test_the_scope_boundary_is_written_down(doc):
    assert "reconciliation is the ORCHESTRATOR" in doc
    assert "subagent-lifecycle" in doc


def test_both_orchestrate_copies_carry_the_same_rules():
    """Parity, not just presence. The two files were byte-identical at the
    commit this rule landed on, and each is installed by a different bootstrap
    script, so a reconciliation rule present in only one is a half-fix.
    """
    assert ORCHESTRATE_ROOT.read_text(encoding="utf-8") == ORCHESTRATE.read_text(
        encoding="utf-8"
    )
