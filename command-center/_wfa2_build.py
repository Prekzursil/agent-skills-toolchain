"""Generate catalog slice WFA-2of2 (bucket B04, units 129-160).

Mechanical, not eyeballed: the script expands 32 terse unit specs into the full
19-field Prompt Two work-unit contract, then RUNS the checks (unique/sequential
ids, field completeness, controlled vocabularies, pairwise near-duplicate scan
with a planted-mutant detector control) before writing anything.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center" / "catalog-slices" / "WFA-2.json"

CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
# Absolute so the executing agent can Read the anchor at that literal path
# (fan-out-contract A5: a path must carry its access method).
SPEC = f"{CORPUS}/_USER-PROMPTS.md"

SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A",
          "8", "9", "10", "11", "12", "13", "14", "15", "16"}
# Reuse the catalog's existing failure vocabulary rather than inventing one
# (WORK-UNIT-CATALOG.json defaults.failure_classification).
FAILCLASSES = {"green-not-live", "overclaim", "detector-failure",
               "uncontrolled-silence", "dependency-blocked", "owner-blocked"}

SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/{kind}"

RETRY_DEFAULT = ("two strikes then pivot: after the SECOND failure on the same "
                 "error-fingerprint, enumerate >=2 alternative approaches before a "
                 "third attempt, or escalate (AGENTS.md 4b)")
RETRY_LIVE = ("one retry only, then STOP and escalate: this unit actuates the live "
              "harness, so a blind third attempt risks compounding live-state damage; "
              "record the partial artifact before escalating")
RETRY_NET = ("three attempts with staggered backoff for transient network/429, but "
             "ZERO retries on a non-transient upstream answer (404/410/license change) "
             "- that is a result, not a failure")

REV_ONE = "one independent adversarial reviewer in a fresh context who did not author the artifact"
REV_CROSS = ("two independent reviewers, at least one cross-vendor (Codex via "
             "mcp__codex__codex), neither of whom authored the artifact; a split verdict "
             "is resolved by reading the probes, not by vote (fan-out-contract B4)")
REV_CONFIRM = ("an independent confirmer who starts from raw source artifacts and "
               "reproduces the verdict without reading the author's conclusion "
               f"({SPEC}:11030-11039)")

EV_SPINE = ("two mechanically independent signals, each anchored to a file:line or a "
            "rerunnable command; ")

TOOLS_RO = ["Read", "Grep", "Glob", "Bash"]
TOOLS_BUILD = ["Read", "Grep", "Glob", "Bash", "PowerShell", "Write", "Edit"]
TOOLS_NET = ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch", "Write"]
TOOLS_XV = ["Read", "Grep", "Glob", "Bash", "Write", "mcp__codex__codex"]

A_IMPL = "opus/anthropic/implementer"
A_ADV = "opus/anthropic/adversarial-refuter"
A_ARCH = "opus/anthropic/workflow-archaeologist"
A_LIC = "opus/anthropic/licensing-analyst"
A_XV = "gpt-5-codex/openai/independent-confirmer"

REG = f"{CORPUS}/08-WORKFLOW-CANDIDATE-REGISTRY.json"
PROV = f"{CORPUS}/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
ARCH = f"{CORPUS}/08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
BPL = f"{CORPUS}/09-WORKFLOW-BLUEPRINT-LIBRARY.json"
FUSE = f"{CORPUS}/10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md"
MAPS = f"{CORPUS}/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
SUBST = f"{CORPUS}/19-SUBSTANCE-AUDIT-BLUEPRINTS.md"

# ---------------------------------------------------------------------------
# (title, phase, kind, target, inputs, deps, assignment, tools, substrate,
#  timeout, evidence, tests, reviewer, retry, failclasses, owner_gate,
#  mechanism, nodup, spec_anchor)
# ---------------------------------------------------------------------------
U: list[dict] = [
 dict(
  t="Matched-case benchmark corpus for fusion evaluation",
  ph="2B", kind="benchmark-corpus",
  tg=("Build a benchmark corpus of executable task cases such that, for EACH of the 30 "
      "merge_units in 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json, at least one case can be "
      "run identically by the fused blueprint AND by every entry in that unit's "
      "`sources_resolved_in_registry`. Emit the case set, a computed case->merge_unit coverage "
      "matrix, and an explicit NON-BENCHMARKABLE list naming every merge_unit for which no "
      "matched case exists and why. Question: for how many of the 30 merge_units can a "
      "like-for-like source-vs-fusion comparison actually be run, and which are excluded?"),
  inp=[MAPS + "#merge_units", BPL + "#blueprints", REG + "#candidates",
       f"{SPEC}:10739 (run source workflows and fused candidates on matched benchmark cases)"],
  dep=["WFA-1of2", "B01"], asg=A_IMPL, tl=TOOLS_BUILD, sub="local-parallel", to=3600,
  ev=EV_SPINE + ("the coverage matrix is COMPUTED from the artifacts (no hand count), and the "
                 "excluded set is enumerated with a per-merge_unit reason string"),
  ts=["both-states: feed the corpus builder one case every source can run and one case no "
      "source can run; it must accept exactly the first and reject the second",
      "the coverage matrix row count equals len(merge_units)==30 or the build fails closed"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["uncontrolled-silence", "overclaim", "detector-failure"], og=False,
  mech="matched-case derivation with a fail-closed non-benchmarkable exclusion list",
  nd=("produces the INPUT cases only; WFA-0130 defines what is measured on them, WFA-0133 "
      "measures the sources, WFA-0132 schedules the comparisons"),
  sa=f"{SPEC}:10739"),

 dict(
  t="Pre-registered fusion acceptance metric set",
  ph="2B", kind="metric-registry",
  tg=("Define and PRE-REGISTER, before any fusion is measured, the metric set and the decision "
      "rule that decides whether a fused workflow is accepted - operationalising "
      "'better correctness, coverage, recovery, or usability' into four computable metrics with "
      "stated estimators, tie-breaks, and a minimum effect size. Question: what exact numeric "
      "predicate over those four metrics converts a benchmark run into ACCEPT / REJECT, and is "
      "it frozen (hash-pinned) before the first measurement?"),
  inp=[f"{SPEC}:11170 (a merged workflow is not accepted because it contains more stages)",
       f"{SPEC}:10741 (certify only workflows that outperform or materially complement)", FUSE],
  dep=["WFA-1of2"], asg=A_IMPL, tl=TOOLS_BUILD, sub="local-parallel", to=1800,
  ev=EV_SPINE + ("the registry file carries a sha256 recorded BEFORE the first benchmark run, "
                 "and the run log cites that hash"),
  ts=["a post-hoc metric edit must be rejected: mutate the registry after pinning and confirm "
      "the runner refuses to score against the mutated copy (both-states)"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure"], og=False,
  mech="pre-registration + hash pinning of the acceptance predicate to block metric shopping",
  nd=("defines WHAT is measured and the accept rule; WFA-0129 supplies cases, WFA-0134 binds "
      "the program-wide completion predicate, WFA-0131 attacks this metric set"),
  sa=f"{SPEC}:11170"),

 dict(
  t="Benchmark-gaming adversarial control",
  ph="2B", kind="adversarial-control",
  tg=("Attack the pre-registered metric set from WFA-0130: construct at least three GAMED "
      "workflow variants that raise the composite score without adding capability (stage "
      "padding, case overfitting, retry-until-pass, and metric-favourable output shaping) and "
      "run them. Question: does the acceptance predicate accept any gamed variant, and if so "
      "what counter-control (held-out cases, capability assertion, effort normalisation) makes "
      "it reject all three while still accepting the genuine improvement?"),
  inp=["WFA-0130 metric registry", "WFA-0129 case corpus",
       f"{SPEC}:11059 (benchmark gaming refuter)"],
  dep=["WFA-0130", "WFA-0129"], asg=A_ADV, tl=TOOLS_BUILD, sub="local-serialized", to=5400,
  ev=EV_SPINE + ("each gamed variant is committed as a runnable fixture with its score, and "
                 "the counter-control is shown to keep the genuine improvement accepted"),
  ts=["the control must FIRE on all three gamed variants and stay SILENT on the honest "
      "baseline - a control silent in both states measures nothing"],
  rv=REV_CROSS, rt=RETRY_LIVE,
  fc=["overclaim", "detector-failure", "green-not-live"], og=False,
  mech="constructive score-inflation attack that yields a held-out counter-control",
  nd=("attacks the SCORING rule; WFA-0136 attacks catalog DISTINCTNESS and WFA-0145 attacks "
      "scout RECALL - three different targets"),
  sa=f"{SPEC}:11059"),

 dict(
  t="Pairwise workflow tournament runner with a statistical stopping rule",
  ph="2B", kind="tournament-engine",
  tg=("Implement the A/B and tournament runner that schedules pairwise source-vs-fusion and "
      "fusion-vs-fusion matches over the WFA-0129 corpus, with a declared sample size, a "
      "sequential stopping rule, and a Condorcet/pairwise aggregation that reports "
      "intransitive cycles instead of hiding them. Question: how many matched runs per pair are "
      "required before the ACCEPT/REJECT call is stable, and which pairs remain undecided at "
      "that budget?"),
  inp=["WFA-0129 case corpus", "WFA-0130 metric registry", MAPS + "#family_composition_matrix",
       f"{SPEC}:11164 (A/B and tournament benchmarking)"],
  dep=["WFA-0129", "WFA-0130"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=7200,
  ev=EV_SPINE + ("the undecided-pair list and any Condorcet cycle are emitted as first-class "
                 "output, not omitted"),
  ts=["seeded-outcome simulation: with a known-superior arm planted, the runner must converge "
      "on it; with two identical arms it must report UNDECIDED rather than a winner"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "uncontrolled-silence", "detector-failure"], og=False,
  mech="sequential pairwise scheduling with explicit undecided/cycle reporting",
  nd=("schedules and aggregates comparisons; WFA-0130 defines the metric, WFA-0133 fixes the "
      "measurement ORDER, WFA-0129 supplies the cases"),
  sa=f"{SPEC}:11164"),

 dict(
  t="Source-baseline-before-fusion ordering invariant",
  ph="2B", kind="baseline-ledger",
  tg=("Enforce that every source workflow is measured on the matched cases BEFORE its fusion is "
      "measured, and persist the source baselines so the named failure 'fused workflow performs "
      "worse than every source workflow' becomes computable rather than rhetorical. Question: "
      "for each of the 30 merge_units, what is the per-metric baseline of every resolved source, "
      "and does the runner refuse to score a fusion whose sources are unmeasured?"),
  inp=["WFA-0129 case corpus", "WFA-0130 metric registry", MAPS + "#merge_units",
       f"{SPEC}:11333 (fused workflow performs worse than every source workflow)"],
  dep=["WFA-0129", "WFA-0130", "WFA-0132"], asg=A_IMPL, tl=TOOLS_BUILD,
  sub="local-serialized", to=5400,
  ev=EV_SPINE + ("the baseline ledger is written before the first fusion run and its mtime/"
                 "commit order proves the sequence"),
  ts=["submit a fusion whose sources have no baseline row: the runner must refuse (fail closed), "
      "and must accept the same fusion once baselines exist (both-states)"],
  rv=REV_ONE, rt=RETRY_LIVE,
  fc=["green-not-live", "dependency-blocked", "detector-failure"], og=False,
  mech="temporal ordering invariant on measurement, persisted as a baseline ledger",
  nd=("this is the ORDER-OF-MEASUREMENT invariant and the baseline store; WFA-0132 is the "
      "match scheduler and WFA-0140 is the capability diff, neither of which persists baselines"),
  sa=f"{SPEC}:11333"),

 dict(
  t="Bind the shared 12-condition completion predicate to a workflow artifact",
  ph="2B", kind="certification-predicate",
  tg=("Instantiate the program's single completion predicate (spec conditions 1-12) for the "
      "workflow-artifact type and emit a per-workflow CERTIFIED / PROVISIONAL / REJECTED record "
      "naming which of the 12 conditions passed, failed, or are not-applicable with a reason. "
      "Question: which of the 12 conditions are genuinely inapplicable to a workflow blueprint "
      "(versus quietly skipped), and does the same reducer run in the local runner, the "
      "tournament runner, and the certification gate?"),
  inp=[f"{SPEC}:10627-10648 (one completion predicate everywhere)", BPL, FUSE],
  dep=["WFA-1of2", "B01"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("a single shared reducer module is imported by all three call sites; the import "
                 "graph is shown, not asserted"),
  ts=["mutation: break each of the 12 conditions in turn and confirm the record flips to "
      "REJECTED for that condition - a condition whose mutation survives is not wired"],
  rv=REV_CONFIRM, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure", "green-not-live"], og=False,
  mech="single-reducer binding of the program completion predicate to the workflow type",
  nd=("defines PASS/FAIL conditions; WFA-0135 checks that a claimed quality TIER has its "
      "evidence on disk, WFA-0137 removes certification after a later regression"),
  sa=f"{SPEC}:10627"),

 dict(
  t="Quality-tier evidence gate (40 flagship end-to-end vs the smoke-tested remainder)",
  ph="2B", kind="tier-ledger",
  tg=("Implement the two-tier contract - at least 40 flagship workflows with full end-to-end "
      "tests, every remaining workflow executable, schema-valid, documented and smoke-tested - "
      "as a gate that resolves each tier claim to the test artifacts that back it on disk. "
      "Question: for each blueprint claiming flagship tier, which end-to-end test file and "
      "which passing run id proves it, and how many claims resolve to nothing?"),
  inp=[f"{SPEC}:10898 (at least 40 must be flagship with full end-to-end tests)", BPL, SUBST],
  dep=["WFA-0134"], asg=A_IMPL, tl=TOOLS_BUILD, sub="local-parallel", to=3600,
  ev=EV_SPINE + ("each flagship row cites test file:line AND a run identifier; a row citing only "
                 "a file path with no run is recorded as UNPROVEN, not as pass"),
  ts=["delete one flagship test file and confirm the gate demotes that blueprint out of "
      "flagship tier rather than staying green (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "green-not-live", "uncontrolled-silence"], og=False,
  mech="tier claim -> on-disk test-artifact resolution with UNPROVEN as a distinct outcome",
  nd=("checks the EVIDENCE BEHIND a tier claim; WFA-0134 defines the pass conditions and "
      "WFA-0157 fixes which FIELD a gate may key on"),
  sa=f"{SPEC}:10898"),

 dict(
  t="Semantic non-duplication proof for the >=96-entry blueprint catalog",
  ph="2B", kind="distinctness-proof",
  tg=("Produce the explicit catalog proof that the shipped blueprint entries are MATERIALLY "
      "distinct, using an embedding-cosine pass rather than token overlap alone, because a "
      "lexical scan cannot separate a full-rewrite paraphrase from a genuinely new mechanism. "
      "Question: which blueprint pairs are near-duplicates under semantic similarity that "
      "token-Jaccard scored as distinct, and does each survivor pair carry a "
      "not_a_duplicate_because sentence that names a mechanism difference, not a wording one?"),
  inp=[f"{SPEC}:10909 (maintain an explicit catalog proving the 96 entries are materially "
       "distinct)", BPL + "#blueprints (108)", MAPS + "#merge_units.not_a_duplicate_because"],
  dep=["WFA-1of2"], asg=A_XV, tl=TOOLS_XV, sub="cloud-batch", to=5400,
  ev=EV_SPINE + ("planted-mutant control: inject a known paraphrase pair and a known-distinct "
                 "pair; report the detector's score on both alongside the real findings"),
  ts=["the planted paraphrase must be flagged and the planted distinct pair must not - a "
      "detector that flags both or neither is reported as broken and its findings discarded"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["detector-failure", "overclaim"], og=False,
  mech="embedding-cosine distinctness with a planted-mutant detector control",
  nd=("measures catalog DISTINCTNESS; WFA-0131 attacks the score, WFA-0149 repairs a "
      "compatibility data defect, WFA-0140 measures capability loss inside one fusion"),
  sa=f"{SPEC}:10909"),

 dict(
  t="Decertification path when a certified workflow later regresses",
  ph="2B", kind="revocation-engine",
  tg=("Implement revocation: when a previously CERTIFIED workflow fails a later regression or "
      "benchmark rerun, flip its record to DECERTIFIED, propagate to every pack, preset and "
      "fusion that embeds it, and surface the affected downstream set. Question: given a "
      "regression on one blueprint, exactly which packs, presets and fused workflows must be "
      "re-gated, and does any consumer keep serving the decertified version?"),
  inp=["WFA-0134 certification records", MAPS + "#composition_graph",
       f"{SPEC}:11166 (certification, deprecation, supersession, and rollback)"],
  dep=["WFA-0134", "WFA-0152"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("the propagation set is computed over the composition graph (108 nodes, one "
                 "connected component) rather than hand-listed"),
  ts=["decertify a leaf blueprint and assert every transitively dependent pack is re-gated; "
      "decertify nothing and assert zero packs are touched (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["green-not-live", "uncontrolled-silence", "detector-failure"], og=False,
  mech="regression-triggered revocation with transitive downstream propagation",
  nd=("triggered by a QUALITY REGRESSION on the same workflow; WFA-0142 is triggered by a "
      "SUPERIOR REPLACEMENT and carries a migration path instead"),
  sa=f"{SPEC}:11166"),

 dict(
  t="Fusion lineage record and the decomposition round-trip test",
  ph="2B", kind="lineage-record",
  tg=("Define the lineage record a fused workflow must carry and implement the executable "
      "round-trip test that decomposes a fusion back into its source mechanisms and asserts the "
      "recovered set equals the declared sources. Question: for each of the 30 merge_units, does "
      "decompose(fuse(sources)) return exactly `sources_declared`, and which units fail because "
      "of the entries already recorded as `sources_unresolved`?"),
  inp=[f"{SPEC}:10913 (a fused workflow must preserve lineage and be decomposable back)",
       MAPS + "#merge_units.sources_declared", MAPS + "#merge_units.sources_unresolved"],
  dep=["WFA-1of2", "B01"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("the round trip is executed per merge_unit and the set difference is printed "
                 "per failure, not summarised as a pass rate"),
  ts=["drop one source from a fusion and confirm the round trip fails with that exact source "
      "named; restore it and confirm the trip passes (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure", "dependency-blocked"], og=False,
  mech="structural decompose(fuse(x)) == x round trip over declared lineage",
  nd=("asserts STRUCTURAL recoverability of the source list; WFA-0140 asserts that the fusion "
      "retains each source's CAPABILITIES, which can hold or fail independently"),
  sa=f"{SPEC}:10913"),

 dict(
  t="License and credit propagation lattice through fusion",
  ph="2B", kind="license-lattice",
  tg=("Implement most-restrictive-wins license propagation and credit carry-through for fusion, "
      "seeded by the 7 license_classification_rules and the 45-row license_risk_register in the "
      "provenance graph. Question: for every fusion whose sources span more than one license "
      "class, what is the resulting license, which combinations are prohibited outright, and "
      "does any fusion currently lose an attribution required by a source?"),
  inp=[PROV + "#license_classification_rules (7)", PROV + "#license_risk_register (45)",
       MAPS + "#merge_units", f"{SPEC}:11334 (workflow provenance or license is lost)"],
  dep=["WFA-0138", "WFA-0153"], asg=A_LIC, tl=TOOLS_BUILD, sub="local-parallel", to=3600,
  ev=EV_SPINE + ("each propagation verdict cites the specific rule index it applied; a fusion "
                 "with an unresolved source license is BLOCKED, never defaulted to permissive"),
  ts=["feed a copyleft+permissive pair and assert the copyleft result; feed an unknown-license "
      "source and assert BLOCKED rather than a silent permissive default (both-states)"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["overclaim", "uncontrolled-silence", "owner-blocked"], og=True,
  mech="most-restrictive-wins license lattice with fail-closed unknown handling",
  nd=("operates at FUSION time on license combination; WFA-0153 closes unresolved provenance "
      "NODES in the static graph, which is an input to this, not the same computation"),
  sa=f"{SPEC}:11334"),

 dict(
  t="Capability-loss detector for fusion",
  ph="2B", kind="capability-diff",
  tg=("Extract a typed capability set (stages, gates, tools, stop rules, recovery paths) from "
      "each source workflow and from the fusion, then compute the set difference. Question: for "
      "each of the 30 merge_units, which source capabilities are absent from the fusion, and is "
      "each absence a deliberate, recorded drop or an unnoticed loss?"),
  inp=[BPL + "#field_schema (stg, gates, tools, stop, res, fail)", MAPS + "#merge_units",
       f"{SPEC}:11333 (workflow fusion loses a source capability)"],
  dep=["WFA-0138"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("the diff is computed from the typed fields, and every reported drop is "
                 "classified DELIBERATE (with the recording line) or UNNOTICED"),
  ts=["remove one gate from a fusion and confirm the detector names that gate; remove nothing "
      "and confirm an empty diff (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["uncontrolled-silence", "detector-failure", "overclaim"], og=False,
  mech="typed capability set-difference with deliberate-vs-unnoticed classification",
  nd=("measures what the fusion CAN DO versus its sources; WFA-0138 only proves the source LIST "
      "is recoverable and would pass even if every capability were dropped"),
  sa=f"{SPEC}:11333"),

 dict(
  t="Control-plane singularity gate at acquisition and at fusion",
  ph="2B", kind="control-plane-census",
  tg=("Implement one census that counts the distinct orchestration control planes a workflow "
      "introduces, and run it at BOTH trigger points: when an external candidate is acquired "
      "(spec forbids importing a second orchestration runtime merely because a workflow was "
      "found there) and when a fusion is assembled (spec names duplicate control planes as a "
      "fusion failure). Question: which acquired candidates or fusions raise the control-plane "
      "count above one, and for each, what is the extracted mechanism that would let it run on "
      "the existing plane instead?"),
  inp=[f"{SPEC}:10727 (do not import a second orchestration runtime)",
       f"{SPEC}:11333 (fusion creates duplicate control planes)",
       REG + "#candidates.runtime", MAPS + "#external_dependency_map"],
  dep=["WFA-1of2"], asg=A_ADV, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("the census enumerates runtimes from the candidate `runtime` field and from the "
                 "fused definition, and the two readings are reported separately"),
  ts=["plant a candidate that carries its own runner and assert the gate fires at acquisition; "
      "plant a pure-mechanism candidate and assert it passes (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure", "green-not-live"], og=False,
  mech="runtime census run at two trigger points by one shared counter",
  nd=("MERGED from two originally separate units (an acquisition-time runtime-import audit and a "
      "fusion-time duplicate-control-plane detector) because both reduce to the same census; "
      "keeping them apart would have been the same mechanism reworded"),
  sa=f"{SPEC}:10727"),

 dict(
  t="Supersession engine with migration and rollback-to-source",
  ph="2B", kind="supersession-engine",
  tg=("Implement supersession: mark workflow A superseded by workflow B, emit the migration path "
      "for existing callers and presets, and preserve the ability to roll back to A and to A's "
      "source components. Question: for a supersession, what is the exact caller migration set, "
      "and can the system restore the superseded workflow and its decomposed sources after the "
      "swap?"),
  inp=[f"{SPEC}:11166 (certification, deprecation, supersession, and rollback)",
       f"{SPEC}:10742 (rollback to source components)", "WFA-0138 lineage records"],
  dep=["WFA-0138", "WFA-0137"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("a rehearsed supersede-then-rollback cycle is executed and the restored "
                 "artifact is byte-compared with the pre-supersession copy"),
  ts=["supersede and roll back, then assert byte equality with the pre-state; assert a rollback "
      "that would drop a caller is refused"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["green-not-live", "dependency-blocked", "overclaim"], og=False,
  mech="supersede + migrate + rehearsed rollback to the prior workflow and its sources",
  nd=("triggered by a BETTER REPLACEMENT and carries a migration path; WFA-0137 is triggered by "
      "a FAILED REGRESSION and simply revokes"),
  sa=f"{SPEC}:11166"),

 dict(
  t="workflow-scout: executable search, rank and provenance-verify",
  ph="2B", kind="scout-pipeline",
  tg=("Implement workflow-scout as an executable meta-workflow: given a typed goal and "
      "constraints, search the local, repository, marketplace and public sources, verify "
      "provenance and license for each hit, and return a RANKED candidate list with a per-hit "
      "evidence anchor. Question: for a given goal, what is the ranked candidate set, what is "
      "each hit's license and maintenance state, and which hits are returned as "
      "UNKNOWN-NEEDS-PROBE rather than ranked?"),
  inp=[f"{SPEC}:10913 (ship workflow-scout and workflow-forge as executable meta-workflows)",
       REG, PROV, ARCH],
  dep=["WFA-1of2", "B03"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=5400,
  ev=EV_SPINE + ("every returned hit carries a resolvable source anchor; a hit whose provenance "
                 "cannot be resolved is returned as UNKNOWN, never silently ranked"),
  ts=["a goal with a known-existing answer must return it above any newly-proposed build; a goal "
      "with no existing answer must return an empty ranked set rather than a fabricated hit"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "uncontrolled-silence", "detector-failure"], og=False,
  mech="goal -> ranked, provenance-verified existing-workflow candidate set",
  nd=("SEARCHES and RANKS what already exists; WFA-0144 synthesises something new, WFA-0145 is "
      "the recall control that proves this search is not blind, WFA-0146 is the routing decision"),
  sa=f"{SPEC}:10913"),

 dict(
  t="workflow-forge: mechanism decomposition and synthesis",
  ph="2B", kind="forge-pipeline",
  tg=("Implement workflow-forge as an executable meta-workflow: decompose the scout's candidates "
      "into transferable mechanisms, propose adopt/adapt/merge/compose/build variants, benchmark "
      "them on the WFA-0129 corpus, and return BOTH the executable workflow and an "
      "evidence-backed design rationale. Question: for a given goal, which mechanism set was "
      "extracted, which variants were benchmarked, and what evidence justifies the returned "
      "synthesis over each rejected variant?"),
  inp=["WFA-0143 scout output", "WFA-0129 case corpus", f"{SPEC}:10913", FUSE],
  dep=["WFA-0143", "WFA-0129", "WFA-0132"], asg=A_IMPL, tl=TOOLS_BUILD,
  sub="worktree-isolated", to=7200,
  ev=EV_SPINE + ("the rationale names every rejected variant with its measured score, so a "
                 "reviewer can see the losers, not only the winner"),
  ts=["given a goal whose best answer is a pure adoption, the forge must return the adoption and "
      "NOT a built-from-scratch workflow (a build-bias control)"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["overclaim", "green-not-live", "detector-failure"], og=False,
  mech="mechanism extraction -> variant proposal -> benchmarked synthesis with a rationale",
  nd=("SYNTHESISES and justifies; WFA-0143 only finds and ranks, and returns nothing new"),
  sa=f"{SPEC}:10913"),

 dict(
  t="Scout anti-rebuild recall control with a planted known-superior workflow",
  ph="2B", kind="recall-control",
  tg=("Prove the scout is not blind before trusting any 'nothing found' answer: plant a "
      "known-superior existing workflow in the searchable corpus, issue a goal it satisfies, and "
      "require the scout to return it. Question: what is the scout's measured recall on a set of "
      "planted known-present items, and does it ever recommend BUILD when a superior existing "
      "workflow is present?"),
  inp=[f"{SPEC}:11331 (workflow discovery ignores an existing superior workflow and rebuilds it)",
       "WFA-0143 scout implementation", REG + "#candidates (284)"],
  dep=["WFA-0143"], asg=A_ADV, tl=TOOLS_BUILD, sub="local-serialized", to=3600,
  ev=EV_SPINE + ("recall is reported as found/planted with the miss list named; a bare recall "
                 "percentage with no miss list is not accepted"),
  ts=["the control must find the planted item (known-present) AND return empty for a planted "
      "known-absent goal - a scout that answers both the same way measures nothing"],
  rv=REV_CROSS, rt=RETRY_LIVE,
  fc=["detector-failure", "overclaim", "green-not-live"], og=False,
  mech="planted known-present / known-absent recall control on the discovery step",
  nd=("measures the SCOUT's blindness; WFA-0131 attacks the benchmark score and WFA-0136 attacks "
      "catalog distinctness - different detectors under test"),
  sa=f"{SPEC}:11331"),

 dict(
  t="Find / repair / merge / build recommendation function",
  ph="2B", kind="routing-function",
  tg=("Implement the typed decision function that converts a scout result plus constraints into "
      "exactly one of FIND, REPAIR, MERGE, COMPOSE or BUILD, with the deciding features and an "
      "audit record per call. Question: what feature thresholds separate REPAIR from BUILD, and "
      "on the 284-candidate registry does the function reproduce the human classification, or "
      "where does it disagree?"),
  inp=[REG + "#candidates.classification (9 of 15 values used)",
       f"{SPEC}:11168 (recommendation logic that decides whether to find, repair, merge, or "
       "build)", "WFA-0143 scout output"],
  dep=["WFA-0143", "WFA-0148"], asg=A_IMPL, tl=TOOLS_BUILD, sub="local-parallel", to=3600,
  ev=EV_SPINE + ("agreement with the existing registry classification is reported as a confusion "
                 "matrix over the 284 candidates, and every disagreement is listed by id"),
  ts=["hold out 20 percent of the registry, fit thresholds on the rest, and report held-out "
      "agreement; a function that only reproduces its training rows is reported as overfit"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure"], og=False,
  mech="typed routing decision with a confusion matrix against the human classification",
  nd=("chooses the ROUTE; WFA-0143 supplies the candidates and WFA-0144 executes the chosen "
      "route - neither decides which route applies"),
  sa=f"{SPEC}:11168"),

 dict(
  t="Settle the 44 UNKNOWN-NEEDS-PROBE candidates",
  ph="2A", kind="probe-dispatch",
  tg=("Every one of the 44 candidates classified UNKNOWN-NEEDS-PROBE in "
      "08-WORKFLOW-CANDIDATE-REGISTRY.json must be resolved to a terminal classification by "
      "running its named settling probe, or must carry an explicit blocked-reason. Question: "
      "after running the probes, what is the final classification of each of the 44, and how "
      "many remain UNKNOWN with a stated blocker?"),
  inp=[REG + "#candidates where classification==UNKNOWN-NEEDS-PROBE (44, recounted from the "
       "array not the counts block)", ARCH,
       f"{SPEC}:10723 (classification vocabulary incl. UNKNOWN-NEEDS-PROBE)"],
  dep=["WFA-1of2"], asg=A_ARCH, tl=TOOLS_BUILD, sub="local-serialized", to=7200,
  ev=EV_SPINE + ("each of the 44 rows carries the probe command actually run and its output "
                 "tail; a reclassification with no probe output is rejected"),
  ts=["a gate that blocks any candidate from entering the blueprint library while its "
      "classification is UNKNOWN-NEEDS-PROBE - verified by attempting to promote one"],
  rv=REV_ONE, rt=RETRY_LIVE,
  fc=["dependency-blocked", "uncontrolled-silence", "green-not-live"], og=False,
  mech="per-candidate settling-probe execution that retires the UNKNOWN class",
  nd=("resolves candidates whose class is ASSIGNED but unproven; WFA-0148 asks whether the "
      "classifier can even EXPRESS six of its own vocabulary values"),
  sa=f"{SPEC}:10723"),

 dict(
  t="Classifier expressiveness audit: six vocabulary values were never assigned",
  ph="2A", kind="classifier-audit",
  tg=("Six of the 15 declared classification values - CLEAN-ROOM-REIMPLEMENT, COMPOSE, "
      "GENERALIZE, REBUILD-FROM-SPEC, REJECT and TRANSLATE - are assigned to zero of the 284 "
      "candidates (recounted from the array). Question: is that a true property of the corpus or "
      "a classifier blind spot, settled by planting one candidate that MUST take each unused "
      "value and checking whether the classifier can emit it?"),
  inp=[REG + "#classification_vocabulary (15) vs assigned values (9)",
       f"{SPEC}:10723 (the 15-value classification vocabulary)"],
  dep=["WFA-1of2"], asg=A_ADV, tl=TOOLS_RO, sub="local-parallel", to=1800,
  ev=EV_SPINE + ("the recount is derived from candidates[].classification, independent of the "
                 "file's own counts block, and both readings are printed"),
  ts=["plant six synthetic candidates, one per unused value, and require the classifier to emit "
      "each; a value it cannot emit is a proven blind spot, not a corpus property"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["detector-failure", "overclaim", "uncontrolled-silence"], og=False,
  mech="unused-vocabulary blind-spot test by planting one forcing case per value",
  nd=("tests the CLASSIFIER's reachable output range; WFA-0147 runs probes for candidates "
      "already labelled UNKNOWN and never questions the label space"),
  sa=f"{SPEC}:10723"),

 dict(
  t="Resolve the 140 asymmetric compatibility declarations",
  ph="2B", kind="compat-repair",
  tg=("Across the 108 blueprints there are 390 declared compatibility references collapsing to "
      "265 undirected edges with 0 dangling, of which 140 are asymmetric - A declares B "
      "compatible while B does not declare A (re-derived from blueprints[].compat, independent of "
      "the merge doc's counts block). Question: for each of the 140, is the compatibility "
      "genuinely directional or is the reverse declaration simply missing, and what is the "
      "repaired symmetric graph?"),
  inp=[BPL + "#blueprints[].compat", MAPS + "#FINDING_asymmetric_compat",
       MAPS + "#composition_graph"],
  dep=["WFA-1of2"], asg=A_IMPL, tl=TOOLS_BUILD, sub="local-parallel", to=3600,
  ev=EV_SPINE + ("the 140 are enumerated as ordered pairs with a per-pair verdict "
                 "DIRECTIONAL or MISSING-REVERSE; a bulk symmetrise with no per-pair verdict is "
                 "rejected as data fabrication"),
  ts=["after repair, recompute asymmetry: DIRECTIONAL pairs must persist as directed edges and "
      "MISSING-REVERSE pairs must vanish; a run that drives asymmetry to 0 by symmetrising "
      "everything fails the test"],
  rv=REV_CONFIRM, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure", "uncontrolled-silence"], og=False,
  mech="per-pair adjudication of a measured graph asymmetry, with bulk-symmetrise banned",
  nd=("repairs the COMPATIBILITY relation; WFA-0150 executes the separately-declared CONFLICT "
      "rows, which are a different relation with a different truth condition"),
  sa=f"{SPEC}:11725" if False else f"{SPEC}:10725"),

 dict(
  t="Execute-to-confirm the 20 declared blueprint conflicts",
  ph="2B", kind="conflict-confirmation",
  tg=("The merge maps declare 20 conflict rows. Question: for each declared conflict, does "
      "running the two workflows together in one session actually produce the conflict (shared "
      "file, shared control plane, incompatible stop rule), and which rows are unreproducible "
      "and must be downgraded to SUSPECTED?"),
  inp=[MAPS + "#conflict_map (20 rows, recounted)", BPL, "WFA-0141 control-plane census"],
  dep=["WFA-0141", "WFA-0149"], asg=A_ADV, tl=TOOLS_BUILD, sub="local-serialized", to=5400,
  ev=EV_SPINE + ("each confirmed conflict cites the observed collision (path, plane or rule) "
                 "from a real co-execution; each unreproducible row is downgraded, not deleted"),
  ts=["a known-compatible pair must co-execute cleanly (negative control) while a known-"
      "conflicting pair must collide - the harness must distinguish them"],
  rv=REV_ONE, rt=RETRY_LIVE,
  fc=["overclaim", "detector-failure", "green-not-live"], og=False,
  mech="co-execution reproduction of a declared conflict, with downgrade instead of deletion",
  nd=("tests the CONFLICT relation by execution; WFA-0149 repairs the COMPATIBILITY relation by "
      "adjudicating declarations and never runs anything"),
  sa=f"{SPEC}:10725"),

 dict(
  t="Supply-chain map for the 105 external dependencies of the blueprint library",
  ph="2A", kind="supply-chain-map",
  tg=("The blueprint library requires 105 distinct external dependencies. Question: for each, "
      "what is the license, the current maintenance state, the pinned version, the advisory "
      "status, and the offline fallback if it disappears - and which of the 105 have no pin and "
      "no fallback?"),
  inp=[MAPS + "#external_dependency_map (105, recounted)", PROV + "#license_risk_register (45)",
       f"{SPEC}:11393-11395 (provenance/license records are a program stopping condition)"],
  dep=["WFA-1of2", "B03"], asg=A_LIC, tl=TOOLS_NET, sub="local-serialized", to=7200,
  ev=EV_SPINE + ("each row cites the upstream URL fetched and the date; a dependency whose "
                 "upstream cannot be reached is UNRESOLVED, not assumed healthy"),
  ts=["a dependency with a known advisory must be flagged and one with none must not - run both "
      "before trusting the clean rows"],
  rv=REV_ONE, rt=RETRY_NET,
  fc=["uncontrolled-silence", "dependency-blocked", "overclaim"], og=False,
  mech="per-dependency license/version/advisory/fallback resolution against live upstreams",
  nd=("maps what the library DEPENDS ON externally; WFA-0139 combines licenses at fusion time "
      "and WFA-0153 closes unresolved nodes inside the provenance graph"),
  sa=f"{SPEC}:11393"),

 dict(
  t="Workflow pack packaging, versioning and publication contract",
  ph="2B", kind="pack-contract",
  tg=("Specify and implement the unit of distribution for certified workflows: pack manifest, "
      "preset bundling, semantic versioning, channel, lineage carry-through and the marketplace "
      "publication record. Question: what exactly does a workflow pack contain, what does "
      "bumping its version require, and can a consumer install one pack version, roll back, and "
      "still resolve every lineage reference?"),
  inp=[f"{SPEC}:11167 (workflow packs, presets, versioning, and marketplace publication)",
       "WFA-0134 certification records", "WFA-0138 lineage records"],
  dep=["WFA-0134", "WFA-0138"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=3600,
  ev=EV_SPINE + ("an install / rollback / re-resolve cycle is executed against a fixture "
                 "marketplace and the resolved lineage set is compared before and after"),
  ts=["a pack containing an uncertified workflow must be refused at publish; the same pack with "
      "the workflow certified must publish (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["green-not-live", "dependency-blocked", "overclaim"], og=False,
  mech="pack manifest + versioning + publish/rollback lineage resolution",
  nd=("defines the DISTRIBUTION unit; WFA-0137 revokes a certification and WFA-0142 replaces a "
      "workflow - both consume this contract rather than defining it"),
  sa=f"{SPEC}:11167"),

 dict(
  t="Close the unresolved nodes in the 466-node provenance graph",
  ph="2A", kind="provenance-closure",
  tg=("The provenance and license graph holds 466 nodes and 1025 edges and carries an explicit "
      "FINDING_unresolved_provenance with an unresolved_refs list and a settling_probe. "
      "Question: after running that probe, how many nodes still fail to resolve to a real source, "
      "and does each survivor carry a named blocker rather than an assumed origin?"),
  inp=[PROV + "#nodes (466) #edges (1025) #FINDING_unresolved_provenance", ARCH, REG],
  dep=["WFA-1of2"], asg=A_ARCH, tl=TOOLS_BUILD, sub="local-parallel", to=5400,
  ev=EV_SPINE + ("resolution is by fetching or reading the cited source, not by inferring it "
                 "from the node name; unresolved survivors are listed individually"),
  ts=["plant one node with a fabricated source and confirm the closure pass marks it "
      "UNRESOLVED rather than accepting the name as evidence"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["uncontrolled-silence", "overclaim", "detector-failure"], og=False,
  mech="node-by-node source resolution that fails closed on an unverifiable origin",
  nd=("closes STATIC graph nodes; WFA-0139 propagates licenses through a FUSION and WFA-0151 "
      "resolves EXTERNAL runtime dependencies - three different object sets"),
  sa=f"{SPEC}:10725"),

 dict(
  t="Executed-corpus replay differential for the 72 H-family candidates",
  ph="2A", kind="replay-differential",
  tg=("72 of the 284 candidates are family H-executed-corpus - workflows reconstructed from runs "
      "that actually happened. Question: when the reconstructed blueprint is replayed against the "
      "recorded execution, do the stage sequence, gates and stopping point match, and which "
      "reconstructions are contradicted by their own transcript?"),
  inp=[REG + "#candidates where family==H-executed-corpus (72, recounted)", ARCH, BPL,
       f"{SPEC}:10721 (search prior artifacts and transcripts)"],
  dep=["WFA-1of2"], asg=A_ARCH, tl=TOOLS_BUILD, sub="local-serialized", to=7200,
  ev=EV_SPINE + ("the differential cites the transcript record id and the specific stage index "
                 "where reconstruction and recording diverge"),
  ts=["replay a reconstruction that is deliberately altered at one stage and confirm the "
      "differential names that stage; replay an unaltered one and confirm zero divergence"],
  rv=REV_ONE, rt=RETRY_LIVE,
  fc=["overclaim", "detector-failure", "green-not-live"], og=False,
  mech="recorded-run versus reconstructed-blueprint stage-level differential",
  nd=("validates that a SALVAGED workflow matches the run it was salvaged from; no other unit "
      "compares a blueprint against a historical execution record"),
  sa=f"{SPEC}:10721"),

 dict(
  t="Translation fidelity oracle for the TRANSLATE route",
  ph="2B", kind="translation-oracle",
  tg=("Exactly one of the 108 blueprints carries route TRANSLATE and zero of the 284 candidates "
      "are classified TRANSLATE, so the translation path is effectively untested. Question: for a "
      "workflow translated from a foreign orchestration format onto this control plane, does the "
      "translation preserve stage order, gate semantics and stopping conditions - and what is the "
      "oracle that proves it rather than asserting it?"),
  inp=[BPL + "#blueprints route==TRANSLATE (1, recounted)",
       REG + "#classification TRANSLATE (0, recounted)",
       f"{SPEC}:10723 (TRANSLATE classification)", f"{SPEC}:11159 (import and translation adapters)"],
  dep=["WFA-1of2", "WFA-0141"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=5400,
  ev=EV_SPINE + ("fidelity is demonstrated by executing source and translation on the same case "
                 "and diffing the stage/gate/stop trace, not by structural inspection alone"),
  ts=["mutate one gate in the translation and require the oracle to fail; leave it intact and "
      "require it to pass (both-states)"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["overclaim", "detector-failure", "uncontrolled-silence"], og=False,
  mech="execution-trace equivalence oracle for a cross-format translation",
  nd=("proves a TRANSLATION preserves semantics; WFA-0141 only counts control planes and would "
      "pass a semantically wrong but single-plane translation"),
  sa=f"{SPEC}:11159"),

 dict(
  t="Typed stopping-rule algebra with executable evaluation",
  ph="2B", kind="stop-rule-algebra",
  tg=("Extract every blueprint's stopping rule into one typed algebra supporting composable "
      "ANY / ALL / NOT expressions, and make each rule EVALUABLE against a live run state rather "
      "than merely documented. Question: how many of the 108 blueprints have a stop rule that "
      "compiles to an evaluable expression, which reduce to prose that cannot be evaluated, and "
      "which have no stop rule at all?"),
  inp=[BPL + "#blueprints[].stop", f"{SPEC}:10911 (documented stopping rules)",
       f"{SPEC}:10760 (composable stopping rules with ANY, ALL, and weighted logic)"],
  dep=["WFA-1of2"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=5400,
  ev=EV_SPINE + ("the compile result per blueprint is EVALUABLE / PROSE-ONLY / ABSENT with the "
                 "raw stop text quoted for every non-evaluable case"),
  ts=["an expression that can never become true must be rejected at compile time; an expression "
      "that is already true at t0 must be flagged as a degenerate immediate stop"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["overclaim", "uncontrolled-silence", "detector-failure"], og=False,
  mech="stop-rule compilation to an evaluable boolean algebra with degenerate-case rejection",
  nd=("makes stop rules EXECUTABLE; WFA-0157 fixes which field a gate may read and does not "
      "compile anything"),
  sa=f"{SPEC}:10911"),

 dict(
  t="Machine-consumer field contract: gate on state_v/size_v, never the free-text gloss",
  ph="2B", kind="field-contract",
  tg=("09-WORKFLOW-BLUEPRINT-LIBRARY.json declares controlled vocabularies for `state` (FOUND, "
      "REPAIRED, MERGED, NEW) while the `state` field itself is a human gloss: recounting the "
      "array yields 36 distinct literals, so only 74 of 108 records match a vocabulary token "
      "exactly and 34 do not. The artifact already directs machine consumers to `state_v`/"
      "`size_v`. Question: does every gate, filter and report in the foundry read the decomposed "
      "`*_v` fields, and does a lint fail the build when any consumer reads the gloss?"),
  inp=[BPL + "#vocabularies_rule", BPL + "#blueprints[].state vs state_v",
       f"{SPEC}:11302 (strict plugin parser rejects unknown fields)"],
  dep=["WFA-1of2"], asg=A_IMPL, tl=TOOLS_BUILD, sub="worktree-isolated", to=1800,
  ev=EV_SPINE + ("the 34/108 non-literal count is re-derived from the array, and the lint is "
                 "shown firing on a deliberately gloss-reading consumer"),
  ts=["write a consumer that reads `state` and assert the lint fails the build; switch it to "
      "`state_v` and assert the build passes (both-states)"],
  rv=REV_ONE, rt=RETRY_DEFAULT,
  fc=["detector-failure", "overclaim", "green-not-live"], og=False,
  mech="static lint forbidding gloss-field reads in machine consumers",
  nd=("constrains WHICH FIELD a consumer may read; WFA-0156 constrains what a stop rule must "
      "COMPILE to. A gate can satisfy one and violate the other"),
  sa=f"{SPEC}:11302"),

 dict(
  t="Prompt-injection quarantine for ingested third-party workflow artifacts",
  ph="2A", kind="ingestion-quarantine",
  tg=("Workflow definitions, transcripts and README text pulled in during archaeology are "
      "untrusted DATA that later stages render into prompts. Question: does an adversarial "
      "instruction embedded in an ingested candidate reach a downstream stage as an instruction, "
      "and does the quarantine (neutralise, tag, render-as-data) stop it without discarding the "
      "candidate's legitimate content?"),
  inp=[f"{SPEC}:11057 (workflow prompt injection refuter)",
       f"{SPEC}:11344 (participant artifact injects instructions into later stages)",
       REG + "#candidates.origin", ARCH],
  dep=["WFA-1of2"], asg=A_ADV, tl=TOOLS_BUILD, sub="local-serialized", to=5400,
  ev=EV_SPINE + ("at least five distinct injection payload shapes are executed end to end "
                 "against the ingestion path, and the downstream prompt is captured verbatim"),
  ts=["each payload must be neutralised AND the candidate's real content must survive - a "
      "quarantine that simply drops the candidate fails the test"],
  rv=REV_CROSS, rt=RETRY_LIVE,
  fc=["green-not-live", "detector-failure", "overclaim"], og=False,
  mech="end-to-end injection replay through the ingestion path with content preservation",
  nd=("defends the INGESTION boundary against hostile content; WFA-0141 counts runtimes and "
      "WFA-0151 checks upstream advisories - neither reads artifact text as an attack surface"),
  sa=f"{SPEC}:11057"),

 dict(
  t="Freshness and revalidation decay for adopted external candidates",
  ph="2A", kind="freshness-monitor",
  tg=("122 of the 284 candidates are classified ADOPT-AS-IS and 20 ADOPT-WITH-WRAPPER "
      "(recounted), each resting on an upstream whose maintenance state, license and version can "
      "change after adoption. Question: what is the revalidation interval per candidate, which "
      "adoptions are already stale against their upstream today, and what signal demotes a stale "
      "adoption back to UNKNOWN-NEEDS-PROBE?"),
  inp=[REG + "#candidates.maintenance #candidates.license (142 adopt-class rows, recounted)",
       f"{SPEC}:10714 (freshness/revalidation audit)", PROV],
  dep=["WFA-0151"], asg=A_LIC, tl=TOOLS_NET, sub="local-serialized", to=5400,
  ev=EV_SPINE + ("staleness is measured against a live upstream read with the fetch date "
                 "recorded; an unreachable upstream is UNKNOWN, never 'still fine'"),
  ts=["an upstream archived or relicensed since adoption must demote the candidate; an unchanged "
      "upstream must not - run both before trusting the unchanged verdicts"],
  rv=REV_ONE, rt=RETRY_NET,
  fc=["green-not-live", "uncontrolled-silence", "dependency-blocked"], og=False,
  mech="time-decay revalidation that demotes an adoption when its upstream changes",
  nd=("demotes on an UPSTREAM change over time; WFA-0137 revokes on an INTERNAL regression and "
      "WFA-0151 inventories dependencies once without a decay clock"),
  sa=f"{SPEC}:10714"),

 dict(
  t="Bucket completeness recount: searched source classes and the trivial-fork discount",
  ph="2A", kind="completeness-audit",
  tg=("The spec enumerates the source classes archaeology must exhaust and forbids counting "
      "trivial forks or renamed copies toward the >=160 candidate floor. Question: which of the "
      "enumerated source classes were never actually searched, and after discounting trivial "
      "forks and renamed copies from the 284 recounted candidates, does the floor still hold?"),
  inp=[f"{SPEC}:10721 (the enumerated source classes)",
       f"{SPEC}:10725 (research at least 160 candidates; do not count trivial forks or renamed "
       "copies)", REG + "#candidates (284, recounted)", ARCH],
  dep=["WFA-0147", "WFA-0148", "WFA-0153", "WFA-0154"], asg=A_XV, tl=TOOLS_XV,
  sub="local-parallel", to=3600,
  ev=EV_SPINE + ("the searched-class set is compared MECHANICALLY against the spec's enumerated "
                 "list, and the discounted count is recomputed from the candidate array"),
  ts=["plant one obvious renamed copy of an existing candidate and require the discount pass to "
      "remove it; plant one genuinely distinct candidate and require it to survive"],
  rv=REV_CROSS, rt=RETRY_DEFAULT,
  fc=["overclaim", "uncontrolled-silence", "detector-failure"], og=False,
  mech="spec-enumerated-set difference plus a trivial-fork discount recount of the floor",
  nd=("audits THIS BUCKET's own coverage and re-derives the floor after discounting; every other "
      "unit produces or repairs an artifact rather than auditing the bucket"),
  sa=f"{SPEC}:10725"),
]


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:52].rstrip("-")


def build() -> list[dict]:
    units = []
    for i, u in enumerate(U):
        n = 129 + i
        uid = f"WFA-{n:04d}"
        units.append({
            "id": uid,
            "title": u["t"],
            "phase": u["ph"],
            "question_or_target": u["tg"],
            "inputs": u["inp"],
            "dependencies": u["dep"],
            "assigned_model_vendor_role": u["asg"],
            "tool_permissions": u["tl"],
            "execution_substrate": u["sub"],
            "timeout_seconds": u["to"],
            "output_path": f"command-center/foundry/{uid}-{slug(u['t'])}.json",
            "output_schema": SCHEMA.format(kind=u["kind"]),
            "evidence_requirement": u["ev"],
            "tests_required": u["ts"],
            "reviewer_requirement": u["rv"],
            "completion_sentinel": f"SUCCESS:{uid}",
            "retry_policy": u["rt"],
            "failure_classification": u["fc"],
            "owner_approval_required": u["og"],
            # --- non-contract metadata (strippable on fold-in) ---
            "bucket": "B04",
            "mechanism": u["mech"],
            "not_a_duplicate_because": u["nd"],
            "spec_anchor": u["sa"],
        })
    return units


CONTRACT = ("id", "title", "phase", "question_or_target", "inputs", "dependencies",
            "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
            "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
            "tests_required", "reviewer_requirement", "completion_sentinel",
            "retry_policy", "failure_classification", "owner_approval_required")

STOP = set("a an the and or of to for that this with is are be as by on in it its from not "
           "must every each which what when does do not no any all one two".split())


def toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_-]+", s.lower()) if w not in STOP and len(w) > 2}


def jac(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def check(units: list[dict], label: str) -> list[str]:
    err: list[str] = []
    ids = [u["id"] for u in units]
    if len(set(ids)) != len(ids):
        err.append("duplicate ids")
    for i, u in enumerate(units):
        want = f"WFA-{129 + i:04d}"
        if u["id"] != want:
            err.append(f"{u['id']}: expected sequential {want}")
        for f in CONTRACT:
            if f not in u:
                err.append(f"{u['id']}: missing field {f}")
            elif f != "owner_approval_required" and not u[f]:
                err.append(f"{u['id']}: empty field {f}")
        if not isinstance(u["owner_approval_required"], bool):
            err.append(f"{u['id']}: owner_approval_required not bool")
        if u["execution_substrate"] not in SUBSTRATES:
            err.append(f"{u['id']}: bad substrate {u['execution_substrate']}")
        if u["phase"] not in PHASES:
            err.append(f"{u['id']}: bad phase {u['phase']}")
        for fc in u["failure_classification"]:
            if fc not in FAILCLASSES:
                err.append(f"{u['id']}: failure class {fc} outside catalog vocabulary")
        if "?" not in u["question_or_target"]:
            err.append(f"{u['id']}: question_or_target has no question")
        if u["completion_sentinel"] != f"SUCCESS:{u['id']}":
            err.append(f"{u['id']}: sentinel mismatch")
    # pairwise near-duplicate scan over title + target + mechanism
    dupes = []
    for a in range(len(units)):
        for b in range(a + 1, len(units)):
            ta = toks(units[a]["title"] + " " + units[a]["question_or_target"] + " " +
                      units[a]["mechanism"])
            tb = toks(units[b]["title"] + " " + units[b]["question_or_target"] + " " +
                      units[b]["mechanism"])
            j = jac(ta, tb)
            if j >= 0.40:
                dupes.append((units[a]["id"], units[b]["id"], round(j, 3)))
    if dupes:
        err.append(f"near-duplicate pairs >=0.40: {dupes}")
    print(f"[{label}] units={len(units)} errors={len(err)}")
    return err


def main() -> int:
    units = build()

    # --- detector control: the dup scanner must FIRE on a planted clone ------
    planted = [dict(x) for x in units]
    clone = dict(planted[5])
    clone["id"] = planted[7]["id"]
    clone["title"] = planted[7]["title"]
    clone["completion_sentinel"] = f"SUCCESS:{clone['id']}"
    planted[7] = clone
    ctrl_err = check(planted, "CONTROL-planted-clone")
    fired = any("near-duplicate" in e for e in ctrl_err)
    print(f"[CONTROL] dup detector fired on planted clone: {fired}")
    if not fired:
        print("FAILED:wfa2 dup detector is silent on a known-duplicate state; refusing to write")
        return 1

    errs = check(units, "REAL")
    for e in errs:
        print("  VIOLATION:", e)
    if errs:
        print("FAILED:wfa2 slice violates its own contract; nothing written")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(units, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"SUCCESS:wfa2 wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
