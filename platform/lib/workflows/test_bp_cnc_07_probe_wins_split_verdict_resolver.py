"""FLAGSHIP end-to-end test: bp-cnc-07 Probe-Wins Split-Verdict Resolver.

Mechanism pinned here:

  1. A verdict with NO recorded probe is DISCARDED, not counted. An undeclared source is zero
     signals, not one - and an EMPTY fingerprint counts as no probe, which closes the measured
     hole where four empty strings trivially differed from any non-empty verifier.
  2. Verdicts whose probes share a mechanism collapse to ONE signal.
  3. MAJORITY IS NEVER THE TIEBREAK. The terminal gate asserts a negative about the resolution
     METHOD (resolved_by_majority == false), which no other blueprint in the range does.
  4. The tiebreak is a mechanically DIFFERENT probe; a probe matching an existing fingerprint is
     rejected as a re-run, never accepted as a new signal.
  5. The both-states control on the disputed detector must FIRE on broken and stay SILENT on
     good - a probe silent in both states measures nothing.
  6. UNRESOLVED is a legitimate terminal state when no independent instrument exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-cnc-07-probe-wins-split-verdict-resolver"


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True


# ------------------------------------------------------- mechanism 1: discard the unprobed


def test_an_unprobed_verdict_is_discarded_and_the_gate_blocks() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["unprobed-verdicts-discarded"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "verdicts_counted_without_probe == 0" in gate["expression"]
    assert doc["stages"][0]["id"] == "extract-probes"
    assert doc["stages"][1]["id"] == "discard-gate"


def test_an_empty_fingerprint_counts_as_no_probe() -> None:
    """This closes a MEASURED hole in a sibling gate.

    There, an absent source normalised to four empty strings, which any non-empty verifier
    trivially differs from - so the same-probe-rerun check could never fire and a CONFIRMED
    verdict with no declared source passed as corroborated. Here it is an enumerated class.
    """
    doc = C.load(BP)
    wu = C.find_stage(doc, "extract-probes")["work_unit"]
    assert "empty-probe-fingerprint" in wu["failure_classification"]
    assert any("empty probe_command must count as no probe" in t for t in wu["tests_required"])
    assert "empty_fingerprint_note" in doc["x_extensions"]
    assert "four empty strings" in doc["x_extensions"]["empty_fingerprint_note"]


def test_the_negative_worked_example_actually_contains_an_unprobed_verdict() -> None:
    neg = C.worked_examples(C.load(BP))[1]
    unprobed = [v for v in neg["params"]["verdicts"] if not v.get("probe_command")]
    assert len(unprobed) == 1, (
        "the negative arm must really carry an unprobed verdict, or it is not exercising the "
        "discard rule at all"
    )
    assert unprobed[0]["probe_shell"] == "none"


# ------------------------------------------------------- mechanism 2: collapse duplicates


def test_shared_mechanism_verdicts_collapse_to_one_signal() -> None:
    doc = C.load(BP)
    wu = C.find_stage(doc, "independence-matrix")["work_unit"]
    assert any("collapse to one signal" in t for t in wu["tests_required"])
    assert "CORRELATED by default (adverse inference)" in wu["evidence_requirement"], (
        "a pair with no named difference must be correlated by default; assuming independence "
        "is the adverse-inference failure"
    )


def test_the_positive_worked_example_contains_a_genuine_duplicate_pair() -> None:
    pos = C.worked_examples(C.load(BP))[0]
    prints = [
        (v["probe_tool"], v["probe_command"], v["probe_field"], v["probe_shell"])
        for v in pos["params"]["verdicts"]
    ]
    assert len(prints) == 6
    assert len(set(prints)) == 5, (
        "the measured historical case is 4-vs-2 where the 2 SHARE a fingerprint; if all six "
        "fingerprints were distinct the example would not exercise the collapse"
    )
    confirms = [v for v in pos["params"]["verdicts"] if v["verdict"] == "CONFIRMED"]
    assert len(confirms) == 2
    assert len({(v["probe_tool"], v["probe_shell"]) for v in confirms}) == 1, (
        "both CONFIRM verdicts must come from the same broken probe"
    )
    assert all(v["probe_shell"] == "git-bash" for v in confirms)


# ------------------------------------------------------ mechanism 3: no majority, ever


def test_the_terminal_gate_forbids_majority_resolution() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["never-resolved-by-majority"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "resolved_by_majority == false" in gate["expression"]
    assert "winning_probe_named == true" in gate["expression"]
    assert doc["stages"][-1]["id"] == "majority-gate"


def test_it_is_the_only_bp2_blueprint_that_gates_on_the_resolution_method() -> None:
    hits = []
    for bid in C.BP2_IDS:
        doc = C.load(bid)
        for name, g in (doc.get("gates") or {}).items():
            if isinstance(g, dict) and "resolved_by_majority" in str(g.get("expression", "")):
                hits.append((bid, name))
    assert [h[0] for h in hits] == [BP], hits


def test_the_walkthrough_states_the_verdict_is_vote_independent() -> None:
    pos = C.worked_examples(C.load(BP))[0]
    assert "would be identical if the vote had been 2 refute versus 4 confirm" in pos["walkthrough"], (
        "the load-bearing property is that the tally is never read; the worked example says so "
        "explicitly rather than merely happening to agree with the majority"
    )


def test_mutation_control_an_unparseable_gate_expression_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["gates"]["never-resolved-by-majority"].__setitem__(
            "expression", "resolved_by_majority =!= false"
        ),
        "semantic",
        what="write a gate expression the grammar cannot parse - a rule that cannot parse can "
        "never fire (DSL-SEM-007)",
    )


# ------------------------------------------- mechanism 4: the third probe must be different


def test_the_third_probe_is_conditional_and_must_differ_mechanically() -> None:
    doc = C.load(BP)
    stage = C.find_stage(doc, "third-probe")
    assert stage["when"] == "still_split == true AND allow_third_probe == true"
    wu = stage["work_unit"]
    assert "differs from BOTH sides by shell, data field or measurement" in wu["question_or_target"]
    assert "probe-is-a-rerun" in wu["failure_classification"]
    assert any("REJECTED as a re-run" in t for t in wu["tests_required"])


def test_conditional_stages_are_a_declared_part_of_the_structure() -> None:
    fp = C.fingerprint(C.load(BP))
    assert fp["conditional_stages"] == ["both-states-control", "control-gate", "third-probe"], (
        fp["conditional_stages"]
    )
    assert "loop" not in fp["stage_kinds"], (
        "the design card describes a single conditional third probe, not a loop; a loop here "
        "would license re-probing until a preferred answer appeared"
    )


# --------------------------------------------------- mechanism 5: the both-states control


def test_the_both_states_control_must_discriminate_the_two_states() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["control-fires-in-both-states"]
    assert gate["blocking"] is True
    assert "control_fired_on_broken_state == true" in gate["expression"]
    assert "control_silent_on_good_state == true" in gate["expression"]
    assert gate["on_fail"] == "escalate-to-human"
    wu = C.find_stage(doc, "both-states-control")["work_unit"]
    tests = " ".join(wu["tests_required"])
    assert "silent in both states must be declared BROKEN" in tests
    assert "firing in both states must be declared BROKEN" in tests
    assert wu["retry_policy"].startswith("no retry on a broken detector")


def test_mutation_control_dropping_one_arm_of_the_control_expression_is_visible() -> None:
    """A one-armed control is the classic silent detector, so prove the text is asserted."""
    doc = C.load(BP)
    doc["gates"]["control-fires-in-both-states"]["expression"] = (
        "control_fired_on_broken_state == true"
    )
    assert not any(C.all_layer_failures(doc).values()), (
        "the schema cannot know a control needs two arms - the requirement lives in the test above"
    )
    good = C.load(BP)
    assert "control_silent_on_good_state" in good["gates"]["control-fires-in-both-states"]["expression"]


# ------------------------------------------------------ mechanism 6: UNRESOLVED is legitimate


def test_unresolved_is_a_declared_terminal_state_not_a_failure_to_decide() -> None:
    doc = C.load(BP)
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["unresolved-no-independent-instrument"]["expression"] == "independent_signals == 0"
    assert rules["unresolved-no-independent-instrument"]["on_stop"] == "emit-partial"
    wu = C.find_stage(doc, "resolve")["work_unit"]
    assert "UNRESOLVED is also a SUCCESS terminal state" in wu["completion_sentinel"]
    assert doc["failure_policy"]["on_failure"] == "degrade-loudly"
    assert doc["retry_policy"]["strategy"] == "none", (
        "a second attempt at a resolution with the same evidence is the same resolution"
    )


def test_the_prompt_contract_dependency_is_declared_honestly() -> None:
    x = C.load(BP)["x_extensions"]
    assert "PROMPT CONTRACT" in x["dependency_note"]
    assert "which is the honest outcome, not a bug" in x["dependency_note"], (
        "if upstream prompts carry no probe field every verdict is discarded and the workflow "
        "returns nothing; that limitation is stated rather than hidden"
    )


# ------------------------------------------------------------------------ worked examples


def test_worked_examples_validate_and_cover_both_arms() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    pos, neg = C.worked_examples(doc)
    assert pos["arm"] == "positive" and "REFUTED" in pos["expected_terminal_state"]
    assert neg["arm"] == "negative-control" and "UNRESOLVED" in neg["expected_terminal_state"]


def test_mutation_control_a_worked_example_with_an_illegal_verdict_token_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["x_extensions"]["worked_examples"][0]["params"]["verdicts"][0].__setitem__(
            "verdict", "PROBABLY_TRUE"
        ),
        "worked_examples",
        what="use a verdict token outside the declared enum, proving the compiled param schema "
        "actually reaches nested array-item enums",
    )
