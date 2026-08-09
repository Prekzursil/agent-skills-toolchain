#!/usr/bin/env python
"""Generator for catalog slice SYN-1.json -- bucket B12 "synthesis and meta-review".

Bucket total 48, this is part 1 of 1, ids SYN-0001..SYN-0048, phase 14
(_USER-PROMPTS.md:11084-11098; PHASE-GRAPH.json allocation_buckets B12).

Field vocabulary is deliberately VARIED per unit. A field that carries exactly one
distinct value across the whole slice is a global default in disguise -- the measured
P1 defect on WORK-UNIT-CATALOG.json (9 of 19 contract fields exist only in a global
`defaults` block, overridden by 0 of 103 items). `phase` is the one legitimate
exception: B12 feeds phase 14 only, and CNL-1/RES-1 are likewise single-phase.
"""
import json
import os
import re
import sys

SPEC = "_USER-PROMPTS.md"

# ---------------------------------------------------------------- tool pools
T = {
    "ro":    ["Read", "Grep", "Glob", "Bash"],
    "rw":    ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    "graph": ["Read", "Grep", "Glob", "Write", "Bash"],
    "calc":  ["Read", "Write", "Bash"],
    "min":   ["Read", "Bash"],
    "xv":    ["Read", "Grep", "Glob", "Bash", "mcp__codex__codex", "mcp__codex__codex-reply"],
    "rwxv":  ["Read", "Grep", "Glob", "Write", "Edit", "Bash",
              "mcp__codex__codex", "mcp__codex__codex-reply"],
    "git":   ["Read", "Grep", "Glob", "Bash", "mcp__github__get_file_contents",
              "mcp__github__list_commits"],
    "mem":   ["Read", "Grep", "Glob", "Write", "Bash",
              "mcp__basic-memory__search_notes", "mcp__basic-memory__read_note",
              "mcp__basic-memory__write_note", "mcp__basic-memory__edit_note"],
    "diag":  ["Read", "Grep", "Glob", "Write", "Bash", "mcp__figma__generate_diagram"],
}

# ------------------------------------------------------------ reviewer pools
R = {
    "xv": ("one fresh-context adversarial reviewer from the OTHER vendor than the author "
           "(Claude author -> Codex reviewer, and the reverse); a same-vendor reviewer "
           "inherits the author's blind spots and does not satisfy this field"),
    "raw": ("one reviewer served ONLY the raw inputs and the recorded probe output, who must "
            "re-derive the verdict BEFORE being shown this unit's conclusion; a reviewer who "
            "reads the conclusion first has been anchored and does not count"),
    "two": ("two independent reviewers who do not see each other's verdict until both are "
            "filed; a split escalates to raw-source adjudication, never to a majority vote"),
    "det": ("one reviewer whose only job is to re-run the DETECTOR CONTROL and confirm the "
            "probe fires on the planted known-broken fixture and is silent on the known-good "
            "one; re-reading the result verifies nothing"),
    "stat": ("one reviewer who re-computes the statistic from the raw per-item table with the "
             "recorded seed, plus one reviewer who checks the null model is the right one for "
             "the sampling frame"),
    "owner": ("owner sign-off in addition to one cross-vendor reviewer, because this unit's "
              "output either reopens an owner decision or gates an owner-visible verdict"),
    "notauthor": ("any reviewer who authored ANY synthesis candidate under review is "
                  "disqualified; the reviewer roster must be joined against the author roster "
                  "and the empty intersection recorded in the receipt"),
    "writer": ("one technical editor for readability plus one evidence reviewer who samples "
               "10 assertions at random and re-resolves each anchor independently"),
}

# --------------------------------------------------------------- retry pools
RT = {
    "two_strikes": ("two strikes then pivot (AGENTS.md 4b): after the 2nd failure carrying the "
                    "same error fingerprint, enumerate >=2 mechanically different approaches "
                    "before any 3rd attempt; a 3rd identical retry is a unit failure"),
    "zero": ("zero retries. The first observation IS the verdict; a later run that disagrees is "
             "a DISCREPANCY to record (spec :11039), never an error to retry away"),
    "resume": ("resumable: on interruption restart from the last durable checkpoint and record "
               "the resume boundary in the receipt; never restart from zero and silently "
               "discard the partial artifact"),
    "env_once": ("one retry only when the failure classifies as environment-transient (429, "
                 "DNS, disk, runner eviction); a logic or evidence failure is never retried"),
    "fresh": ("one retry ONLY in a fresh context with the inputs re-read from disk, because the "
              "dominant failure mode here is an anchored prior, not a flaky tool"),
    "no_reroll": ("no re-roll of a disagreeing run. If a second pass produces a different set, "
                  "BOTH sets are kept and the delta becomes the finding"),
    "bounded3": ("at most 3 attempts, each changing substrate or interpreter; the receipt must "
                 "name what changed between attempts or the attempt does not count"),
}


def sent(uid, post):
    return ("SUCCESS:%s emitted only when the artifact at output_path exists, is non-empty, "
            "parses against output_schema, and %s. Any other terminal state is FAILED:%s "
            "<classification> with the diagnostic tail attached." % (uid, post, uid))


CC = "command-center"
UNITS = []


def add(**kw):
    UNITS.append(kw)


# =============================================================================
# A. ROOT-CAUSE HIERARCHY AND DECISION TRACE (SYN-0001 .. SYN-0007)
# =============================================================================

