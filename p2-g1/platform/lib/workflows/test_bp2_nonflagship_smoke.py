"""Smoke tests for the six NON-flagship bp-2 blueprints.

The spec's floor for a non-flagship workflow is "executable, schema-valid, documented, and
smoke-tested". The catalog suite already covers schema validity, semantics, schema-ref
resolution and worked-example typing for all twelve; this module adds the per-blueprint
MECHANISM assertion plus one both-states mutation control each, so a non-flagship blueprint is
still pinned to the specific thing that makes it distinct rather than merely to being valid.

Covered here: bp-brn-02, bp-brn-03, bp-brn-04, bp-cnc-02, bp-cnc-05, bp-req-02.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

NON_FLAGSHIP = sorted(set(C.BP2_IDS) - C.FLAGSHIP_IDS)


def test_the_non_flagship_set_is_exactly_six() -> None:
    assert len(NON_FLAGSHIP) == 6, NON_FLAGSHIP
    assert set(NON_FLAGSHIP) == {
        "bp-brn-02-diverge-then-converge",
        "bp-brn-03-constraint-inversion",
        "bp-brn-04-analogy-transfer",
        "bp-cnc-02-two-peer-cross-vendor-debate",
        "bp-cnc-05-governance-decision-gate",
        "bp-req-02-recursive-decision-ledger-walk",
    }


# ------------------------------------------------- bp-brn-02: the HARD temporal barrier


def test_brn02_the_barrier_is_hard_and_precedes_all_judgement() -> None:
    doc = C.load("bp-brn-02-diverge-then-converge")
    freeze = C.find_stage(doc, "freeze")
    assert freeze["kind"] == "barrier"
    assert freeze["barrier"]["mode"] == "all"
    assert freeze["barrier"]["on_partial"] == "fail", (
        "a barrier that proceeds on partial is not a freeze; the whole mechanism is that the "
        "idea set is closed before scoring starts"
    )
    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("freeze") < stages.index("converge")
    assert stages.index("barrier-gate") < stages.index("converge")
    assert doc["gates"]["barrier-integrity"]["blocking"] is True
    assert (
        "ideas_added_after_barrier == 0"
        in doc["gates"]["barrier-integrity"]["expression"]
    )


def test_brn02_the_divergers_never_see_the_scoring_criteria() -> None:
    doc = C.load("bp-brn-02-diverge-then-converge")
    assert doc["roles"]["diverger"]["independence"] == "independent"
    assert (
        "NOT shown to the divergers" in doc["params"]["constraints"]["description"]
    ), (
        "a constraint list IS a judgement criterion; leaking it into generation defeats the "
        "temporal separation"
    )
    wu = C.find_stage(doc, "generate-under-lens")["work_unit"]
    assert "Do not rank, do not filter" in wu["question_or_target"]


def test_brn02_mutation_control_a_soft_barrier_is_structurally_visible() -> None:
    doc = C.load("bp-brn-02-diverge-then-converge")
    C.find_stage(doc, "freeze")["barrier"]["on_partial"] = "proceed-degraded"
    assert C.fingerprint_key(doc) != C.fingerprint_key(
        C.load("bp-brn-02-diverge-then-converge")
    ), (
        "barrier mode/on_partial is part of the fingerprint, so softening the freeze is visible"
    )


def test_brn02_mutation_control_a_council_rule_outside_the_metric_registry_is_caught() -> (
    None
):
    C.assert_mutation_caught(
        "bp-brn-02-diverge-then-converge",
        lambda d: C.find_stage(d, "converge")["stopping_rules"][0].__setitem__(
            "expression", "custom:ideas_added_after_barrier == 0"
        ),
        "semantic",
        what="use the councilspec custom: prefix, which the wfdsl expression lexer rejects - the "
        "two grammars are NOT co-extensive and only registry metric names satisfy both",
    )


# ---------------------------------- bp-brn-03: orchestrator-owned hard-ban tagging pre-gate


def test_brn03_the_safety_gate_blocks_before_any_inversion_runs() -> None:
    doc = C.load("bp-brn-03-constraint-inversion")
    gate = doc["gates"]["hard-ban-tagging-integrity"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail", (
        "a mis-tagged run must not proceed to generate unsafe suggestions"
    )
    assert "hard_ban_tags_authored_by_agent == 0" in gate["expression"]
    assert "tagging_authority == ORCHESTRATOR" in gate["expression"]
    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("safety-gate") < stages.index("invert")
    assert stages.index("safety-gate") == 1


def test_brn03_a_hard_ban_refusal_is_a_correct_terminal_state_not_a_retryable_error() -> (
    None
):
    doc = C.load("bp-brn-03-constraint-inversion")
    assert "hard-ban-refused" in doc["retry_policy"]["no_retry_on"]
    wu = C.find_stage(doc, "invert-one")["work_unit"]
    assert "CORRECT terminal state, not an error to retry" in wu["completion_sentinel"]
    assert "hard-ban-refused" in wu["failure_classification"]
    tagged_by = doc["params"]["constraints"]["items"]["properties"]["tagged_by"]
    assert tagged_by["enum"] == ["orchestrator", "owner"], (
        "'agent' is deliberately not a legal value for who applied the hard-ban tag"
    )


def test_brn03_mutation_control_dropping_the_agent_authorship_clause_is_visible() -> (
    None
):
    doc = C.load("bp-brn-03-constraint-inversion")
    doc["gates"]["hard-ban-tagging-integrity"]["expression"] = (
        "untagged_constraints == 0"
    )
    assert not any(C.all_layer_failures(doc).values()), (
        "the schema cannot know this safety clause is required; it is pinned by the test above"
    )
    assert "safety_note" in C.load("bp-brn-03-constraint-inversion")["x_extensions"]


# ------------------------------------------- bp-brn-04: neutrality gate + retrodiction control


def test_brn04_the_retrodiction_control_gates_every_verdict() -> None:
    doc = C.load("bp-brn-04-analogy-transfer")
    gate = doc["gates"]["retrodiction-control-fires"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "known_transfer_rediscovered == true" in gate["expression"]
    assert "control_ran_on_same_neutral_statement == true" in gate["expression"], (
        "a control run on a friendlier paraphrase measures nothing"
    )
    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("control-gate") < stages.index("transfer-test")
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["instrument-broken"]["on_stop"] == "escalate"


def test_brn04_is_the_only_bp2_blueprint_that_touches_the_network() -> None:
    networked = [
        bid for bid in C.BP2_IDS if C.fingerprint(C.load(bid))["network"] != "none"
    ]
    assert networked == ["bp-brn-04-analogy-transfer"], networked
    policy = C.load("bp-brn-04-analogy-transfer")["tool_policy"]
    assert policy["network"] == "read-only"
    assert policy["source_policy"]["treat_fetched_content_as_data"] is True
    assert policy["source_policy"]["license_allowlist"]
    assert "Write(platform/lib/**)" in policy["require_owner_approval"], (
        "an imported mechanism must not reach the build tree without owner approval"
    )


def test_brn04_mutation_control_a_neutrality_gate_that_cannot_fail_is_caught() -> None:
    C.assert_mutation_caught(
        "bp-brn-04-analogy-transfer",
        lambda d: d["gates"]["statement-is-neutral"].__setitem__("expression", "1 2 3"),
        "semantic",
        what="replace the neutrality expression with text the grammar cannot parse",
    )


# ---------------------------------------- bp-cnc-02: sequential debate + blocking dispatch


def test_cnc02_the_loop_body_is_sequential_so_each_peer_reads_the_other() -> None:
    doc = C.load("bp-cnc-02-two-peer-cross-vendor-debate")
    loop = C.find_stage(doc, "exchange")
    body = loop["body"]
    assert [b["id"] for b in body] == ["peer-a-turn", "peer-b-turn"]
    assert body[1]["depends_on"] == ["peer-a-turn"], (
        "without the edge the peers run in parallel and this is two monologues, not a debate"
    )
    assert loop["convergence"]["max_iterations"] == 3
    assert loop["convergence"]["no_progress_rounds"] == 1


def test_cnc02_the_dispatch_contract_is_blocking_and_prompts_by_file() -> None:
    doc = C.load("bp-cnc-02-two-peer-cross-vendor-debate")
    gate = doc["gates"]["dispatch-was-blocking"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"
    for clause in (
        "background_dispatches == 0",
        "receipt_shaped_results == 0",
        "output_last_message_files_present == true",
        "nonzero_exits == 0",
    ):
        assert clause in gate["expression"], clause
    for stage_id in ("peer-a-turn", "peer-b-turn"):
        st = C.find_stage(doc, stage_id)
        assert st["prompt_ref"].endswith(".md"), "prompt by FILE, never inline"
        assert st["work_unit"]["execution_substrate"] == "codex-mcp-blocking"
    barrier_free = doc["x_extensions"]["dispatch_contract"]
    assert barrier_free["blocking"].startswith("MANDATORY")
    assert "32,767" in barrier_free["prompt_transport"]
    assert "--ignore-user-config" in barrier_free["arg_hygiene"]


def test_cnc02_a_collapsed_debate_is_relabelled_not_reported_as_a_debate() -> None:
    doc = C.load("bp-cnc-02-two-peer-cross-vendor-debate")
    assert doc["gates"]["debate-actually-happened"]["blocking"] is False
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["collapsed-to-single-critic"]["on_stop"] == "emit-partial"
    assert "severed-stream" in doc["retry_policy"]["no_retry_on"]
    council = C.find_stage(doc, "synthesise")
    ids = {r["id"] for r in council["stopping_rules"]}
    assert "suspicious-round-one-convergence" in ids, (
        "a debate that converges completely on round one is suspicious by design"
    )


def test_cnc02_mutation_control_a_parallel_debate_body_is_visible() -> None:
    doc = C.load("bp-cnc-02-two-peer-cross-vendor-debate")
    C.find_stage(doc, "peer-b-turn").pop("depends_on")
    failures = C.all_layer_failures(doc)
    assert not any(failures.values()), (
        "the DSL cannot know these two must be sequential, so the ordering is pinned by the "
        f"test above: { {k: v[:2] for k, v in failures.items() if v} }"
    )


def test_cnc02_mutation_control_an_illegal_council_enum_token_is_caught() -> None:
    C.assert_mutation_caught(
        "bp-cnc-02-two-peer-cross-vendor-debate",
        lambda d: C.find_stage(d, "synthesise")["stopping_rules"][0].__setitem__(
            "expression", "verdict == PROBABLY_FINE"
        ),
        "advisory",
        what="use an enum token outside the councilspec registry's 15-token set, which "
        "DSL-SEM-014 reports as a cross-implementation advisory",
    )


# ----------------------------------- bp-cnc-05: falsifiable decision + append-only ledger


def test_cnc05_an_unfalsifiable_decision_is_rejected() -> None:
    doc = C.load("bp-cnc-05-governance-decision-gate")
    gate = doc["gates"]["decision-is-falsifiable"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"
    assert "reversal_condition_names_a_probe == true" in gate["expression"], (
        "a reversal condition that names no probe is decorative"
    )
    assert "reversal-condition-missing" in doc["retry_policy"]["no_retry_on"], (
        "the run must not get a second chance to restate it more softly"
    )


def test_cnc05_an_owner_evidence_class_is_marked_not_independently_verifiable() -> None:
    doc = C.load("bp-cnc-05-governance-decision-gate")
    gate = doc["gates"]["evidence-class-declared"]
    assert (
        "owner_class_marked_not_independently_verifiable == true" in gate["expression"]
    )
    vocab = doc["x_extensions"]["evidence_class_vocabulary"]
    assert set(vocab) == {"CMD", "FILE", "DOC", "OWNER"}
    assert "NOT independently verifiable" in vocab["OWNER"]


def test_cnc05_the_owner_checkpoint_is_conditional_and_owner_only() -> None:
    doc = C.load("bp-cnc-05-governance-decision-gate")
    cp = C.find_stage(doc, "owner-escalation")
    assert cp["kind"] == "human_checkpoint"
    assert (
        cp["when"] == "owner_decision_required == true OR reversibility == IRREVERSIBLE"
    )
    assert cp["approval_mode"] == "owner-only"
    assert cp["on_timeout"] == "escalate"
    assert isinstance(cp["timeout_seconds"], int)
    assert cp["decision_artifact"]["path"].endswith("owner-approval.json")


def test_cnc05_the_ledger_is_append_only_and_that_is_gated() -> None:
    doc = C.load("bp-cnc-05-governance-decision-gate")
    gate = doc["gates"]["ledger-is-append-only"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"
    assert "entries_overwritten == 0" in gate["expression"]
    assert "superseded_entries_marked == true" in gate["expression"]
    assert doc["stages"][-1]["id"] == "append-only-gate"
    wu = C.find_stage(doc, "ledger-write")["work_unit"]
    assert "ledger-overwrite" in wu["failure_classification"]
    assert wu["retry_policy"].startswith("no retry on an overwrite")


def test_cnc05_mutation_control_a_human_checkpoint_without_a_timeout_is_caught() -> (
    None
):
    C.assert_mutation_caught(
        "bp-cnc-05-governance-decision-gate",
        lambda d: C.find_stage(d, "owner-escalation").pop("timeout_seconds"),
        "schema",
        what="leave a human checkpoint with an on_timeout but no timeout, so it can hang forever",
    )


# ---------------------------------------- bp-req-02: frontier walk with a drilled resume


def test_req02_the_frontier_size_is_the_convergence_metric() -> None:
    doc = C.load("bp-req-02-recursive-decision-ledger-walk")
    conv = C.find_stage(doc, "walk")["convergence"]
    assert conv["converged_when"] == "frontier_size == 0 OR depth_reached >= max_depth"
    names = {m["name"] for m in conv["metrics"]}
    assert "frontier_size" in names and "depth_reached" in names
    assert "max_depth" in doc["params"], (
        "DSL-SEM-008 permits a param name in a convergence expression, and max_depth is one"
    )
    assert conv["max_iterations"] == 400


def test_req02_every_node_write_is_a_checkpoint_and_the_body_has_three_stages() -> None:
    doc = C.load("bp-req-02-recursive-decision-ledger-walk")
    body = C.find_stage(doc, "walk")["body"]
    assert [b["id"] for b in body] == [
        "ask-frontier-node",
        "expand-children",
        "checkpoint-node",
    ]
    assert body[2]["checkpoint"] is True
    assert body[1]["depends_on"] == ["ask-frontier-node"]
    assert body[2]["depends_on"] == ["expand-children"]
    gate = doc["gates"]["every-node-write-is-a-checkpoint"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"
    wu = body[2]["work_unit"]
    assert "READ THEM BACK" in wu["question_or_target"], (
        "a write that was never flushed is indistinguishable from a write that never happened"
    )


def test_req02_a_pruned_subtree_is_marked_not_deleted() -> None:
    doc = C.load("bp-req-02-recursive-decision-ledger-walk")
    gate = doc["gates"]["pruned-subtree-is-restorable"]
    assert "prunes_without_recorded_reason == 0" in gate["expression"]
    assert "pruned_nodes_deleted == 0" in gate["expression"]
    assert "node-deleted" in doc["retry_policy"]["no_retry_on"]
    wu = C.find_stage(doc, "expand-children")["work_unit"]
    assert any("must RESTORE the pruned subtree" in t for t in wu["tests_required"])
    assert "improvised-expansion" in wu["failure_classification"], (
        "a child added with no citing rule makes the tree unauditable"
    )


def test_req02_resume_is_drilled_with_a_both_states_arm_not_asserted() -> None:
    doc = C.load("bp-req-02-recursive-decision-ledger-walk")
    drill = C.find_stage(doc, "resume-drill")
    assert drill["when"] == "resume_drill == true"
    wu = drill["work_unit"]
    tests = " ".join(wu["tests_required"])
    assert "corrupt one checkpoint and confirm the drill FAILS" in tests
    assert "passes in both states measures nothing" in tests
    assert "re-asked - which must be zero" in wu["evidence_requirement"]
    assert (
        doc["gates"]["resume-lands-on-the-frontier"]["on_fail"] == "escalate-to-human"
    )
    assert doc["resume"]["enabled"] is True
    assert doc["resume"]["granularity"] == "work-unit"


def test_req02_has_no_council_and_no_fanout_at_all() -> None:
    fp = C.fingerprint(C.load("bp-req-02-recursive-decision-ledger-walk"))
    assert "council" not in fp["stage_kinds"]
    assert "fanout" not in fp["stage_kinds"]
    assert fp["cache_scope"] == "disabled", (
        "caching a human's answer to a tree node would serve a stale decision"
    )


def test_req02_mutation_control_a_prune_rule_that_deletes_is_visible() -> None:
    C.assert_mutation_caught(
        "bp-req-02-recursive-decision-ledger-walk",
        lambda d: d["params"]["dependency_rules"]["schema"]["properties"]["rules"][
            "items"
        ]["properties"].pop("prune"),
        "worked_examples",
        what="remove prune from the dependency-rule contract while the worked example still "
        "uses it, which the additionalProperties:false inline schema must reject",
    )
