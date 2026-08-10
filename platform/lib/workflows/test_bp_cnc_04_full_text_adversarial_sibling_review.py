"""FLAGSHIP end-to-end test: bp-cnc-04 Full-Text Adversarial Sibling Review.

Mechanism pinned here:

  1. DIGESTS ARE A FORBIDDEN INPUT. The ban gate is blocking with on_fail == "fail", and it
     asserts byte equality between the assembled text and the source, so a truncation is
     arithmetic rather than a matter of trust.
  2. The durable artifact is MANDATORY - enforced through the shared completion-predicate-v1
     reducer, not a bespoke check. A review that exists only in a transcript is NOT-RUN.
  3. The context-overflow repair SHARDS BY PREMISE and never truncates. This is the range's only
     repair_loop, and its whole reason for existing is to forbid the tempting repair.
  4. The repair loop has an INDEPENDENT verify stage - a repair loop without one is a retry that
     reports success.
  5. Truncation and digest input are in no_retry_on, so the forbidden repair cannot be reached
     by the retry path either.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-cnc-04-full-text-adversarial-sibling-review"


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True


# ------------------------------------------------------------- mechanism 1: digests banned


def test_the_digest_ban_gate_blocks_and_asserts_byte_equality() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["digests-are-forbidden"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "digest_inputs == 0" in gate["expression"]
    assert "truncated_lane_inputs == 0" in gate["expression"]
    assert "assembled_bytes_match_source_bytes == true" in gate["expression"]

    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("digest-ban-gate") < stages.index("attack"), (
        "the ban must be checked before any adversary is paid for"
    )


def test_the_barrier_rejects_a_digest_shaped_result() -> None:
    barrier = C.find_stage(C.load(BP), "attack")["barrier"]
    assert "based on the digest" in barrier["reject_result_matching"]
    assert "started in the background" in barrier["reject_result_matching"]
    assert barrier["verify_artifact_exists"] is True


def test_mutation_control_a_non_blocking_digest_ban_is_caught_structurally() -> None:
    """Flipping the ban to advisory stays schema-valid, so the fingerprint must notice it."""
    doc = C.load(BP)
    doc["gates"]["digests-are-forbidden"]["blocking"] = False
    doc["gates"]["digests-are-forbidden"]["on_fail"] = "record-and-continue"
    assert C.fingerprint_key(doc) != C.fingerprint_key(C.load(BP)), (
        "the gate_shape component of the fingerprint must encode blocking and on_fail, or a "
        "workflow that merely logs a digest input would look identical to one that refuses it"
    )


# ------------------------------------------------------ mechanism 2: mandatory durable write


def test_the_durable_artifact_gate_uses_the_shared_completion_predicate() -> None:
    gate = C.load(BP)["gates"]["durable-artifact-exists"]
    assert gate["predicate"] == "completion-predicate-v1", (
        "the durable-artifact check must reference the ONE shared 12-condition reducer rather "
        "than reimplementing a second predicate"
    )
    assert gate["predicate_ref"].startswith("command-center/COMPLETION-GATES.json#")
    assert gate["conditions_required"] == [1, 2, 3, 11, 12]
    assert gate["blocking"] is True


def test_the_review_artifact_has_a_real_minimum_size_and_named_consumers() -> None:
    doc = C.load(BP)
    review = doc["outputs"]["review"]
    assert review["min_bytes"] >= 1024
    assert review["register_in_manifest"] is True
    assert review["consumers"], "condition 12 needs named consumers to be checkable"
    wu = C.find_stage(doc, "write-review")["work_unit"]
    assert any(
        "transcript-only review counts as NOT-RUN" in t for t in wu["tests_required"]
    )


def test_mutation_control_dropping_the_predicate_conditions_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["gates"]["durable-artifact-exists"].pop("conditions_required"),
        "schema",
        what="reference completion-predicate-v1 without saying which of the 12 conditions it "
        "asserts - a gate that names no condition checks nothing",
    )


# ------------------------------------------------- mechanism 3 and 4: the shard-by-premise repair


def test_the_repair_loop_targets_the_attack_stage_and_shards_by_premise() -> None:
    doc = C.load(BP)
    repair = C.find_stage(doc, "shard-repair")
    assert repair["kind"] == "repair_loop"
    assert repair["target"] == ["attack"]
    assert repair["require_root_cause"] is True
    assert "context-overflow" in repair["classification_filter"]
    assert repair["repair"]["id"] == "reshard-by-premise"
    wu = repair["repair"]["work_unit"]
    assert "truncated_lane_inputs == 0" in wu["completion_sentinel"]
    assert any("truncation is the forbidden repair" in t for t in wu["tests_required"])


def test_this_is_the_only_repair_loop_in_the_bp2_range() -> None:
    """Distinctness is structural: exactly one of the twelve carries a repair_loop."""
    with_repair = [
        bid
        for bid in C.BP2_IDS
        if "repair_loop" in C.fingerprint(C.load(bid))["stage_kinds"]
    ]
    assert with_repair == [BP], with_repair


def test_the_repair_loop_has_an_independent_verify_gate() -> None:
    repair = C.find_stage(C.load(BP), "shard-repair")
    verify = repair["verify"]
    assert verify["kind"] == "gate", (
        "the verify must be a GATE, not another task by the repairing role - a repair loop "
        "whose verifier is the repairer is a retry that reports success"
    )
    assert verify["gate_ref"] == "repair-was-verified"
    gate = C.load(BP)["gates"]["repair-was-verified"]
    assert gate["blocking"] is True
    assert "sharded_by_premise == true" in gate["expression"]
    assert "truncated_lane_inputs == 0" in gate["expression"]
    assert gate["on_fail"] == "escalate-to-human"


def test_mutation_control_a_repair_loop_without_a_verify_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "shard-repair").pop("verify"),
        "schema",
        what="remove the independent verify stage from the repair loop",
    )


def test_mutation_control_a_repair_loop_targeting_a_nonexistent_stage_is_caught() -> (
    None
):
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "shard-repair").__setitem__(
            "target", ["no-such-stage"]
        ),
        "semantic",
        what="target a stage that does not exist (DSL-SEM-009)",
    )


# ---------------------------------------------------- mechanism 5: the forbidden repair is closed


def test_truncation_and_digest_input_can_never_be_retried_into() -> None:
    doc = C.load(BP)
    retry = doc["retry_policy"]
    assert "truncation-attempted" in retry["no_retry_on"]
    assert "digest-input" in retry["no_retry_on"]
    assert "context-overflow" in retry["retry_on"], (
        "an overflow IS retryable - but only through the sharding repair, never by truncating"
    )
    wu = C.find_stage(doc, "attack-one-premise")["work_unit"]
    assert wu["retry_policy"].startswith("no retry by truncation, ever")


def test_the_workflow_escalates_rather_than_shipping_a_truncated_review() -> None:
    rules = {r["id"]: r for r in C.load(BP)["stopping_rules"]}
    assert rules["truncation-attempted"]["on_stop"] == "escalate"
    assert rules["review-not-written"]["on_stop"] == "escalate"
    assert rules["every-shared-premise-verdicted"]["minimum_conditions"] == (
        "digest_inputs == 0 AND truncated_lane_inputs == 0"
    )


# ------------------------------------------------------------------------ worked examples


def test_worked_examples_are_the_two_arm_digest_versus_full_text_benchmark() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    pos, neg = C.worked_examples(doc)
    assert pos["arm"] == "positive"
    assert all(not p.endswith("digest.md") for p in pos["params"]["lane_outputs_full"])
    assert neg["arm"] == "negative-control"
    assert all(p.endswith("digest.md") for p in neg["params"]["lane_outputs_full"]), (
        "the negative arm must actually feed digests, or it is not the two-arm control"
    )
    assert "digest-input" in neg["expected_terminal_state"]


def test_the_ship_no_ship_condition_is_recorded_not_buried() -> None:
    neg = C.worked_examples(C.load(BP))[1]
    assert "the full-text cost is not justified" in neg["walkthrough"], (
        "the design card states a retirement condition for this blueprint; dropping it would be "
        "an overclaim even though the mechanism is sound"
    )


def test_the_unverified_residual_names_its_settling_experiment() -> None:
    x = C.load(BP)["x_extensions"]
    assert "UNVERIFIED" in x["unverified"]
    assert "two-arm" in x["unverified"]