add(
    id="SYN-0001",
    title="Construct the root-cause hierarchy as a typed causal DAG, not a flat findings list",
    question_or_target=(
        "Implementation target: build " + CC + "/synthesis/ROOT-CAUSE-HIERARCHY.json from the "
        "normalized claim corpus, satisfying the spec's explicit shape requirement -- "
        "'Synthesis must produce a root-cause hierarchy and decision trace, not a flat list of "
        "findings' (" + SPEC + ":11086). Each node is typed CAUSE|MECHANISM|SYMPTOM, carries its "
        "own evidence anchors, and every symptom edge names the mechanism by which the parent "
        "produces the child. A depth-1 graph (all findings hanging off one synthetic root) is a "
        "flat list wearing a graph's clothing and must be rejected by this unit itself."),
    inputs=[
        CC + "/CLAIM-REGISTRY.json (canonical claim records, duplicate/support/contradiction edges)",
        CC + "/RISK-REGISTER.md and " + CC + "/UNKNOWNS-REGISTER.md",
        "Phase 11/12/13 verdict artifacts (buckets B09, B10, B11)",
        SPEC + ":11084-11098 (Phase 14 contract)",
    ],
    dependencies=["CC-0017", "CC-0019", "B09", "B10", "B11"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "causal-analyst"},
    tool_permissions=T["graph"],
    execution_substrate="local-parallel",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
    output_schema=CC + "/schema/root-cause-graph.schema.json",
    evidence_requirement=(
        "Report node count by type, edge count, max depth, median branching factor, and the "
        "findings-per-root-cause compression ratio. Every CAUSE node cites >=2 independent "
        "evidence anchors by file:line; a CAUSE with one anchor is admitted only when it is "
        "labelled SINGLE-SOURCE in the node itself."),
    tests_required=[
        "test_graph_is_acyclic",
        "test_max_depth_at_least_2 (rejects the flat-list-as-graph shape)",
        "test_every_cause_node_has_typed_edges_to_its_symptoms",
        "negative control: a synthetic corpus of 20 unrelated findings must NOT produce a single "
        "shared root cause",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0001", "the graph is acyclic and max depth >= 2"),
    retry_policy=RT["two_strikes"],
    failure_classification=["flat-list-masquerading-as-hierarchy", "unanchored-cause-node",
                            "cycle-in-causal-graph", "schema-invalid"],
    owner_approval_required=False,
)

add(
    id="SYN-0002",
    title="Structural integrity gate on the hierarchy: orphans, cycles, dangling evidence, planted-orphan control",
    question_or_target=(
        "Question: can any finding, risk, or blind spot reach the end of Phase 14 WITHOUT being "
        "attached to a cause node? Target: a gate over SYN-0001's graph that fails on (a) any "
        "claim-registry record with zero inbound attachment, (b) any cause node with neither "
        "children nor evidence, (c) any edge whose endpoint id does not exist, and (d) any cycle. "
        "The gate is only trusted after a PLANTED orphan and a PLANTED cycle are both detected "
        "(detector control, single-signal-verification rule 3)."),
    inputs=[
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
        CC + "/CLAIM-REGISTRY.json (the full claim id set = the denominator)",
        CC + "/RISK-REGISTER.md (accepted residual risks must also attach)",
    ],
    dependencies=["SYN-0001"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "graph-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="local-parallel",
    timeout_seconds=2700,
    output_path=CC + "/receipts/SYN-0002.json",
    output_schema=CC + "/schema/detector-control.schema.json",
    evidence_requirement=(
        "Print the four counts with their denominators (orphan claims / total claims, etc.) and "
        "the exit code of the gate on BOTH the planted-defect fixture and the clean graph. A "
        "zero-orphan claim with no planted-orphan run attached is NOT-CHECKED, not a pass."),
    tests_required=[
        "detector control: planted orphan claim -> gate exits non-zero",
        "detector control: planted cycle -> gate exits non-zero",
        "both-states: clean graph -> gate exits 0 with zero findings",
        "test_dangling_edge_endpoint_is_detected",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0002",
                             "both planted-defect runs are recorded as FIRED and the clean run as SILENT"),
    retry_policy=RT["bounded3"],
    failure_classification=["detector-failure", "silent-in-both-states", "orphaned-finding",
                            "false-green"],
    owner_approval_required=False,
)

add(
    id="SYN-0003",
    title="Rival-explanation generation: every root cause gets a competing hypothesis and a discriminating experiment",
    question_or_target=(
        "Question: for each CAUSE node in the hierarchy, what is the strongest RIVAL causal "
        "explanation of the same symptom set, and what single experiment would separate the two? "
        "A cause admitted with no rival considered must be labelled SINGLE-HYPOTHESIS in the "
        "final report. This is the synthesis-time counterpart of the spec's demand for "
        "'counterevidence to every major conclusion' (" + SPEC + ":10700) applied to causation "
        "rather than to claims."),
    inputs=[
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
        "Phase 12 refutation artifacts (bucket B10) -- refuters often already named the rival",
        CC + "/UNKNOWNS-REGISTER.md",
    ],
    dependencies=["SYN-0001", "B10"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "rival-hypothesis-generator"},
    tool_permissions=T["xv"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0003.rival-explanations.json",
    output_schema=CC + "/schema/rival-hypothesis.schema.json",
    evidence_requirement=(
        "One record per CAUSE node: rival statement, the observation both hypotheses predict, the "
        "observation they predict DIFFERENTLY, and the exact command or probe that would collect "
        "it. A rival that predicts nothing different is not a rival and must be recorded as "
        "NON-DISCRIMINATING rather than counted."),
    tests_required=[
        "test_every_cause_node_has_a_rival_record_or_a_SINGLE_HYPOTHESIS_label",
        "test_no_rival_is_a_restatement (token-overlap gate against the original cause text)",
        "test_every_discriminating_experiment_names_a_runnable_probe",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0003",
                             "every CAUSE node maps to exactly one rival record or one explicit SINGLE-HYPOTHESIS label"),
    retry_policy=RT["fresh"],
    failure_classification=["rival-is-a-restatement", "non-discriminating-experiment",
                            "single-hypothesis-unlabelled"],
    owner_approval_required=False,
)

add(
    id="SYN-0004",
    title="Severity re-derivation after collapse: detect causes rated below their own children",
    question_or_target=(
        "Question: after N findings collapse into one root cause, does the cause carry at least "
        "the maximum severity of its subtree? Target: recompute severity bottom-up over the "
        "hierarchy and emit every INVERSION (a P2 cause with a P0 child) and every DILUTION (a "
        "cause whose severity was averaged rather than maximised). Collapse is the moment a P0 "
        "silently becomes a bullet under a P2 heading."),
    inputs=[
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
        CC + "/CLAIM-REGISTRY.json (per-claim severity as recorded at capture time)",
        CC + "/RISK-REGISTER.md",
    ],
    dependencies=["SYN-0001", "SYN-0002"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "severity-adjudicator"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=1800,
    output_path=CC + "/receipts/SYN-0004.json",
    output_schema=CC + "/schema/severity-reconciliation.schema.json",
    evidence_requirement=(
        "A table of every cause node: recorded severity, computed max-child severity, delta, and "
        "verdict. Any delta != 0 is a finding with the child claim id named. Include the count of "
        "P0/P1 claims whose severity survived collapse unchanged."),
    tests_required=[
        "test_max_not_mean_aggregation",
        "planted inversion: inject a P0 child under a P3 cause -> must be reported",
        "test_severity_vocabulary_is_closed (unknown severity token fails loudly, never defaults to low)",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0004", "zero unexplained severity deltas remain open"),
    retry_policy=RT["zero"],
    failure_classification=["severity-inversion", "severity-dilution", "unknown-token-defaulted-low"],
    owner_approval_required=False,
)

add(
    id="SYN-0005",
    title="Build the decision trace: owner decision or option id -> units -> artifacts -> tests -> outcome",
    question_or_target=(
        "Implementation target: a queryable DECISION-TRACE joining each owner decision and each "
        "selected option id forward through the work units that implement it, the artifacts they "
        "produced, the tests that cover them, and the final outcome -- the second half of the "
        "spec's Phase 14 shape requirement (" + SPEC + ":11086) and the 'verified decision trace' "
        "final deliverable (" + SPEC + ":11433). Every hop carries its own anchor so the trace is "
        "walkable in both directions."),
    inputs=[
        CC + "/OWNER-DECISIONS.md",
        CC + "/OPTION-ID-RESOLUTION.json (the namespace registry -- a bare M-NN is ambiguous)",
        CC + "/WORK-UNIT-CATALOG.json, " + CC + "/ARTIFACT-MANIFEST.json, " + CC + "/TEST-REGISTRY.json",
        CC + "/events/EVENTS.jsonl (append-only decision and completion events)",
    ],
    dependencies=["CC-0021", "CC-0022", "CC-0024", "SYN-0001"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "traceability-engineer"},
    tool_permissions=T["graph"],
    execution_substrate="local-parallel",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0005.decision-trace.json",
    output_schema=CC + "/schema/decision-trace.schema.json",
    evidence_requirement=(
        "Per decision: the decision text with its source anchor, the resolved option ids, the unit "
        "ids, the artifact paths that exist on disk, the test ids with their last recorded result, "
        "and the outcome label. Report the count of decisions whose chain breaks at each hop -- a "
        "break is the finding, and a decision with a complete chain but zero tests is a break too."),
    tests_required=[
        "test_every_owner_decision_appears_exactly_once",
        "test_trace_is_walkable_backwards (artifact -> unit -> decision)",
        "test_bare_option_token_is_rejected_until_namespace_resolved",
        "planted break: delete one artifact path -> the chain must report BROKEN at the artifact hop",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0005",
                             "every owner decision has a trace row and every break is enumerated with its hop"),
    retry_policy=RT["resume"],
    failure_classification=["broken-trace-hop", "ambiguous-option-token", "decision-with-no-coverage",
                            "orphan-artifact"],
    owner_approval_required=False,
)

add(
    id="SYN-0006",
    title="Decision-reversal ledger: decisions later contradicted by evidence that were never reopened",
    question_or_target=(
        "Question: which recorded owner decisions or program rulings were CONTRADICTED by later "
        "evidence and never reopened? The pinned instance is 17-DECISION-LOG.md:175, which states "
        "the 31-way M-NN option-id collision in the present tense and queues it as P2-09, while "
        "the re-prefix was applied on 2026-08-07 and the live collision count is 0. Target: a "
        "ledger of every such decision with the contradicting probe, the date the contradiction "
        "became true, and a reopen-or-supersede recommendation for the owner."),
    inputs=[
        CC + "/OWNER-DECISIONS.md and the corpus 17-DECISION-LOG.md",
        CC + "/CLAIM-REGISTRY.json (contradiction edges from Phase 1)",
        CC + "/events/EVENTS.jsonl (timestamps establish which came first)",
        "Phase 11 confirmer verdicts (bucket B09)",
    ],
    dependencies=["CC-0022", "SYN-0005", "B09"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "decision-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/synthesis/SYN-0006.decision-reversal-ledger.json",
    output_schema=CC + "/schema/decision-reversal.schema.json",
    evidence_requirement=(
        "Per entry: the decision anchor, the contradicting evidence anchor, both timestamps, and "
        "the verdict STILL-TRUE | SUPERSEDED-UNRECORDED | REOPEN-REQUIRED. The 17-DECISION-LOG.md:175 "
        "case must appear as SUPERSEDED-UNRECORDED with the 2026-08-07 fix cited, or this unit's "
        "detector is broken and the whole ledger is untrusted."),
    tests_required=[
        "known-present control: the 17-DECISION-LOG.md:175 collision entry MUST be found",
        "test_timestamp_ordering_decides_direction (a decision cannot be contradicted by earlier evidence)",
        "test_no_entry_is_closed_without_an_anchor",
    ],
    reviewer_requirement=R["owner"],
    completion_sentinel=sent("SYN-0006",
                             "the known-present control entry was found and every REOPEN-REQUIRED row carries an owner question"),
    retry_policy=RT["no_reroll"],
    failure_classification=["stale-decision-carried-as-live", "unrecorded-supersession",
                            "detector-missed-known-present"],
    owner_approval_required=True,
)

add(
    id="SYN-0007",
    title="Counterfactual earliest-intervention ranking: which single earlier action would have prevented the largest subtree",
    question_or_target=(
        "Question: for each root cause, what is the CHEAPEST EARLIER action that would have "
        "prevented the largest number of downstream findings, and at which phase could it have "
        "been taken? Target: a ranked intervention table (subtree size x severity / estimated "
        "cost) that tells the Phase 16 loop what to build first. This is prioritisation of "
        "prevention, distinct from SYN-0047 which maps causes onto the existing regression "
        "surface and distinct from IMP-0384 which performs the writeback."),
    inputs=[
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
        CC + "/synthesis/SYN-0004 severity reconciliation output",
        CC + "/PHASE-GRAPH.json (which phase could have caught it)",
    ],
    dependencies=["SYN-0001", "SYN-0004"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "program-strategist"},
    tool_permissions=T["calc"],
    execution_substrate="cloud-batch",
    timeout_seconds=3600,
    output_path=CC + "/synthesis/SYN-0007.intervention-ranking.json",
    output_schema=CC + "/schema/intervention-ranking.schema.json",
    evidence_requirement=(
        "Each row states the prevented subtree by explicit claim-id list (not a count alone), the "
        "phase at which the intervention was available with its spec line, and the cost basis. A "
        "row whose cost is asserted rather than derived must carry an ESTIMATE tag with its band."),
    tests_required=[
        "test_prevented_set_is_a_real_subtree_of_the_hierarchy",
        "test_ranking_is_stable_under_cost_tie_breaks (deterministic sort key)",
        "test_no_intervention_is_placed_at_a_phase_later_than_the_finding_it_prevents",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0007", "every ranked row enumerates its prevented claim ids"),
    retry_policy=RT["env_once"],
    failure_classification=["asserted-cost-without-band", "phase-anachronism", "unstable-ranking"],
    owner_approval_required=False,
)

# =============================================================================
# B. MULTIPLE INDEPENDENT SYNTHESES (SYN-0008 .. SYN-0013)
# =============================================================================

add(
    id="SYN-0008",
    title="Run N-way independent synthesis under information partition and cross-vendor diversity",
    question_or_target=(
        "Implementation target: execute the spec's 'multiple independent synthesis agents' "
        "(" + SPEC + ":11088) as >=3 synthesizers that (a) span at least two vendors, (b) receive "
        "DISJOINT-plus-shared-core evidence partitions, and (c) cannot read each other's output "
        "until all N are filed. The independence is a property of the harness, not a promise in "
        "the prompt: the dispatcher must be unable to leak sibling output, and that must be "
        "proven by a leak-attempt fixture."),
    inputs=[
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json and " + CC + "/synthesis/SYN-0005.decision-trace.json",
        "Phase 10/11/12/13 artifact sets (buckets B08, B09, B10, B11)",
        "rules/common/cross-vendor-dispatch.md (blocking dispatch, prompt-by-file, --ignore-user-config)",
        SPEC + ":11086-11098",
    ],
    dependencies=["SYN-0001", "SYN-0005", "B08", "B09", "B10", "B11"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "synthesis-lead"},
    tool_permissions=T["rwxv"],
    execution_substrate="local-serialized",
    timeout_seconds=10800,
    output_path=CC + "/synthesis/SYN-0008.candidate-syntheses.json",
    output_schema=CC + "/schema/synthesis-candidate.schema.json",
    evidence_requirement=(
        "For each candidate: vendor, model, the exact partition manifest it was given, wall-clock "
        "start and end, and the sha256 of its prompt file. Cross-vendor dispatch must be "
        "FOREGROUND and prove completion with exit code 0 AND a non-empty parsed output file -- a "
        "job id, a 'started in the background' string, or a progress stream is a SEVERED result, "
        "not a synthesis."),
    tests_required=[
        "leak fixture: a synthesizer that requests a sibling's output must be denied and the "
        "denial logged",
        "test_partition_manifest_covers_the_union_of_inputs (no evidence class reaches zero agents)",
        "test_every_candidate_parsed_against_the_schema_before_fan_in",
    ],
    reviewer_requirement=R["notauthor"],
    completion_sentinel=sent("SYN-0008",
                             ">=3 candidates exist, span >=2 vendors, and the leak fixture is recorded as DENIED"),
    retry_policy=RT["two_strikes"],
    failure_classification=["severed-stream", "win-arg-limit", "cross-read-leak",
                            "single-vendor-panel", "timeout-<n>s"],
    owner_approval_required=False,
)

add(
    id="SYN-0009",
    title="Raw-source control synthesis: one synthesizer that never sees a digest",
    question_or_target=(
        "Question: how much of the consensus synthesis is an artifact of the DIGESTS rather than "
        "the evidence? Target: one additional synthesizer whose input set contains only raw "
        "artifacts -- source files, test output, transcripts -- and zero summaries, digests, or "
        "sibling conclusions. Its output is the control against digest-cascade, where every "
        "downstream agent inherits one upstream summariser's framing."),
    inputs=[
        "raw Phase 10-13 outputs with all *DIGEST*, *SUMMARY* and receipt-narrative files excluded "
        "by an explicit deny-list recorded in the receipt",
        "the repository working tree at the pinned SHA",
        SPEC + ":11088",
    ],
    dependencies=["B08", "B09", "B10", "B11"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "control-synthesizer"},
    tool_permissions=T["ro"],
    execution_substrate="worktree-isolated",
    timeout_seconds=10800,
    output_path=CC + "/synthesis/SYN-0009.raw-source-control.json",
    output_schema=CC + "/schema/synthesis-candidate.schema.json",
    evidence_requirement=(
        "The deny-list and the resulting input inventory (count of files admitted vs excluded) "
        "must be in the receipt. Any conclusion this control reaches that NO digest-fed candidate "
        "reached is flagged DIGEST-SUPPRESSED and escalated to SYN-0013."),
    tests_required=[
        "test_no_admitted_input_path_matches_the_digest_denylist",
        "test_control_output_is_produced_without_reading_SYN_0008_candidates",
        "known-present control: a fact that exists ONLY in a raw artifact must appear in this output",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0009",
                             "the admitted-input inventory shows zero digest-class files and the known-present control fact is present"),
    retry_policy=RT["fresh"],
    failure_classification=["digest-contamination", "digest-suppressed-finding", "input-inventory-missing"],
    owner_approval_required=False,
)

add(
    id="SYN-0010",
    title="Chance-corrected inter-synthesis agreement statistic with an explicit null model",
    question_or_target=(
        "Question: how much do the independent syntheses actually agree, measured against what "
        "agreement would look like by chance? Target: compute a chance-corrected agreement "
        "coefficient over the candidates' root-cause sets and severity rankings, publish the null "
        "model used, and refuse the prose form 'the agents converged'. Distinct from SYN-0023, "
        "which explains WHY they agree; this unit only measures HOW MUCH."),
    inputs=[
        CC + "/synthesis/SYN-0008.candidate-syntheses.json",
        CC + "/synthesis/SYN-0009.raw-source-control.json",
        "the canonical mechanism ids from " + CC + "/CLAIM-REGISTRY.json (the item universe)",
    ],
    dependencies=["SYN-0008", "SYN-0009"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "statistician"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=2400,
    output_path=CC + "/receipts/SYN-0010.json",
    output_schema=CC + "/schema/agreement-statistic.schema.json",
    evidence_requirement=(
        "The per-item agreement matrix, the coefficient with its interval, the null model in one "
        "sentence, and the item universe size. A coefficient reported without its universe size "
        "and null model is uninterpretable and must be treated as NOT-CHECKED."),
    tests_required=[
        "synthetic control: 3 identical candidates -> coefficient at its maximum",
        "synthetic control: 3 random candidates over the same universe -> coefficient near zero",
        "test_coefficient_is_recomputable_from_the_published_matrix_alone",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0010",
                             "both synthetic controls land at their expected extremes"),
    retry_policy=RT["zero"],
    failure_classification=["statistic-without-null-model", "uninterpretable-coefficient",
                            "control-did-not-separate"],
    owner_approval_required=False,
)

add(
    id="SYN-0011",
    title="Adjudicate every divergence from raw source, never by agent vote",
    question_or_target=(
        "Implementation target: for each point where the independent syntheses disagree, produce "
        "an adjudication record resolved by re-reading the RAW source, not by counting agents. "
        "The estate rule is explicit -- on a split verdict about a briefed fact the specific probe "
        "wins over the agent count -- and it was earned when two agents 'CONFIRMED' a false fact "
        "with a broken detector. A majority-vote resolution is a unit failure here even when the "
        "majority is right."),
    inputs=[
        CC + "/synthesis/SYN-0008.candidate-syntheses.json and SYN-0009 control output",
        CC + "/receipts/SYN-0010.json (the divergence list is derived from the agreement matrix)",
        "the raw artifacts underlying each divergent claim",
    ],
    dependencies=["SYN-0010"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "adjudicator"},
    tool_permissions=T["ro"],
    execution_substrate="local-serialized",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0011.adjudications.json",
    output_schema=CC + "/schema/adjudication-record.schema.json",
    evidence_requirement=(
        "Per divergence: the competing statements verbatim, the raw anchor read to settle it, the "
        "verdict, and the losing statement's disposition (WRONG | CORRECTLY-SCOPED-DIFFERENTLY | "
        "BOTH-TRUE-DIFFERENT-SCOPE). The count of divergences resolved in favour of the MINORITY "
        "position must be reported explicitly."),
    tests_required=[
        "test_no_adjudication_cites_agent_count_as_its_reason (lexical gate on the reason field)",
        "test_every_adjudication_cites_a_raw_anchor_that_resolves",
        "planted split: two candidates assert opposite readings of a file whose content is known -> "
        "the adjudicator must pick the one the file supports",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0011",
                             "zero adjudications cite agent count and every one resolves a raw anchor"),
    retry_policy=RT["no_reroll"],
    failure_classification=["resolved-by-vote", "unresolvable-without-owner", "anchor-did-not-resolve"],
    owner_approval_required=False,
)

add(
    id="SYN-0012",
    title="Leave-one-source-out sensitivity: which conclusions flip when a single source is removed",
    question_or_target=(
        "Question: which top-level conclusions are FRAGILE -- they reverse or vanish when one "
        "source artifact, one agent, or one probe is removed from the evidence base? Target: "
        "recompute the synthesis conclusion set with each major source held out in turn and "
        "publish a per-conclusion robustness score. A conclusion that survives only because one "
        "artifact exists is a single point of epistemic failure and must be labelled as such in "
        "the final report."),
    inputs=[
        CC + "/synthesis/SYN-0011.adjudications.json (the settled conclusion set)",
        CC + "/CLAIM-REGISTRY.json source-lineage fields",
        CC + "/ARTIFACT-MANIFEST.json (the source inventory defines the hold-out space)",
    ],
    dependencies=["SYN-0011"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "sensitivity-analyst"},
    tool_permissions=T["calc"],
    execution_substrate="cloud-batch",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0012.sensitivity.json",
    output_schema=CC + "/schema/sensitivity-report.schema.json",
    evidence_requirement=(
        "A conclusion x held-out-source matrix with the survival verdict in every cell, plus the "
        "list of (conclusion, single source) pairs where removal is fatal. Report the hold-out "
        "space size; a sweep over 3 of 40 sources is a sample and must be labelled one."),
    tests_required=[
        "test_holdout_space_equals_the_declared_source_inventory",
        "planted fragility: a conclusion supported by exactly one fabricated source must be "
        "reported FATAL on that hold-out",
        "test_robust_conclusions_are_unchanged_across_all_holdouts",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0012",
                             "every settled conclusion has a robustness score and the fatal-pair list is enumerated"),
    retry_policy=RT["env_once"],
    failure_classification=["single-source-conclusion", "partial-sweep-reported-as-complete",
                            "matrix-cell-not-computed"],
    owner_approval_required=False,
)

add(
    id="SYN-0013",
    title="Measure what dies at the digest boundary and enforce an anchors-exempt EVIDENCE block",
    question_or_target=(
        "Question: how many UNVERIFIED tags, file:line anchors and URLs exist in the full "
        "artifacts versus in the synthesis that consumed them? The measured estate baseline is "
        "brutal: 87 percent of file:line references and 100 percent of URLs die at the digest "
        "boundary, and 18 UNVERIFIED tags survive into 30 digests against 127 in the source "
        "documents. Target: measure the loss for THIS program and enforce an EVIDENCE block of "
        "3-5 anchors that is exempt from any word cap."),
    inputs=[
        "the full Phase 10-13 artifact bodies (denominator)",
        CC + "/synthesis/SYN-0008.candidate-syntheses.json (numerator)",
        "rules/common/fan-out-contract.md sections A3 and B3",
    ],
    dependencies=["SYN-0008", "SYN-0009"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "evidence-auditor"},
    tool_permissions=T["rw"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0013.json",
    output_schema=CC + "/schema/digest-loss-report.schema.json",
    evidence_requirement=(
        "Counts with denominators for three token classes (UNVERIFIED, file:line, URL) in source "
        "vs synthesis, plus the retention rate per class. The counter must be use-vs-mention "
        "aware: a document ABOUT anchor loss necessarily contains the token it counts, so the "
        "detector must be proven on a fixture containing both a real anchor and a quoted one."),
    tests_required=[
        "use-vs-mention control: a fixture with 1 real anchor and 1 quoted anchor must count 1",
        "test_retention_rate_is_reported_per_class_not_aggregated",
        "test_EVIDENCE_block_presence_is_enforced_on_every_candidate",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0013",
                             "the use-vs-mention control passes and per-class retention rates are published"),
    retry_policy=RT["bounded3"],
    failure_classification=["use-vs-mention", "anchor-loss-at-digest", "aggregate-hides-class-loss"],
    owner_approval_required=False,
)

# =============================================================================
# C. THE SEVEN SPEC-NAMED META-REVIEW LENSES (SYN-0014 .. SYN-0021)
# =============================================================================

add(
    id="SYN-0014",
    title="Unsupported-certainty lens: confidence band asserted without support",
    question_or_target=(
        "Question (spec lens 1, " + SPEC + ":11090): which synthesis claims carry a confidence "
        "band or a certainty word while citing zero evidence anchors, or citing an anchor that "
        "does not support the band asserted? Target: a mechanical scan pairing every claim's band "
        "against its anchor set, then a human-read sample of the anchored ones to catch the "
        "harder case where the anchor exists but supports a weaker statement."),
    inputs=[
        CC + "/synthesis/SYN-0011.adjudications.json and the candidate syntheses",
        CC + "/CLAIM-REGISTRY.json (confidence and verification-status fields)",
        "AGENTS.md section 7 (Sherman-Kent bands and the evidence-tag pairing rule)",
    ],
    dependencies=["SYN-0011"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "meta-reviewer"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0014.json",
    output_schema=CC + "/schema/meta-review-finding.schema.json",
    evidence_requirement=(
        "Two counts with denominators: band-without-any-anchor, and band-not-supported-by-its-anchor "
        "from a stratified read of at least 30 anchored claims. Name the claim ids in both sets. A "
        "zero in the second bucket without a stated sample size is NOT-CHECKED."),
    tests_required=[
        "known-present control: plant a claim reading 'almost certain' with no anchor -> must fire",
        "both-states: a properly banded and anchored claim must NOT fire",
        "test_band_vocabulary_is_the_declared_five_and_an_unknown_hedge_is_reported_not_ignored",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0014",
                             "both counts carry denominators and the sampled-read size is stated"),
    retry_policy=RT["two_strikes"],
    failure_classification=["unsupported-certainty", "bare-hedge-no-band", "sample-size-unstated"],
    owner_approval_required=False,
)

add(
    id="SYN-0015",
    title="Quantifier-versus-measured-N overclaim scan",
    question_or_target=(
        "Question: for every synthesis sentence containing a universal quantifier -- every, all, "
        "none, zero, never, always, no unit, 100 percent -- does the measurement behind it cover "
        "the full population, or a subset? Target: extract each quantified sentence, bind it to "
        "its measured denominator, and rewrite it to the scope actually measured. On this estate "
        "5 of 8 refutations were overclaims where the CODE WAS CORRECT and the sentence was wider "
        "than the evidence; this is that class, and it is distinct from SYN-0014, which fires on "
        "missing support rather than excessive scope."),
    inputs=[
        "all Phase 14 candidate syntheses and " + CC + "/synthesis/SYN-0011.adjudications.json",
        "the underlying measurement receipts (each provides the true denominator)",
        "rules/common/fan-out-contract.md section C2",
    ],
    dependencies=["SYN-0011", "SYN-0014"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "overclaim-refuter"},
    tool_permissions=T["xv"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0015.json",
    output_schema=CC + "/schema/overclaim-scan.schema.json",
    evidence_requirement=(
        "Per flagged sentence: the quantifier, the asserted population, the measured population "
        "with its receipt anchor, and the corrected sentence. Record that a correctly-scoped "
        "rewrite counts as CONFIRMED, not as a defect in the underlying work -- the finding is the "
        "sentence, not the code."),
    tests_required=[
        "known-present control: plant 'no unit fails' next to a receipt measuring 12 of 103 -> must fire",
        "test_quantifier_extractor_ignores_quoted_examples (use-vs-mention)",
        "both-states: a sentence already scoped to its denominator must not fire",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0015",
                             "every flagged sentence carries a corrected, scope-bounded rewrite"),
    retry_policy=RT["fresh"],
    failure_classification=["overclaim", "use-vs-mention", "denominator-unavailable"],
    owner_approval_required=False,
)

add(
    id="SYN-0016",
    title="Omitted-dissent audit: every minority position must survive into the synthesis or carry a disposal reason",
    question_or_target=(
        "Question (spec lens 2, " + SPEC + ":11091): which dissents, minority reports and refuter "
        "objections raised in Phases 11-13 and in council runs are ABSENT from the synthesis? "
        "Target: enumerate the dissent population from its sources, join it to the synthesis text, "
        "and require every unmatched dissent to carry an explicit disposal reason. Silently "
        "dropping a minority report is one of the named council failure classes "
        "(" + SPEC + ":11341) and must not be reintroduced at synthesis time."),
    inputs=[
        "council transcripts and dissent/minority-report fields (bucket B05 outputs, Phase 2C)",
        "Phase 12 refutation artifacts (bucket B10) and Phase 11 discrepancy records (bucket B09)",
        "the candidate syntheses",
    ],
    dependencies=["SYN-0008", "B09", "B10"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "dissent-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0016.json",
    output_schema=CC + "/schema/dissent-audit.schema.json",
    evidence_requirement=(
        "The dissent population size with its extraction rule, the matched count, and the "
        "unmatched list with each item's source anchor. An unmatched dissent closed as "
        "'superseded' must name the evidence that superseded it."),
    tests_required=[
        "known-present control: a dissent that IS present in the synthesis must match (detector can find)",
        "planted omission: remove one dissent from the synthesis copy -> must be reported unmatched",
        "test_matching_is_semantic_not_substring (a paraphrased dissent still matches)",
    ],
    reviewer_requirement=R["notauthor"],
    completion_sentinel=sent("SYN-0016",
                             "the unmatched list is empty or every entry carries a written disposal reason"),
    retry_policy=RT["no_reroll"],
    failure_classification=["dropped-dissent", "disposal-without-reason", "substring-matcher-too-weak"],
    owner_approval_required=False,
)

add(
    id="SYN-0017",
    title="Duplicate-mechanism collapse inside the synthesis itself, with planted-mutant control",
    question_or_target=(
        "Question (spec lens 3, " + SPEC + ":11092): do two synthesis findings or recommendations "
        "describe the SAME mechanism in different wording? Target: run two mechanically different "
        "detectors (lexical near-duplicate and embedding similarity) over the synthesis findings, "
        "collapse confirmed duplicates, and prove both detectors on planted mutants. Distinct "
        "target from CC-0020 (duplicate WORK UNITS) and AUD-0069 (duplicate OPTION CARDS): those "
        "guard the input catalogs, this guards the output narrative."),
    inputs=[
        "the merged synthesis finding set after SYN-0011 adjudication",
        CC + "/CLAIM-REGISTRY.json canonical_mechanism field (the dedup key of record)",
        "tools/command-center/ dedup helpers if CC-0020 shipped one",
    ],
    dependencies=["SYN-0011", "CC-0020"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "mechanism-extractor"},
    tool_permissions=T["rw"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0017.mechanism-dedup.json",
    output_schema=CC + "/schema/dedup-report.schema.json",
    evidence_requirement=(
        "Both detectors' scores per candidate pair, the agreement between them, and the collapse "
        "decisions. Planted mutants must include an exact rename, a paraphrase, and a "
        "one-parameter fork; report which detector caught which. Lexical-only coverage must be "
        "disclosed inline -- a full rewrite of the same mechanism scores like a distinct entry."),
    tests_required=[
        "planted mutant control: rename / paraphrase / parameter-fork all detected",
        "both-states: two genuinely distinct findings must NOT be collapsed",
        "test_collapse_preserves_the_union_of_evidence_anchors_from_both_members",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0017",
                             "all three planted mutants were caught and no distinct pair was collapsed"),
    retry_policy=RT["bounded3"],
    failure_classification=["duplicate-mechanism", "over-collapse", "lexical-only-coverage-undisclosed"],
    owner_approval_required=False,
)

add(
    id="SYN-0018",
    title="Stale-evidence re-validation across the SHA delta between claim capture and report time",
    question_or_target=(
        "Question (spec lens 4, " + SPEC + ":11093): for every evidence anchor recorded earlier in "
        "the program, does it still point at the same content at the report-time SHA? Target: "
        "re-resolve each anchor at both SHAs and classify STABLE | LINE-MOVED | CONTENT-CHANGED | "
        "FILE-GONE. This is a TEMPORAL check across two commits and is distinct from AUD-0037, "
        "which asks statically whether an anchor says what is claimed. Read blobs with "
        "git cat-file -p <rev>:<path>, never git archive, which returns CRLF worktree bytes on "
        "this box."),
    inputs=[
        CC + "/CLAIM-REGISTRY.json (anchor + capture SHA per claim)",
        "the report-time SHA recorded in " + CC + "/STATUS.md",
        "rules/common/windows-shell.md section 8b (the blob-vs-archive recipe)",
    ],
    dependencies=["AUD-0037", "SYN-0011"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "evidence-auditor"},
    tool_permissions=T["git"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0018.json",
    output_schema=CC + "/schema/evidence-decay-report.schema.json",
    evidence_requirement=(
        "Per anchor: capture SHA, report SHA, the byte range read at each, and the class. Report "
        "the four class counts with the total as denominator. The recipe used must be named in "
        "the receipt; a run that used git archive is invalid by construction on this platform."),
    tests_required=[
        "recipe control: git cat-file and git show agree byte-for-byte; git archive differs by CRLF",
        "planted drift: insert a line above a known anchor -> must classify LINE-MOVED not STABLE",
        "planted rewrite: change the anchored line -> must classify CONTENT-CHANGED",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0018",
                             "the recipe control passed and all four class counts carry the total denominator"),
    retry_policy=RT["zero"],
    failure_classification=["stale-evidence", "wrong-blob-recipe", "crlf-artifact", "anchor-file-gone"],
    owner_approval_required=False,
)

add(
    id="SYN-0019",
    title="Report-time artifact-manifest verification gate that blocks the completion report",
    question_or_target=(
        "Implementation target: the spec's hardest Phase 14 requirement -- 'The final synthesis "
        "agent must verify the artifact manifest on disk before writing the completion report' "
        "(" + SPEC + ":11098). Build it as a BLOCKING gate in the report writer with a freshness "
        "window: existence plus non-empty plus minimum size plus schema parse plus content hash, "
        "re-run within N minutes of the report write. Distinct from AUD-0036's bidirectional "
        "reconciliation, which is a point-in-time audit that DECAYS -- a green reconcile from "
        "yesterday is not a control for today's write."),
    inputs=[
        CC + "/ARTIFACT-MANIFEST.json",
        "AUD-0036 reconciliation output (the prior, now-decaying audit)",
        CC + "/schema/ (all schemas the manifest entries claim to satisfy)",
        SPEC + ":11098 and " + SPEC + ":10631-10646 (the 12 completion conditions)",
    ],
    dependencies=["AUD-0036", "CC-0009", "SYN-0041"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "gate-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0019.json",
    output_schema=CC + "/schema/manifest-verification.schema.json",
    evidence_requirement=(
        "The gate's exit code, the freshness window in seconds, the wall-clock gap between "
        "verification and report write, and the per-entry table (path, bytes, hash, parse verdict). "
        "Windows reserved device names need the extended-length prefix; a path that cannot be "
        "stat-ed must be FAILED, never skipped."),
    tests_required=[
        "planted deletion: remove one manifest-listed artifact -> the report write must be BLOCKED",
        "planted truncation: zero a listed artifact -> blocked on the minimum-size condition",
        "staleness control: a verification older than the window must not authorise a write",
        "both-states: a clean manifest must permit the write with exit 0",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0019",
                             "all three planted-defect runs BLOCKED and the clean run PERMITTED, with timestamps"),
    retry_policy=RT["zero"],
    failure_classification=["missing-artifact", "decayed-green", "reserved-device-name",
                            "gate-skipped-unreadable-path"],
    owner_approval_required=False,
)

add(
    id="SYN-0020",
    title="Docs-versus-code parity: execute every documented command and diff stated behaviour against measured",
    question_or_target=(
        "Question (spec lens 6, " + SPEC + ":11095, and stopping condition 12 'docs and code "
        "agree'): which documented commands fail to run, and which documented behaviours "
        "contradict measured behaviour? Target: extract every fenced command from the shipped "
        "docs, run it in a clean shell, and separately diff prose behaviour statements against "
        "test results. The known live instance is RELEASE-CHECKLIST.md prescribing verification "
        "'against the LF blob (git archive)', which returns CRLF on this box -- a doc that "
        "prescribes a wrong recipe for the very trap it warns about."),
    inputs=[
        "RELEASE-CHECKLIST.md, RUNBOOK.md, README and the plugin/marketplace docs",
        "Phase 10 test results (bucket B08) as the behavioural ground truth",
        SPEC + ":11024 (documentation command tests) and " + SPEC + ":11389",
    ],
    dependencies=["B08", "CC-0006"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "docs-conformance-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="local-serialized",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0020.docs-code-parity.json",
    output_schema=CC + "/schema/conformance-report.schema.json",
    evidence_requirement=(
        "Per extracted command: the doc anchor, the exact invocation, exit code, and first lines "
        "of output. Per behaviour statement: the doc anchor, the test id that measures it, and "
        "AGREE | CONTRADICT | UNTESTED. The RELEASE-CHECKLIST git-archive line must appear as "
        "CONTRADICT or this unit's extractor is broken."),
    tests_required=[
        "known-present control: the git-archive recipe line is extracted and marked CONTRADICT",
        "test_command_extractor_skips_illustrative_blocks_marked_noexec (use-vs-mention)",
        "test_untested_statements_are_reported_as_UNTESTED_not_as_AGREE",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0020",
                             "the known-present control fired and no statement is silently classed AGREE without a test id"),
    retry_policy=RT["two_strikes"],
    failure_classification=["docs-code-mismatch", "wrong-recipe-in-docs", "untested-counted-as-agree",
                            "shell-quoting-corrupted-command"],
    owner_approval_required=False,
)

add(
    id="SYN-0021",
    title="Completion-claim census: every done claim joined to the shared predicate verdict",
    question_or_target=(
        "Question (spec lens 7, " + SPEC + ":11096): which statements anywhere in the program "
        "assert completion -- done, complete, shipped, closed, verified -- WITHOUT the shared "
        "12-condition predicate returning true for the thing they describe? Target: extract the "
        "claim population, join each to the predicate verdict from TST-0001's oracle, and "
        "downgrade every unbacked claim in the final report. 'Exit code zero alone is never "
        "success. A plausible digest is not a receipt.' (" + SPEC + ":10646)"),
    inputs=[
        "TST-0001 conformance oracle for the 12-condition predicate and CC-0003's reducer",
        CC + "/events/EVENTS.jsonl and all receipts under " + CC + "/receipts/",
        "the candidate syntheses and STATUS.md",
    ],
    dependencies=["CC-0003", "TST-0001", "SYN-0008"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "completion-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0021.completion-census.json",
    output_schema=CC + "/schema/completion-census.schema.json",
    evidence_requirement=(
        "Per completion claim: the text, its anchor, the subject it claims complete, the predicate "
        "verdict with the failing condition number when false, and the downgrade applied. Report "
        "the backed / unbacked split with the total as denominator."),
    tests_required=[
        "planted claim: a receipt asserting SUCCESS with a missing artifact must be reported unbacked",
        "test_predicate_verdict_comes_from_the_shared_reducer_not_a_local_reimplementation",
        "test_extractor_distinguishes_a_completion_claim_from_a_completion_REQUIREMENT (use-vs-mention)",
    ],
    reviewer_requirement=R["notauthor"],
    completion_sentinel=sent("SYN-0021",
                             "every completion claim carries a predicate verdict and the split has a denominator"),
    retry_policy=RT["zero"],
    failure_classification=["completion-claim-unbacked", "local-predicate-reimplementation",
                            "use-vs-mention"],
    owner_approval_required=False,
)

# =============================================================================
# D. STALE PREMISE, CONFORMITY, AND SELF-AUDIT (SYN-0022 .. SYN-0027)
# =============================================================================

add(
    id="SYN-0022",
    title="Re-probe every briefed ground-truth fact with a mechanically different probe",
    question_or_target=(
        "Question: which facts the program treated as pinned ground truth are no longer true, or "
        "were never true? Target: re-probe each briefed fact using a DIFFERENT shell, a different "
        "data field, or a different measurement -- re-running the original probe does not count "
        "and must not be reported as CONFIRMED. Precedent on this estate: 4 briefed 'VERIFIED "
        "GROUND TRUTH' facts were false in one run, and 2 agents 'CONFIRMED' a false fact by "
        "re-running the orchestrator's own broken detector. Distinct from SYN-0018, where the "
        "anchor moved; here the anchor resolves perfectly and the FACT is stale. Reuse CNF-0006's "
        "probe-fingerprint tuple (tool, shell, data field, measurement kind) rather than "
        "re-inventing it: that unit applies it to the confirmation corpus, this one applies it to "
        "the briefed premises."),
    inputs=[
        "the pinned ground-truth block issued to every unit in this program",
        CC + "/BASELINE-SNAPSHOT.json (what was measured, and with which probe)",
        "CNF-0006's probe-fingerprint implementation",
        "rules/common/single-signal-verification.md",
    ],
    dependencies=["SYN-0006", "CNF-0006"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "stale-premise-refuter"},
    tool_permissions=T["xv"],
    execution_substrate="local-serialized",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0022.premise-reprobe.json",
    output_schema=CC + "/schema/reprobe-record.schema.json",
    evidence_requirement=(
        "Per fact: the ORIGINAL probe (source), the NEW mechanically different probe (verifier), "
        "both outputs verbatim, and the verdict CONFIRMED | REFUTED | NOT-CHECKED. A record whose "
        "source probe is empty is a violation, not an independent pair -- an undeclared source is "
        "zero signals, not one."),
    tests_required=[
        "test_source_and_verifier_probe_fingerprints_differ (a rerun is rejected)",
        "test_a_record_with_an_empty_source_probe_is_a_VIOLATION_not_a_pass",
        "known-refuted control: the M-NN collision fact must come back REFUTED-AS-BRIEFED",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0022",
                             "every record declares both probes and no verifier duplicates its source"),
    retry_policy=RT["no_reroll"],
    failure_classification=["stale-premise", "same-probe-rerun", "undeclared-source-probe",
                            "evidence-tag-theatre"],
    owner_approval_required=False,
)

add(
    id="SYN-0023",
    title="Convergence attribution: separate corroboration from conformity",
    question_or_target=(
        "Question: for each conclusion the independent syntheses agreed on, is the agreement "
        "traceable to INDEPENDENT source lineage, or to one shared upstream artifact every agent "
        "read? Target: label each agreed conclusion CORROBORATED (>=2 independent lineages) or "
        "CONFORMITY (one shared ancestor), because N agents reading the same stale input is one "
        "lens, not N. Distinct from SYN-0010, which measures the amount of agreement without "
        "explaining it."),
    inputs=[
        CC + "/receipts/SYN-0010.json (the agreement matrix supplies the agreed set)",
        CC + "/CLAIM-REGISTRY.json source-lineage edges",
        CC + "/synthesis/SYN-0008.candidate-syntheses.json partition manifests",
    ],
    dependencies=["SYN-0010", "SYN-0012"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "independence-analyst"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0023.json",
    output_schema=CC + "/schema/convergence-attribution.schema.json",
    evidence_requirement=(
        "Per agreed conclusion: the lineage set per agent, the lowest common ancestor artifact if "
        "any, and the label. Report the CONFORMITY share of the agreed set -- a high agreement "
        "coefficient with a high conformity share is a warning, not a result."),
    tests_required=[
        "planted conformity: feed all agents one artifact carrying a false claim -> the agreed "
        "claim must be labelled CONFORMITY",
        "planted corroboration: two disjoint partitions supporting one conclusion -> CORROBORATED",
        "test_lineage_join_uses_artifact_identity_not_title_similarity",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0023",
                             "both planted cases labelled correctly and the conformity share is published"),
    retry_policy=RT["zero"],
    failure_classification=["conformity-read-as-corroboration", "shared-stale-ancestor",
                            "lineage-join-by-title"],
    owner_approval_required=False,
)

add(
    id="SYN-0024",
    title="Negative and contradictory evidence survival audit",
    question_or_target=(
        "Question: how much of the negative, null and contradictory evidence collected in Phase 2 "
        "and Phase 10 survives into the synthesis? The spec is explicit that the workflow 'must "
        "preserve negative and contradictory evidence rather than optimizing only for favorable "
        "results' (" + SPEC + ":11278). Target: count negative-result records at source and in the "
        "synthesis, and require a written reason for every one that did not survive. A synthesis "
        "that reads as uniformly positive against a corpus containing refutations is suppressing, "
        "not summarising."),
    inputs=[
        "Phase 2 negative-result and contradiction-hunt outputs (bucket B03)",
        "Phase 10 red test results and mutation survivors (bucket B08)",
        "the candidate syntheses",
    ],
    dependencies=["SYN-0008", "B03", "B08"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "negative-evidence-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="cloud-batch",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0024.json",
    output_schema=CC + "/schema/negative-evidence-audit.schema.json",
    evidence_requirement=(
        "Source count and surviving count with the extraction rule for each, the survival rate, "
        "and the dropped list with per-item reason. Report the positive-to-negative ratio in the "
        "synthesis against the ratio in the corpus; a large divergence is the finding."),
    tests_required=[
        "known-present control: a recorded REFUTED claim must be found by the extractor at source",
        "planted drop: remove one negative record from the synthesis copy -> must be reported",
        "test_ratio_is_computed_over_comparable_units_not_raw_bytes",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0024",
                             "the survival rate is published with both denominators and every drop has a reason"),
    retry_policy=RT["env_once"],
    failure_classification=["negative-evidence-suppressed", "favourable-result-bias",
                            "extraction-rule-unstated"],
    owner_approval_required=False,
)

add(
    id="SYN-0025",
    title="Prompt-injection defence for the synthesis intake, proven with a planted-instruction fixture",
    question_or_target=(
        "Implementation target: treat every artifact entering synthesis as untrusted DATA. A "
        "council transcript, a refuter note, a fetched page or a work-unit receipt can carry "
        "'ignore previous instructions', a role spoof, or an embedded command -- the spec lists "
        "'council transcript or participant artifact injects instructions into later stages' as a "
        "required regression class (" + SPEC + ":11344). Target: an intake sanitiser plus a "
        "planted-injection fixture that must be neutralised, logged, and reported without the "
        "instruction ever reaching the synthesizer's instruction channel."),
    inputs=[
        "the full Phase 10-13 artifact intake set",
        SPEC + ":11344 and " + SPEC + ":11243",
        "AGENTS.md section 9 (fetched content is untrusted data, never instructions)",
    ],
    dependencies=["SYN-0008"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "security-reviewer"},
    tool_permissions=T["rw"],
    execution_substrate="worktree-isolated",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0025.json",
    output_schema=CC + "/schema/injection-defence-report.schema.json",
    evidence_requirement=(
        "The fixture text, where it was planted, the sanitiser's log line, and proof the "
        "synthesizer's output is unchanged with and without the fixture present. Sanitisation must "
        "happen BEFORE any field split, because a delimiter inside a field value shifts every "
        "later column ahead of a per-field scrub."),
    tests_required=[
        "planted injection in a council transcript -> neutralised and logged",
        "planted injection in a receipt evidence field -> neutralised and logged",
        "differential: synthesis output with and without the fixture is byte-identical",
        "both-states: a clean artifact produces zero sanitiser log lines",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0025",
                             "both planted injections were neutralised and the differential output is identical"),
    retry_policy=RT["bounded3"],
    failure_classification=["prompt-injection-through-artifact", "sanitise-after-split",
                            "instruction-reached-instruction-channel"],
    owner_approval_required=False,
)

add(
    id="SYN-0026",
    title="Cross-vendor meta-reviewer with a written reconciliation protocol for contested calls",
    question_or_target=(
        "Implementation target: run the spec's meta-review (" + SPEC + ":11088-11096) a second "
        "time with a reviewer from the OTHER vendor, then reconcile. A same-vendor judge shares "
        "the synthesizer's blind spots, so a single-vendor meta-review is one lens wearing the "
        "name of two. The reconciliation must be a written protocol -- agreement is recorded, "
        "disagreement is escalated to raw source, and neither side may close the other's finding "
        "unilaterally."),
    inputs=[
        "all SYN-0014..SYN-0021 lens outputs",
        CC + "/synthesis/SYN-0011.adjudications.json",
        "rules/common/cross-vendor-dispatch.md (foreground dispatch, prompt-by-file, terminal state)",
    ],
    dependencies=["SYN-0014", "SYN-0015", "SYN-0016", "SYN-0017", "SYN-0018", "SYN-0020", "SYN-0021"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "cross-vendor-meta-reviewer"},
    tool_permissions=T["xv"],
    execution_substrate="local-serialized",
    timeout_seconds=10800,
    output_path=CC + "/synthesis/SYN-0026.cross-vendor-meta-review.json",
    output_schema=CC + "/schema/meta-review-finding.schema.json",
    evidence_requirement=(
        "Per lens: the second-vendor verdict, the first-vendor verdict, AGREE | CONTEST, and for "
        "every CONTEST the raw anchor read to settle it. Dispatch evidence must show exit 0 AND a "
        "non-empty parsed output file; a progress stream is not a result."),
    tests_required=[
        "test_reviewer_vendor_differs_from_every_author_vendor_per_lens",
        "test_no_contested_finding_is_closed_by_one_side_alone",
        "dispatch control: a deliberately severed run must classify FAILED, not SUCCESS",
    ],
    reviewer_requirement=R["notauthor"],
    completion_sentinel=sent("SYN-0026",
                             "every lens has a second-vendor verdict and every CONTEST cites a raw anchor"),
    retry_policy=RT["two_strikes"],
    failure_classification=["single-vendor-meta-review", "severed-stream", "unilateral-closure",
                            "codex-exit-<n>"],
    owner_approval_required=False,
)

add(
    id="SYN-0027",
    title="Self-application control: run every meta-review lens over the meta-review's own output",
    question_or_target=(
        "Question: does the meta-review commit the defects it audits? On this estate an audit "
        "agent reproduced the exact failure it was documenting -- reading a blocked command's "
        "content instead of its verb -- and shipped the opposite of a sibling's correct verdict. "
        "Target: apply SYN-0014, SYN-0015, SYN-0017 and SYN-0022 to the meta-review artifacts "
        "themselves, use-vs-mention aware, because a document ABOUT a defect necessarily contains "
        "that defect's text. Distinct from SYN-0040, which tests whether the gates FIRE at all."),
    inputs=[
        "all SYN-0014..SYN-0026 outputs (the meta-review corpus becomes the subject)",
        "the same lens implementations, unmodified",
        "rules/common/single-signal-verification.md (auditors are not exempt)",
    ],
    dependencies=["SYN-0026"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "self-audit-engineer"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0027.json",
    output_schema=CC + "/schema/self-audit-report.schema.json",
    evidence_requirement=(
        "Per lens: findings raised against the meta-review itself, with the same anchor discipline. "
        "The use-vs-mention discriminator must be reported per finding (USE or MENTION) and a "
        "MENTION must never be counted as a defect."),
    tests_required=[
        "use-vs-mention control: a lens document quoting 'every unit passes' must not self-flag",
        "known-present control: plant a real unanchored certainty claim in a lens output -> must fire",
        "test_lens_implementations_are_byte_identical_to_the_ones_used_upstream",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0027",
                             "the use-vs-mention control passed and every finding carries a USE or MENTION label"),
    retry_policy=RT["fresh"],
    failure_classification=["auditor-reproduced-the-defect", "use-vs-mention", "lens-drift-between-runs"],
    owner_approval_required=False,
)

# =============================================================================
# E. COVERAGE AND TRACEABILITY CLOSURE (SYN-0028 .. SYN-0034)
# =============================================================================

add(
    id="SYN-0028",
    title="Option-id closure: every selected option implemented, superseded, or rejected with owner reasoning",
    question_or_target=(
        "Question (stopping condition 1, " + SPEC + ":11378): is every selected option id in "
        "exactly one terminal state -- IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING? "
        "Target: resolve every id through the namespace registry first, because a bare M-NN "
        "resolves to two unrelated cards and three further namespaces exist on disk, then join to "
        "the decision trace. An id counted twice under two meanings is a false coverage claim in "
        "both directions."),
    inputs=[
        CC + "/OPTION-ID-RESOLUTION.json and CC-0021's namespace registry",
        CC + "/synthesis/SYN-0005.decision-trace.json",
        "the corpus 07-OPTION-UNIVERSE.json and 13-ARCHITECTURE-CANDIDATES.md",
    ],
    dependencies=["CC-0021", "CC-0023", "SYN-0005"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "coverage-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0028.option-closure.json",
    output_schema=CC + "/schema/option-closure.schema.json",
    evidence_requirement=(
        "Per option id: the resolved namespace, the terminal state, the anchor proving it, and for "
        "REJECTED the owner-approval anchor. Report the three state counts against the selected-set "
        "size, plus the count of ids that remain namespace-ambiguous and are therefore NOT-CHECKED."),
    tests_required=[
        "test_no_bare_ambiguous_token_is_assigned_a_state",
        "test_states_are_mutually_exclusive_and_exhaustive_over_the_selected_set",
        "known-present control: an id known to be implemented must resolve to IMPLEMENTED with its anchor",
    ],
    reviewer_requirement=R["owner"],
    completion_sentinel=sent("SYN-0028",
                             "the three state counts plus the ambiguous count sum to the selected-set size"),
    retry_policy=RT["no_reroll"],
    failure_classification=["silently-dropped-option", "ambiguous-id-double-counted",
                            "rejection-without-owner-reasoning"],
    owner_approval_required=True,
)

add(
    id="SYN-0029",
    title="Owner-requirement closure: exactly one disposition label per extracted requirement",
    question_or_target=(
        "Question: does the final report state a disposition for every owner requirement and "
        "numeric floor extracted in CC-0024? Target: join the requirement register to the report "
        "and assign exactly one of VERIFIED | INFERRED | UNVERIFIED | REJECTED | DEFERRED to each; "
        "a requirement with no label has DISAPPEARED, which Phase 13 names explicitly ('what owner "
        "requirements disappeared', " + SPEC + ":11073). Distinct from CC-0024, which EXTRACTS and "
        "binds requirements to units; this unit closes them against the outcome."),
    inputs=[
        "CC-0024's requirement register (requirement text, spec anchor, bound unit ids)",
        CC + "/synthesis/SYN-0041 report draft",
        "Phase 13 blind-spot findings (bucket B11)",
    ],
    dependencies=["CC-0024", "B11", "SYN-0041"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "requirements-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0029.json",
    output_schema=CC + "/schema/requirement-closure.schema.json",
    evidence_requirement=(
        "A row per requirement: text, spec anchor, label, and the report anchor carrying the label. "
        "Report unlabelled count against the register size. Zero unlabelled with no register size "
        "stated is NOT-CHECKED."),
    tests_required=[
        "test_exactly_one_label_per_requirement (a double-labelled row fails)",
        "planted omission: delete one requirement from the report -> must be reported unlabelled",
        "test_label_vocabulary_is_the_declared_five",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0029",
                             "every register row carries exactly one label with a report anchor"),
    retry_policy=RT["zero"],
    failure_classification=["disappeared-requirement", "double-labelled-row", "register-size-unstated"],
    owner_approval_required=False,
)

add(
    id="SYN-0030",
    title="Four-way referential join across catalog, manifest, test registry and claim registry",
    question_or_target=(
        "Question: where do the four program registries disagree about what exists? Target: a "
        "four-way join over WORK-UNIT-CATALOG.json, ARTIFACT-MANIFEST.json, TEST-REGISTRY.json and "
        "CLAIM-REGISTRY.json reporting orphans in EVERY direction -- a unit with no artifact, an "
        "artifact with no unit, a test bound to no claim, a claim covered by no test. Distinct "
        "from SYN-0019, which compares one registry against the filesystem; this compares "
        "registries against each other."),
    inputs=[
        CC + "/WORK-UNIT-CATALOG.json, " + CC + "/ARTIFACT-MANIFEST.json",
        CC + "/TEST-REGISTRY.json, " + CC + "/CLAIM-REGISTRY.json",
        "CC-0014's test-to-claim-to-unit binding, if shipped",
    ],
    dependencies=["CC-0009", "CC-0014", "SYN-0019"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "registry-integrity-engineer"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=2700,
    output_path=CC + "/receipts/SYN-0030.json",
    output_schema=CC + "/schema/referential-integrity.schema.json",
    evidence_requirement=(
        "Eight directed orphan counts (four registries, both directions per adjacent pair) each "
        "with its denominator, and the id lists for any non-zero count. A single 'all consistent' "
        "sentence without the eight counts does not satisfy this field."),
    tests_required=[
        "planted orphan in each of the four registries -> four separate reports",
        "both-states: a consistent fixture yields eight zeros",
        "test_join_keys_are_ids_not_titles",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0030",
                             "all eight directed counts are published with denominators"),
    retry_policy=RT["zero"],
    failure_classification=["registry-orphan", "join-by-title", "aggregate-hides-direction"],
    owner_approval_required=False,
)

add(
    id="SYN-0031",
    title="Re-count every numeric floor at report time with an independent extractor",
    question_or_target=(
        "Question (stopping conditions 16-19, " + SPEC + ":11393-11396): do the floors still hold "
        "when counted at report time by an extractor written independently of the one that "
        "produced the Prompt One audit? Floors: >=160 workflow candidates, >=96 blueprints, >=48 "
        "council protocols, >=64 presets, >=2048 work units, >=160 platform options. Target: an "
        "independent recount, and where the two extractors disagree, resolve from the documents. "
        "Restating Prompt One's numbers is not a measurement."),
    inputs=[
        CC + "/PROMPT-ONE-FLOOR-AUDIT.json (the prior count, treated as a claim not a fact)",
        "the corpus 07/08/09/12 documents and their JSON twins",
        "the merged WORK-UNIT-CATALOG.json after all slices land",
    ],
    dependencies=["CC-0008", "CC-0024"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "independent-counter"},
    tool_permissions=T["xv"],
    # credentialed cross-vendor dispatch -> local and serialized per the scaling
    # doctrine (:10575). Caught by _verify_SYN_1.py, which flagged this as cloud-batch.
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0031.json",
    output_schema=CC + "/schema/floor-recount.schema.json",
    evidence_requirement=(
        "Per floor: the prior count, this count, the extraction rule verbatim, the first three and "
        "last three ids, and AGREE | DISAGREE. Two disjoint regexes must be proven silent on each "
        "other's items where two counts share a document, and the protocol/preset pair must be "
        "checked for an empty intersection rather than summed blind."),
    tests_required=[
        "test_two_extractors_agree_or_the_disagreement_is_resolved_from_the_document",
        "test_protocol_and_preset_id_sets_are_disjoint",
        "known-present control: the first and last id of each set are quoted from the document",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0031",
                             "every floor has both counts and an explicit AGREE or resolved DISAGREE"),
    retry_policy=RT["env_once"],
    failure_classification=["restated-not-measured", "regex-cross-matching", "max-of-two-lists-error"],
    owner_approval_required=False,
)

add(
    id="SYN-0032",
    title="Bucket and phase representation audit, including the unfunded Phase 16",
    question_or_target=(
        "Question: is every allocation bucket and every one of the 21 phases represented in the "
        "synthesis, or did a whole lane vanish? Target: join the 13 buckets and 21 phases against "
        "the synthesis content and the receipt inventory; a bucket with receipts but no synthesis "
        "presence is a silent drop. Phase 16 is the pinned special case -- PHASE-GRAPH.json records "
        "it as the only phase with NO allocation bucket, so its coverage must be measured, not "
        "assumed."),
    inputs=[
        CC + "/PHASE-GRAPH.json allocation_buckets and phases",
        "the receipt inventory under " + CC + "/receipts/ grouped by id prefix",
        "the candidate syntheses",
    ],
    dependencies=["SYN-0008", "CC-0016"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "coverage-auditor"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=1800,
    output_path=CC + "/receipts/SYN-0032.json",
    output_schema=CC + "/schema/coverage-map.schema.json",
    evidence_requirement=(
        "A 13-row bucket table and a 21-row phase table, each with receipt count, synthesis "
        "mention count, and verdict REPRESENTED | RECEIPTS-ONLY | ABSENT. Phase 16 must carry an "
        "explicit funded-by note naming the units that actually cover it."),
    tests_required=[
        "test_all_13_buckets_and_all_21_phases_appear_as_rows (no row may be omitted)",
        "planted absence: strip one bucket from the synthesis copy -> reported RECEIPTS-ONLY",
        "test_mention_counting_ignores_the_table_of_contents (use-vs-mention)",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0032",
                             "both tables are complete and Phase 16 carries a funded-by note"),
    retry_policy=RT["bounded3"],
    failure_classification=["silently-dropped-bucket", "unfunded-phase", "use-vs-mention"],
    owner_approval_required=False,
)

add(
    id="SYN-0033",
    title="Cross-phase contradiction sweep: research versus test result versus confirmer verdict",
    question_or_target=(
        "Question: which claims from different phases contradict each other and were never "
        "reconciled -- a Phase 2 research finding versus a Phase 10 measurement, a Phase 5 "
        "implementation note versus a Phase 11 confirmer verdict? Target: apply the Phase 1 "
        "contradiction-edge schema ACROSS phase boundaries, which intra-phase dedup never sees, "
        "and route each surviving contradiction to raw-source adjudication."),
    inputs=[
        CC + "/CLAIM-REGISTRY.json (contradiction edges plus the phase field per claim)",
        "Phase 10 measurement receipts and Phase 11 confirmer verdicts (buckets B08, B09)",
        CC + "/synthesis/SYN-0011.adjudications.json (do not re-litigate what is settled)",
    ],
    dependencies=["CC-0019", "SYN-0011", "B08", "B09"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "contradiction-analyst"},
    tool_permissions=T["ro"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0033.cross-phase-contradictions.json",
    output_schema=CC + "/schema/contradiction-report.schema.json",
    evidence_requirement=(
        "Per contradiction: both claims verbatim with anchors, their phases, whether either was "
        "already adjudicated, and the settling probe. Report the count of cross-phase pairs "
        "examined so a zero has a denominator."),
    tests_required=[
        "planted cross-phase contradiction -> detected",
        "test_intra_phase_pairs_are_excluded_from_this_sweep (no double reporting with Phase 1 dedup)",
        "test_already_adjudicated_pairs_are_marked_SETTLED_not_reopened",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0033",
                             "the examined-pair count is published and every open contradiction names a settling probe"),
    retry_policy=RT["two_strikes"],
    failure_classification=["cross-phase-contradiction", "double-reported-with-phase1",
                            "zero-without-denominator"],
    owner_approval_required=False,
)

# NOTE: this slot originally held a residual-unknown closure unit. A concurrent
# sibling slice landed BLD-0029 ("Unknowns-register closure: a named settling
# experiment and an owner-visible impact per unknown", phase 13) which is the SAME
# mechanism -- token-Jaccard 0.417, the highest cross-slice score in the sweep. It
# was re-targeted rather than shipped as a duplicate; Phase 14 consumes BLD-0029's
# closure instead (see SYN-0041, SYN-0043, SYN-0048 inputs).
add(
    id="SYN-0034",
    title="Improvement ledger: turn benchmark evidence into a per-change verdict and one derived net verdict",
    question_or_target=(
        "Question (stopping condition 8, " + SPEC + ":11385, and objective 2 'verified "
        "improvement', " + SPEC + ":10490): for every change this program made, what is the "
        "measured baseline, the measured post value, the delta, and the verdict IMPROVED | "
        "NEUTRAL | REGRESSED | UNMEASURED -- and what NET verdict do those rows derive? The spec "
        "is explicit that 'No improvement is retained merely because an agent produced it' "
        "(" + SPEC + ":11150). Distinct from bucket B08, which RUNS the benchmarks, and from "
        "SYN-0035, which calibrates confidence bands rather than measuring effect size."),
    inputs=[
        CC + "/BASELINE-SNAPSHOT.json (the pre-change measurements captured in Phase 0)",
        "Phase 10 benchmark and latency receipts (bucket B08)",
        CC + "/synthesis/SYN-0005.decision-trace.json (the change inventory)",
        SPEC + ":11143-11150 and " + SPEC + ":11385",
    ],
    dependencies=["B08", "B09", "SYN-0005", "SYN-0021"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "benchmark-synthesist"},
    tool_permissions=T["calc"],
    execution_substrate="cloud-batch",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0034.improvement-ledger.json",
    output_schema=CC + "/schema/improvement-ledger.schema.json",
    evidence_requirement=(
        "Per change: baseline value with its capture anchor, post value with its anchor, delta, "
        "and either an interval or the explicit statement that n is too small for one. Publish "
        "the four verdict counts against the change total. A change whose baseline was never "
        "captured is UNMEASURED and is counted separately -- folding it into NEUTRAL manufactures "
        "a clean result out of a missing measurement."),
    tests_required=[
        "test_a_change_with_no_captured_baseline_is_UNMEASURED_not_NEUTRAL",
        "planted regression: inject a metric that worsened -> REGRESSED in both its row and the net",
        "test_net_verdict_is_derived_from_the_rows_and_recomputable_from_the_published_table",
        "test_regressions_are_listed_even_when_the_net_is_positive",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0034",
                             "every change row carries a verdict and the net verdict recomputes from the published rows"),
    retry_policy=RT["env_once"],
    failure_classification=["unmeasured-counted-as-neutral", "regression-hidden-by-net",
                            "baseline-never-captured", "benchmark-gaming"],
    owner_approval_required=False,
)

# =============================================================================
# F. CALIBRATION AND PROCESS QUALITY (SYN-0035 .. SYN-0040)
# =============================================================================

add(
    id="SYN-0035",
    title="Program-wide confidence calibration: band asserted versus outcome observed",
    question_or_target=(
        "Question: were the confidence bands used across the program calibrated? Target: join "
        "every banded claim to its later verification outcome and compute hit-rate per band plus "
        "an overall proper score, so the report can state whether 'likely' meant 55-80 percent in "
        "practice. The measured estate precedent is stark -- agents self-rated high confidence on "
        "89 percent of findings while 42 percent of those checked were REFUTED."),
    inputs=[
        CC + "/CLAIM-REGISTRY.json (band at capture time)",
        "Phase 11 confirmer verdicts and Phase 12 refuter verdicts (buckets B09, B10)",
        "AGENTS.md section 7 band definitions (the numeric intervals under test)",
    ],
    dependencies=["B09", "B10", "SYN-0014"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "calibration-analyst"},
    tool_permissions=T["calc"],
    execution_substrate="cloud-batch",
    timeout_seconds=3600,
    output_path=CC + "/synthesis/SYN-0035.calibration-report.json",
    output_schema=CC + "/schema/calibration-report.schema.json",
    evidence_requirement=(
        "A per-band table: n, observed hit rate, the band's nominal interval, and whether the "
        "observed rate falls inside it. Include the proper score and the count of banded claims "
        "that were never adjudicated (these are excluded from the rate and must be reported "
        "separately, not silently dropped)."),
    tests_required=[
        "test_unadjudicated_claims_are_excluded_and_counted_not_imputed",
        "synthetic control: a perfectly calibrated fixture scores at its optimum",
        "test_band_intervals_come_from_the_written_definition_not_from_the_data",
    ],
    reviewer_requirement=R["stat"],
    completion_sentinel=sent("SYN-0035",
                             "every band row states n and the unadjudicated count is reported separately"),
    retry_policy=RT["env_once"],
    failure_classification=["miscalibrated-band", "imputed-outcome", "n-too-small-unstated"],
    owner_approval_required=False,
)

add(
    id="SYN-0036",
    title="Producer reliability weighting from refutation survival, with an anti-silencing guard",
    question_or_target=(
        "Question: which producers -- agent role, vendor, substrate -- generated claims that "
        "survived adversarial refutation, and at what rate? Target: a reliability table used to "
        "WEIGHT future synthesis and to target re-verification, with a hard guard that a low "
        "weight may never suppress a finding. The measured failure to avoid: scoring agents on "
        "output volume, where the best verification agent in the corpus sits near the bottom on "
        "kilobytes per token."),
    inputs=[
        "Phase 12 refuter verdicts joined to claim authorship (buckets B10, B09)",
        CC + "/WORK-UNIT-CATALOG.json assigned_model_vendor_role per unit",
        CC + "/events/EVENTS.jsonl",
    ],
    dependencies=["SYN-0035", "B10"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "reliability-analyst"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=2700,
    output_path=CC + "/receipts/SYN-0036.json",
    output_schema=CC + "/schema/reliability-weighting.schema.json",
    evidence_requirement=(
        "Per producer: claims filed, refuted, survived, survival rate with a confidence interval, "
        "and n. A producer with n below the stated minimum is reported as INSUFFICIENT-N, never "
        "given a weight. State explicitly that volume is not an input to the score."),
    tests_required=[
        "test_no_finding_is_removed_or_downranked_by_weighting (the anti-silencing guard)",
        "test_volume_metrics_are_absent_from_the_score_inputs",
        "test_small_n_producers_are_labelled_not_scored",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0036",
                             "the anti-silencing guard test passed and every low-n producer is labelled"),
    retry_policy=RT["zero"],
    failure_classification=["weighting-silenced-a-finding", "volume-scored-as-quality",
                            "insufficient-n-scored-anyway"],
    owner_approval_required=False,
)

add(
    id="SYN-0037",
    title="Reviewer-independence audit: no self-review and no circular review chain",
    question_or_target=(
        "Question: did any agent review its own output, and does any review chain close into a "
        "cycle (A reviews B, B reviews A)? Target: build the authorship-to-review bipartite graph "
        "from the receipt corpus and prove the self-review intersection is empty and the chain "
        "graph is acyclic. Independence asserted in a prompt is not independence measured in the "
        "ledger."),
    inputs=[
        "every receipt under " + CC + "/receipts/ (author id and reviewer id fields)",
        CC + "/events/EVENTS.jsonl dispatch records",
        CC + "/WORK-UNIT-CATALOG.json reviewer_requirement fields",
    ],
    dependencies=["SYN-0030"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "process-auditor"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=1800,
    output_path=CC + "/receipts/SYN-0037.json",
    output_schema=CC + "/schema/independence-audit.schema.json",
    evidence_requirement=(
        "The author x reviewer intersection (must be empty, printed as a set), the cycle list "
        "(must be empty, printed as a list), and the count of receipts missing either field -- a "
        "missing reviewer id is a violation, not an absence of evidence of violation."),
    tests_required=[
        "planted self-review -> detected",
        "planted two-cycle -> detected",
        "test_a_receipt_with_no_reviewer_id_is_a_VIOLATION_not_a_skip",
    ],
    reviewer_requirement=R["notauthor"],
    completion_sentinel=sent("SYN-0037",
                             "both planted violations were detected and the missing-field count is published"),
    retry_policy=RT["zero"],
    failure_classification=["self-review", "circular-review", "missing-reviewer-field-skipped"],
    owner_approval_required=False,
)

add(
    id="SYN-0038",
    title="Synthesis reproducibility: re-run the deterministic stages and diff",
    question_or_target=(
        "Question: is the synthesis pipeline reproducible? Target: re-run every deterministic "
        "stage -- the joins, counts, statistics and gates -- from identical inputs in a clean "
        "worktree and require byte-identical output; declare and bound the non-deterministic "
        "stages (the model-authored narratives) rather than pretending they are stable. A pipeline "
        "whose numbers change between runs cannot support a completion verdict."),
    inputs=[
        "all SYN-0002, SYN-0004, SYN-0010, SYN-0013, SYN-0030, SYN-0031 outputs and their scripts",
        "the pinned input SHA and the recorded seeds",
        "a clean worktree created for this unit only",
    ],
    dependencies=["SYN-0030", "SYN-0031", "SYN-0010"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "reproducibility-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="worktree-isolated",
    timeout_seconds=7200,
    output_path=CC + "/receipts/SYN-0038.json",
    output_schema=CC + "/schema/reproducibility-report.schema.json",
    evidence_requirement=(
        "Per stage: sha256 of run 1 output, sha256 of run 2 output, identical yes/no, and for any "
        "mismatch the diff summary and the identified source of nondeterminism (clock, ordering, "
        "path separator, locale). Line endings must be normalised before hashing or every file "
        "will differ for the wrong reason."),
    tests_required=[
        "test_declared_deterministic_stages_hash_identically_across_two_runs",
        "test_nondeterministic_stages_are_declared_in_advance_not_discovered_after",
        "planted nondeterminism: inject a timestamp into an output -> must be caught and attributed",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0038",
                             "every deterministic stage hashed identically and every mismatch has an attributed cause"),
    retry_policy=RT["bounded3"],
    failure_classification=["nondeterministic-output", "crlf-hash-artifact", "undeclared-nondeterminism"],
    owner_approval_required=False,
)

add(
    id="SYN-0039",
    title="Second-order meta-review with an explicit recursion stopping rule",
    question_or_target=(
        "Question: are the meta-review's OWN findings anchored, scoped and actionable -- and at "
        "what depth does reviewing the reviewers stop paying? Target: one second-order pass over "
        "the meta-review findings applying only three tests (is it anchored, is it scoped to its "
        "evidence, does it name a remedy), plus a written stopping rule that terminates the "
        "regress. Distinct from SYN-0026 (a different VENDOR at the same order) and SYN-0027 "
        "(the same lenses applied to their own output)."),
    inputs=[
        "all SYN-0014..SYN-0027 findings",
        CC + "/receipts/SYN-0027.json",
        "the declared stopping rule for review depth",
    ],
    dependencies=["SYN-0027"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "meta-review-chair"},
    tool_permissions=T["ro"],
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path=CC + "/receipts/SYN-0039.json",
    output_schema=CC + "/schema/second-order-review.schema.json",
    evidence_requirement=(
        "Per meta-finding: anchored yes/no, scoped yes/no, remedy named yes/no, and the disposition. "
        "The stopping rule must be stated with its trigger (information gain below threshold, or "
        "depth 2, whichever first) and the measured information gain at this depth reported."),
    tests_required=[
        "test_stopping_rule_is_evaluated_and_its_value_recorded_not_assumed",
        "test_no_third_order_pass_is_launched_once_the_rule_fires",
        "known-present control: an unanchored meta-finding must be caught at this order",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0039",
                             "the stopping rule fired with a recorded measurement and no deeper pass was launched"),
    retry_policy=RT["fresh"],
    failure_classification=["infinite-regress", "unanchored-meta-finding", "stopping-rule-assumed"],
    owner_approval_required=False,
)

add(
    id="SYN-0040",
    title="False-pass hunt: a both-states control for every synthesis-level gate",
    question_or_target=(
        "Question: which Phase 14 gate could pass while the thing it guards is broken? Target: for "
        "each gate shipped by this bucket, construct the known-BROKEN state, confirm the gate "
        "FIRES there, and confirm it is SILENT on the known-good state. A probe silent in both "
        "states measures nothing -- measured on this estate when a codex-exec probe printed no "
        "parse error in either state and was one step from being reported as verification. "
        "Scope is what makes this unit necessary rather than a third copy: TST-0018 scans the "
        "detectors that already exist at Phase 0 baseline and BLD-0040 inventories the program at "
        "Phase 13, both of which run BEFORE any Phase 14 gate exists. Also distinct from SYN-0027, "
        "which asks whether the lenses commit the defects they audit."),
    inputs=[
        "every gate and detector produced by SYN-0002, SYN-0013, SYN-0016..SYN-0021, SYN-0030",
        "rules/common/single-signal-verification.md rule 3b (the both-states test)",
        "a fixtures directory created for this unit",
    ],
    dependencies=["SYN-0002", "SYN-0013", "SYN-0019", "SYN-0021", "SYN-0030"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "detector-control-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="worktree-isolated",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0040.gate-control-matrix.json",
    output_schema=CC + "/schema/detector-control.schema.json",
    evidence_requirement=(
        "A matrix with one row per gate: broken-state exit code, good-state exit code, verdict "
        "VALID | SILENT-IN-BOTH | NOISY-IN-BOTH. Any gate not exercised is listed as NOT-CHECKED "
        "with the reason; an unexercised gate must never be counted as VALID."),
    tests_required=[
        "test_every_bucket_gate_appears_as_a_row",
        "test_a_gate_that_passes_both_states_is_reported_SILENT_IN_BOTH_and_fails_the_matrix",
        "mutation sweep: revert one real defect fix at a time and require the owning gate to go red",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0040",
                             "every gate has both exit codes recorded and no gate is VALID without them"),
    retry_policy=RT["two_strikes"],
    failure_classification=["silent-in-both-states", "unexercised-gate-counted-valid",
                            "mutation-survived"],
    owner_approval_required=False,
)

# =============================================================================
# G. DELIVERABLES, DURABILITY, HANDOFF (SYN-0041 .. SYN-0048)
# =============================================================================

add(
    id="SYN-0041",
    title="Write the final evidence-backed report with the five-way taxonomy and exactly-one-label enforcement",
    question_or_target=(
        "Implementation target: the final deliverable -- 'a final evidence-backed report "
        "distinguishing VERIFIED, INFERRED, UNVERIFIED, REJECTED, and DEFERRED items' "
        "(" + SPEC + ":11435). Every item carries exactly one label, every label carries its "
        "evidence anchor, and the writer is BLOCKED by SYN-0019's manifest gate. The report is "
        "generated from the machine artifacts, never hand-typed, so that regenerating it after a "
        "correction is a one-command operation rather than an editing pass."),
    inputs=[
        "SYN-0011 adjudications, SYN-0001 hierarchy, SYN-0005 decision trace",
        "all meta-review lens outputs SYN-0014..SYN-0027",
        "SYN-0028 option closure, BLD-0029 unknowns closure, SYN-0034 improvement ledger, "
        "SYN-0035 calibration",
        SPEC + ":11402-11435 (the final deliverables list)",
    ],
    dependencies=["SYN-0011", "SYN-0017", "SYN-0026", "SYN-0033"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "report-generator"},
    tool_permissions=T["rw"],
    execution_substrate="local-serialized",
    timeout_seconds=10800,
    output_path=CC + "/synthesis/SYN-0041.final-report.json",
    output_schema=CC + "/schema/final-report.schema.json",
    evidence_requirement=(
        "Per item: label, claim text, >=1 anchor, and the upstream artifact id it was generated "
        "from. Publish the five label counts against the item total. The generator command and "
        "its input SHA must be recorded so the report is regenerable."),
    tests_required=[
        "test_exactly_one_label_per_item_and_no_item_unlabelled",
        "test_report_regenerates_byte_identically_from_the_same_inputs",
        "test_writer_refuses_to_run_when_the_manifest_gate_has_not_passed_within_its_window",
        "test_every_VERIFIED_item_cites_an_anchor_that_resolves",
    ],
    reviewer_requirement=R["writer"],
    completion_sentinel=sent("SYN-0041",
                             "the five label counts sum to the item total and the manifest gate receipt is attached"),
    retry_policy=RT["resume"],
    failure_classification=["unlabelled-item", "hand-typed-report", "manifest-gate-bypassed",
                            "anchor-did-not-resolve"],
    owner_approval_required=False,
)

add(
    id="SYN-0042",
    title="Strongest-remaining-caveat as a required non-vacuous field on every surviving claim",
    question_or_target=(
        "Implementation target: the spec's rule that 'Every surviving claim must state the "
        "strongest remaining caveat' (" + SPEC + ":11064), enforced as a schema-required field "
        "with a vacuity detector. A caveat that restates the claim, says 'further testing "
        "recommended', or repeats a generic disclaimer is vacuous and must be rejected; a valid "
        "caveat names the specific condition under which the claim would fail and the observation "
        "that would reveal it."),
    inputs=[
        CC + "/synthesis/SYN-0041.final-report.json",
        "Phase 12 refuter residuals (bucket B10) -- the strongest caveat usually already exists there",
        CC + "/synthesis/SYN-0012.sensitivity.json (fragility is a caveat source)",
    ],
    dependencies=["SYN-0041", "SYN-0012", "B10"],
    assigned_model_vendor_role={"model": "gpt-5.x-codex", "vendor": "openai",
                                "role": "caveat-adversary"},
    tool_permissions=T["rwxv"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path=CC + "/receipts/SYN-0042.json",
    output_schema=CC + "/schema/caveat-audit.schema.json",
    evidence_requirement=(
        "Per surviving claim: the caveat text, the vacuity verdict with the rule that fired, and "
        "the replacement where vacuous. Report vacuous count against surviving-claim count. The "
        "vacuity detector must be proven on a hand-written vacuous caveat and a hand-written "
        "specific one."),
    tests_required=[
        "detector control: a restatement caveat is flagged vacuous; a condition-naming caveat is not",
        "test_every_surviving_claim_has_a_nonempty_caveat_field",
        "test_caveat_does_not_contradict_the_claim_label (a VERIFIED item with a fatal caveat is a labelling error)",
    ],
    reviewer_requirement=R["xv"],
    completion_sentinel=sent("SYN-0042",
                             "zero vacuous caveats remain and the detector control separated both fixtures"),
    retry_policy=RT["fresh"],
    failure_classification=["vacuous-caveat", "caveat-contradicts-label", "detector-failure"],
    owner_approval_required=False,
)

add(
    id="SYN-0043",
    title="Terminal evaluation of the 21 program stopping conditions, with NOT-CHECKED blocking completion",
    question_or_target=(
        "Implementation target: execute CC-0015's encoded predicates for all 21 stopping "
        "conditions (" + SPEC + ":11376-11398) at report time and emit TRUE | FALSE | NOT-CHECKED "
        "per condition with the probe that produced it. A NOT-CHECKED may never be folded into a "
        "pass, and condition 13 (release or canary succeeds) is known to be unsatisfiable as "
        "written under the binding PR-ONLY release mode, so its resolution must be recorded rather "
        "than silently skipped. Three units share these 21 conditions and the split is "
        "deliberate: CC-0015 ENCODES them, TST-0347 proves each can be made FALSE, and this unit "
        "RUNS them and adjudicates the terminal verdict. Any predicate TST-0347 found unfalsifiable "
        "is reported DECORATIVE here, never TRUE -- a condition no mutation can flip reads true at "
        "release time regardless of the world."),
    inputs=[
        "CC-0015's machine-checkable stopping-condition predicates",
        "all Phase 14 outputs plus " + CC + "/COMPLETION-GATES.json",
        CC + "/OWNER-DECISIONS.md (release mode = PR-ONLY is binding)",
        SPEC + ":11372-11400",
    ],
    dependencies=["CC-0015", "TST-0347", "SYN-0019", "SYN-0028", "SYN-0031", "SYN-0034",
                  "SYN-0041", "BLD-0029"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "completion-adjudicator"},
    tool_permissions=T["rw"],
    execution_substrate="local-serialized",
    timeout_seconds=7200,
    output_path=CC + "/synthesis/SYN-0043.stopping-verdict.json",
    output_schema=CC + "/schema/stopping-verdict.schema.json",
    evidence_requirement=(
        "A 21-row table: condition text, verdict, the probe command with its output tail, and the "
        "timestamp. A program-complete verdict requires 21 TRUE; any NOT-CHECKED yields "
        "PROGRAM-INCOMPLETE with the missing probe named. Condition 13 carries its PR-ONLY "
        "resolution or is reported FALSE."),
    tests_required=[
        "test_a_single_NOT_CHECKED_forces_PROGRAM_INCOMPLETE",
        "test_all_21_conditions_appear_as_rows_with_no_omission",
        "planted false: force condition 4 (no required test is red) false -> overall verdict must flip",
        "test_condition_13_resolution_is_explicit_under_PR_ONLY",
    ],
    reviewer_requirement=R["owner"],
    completion_sentinel=sent("SYN-0043",
                             "all 21 rows carry a verdict and a probe, and the overall verdict follows the stated rule"),
    retry_policy=RT["zero"],
    failure_classification=["not-checked-folded-into-pass", "unsatisfiable-condition-skipped",
                            "missing-condition-row"],
    owner_approval_required=True,
)

add(
    id="SYN-0044",
    title="Generate architecture diagrams FROM the dependency graph so docs cannot drift from structure",
    question_or_target=(
        "Implementation target: the 'architecture diagrams' final deliverable "
        "(" + SPEC + ":11431), generated from DEPENDENCY-GRAPH.json and PHASE-GRAPH.json rather "
        "than hand-drawn, so a structural change re-renders the picture instead of silently "
        "invalidating it. A hand-drawn diagram is a docs-code mismatch waiting to happen; a "
        "generated one makes SYN-0020's parity check trivially true for this artifact class."),
    inputs=[
        CC + "/DEPENDENCY-GRAPH.json (byte-parity gated -- read only, never extend)",
        CC + "/PHASE-GRAPH.json",
        "the chosen architecture record from Phase 3 (bucket B06)",
    ],
    dependencies=["CC-0016", "SYN-0020", "B06"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "diagram-generator"},
    tool_permissions=T["diag"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path=CC + "/synthesis/SYN-0044.diagram-set.json",
    output_schema=CC + "/schema/diagram-manifest.schema.json",
    evidence_requirement=(
        "Per diagram: source graph file with its sha256, the generator command, the output path, "
        "and the node and edge counts rendered versus present in the source. A rendered count "
        "below the source count means the diagram is lying by omission and must say so in its own "
        "caption."),
    tests_required=[
        "test_rendered_node_and_edge_counts_equal_the_source_graph_or_the_omission_is_captioned",
        "test_regeneration_after_a_graph_edit_changes_the_diagram (drift is impossible by construction)",
        "test_generator_does_not_write_to_DEPENDENCY_GRAPH_json (the CI parity gate must stay green)",
    ],
    reviewer_requirement=R["writer"],
    completion_sentinel=sent("SYN-0044",
                             "counts match or the omission is captioned, and the parity gate is still green"),
    retry_policy=RT["env_once"],
    failure_classification=["hand-drawn-drift", "diagram-omission-uncaptioned",
                            "wrote-to-parity-gated-file"],
    owner_approval_required=False,
)

add(
    id="SYN-0045",
    title="Owner executive brief with a no-new-claims invariant against the machine report",
    question_or_target=(
        "Implementation target: a one-page owner-facing brief -- what was built, what is proven, "
        "what is open, what needs a decision, what to do next -- with a MECHANICAL invariant that "
        "every claim in the brief exists in SYN-0041's report. Summarisation loses information by "
        "design; it must not ADD any. Distinct from SYN-0013, which measures what is LOST at a "
        "digest boundary: this unit measures what is INVENTED at one."),
    inputs=[
        CC + "/synthesis/SYN-0041.final-report.json (the only permitted claim source)",
        CC + "/synthesis/SYN-0043.stopping-verdict.json",
        "the open owner questions from SYN-0006, SYN-0028 and BLD-0029",
    ],
    dependencies=["SYN-0041", "SYN-0042", "SYN-0043"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "technical-writer"},
    tool_permissions=T["rw"],
    execution_substrate="local-parallel",
    timeout_seconds=2700,
    output_path=CC + "/synthesis/SYN-0045.owner-brief.md",
    output_schema=CC + "/schema/owner-brief.schema.json",
    evidence_requirement=(
        "The set difference brief-claims minus report-claims must be empty and printed as such. "
        "Report the brief's word count, the claim count, and the retention rate against the "
        "report. Every open decision is stated as one question with a recommendation, the "
        "strongest tradeoff, and the default if unanswered."),
    tests_required=[
        "test_no_claim_in_the_brief_is_absent_from_the_report (the no-new-claims invariant)",
        "planted invention: add an unsupported sentence -> the invariant must fail",
        "test_every_open_decision_carries_recommendation_tradeoff_and_default",
    ],
    reviewer_requirement=R["writer"],
    completion_sentinel=sent("SYN-0045",
                             "the set difference is empty and every open decision has all three required parts"),
    retry_policy=RT["fresh"],
    failure_classification=["invented-claim-in-summary", "decision-without-default",
                            "brief-exceeds-one-page"],
    owner_approval_required=False,
)

add(
    id="SYN-0046",
    title="Write-as-you-go durability harness for the whole synthesis lane",
    question_or_target=(
        "Implementation target: make every unit in this bucket write a TRUTHFUL skeleton before it "
        "measures anything -- every claim enumerated and marked UNKNOWN-not-yet-measured, plus a "
        "COVERAGE line naming which sections are unmeasured -- then rewrite at each milestone. The "
        "measured precedent: one review unit ran 70 minutes, produced 691 KB of transcript, "
        "completed a full mutation harness, then froze and wrote NOTHING. A partial artifact with "
        "honest UNKNOWNs is a success; a perfect artifact that is never written is a total loss."),
    inputs=[
        "every output_path declared by SYN-0001..SYN-0048",
        "rules/common/fan-out-contract.md section C1",
        "the milestone list per unit (derived from each unit's tests_required)",
    ],
    dependencies=["SYN-0001"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "durability-engineer"},
    tool_permissions=T["rw"],
    execution_substrate="local-serialized",
    timeout_seconds=2700,
    output_path=CC + "/receipts/SYN-0046.json",
    output_schema=CC + "/schema/durability-harness.schema.json",
    evidence_requirement=(
        "Proof that each declared output path holds a truthful skeleton within 120 seconds of unit "
        "start, with the sentence: if it still reads this way, the unit died before measuring "
        "anything and no verdict here may be cited. Record the skeleton timestamp and the first "
        "milestone rewrite timestamp per unit."),
    tests_required=[
        "kill test: terminate a unit mid-run -> the on-disk artifact is present and honestly marked UNKNOWN",
        "test_skeleton_contains_every_claim_slot_the_final_artifact_will_have",
        "test_a_milestone_rewrite_never_removes_a_previously_measured_value",
    ],
    reviewer_requirement=R["det"],
    completion_sentinel=sent("SYN-0046",
                             "the kill test produced a truthful partial artifact for at least one real unit"),
    retry_policy=RT["resume"],
    failure_classification=["total-loss-on-freeze", "skeleton-missing-claim-slot",
                            "milestone-rewrite-lost-data"],
    owner_approval_required=False,
)

add(
    id="SYN-0047",
    title="Known-failure-class coverage map: join the spec's 48 seeded classes against root causes and the live suite",
    question_or_target=(
        "Question: which of the failure classes the spec requires in the regression suite "
        "(" + SPEC + ":11298-11347) are NOT covered by a test today, and which synthesized root "
        "causes correspond to no listed class? Target: a three-way coverage map (spec class x root "
        "cause x existing test) whose UNCOVERED set becomes the input to the Phase 16 writeback. "
        "This unit MEASURES the gap and hands it over; IMP-0384 performs the lesson writeback and "
        "benchmark augmentation, so authoring the tests here would duplicate that unit."),
    inputs=[
        SPEC + ":11298-11347 (the enumerated failure classes)",
        CC + "/TEST-REGISTRY.json and the Phase 10 suite inventory (bucket B08)",
        CC + "/synthesis/SYN-0001.root-cause-hierarchy.json",
    ],
    dependencies=["SYN-0001", "CC-0014", "B08"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "coverage-cartographer"},
    tool_permissions=T["calc"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path=CC + "/synthesis/SYN-0047.failure-class-coverage.json",
    output_schema=CC + "/schema/coverage-map.schema.json",
    evidence_requirement=(
        "One row per enumerated spec class with the test id that covers it or UNCOVERED, plus the "
        "reverse list of root causes matching no class. Report both counts with denominators. A "
        "test claimed as coverage must have a mutation record proving it fires, per CC-0014; "
        "otherwise the cell is CLAIMED-NOT-PROVEN."),
    tests_required=[
        "test_every_enumerated_spec_class_appears_as_a_row (extraction count is asserted, not eyeballed)",
        "test_a_test_without_a_mutation_record_is_CLAIMED_NOT_PROVEN_not_COVERED",
        "known-present control: a class with a known passing test resolves to COVERED",
    ],
    reviewer_requirement=R["two"],
    completion_sentinel=sent("SYN-0047",
                             "the row count equals the extracted class count and the uncovered set is enumerated"),
    retry_policy=RT["two_strikes"],
    failure_classification=["uncovered-failure-class", "claimed-not-proven-counted-as-covered",
                            "extraction-count-unasserted"],
    owner_approval_required=False,
)

add(
    id="SYN-0048",
    title="Program handoff package with resumable state and temporal-validity supersession edges",
    question_or_target=(
        "Implementation target: the package a fresh session needs to resume this program cold -- "
        "the pinned SHA, the in-flight unit set with their last durable checkpoints, the open "
        "owner questions, the deferred items with their reopen triggers, and durable memory notes "
        "carrying supersession edges (superseded_by on the old note, valid_as_of on the new) so "
        "recall surfaces current truth and dead ends are not re-walked. Distinct from IMP-0384, "
        "which writes back the lesson from ONE improvement inside the Phase 16 loop; this is the "
        "program-level resume contract."),
    inputs=[
        CC + "/synthesis/SYN-0041.final-report.json and SYN-0043 stopping verdict",
        CC + "/receipts/BLD-0029.json (the unknowns closure) and the open owner questions",
        "existing basic-memory notes for this program (to be superseded, never silently deleted)",
        CC + "/STATUS.md and " + CC + "/events/EVENTS.jsonl",
    ],
    dependencies=["SYN-0041", "SYN-0043", "SYN-0045", "BLD-0029"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "continuity-engineer"},
    tool_permissions=T["mem"],
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path=CC + "/synthesis/SYN-0048.handoff-package.json",
    output_schema=CC + "/schema/handoff-package.schema.json",
    evidence_requirement=(
        "The package contents listed with each item resolving on disk, the memory note permalinks "
        "written, and for every superseded note the pair of edges actually persisted (read back "
        "after write, not assumed). A cold-resume rehearsal transcript must show a fresh reader "
        "reaching the correct next action using only this package."),
    tests_required=[
        "cold-resume rehearsal: a fresh context using only the package names the correct next action",
        "test_every_superseded_note_has_superseded_by_and_the_successor_has_valid_as_of (read back)",
        "test_no_memory_note_is_deleted_only_superseded",
        "test_every_deferred_item_carries_a_reopen_trigger",
    ],
    reviewer_requirement=R["raw"],
    completion_sentinel=sent("SYN-0048",
                             "the cold-resume rehearsal succeeded and every supersession edge was read back from the store"),
    retry_policy=RT["resume"],
    failure_classification=["unresumable-handoff", "supersession-edge-not-persisted",
                            "deleted-instead-of-superseded"],
    owner_approval_required=False,
)

# =============================================================================
# finalize: apply the invariant fields, validate, write
# =============================================================================

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]

SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9",
          "10", "11", "12", "13", "14", "15", "16"}

out = []
errs = []
for i, u in enumerate(UNITS, start=1):
    u = dict(u)
    u["phase"] = "14"                      # bucket B12 feeds phase 14 only
    expect = "SYN-%04d" % i
    if u["id"] != expect:
        errs.append("id sequence: got %s expected %s" % (u["id"], expect))
    ordered = {}
    for f in FIELDS:
        if f not in u:
            errs.append("%s missing field %s" % (u["id"], f))
        else:
            ordered[f] = u[f]
    extra = [k for k in u if k not in FIELDS]
    if extra:
        errs.append("%s extra fields %s" % (u["id"], extra))
    out.append(ordered)

# structural validation
seen = set()
for u in out:
    uid = u["id"]
    if uid in seen:
        errs.append("duplicate id %s" % uid)
    seen.add(uid)
    if not re.match(r"^SYN-\d{4}$", uid):
        errs.append("bad id format %s" % uid)
    if u["phase"] not in PHASES:
        errs.append("%s bad phase" % uid)
    if u["execution_substrate"] not in SUBSTRATES:
        errs.append("%s bad substrate %s" % (uid, u["execution_substrate"]))
    if not isinstance(u["timeout_seconds"], int) or u["timeout_seconds"] <= 0:
        errs.append("%s bad timeout" % uid)
    for arr in ("inputs", "dependencies", "tool_permissions", "tests_required",
                "failure_classification"):
        if not isinstance(u[arr], list):
            errs.append("%s %s is not a list" % (uid, arr))
    if len(u["inputs"]) < 2:
        errs.append("%s too few inputs" % uid)
    if len(u["tests_required"]) < 2:
        errs.append("%s too few tests" % uid)
    a = u["assigned_model_vendor_role"]
    if not (isinstance(a, dict) and {"model", "vendor", "role"} <= set(a)):
        errs.append("%s bad assignment shape" % uid)
    if uid not in u["completion_sentinel"]:
        errs.append("%s sentinel does not name the unit" % uid)
    if uid not in u["output_path"]:
        errs.append("%s output_path does not embed the id" % uid)
    if not isinstance(u["owner_approval_required"], bool):
        errs.append("%s owner_approval_required not bool" % uid)
    for d in u["dependencies"]:
        if not re.match(r"^(SYN|CC|AUD|RES|WFA|CNL|ARC|IMP|TST|CNF|ADV|BLD|REL)-\d{4}$|^B\d{2}$", d):
            errs.append("%s bad dependency token %s" % (uid, d))
    # intra-slice deps must point backwards (no forward-only cycles inside the slice)
    for d in u["dependencies"]:
        if d.startswith("SYN-") and d == uid:
            errs.append("%s depends on itself" % uid)

# no field may collapse to a single value across the slice (phase is the declared exception)
for f in FIELDS:
    if f in ("id", "title", "question_or_target", "phase", "output_path", "completion_sentinel"):
        continue
    vals = set(json.dumps(u[f], sort_keys=True) for u in out)
    if len(vals) < 2:
        errs.append("FIELD COLLAPSE: %s has one distinct value across the slice" % f)

dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SYN-1.json")
if errs:
    for e in errs:
        print("ERROR: " + e)
    sys.exit(1)

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
    fh.write("\n")
print("WROTE %s units=%d" % (dst, len(out)))
