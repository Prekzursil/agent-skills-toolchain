"""FLAGSHIP end-to-end test: bp-cnc-03 Semantic-Entropy Escalation Council.

Mechanism pinned here:

  1. The threshold is PRE-COMMITTED and hashed before any answer is read. A threshold chosen
     after seeing the answers is not a threshold.
  2. Fewer than three answers, or fewer than two vendors, is a REFUSAL (on_fail == "fail"),
     not a degraded run - entropy over correlated or too-few points is meaningless.
  3. The route is DETERMINISTIC: replay.deterministic is true with a seed, a journal, a record
     set and hash-equal verification, and retry strategy is "none".
  4. ONE decision per invocation: NO loop and NO fan-out anywhere in the document.
  5. A correlated-blind-spot warning fires when agreement comes from same-family producers,
     because low entropy means agreement, NOT truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-cnc-03-semantic-entropy-escalation"


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True


# ------------------------------------------------------- mechanism 1: threshold precommit


def test_the_threshold_is_precommitted_and_the_gate_blocks() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["threshold-precommitted"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "threshold_recorded_before_answers_read == true" in gate["expression"]

    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("precommit-threshold") < stages.index("collect"), (
        "the commit stage must precede the collect stage in the graph, or the precommit claim "
        "is only a label"
    )
    assert doc["stages"][0]["id"] == "precommit-threshold"
    wu = C.find_stage(doc, "precommit-threshold")["work_unit"]
    assert "answers_read == 0" in wu["evidence_requirement"]
    assert wu["retry_policy"].startswith("no retry")


def test_mutation_control_reordering_the_precommit_after_collect_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "precommit-threshold").__setitem__(
            "depends_on", ["collect"]
        ),
        "semantic",
        what="make the threshold commit depend on the collect stage, creating a cycle through "
        "collect -> threshold-gate -> precommit-threshold (DSL-SEM-003)",
    )


# ---------------------------------------------------------------- mechanism 2: the refusal


def test_fewer_than_three_independent_answers_is_a_refusal_not_a_degradation() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["enough-independent-answers"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail", (
        "the design card says the gate REFUSES rather than computing a meaningless entropy; "
        "any on_fail other than fail turns the refusal into a degraded pass"
    )
    assert "answers_supplied >= 3" in gate["expression"]
    assert "distinct_vendors >= 2" in gate["expression"]
    assert doc["params"]["model_answers"]["min_items"] == 3
    assert doc["failure_policy"]["on_failure"] == "fail-fast"


def test_mutation_control_lowering_the_minimum_answer_count_is_caught() -> None:
    """The negative worked example supplies three answers; a min_items of 4 must reject it."""
    C.assert_mutation_caught(
        BP,
        lambda d: d["params"]["model_answers"].__setitem__("min_items", 4),
        "worked_examples",
        what="raise min_items above what the worked examples supply, proving the param "
        "contract is actually enforced against the examples",
    )


# ------------------------------------------------------------- mechanism 3: determinism


def test_replay_is_fully_deterministic_with_hash_equality() -> None:
    replay = C.load(BP)["replay"]
    assert replay["deterministic"] is True
    assert isinstance(replay["seed"], int)
    assert replay["verify"] == "hash-equal"
    assert replay["hash_algorithm"] == "sha256"
    assert replay["on_divergence"] == "fail"
    for src in ("clock", "random", "network", "filesystem-order", "process-id"):
        assert src in replay["forbid_nondeterministic_sources"], src


def test_retry_is_disabled_because_a_rerun_is_the_same_measurement() -> None:
    retry = C.load(BP)["retry_policy"]
    assert retry["strategy"] == "none"
    assert retry["max_attempts"] == 1


def test_mutation_control_a_deterministic_replay_without_a_seed_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["replay"].pop("seed"),
        "schema",
        what="claim deterministic replay with no seed - the schema requires seed, journal, "
        "record and verify before that claim is anything but decorative",
    )


def test_mutation_control_retry_none_with_more_than_one_attempt_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["retry_policy"].__setitem__("max_attempts", 3),
        "schema",
        what="declare strategy none while allowing three attempts",
    )


# --------------------------------------------------------- mechanism 4: one decision, no loop


def test_there_is_no_loop_and_no_fanout_anywhere() -> None:
    """The design card is explicit: the gate does not loop, one decision per invocation."""
    fp = C.fingerprint(C.load(BP))
    assert "loop" not in fp["stage_kinds"], fp["stage_kinds"]
    assert "fanout" not in fp["stage_kinds"], fp["stage_kinds"]
    assert fp["loop_shape"] == []
    assert fp["fanout_shape"] == []
    assert C.load(BP)["resume"]["enabled"] is False, (
        "a single-shot decision has nothing to resume; enabling resume would imply a "
        "multi-step run the design card explicitly rules out"
    )


def test_the_terminal_route_admits_exactly_two_outcomes() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["deterministic-route"]
    assert gate["expression"] == "decision == ACCEPT OR decision == ESCALATE"
    assert doc["stages"][-1]["id"] == "route"
    assert doc["stages"][-1]["kind"] == "gate"


# ------------------------------------------------- mechanism 5: correlated blind spot warning


def test_the_blindspot_warning_stage_exists_and_is_both_states_specified() -> None:
    wu = C.find_stage(C.load(BP), "blindspot-warning")["work_unit"]
    tests = " ".join(wu["tests_required"])
    assert "same-family" in tests
    assert "FIRE" in tests and "SILENT" in tests, (
        "the warning must discriminate the two states; a warning that fires in both measures "
        "nothing, which is the failure this wording exists to prevent"
    )
    assert "NO-WARNING" in wu["evidence_requirement"], (
        "the absence of a warning must be recorded explicitly, not left as an empty file"
    )


def test_council_stopping_metrics_are_absent_because_there_is_no_council_stage() -> (
    None
):
    doc = C.load(BP)
    kinds = C.fingerprint(doc)["stage_kinds"]
    assert "council" not in kinds
    _, advisories = C.semantic(doc)
    assert not advisories, (
        "no council stage means DSL-SEM-014 has nothing to complain about"
    )


# ------------------------------------------------------------------------ worked examples


def test_worked_examples_cover_the_escalate_and_the_refusal_paths() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    pos, neg = C.worked_examples(doc)
    assert pos["arm"] == "positive"
    assert "ESCALATE" in pos["expected_terminal_state"]
    assert neg["arm"] == "negative-control"
    assert "correlated-producers" in neg["expected_terminal_state"]
    assert "269" in neg["walkthrough"] and "234" in neg["walkthrough"], (
        "the negative arm is grounded in the measured wrong number this program actually hit"
    )


def test_the_positive_arm_declines_to_pick_the_numerically_closer_answer() -> None:
    pos = C.worked_examples(C.load(BP))[0]
    assert (
        "does not pick 234 because two answers are numerically closer"
        in pos["walkthrough"]
    ), (
        "routing rather than judging is the whole point; if the walkthrough silently picked a "
        "winner the blueprint would be a correctness oracle, which the card forbids"
    )
