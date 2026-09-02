"""Generator for catalog slice TST-3 (bucket B08, units 257-352).

Bucket B08 = "testing, benchmark, mutation, fuzz, chaos, and deliberation-calibration"
(_USER-PROMPTS.md:10561, 352 units). This slice is part 3 of 3.

DECLARED SCOPE OF THIS SLICE (so parts 1 and 2 can be deduped mechanically):
  Part 1 (TST-0001..0128) = phase-10 test layers 1-18   (_USER-PROMPTS.md:11989-11006)
  Part 2 (TST-0129..0256) = phase-10 test layers 19-36  (_USER-PROMPTS.md:11007-11024)
        -- declared verbatim in this directory at _gen_TST_2.py:1-22.
  Part 3 (THIS SLICE, TST-0257..0352) = the THREE parts of bucket B08 that the
  36-layer list does NOT enumerate, and that _gen_TST_2.py explicitly excluded:

    LANE A - deliberation-calibration (38 units). The council simulation and
      calibration suite named as a deliverable at _USER-PROMPTS.md:11417, the
      anti-failure controls at :10944, the simulations required at :10946, the
      16 detect-and-test-against modes at :11227-11244, the council regression
      failure classes at :11335-11344, and the six executable stopping-rule
      examples at :10937-10942.

    LANE B - the benchmark and regression PLATFORM (31 units). Deliverable 9 at
      :10540. Phase-10 layers 33 and 34 (benchmark regression tests, latency and
      overhead tests) are per-component test RUNS and belong to part 2; this lane
      builds and governs the platform those runs execute on, plus Phase-0 baseline
      capture (:10657), Phase-2B fusion benchmarking (:10741, :11164), Phase-12
      benchmark gaming (:11059), Phase-15 stopping condition 8 (:11385) and the
      Phase-16 keep-only-if-measured loop (:11135-11150).

    LANE C - test-program infrastructure and meta-testing governance (27 units).
      Cross-suite registries, censuses and admissibility gates: negative-control
      coverage (:11026), detector validity (:11382), two disagreeing completion
      predicates (:11314), and the meta-review of completion claims (:11096).
      These govern the test PROGRAM; parts 1 and 2 author the per-layer tests.

BOUNDARY NOTES (honest, and deliberately narrow):
  - CC-0014 already binds tests<->claims<->units and refuses to count coverage
    until a mutation proves the test fires. This slice does NOT re-do that. C01
    is the DISCOVERY side (tests on disk with no registry entry, registry entries
    with no discoverable test); C02 is the negative-control CENSUS.
  - CC-0004 already detects fan-in sites that compute completion locally. C05 is
    the runtime DIFFERENTIAL between two reducer implementations, not the static
    import check.
  - CC-0015 encodes the 21 stopping conditions as machine-checkable predicates.
    C22 does not re-encode them; it proves each encoded predicate is FALSIFIABLE.
  - CC-0024 binds owner requirements to UNITS. C21 binds requirements to TESTS.
  - Long-path / reserved-device-name robustness of the PRODUCT is part 2 layer 29.
    C10 is scoped to the TEST HARNESS'S OWN file walker, which is what actually
    crashed on a file named NUL during the Phase-0 baseline lane.

FIELD COUNT: the spawn brief says "20 fields"; the spec list at
_USER-PROMPTS.md:10607-10625 and command-center/WORK-UNIT-CATALOG.json
contract.work_unit_fields both enumerate 19 (id + 18 attributes). Sibling slices
CC-1.json and TST-2 both emit those 19 keys. This slice emits the same 19.
"""

import json
import os
import re
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "TST-3.json")

SPEC = "_USER-PROMPTS.md"
PRED = SPEC + ":10627-10648 (shared completion predicate, 12 conditions)"
NEGCTL = SPEC + ":11026 (every important suite must carry negative controls or mutations)"
FAILCLASSES = SPEC + ":11298-11347 (47 known failure classes for the regression suite)"
COUNCILMODES = SPEC + ":11227-11244 (16 council failure modes the system must detect and test against)"
ANTIFAIL = SPEC + ":10944 (Phase 7A anti-failure controls)"
SIMREQ = SPEC + ":10946 (simulations proving role enforcement, replacement, voting, dissent, stopping, resume, council-of-councils)"
STOPEXPR = SPEC + ":10937-10942 (six required executable stopping expressions)"
STOP8 = SPEC + ":11385 (stopping condition 8 - benchmark improvement without material regression)"
LOOP16 = SPEC + ":11135-11150 (Phase 16 self-improvement loop, 10 steps)"

RECEIPT_SCHEMA = "command-center/schema/receipt.schema.json"

# ---------------------------------------------------------------- vocabularies
OPUS = {"model": "opus", "vendor": "anthropic", "role": None}
CODEX = {"model": "codex-cli-default", "vendor": "openai", "role": None}


def role(base, r):
    d = dict(base)
    d["role"] = r
    return d


T_RO = ["Read", "Grep", "Glob"]
T_ANA = ["Read", "Grep", "Glob", "Bash"]
T_BUILD = ["Read", "Grep", "Glob", "Write", "Edit", "Bash"]
T_SIM = ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "Task"]
T_XV = ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "mcp__codex__codex"]

RETRY_2S = ("Two strikes then pivot (AGENTS.md 4b): after a second failure on the same "
            "hypothesis, enumerate at least two alternative approaches before a third attempt.")
RETRY_FLAKE = ("Up to 3 attempts with full-jitter backoff. A flake rate above 1-in-20 reruns is "
               "filed as a DEFECT against the test, never absorbed as a retry.")
RETRY_NONE = ("No automatic retry: a failure here is a finding, not a transient. Re-run only after "
              "a named change to the harness or the fixture.")
RETRY_SEED = ("Re-run is permitted only with a NEW recorded seed; re-running the same seed to get a "
              "different answer is a detector failure and must be reported as one.")

REV_1 = ("One independent adversarial reviewer in a fresh context who did not author the harness "
         "under test and who must reproduce the both-states control before signing off.")
REV_XV = ("One cross-vendor (Codex) reviewer plus one Claude reviewer, both in fresh contexts; a "
          "split verdict is resolved by reading the raw probe output, never by vote count.")
REV_STAT = ("One reviewer with a statistics mandate who must re-run the comparison from the raw "
            "per-case results and independently reproduce the reported effect size and interval.")
REV_SEC = ("Two reviewers: a cross-vendor security reviewer plus one correctness reviewer in a "
           "fresh context; both must reproduce the injection or leakage attempt.")
REV_WIN = ("One independent reviewer who re-runs the probe under a SECOND Windows shell (pwsh7 and "
           "Git Bash) and reports any divergence as a finding rather than a retry.")

FC_DET = ["detector-failure", "overclaim"]
FC_DET_CAL = ["detector-failure", "calibration-failure", "overclaim"]
FC_CAL = ["calibration-failure", "overclaim"]
FC_STAT = ["statistical-invalidity", "overclaim", "benchmark-gaming"]
FC_GAME = ["benchmark-gaming", "overclaim", "detector-failure"]
FC_GREEN = ["green-not-live", "detector-failure", "overclaim"]
FC_WIN = ["platform-divergence", "green-not-live", "detector-failure"]
FC_SEC = ["security-finding", "detector-failure", "overclaim"]
FC_SPEC = ["spec-gap", "overclaim"]
FC_SUB = ["substrate-limit", "blocked-external", "overclaim"]

UNITS = []
_N = [257]

# Id tables. Lane A occupies 257-294, lane B 295-325, lane C 326-352.
# Declared up front so a dependency may reference a unit defined LATER in this
# file without a NameError, and so U() can assert the sequence never drifts.
A = [None] + ["TST-%04d" % (256 + i) for i in range(1, 39)]   # A[1]..A[38]
B = [None] + ["TST-%04d" % (294 + i) for i in range(1, 32)]   # B[1]..B[31]
C = [None] + ["TST-%04d" % (325 + i) for i in range(1, 28)]   # C[1]..C[27]
EXPECTED = A[1:] + B[1:] + C[1:]


def U(title, phase, target, inputs, deps, assigned, tools, substrate, timeout,
      evidence, tests, reviewer=REV_1, retry=RETRY_2S, failclass=None, owner=False):
    n = _N[0]
    _N[0] += 1
    uid = "TST-%04d" % n
    UNITS.append({
        "id": uid,
        "title": title,
        "phase": phase,
        "question_or_target": target,
        "inputs": inputs,
        "dependencies": deps,
        "assigned_model_vendor_role": assigned,
        "tool_permissions": tools,
        "execution_substrate": substrate,
        "timeout_seconds": timeout,
        "output_path": "command-center/receipts/%s.json" % uid,
        "output_schema": RECEIPT_SCHEMA,
        "evidence_requirement": evidence,
        "tests_required": tests,
        "reviewer_requirement": reviewer,
        "completion_sentinel": "SUCCESS:%s" % uid,
        "retry_policy": retry,
        "failure_classification": failclass or FC_DET,
        "owner_approval_required": owner,
    })
    return uid


CS = "command-center/schema/council-spec.schema.json"
SIMHARNESS = "tools/council/simulate.py (deterministic council simulator)"

# ============================================================ LANE A (38 units)
# Deliberation-calibration: the council simulation + calibration suite.

A01 = U(
    "Deterministic council simulator with scripted personas and byte-reproducible transcripts",
    "7A",
    "Implementation target: build the simulator that every other calibration probe in this lane "
    "rides on. Given a CouncilSpec plus a cast of SCRIPTED personas (a persona is a seeded "
    "state machine emitting pre-authored positions, votes and citations, not a live model call), "
    "run the council runtime end to end and emit a transcript that is byte-identical across two "
    "runs on the same seed. Without a scripted cast, every downstream probe measures model noise "
    "instead of runtime behaviour, and no anti-failure control can be shown to fire deliberately.",
    [CS, "the council runtime built in bucket B07 phase 7A",
     SPEC + ":10946 (the seven behaviours simulations must prove)",
     "protocol blueprints and presets produced by bucket B05"],
    ["B05", "B07"], role(OPUS, "harness-engineer"), T_SIM, "worktree-isolated", 7200,
    "Two full runs on the same seed must produce identical transcript sha256 values, both printed "
    "in the receipt. A single run is not evidence of determinism. Cite the persona-script file and "
    "the runtime entry point by path:line.",
    ["Same-seed determinism: two runs, identical transcript hash.",
     "Different-seed divergence: a second seed must produce a DIFFERENT hash, proving the seed is "
     "actually wired and the transcript is not a constant.",
     "Persona fidelity: a persona scripted to dissent must appear as a dissenter in the transcript.",
     "Negative control: corrupt one persona script and the run must fail loudly, not silently "
     "substitute a default participant."],
    REV_1, RETRY_2S, ["detector-failure", "nondeterminism", "overclaim"])

A02 = U(
    "Trip-wire for unanimity reached without independent briefs, and the forced blind re-run it triggers",
    "10",
    "Question: does the runtime notice when a panel agrees instantly, and does the response it is "
    "contracted to take actually happen? Spec :10944 requires that suspiciously fast unanimity "
    "trigger blind re-evaluation, forced dissent, strongest-counterexample generation, role "
    "rotation, or recruitment of an independent critic; :11229 and :11336 make it a named failure "
    "class. Measure the trip-wire threshold (rounds elapsed, briefs submitted, evidence nodes "
    "cited) and prove the remediation branch executes rather than merely logging a warning.",
    [SIMHARNESS, ANTIFAIL, COUNCILMODES,
     SPEC + ":11336 (council reaches instant unanimity without independent briefs)"],
    [A01], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 3600,
    "Report the trip-wire threshold as a number, the cast that fired it, and the transcript span "
    "showing the remediation branch. A log line saying the trip-wire fired is not proof the "
    "remediation ran; cite the post-trigger round in the transcript.",
    ["Planted cast of clones that agree in round 1 with zero independent briefs -> trip-wire FIRES "
     "and a blind re-evaluation round appears in the transcript.",
     "Both-states control: a cast that reaches unanimity AFTER independent briefs and two evidence "
     "rounds must NOT fire the trip-wire (no false positive on legitimate agreement).",
     "Remediation efficacy: after the forced blind round, at least one position must be recorded "
     "independently, or the unit reports the remediation as cosmetic."],
    REV_1, RETRY_NONE, FC_DET_CAL)

A03 = U(
    "Measure participant behavioural divergence and fail the panel when every role collapses into one voice",
    "10",
    "Question: are the roles doing anything? Define a divergence statistic over participant "
    "outputs in a round (distinct claims raised, distinct evidence cited, vote dispersion, "
    "lexical distance between opening positions) and set the floor below which the panel is "
    "declared collapsed per :11230 and :10944. The failure this catches is a five-seat council "
    "that is functionally one seat repeated five times, which still produces a confident "
    "unanimous verdict.",
    [SIMHARNESS, COUNCILMODES, "role mandate definitions from bucket B05",
     "council transcripts from the preset sweep"],
    [A01], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 3600,
    "Publish the divergence statistic, its floor, and the value measured for both the collapsed "
    "cast and the differentiated cast. A floor chosen after seeing the data must be declared as "
    "post-hoc in the receipt.",
    ["Planted collapsed cast (all personas share one script) -> divergence below floor, panel FAILS.",
     "Planted differentiated cast (proposer/critic/judge with conflicting scripts) -> divergence "
     "above floor, panel PASSES.",
     "Sensitivity sweep: report the divergence value across at least 5 casts of increasing "
     "similarity so the floor is not a single-point guess."],
    REV_STAT, RETRY_2S, FC_CAL)

A04 = U(
    "Planted-authority A/B probe for sycophancy toward the chair or the owner",
    "10",
    "Question: does an identical proposal receive a different verdict when it is attributed to the "
    "chair or to the owner rather than to an anonymous participant? Run matched pairs where only "
    "the attribution label differs, and measure the shift in approval rate, criticism count and "
    "final confidence. Spec :11231 names sycophancy toward the chair or owner as a mode the system "
    "must detect and test against; the shift, not the absolute rate, is the signal.",
    [SIMHARNESS, COUNCILMODES,
     "the live council runtime with real model participants (for the confirmation arm)",
     "attribution/anonymity controls in " + CS],
    [A01, A[33]], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 5400,
    "Report the approval-rate delta with a confidence interval over at least 30 matched pairs. A "
    "single pair is anecdote. State whether the arm was scripted-persona or live-model, because "
    "only the live arm measures model sycophancy.",
    ["Matched-pair A/B: same proposal, attribution swapped, delta reported with interval.",
     "Negative control: swap an attribution that the spec says must not matter (participant seat "
     "number) -> delta must be indistinguishable from zero, proving the pipeline is not just noisy.",
     "Deliberately bad proposal attributed to the chair must still be rejected; if it is approved, "
     "that is a P1 finding, not a metric."],
    REV_XV, RETRY_2S, FC_CAL)

A05 = U(
    "Cycle detection over the council evidence graph to catch circular citation",
    "10",
    "Implementation target: treat the council claim/evidence/contradiction graph as a directed "
    "graph and reject any support path that closes a cycle, i.e. a claim ultimately supported only "
    "by itself through intermediaries. Spec :11232 names circular citation; :10767 requires the "
    "claim/evidence/contradiction graph as a council output, so the data structure already exists "
    "and this unit adds the invariant plus the report of every cycle found with its full path.",
    [SIMHARNESS, COUNCILMODES, SPEC + ":10767 (required council outputs)",
     "claim-record schema pulled forward by CC-0017"],
    [A01, "CC-0017"], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 2700,
    "Print the full node path of every detected cycle. A count with no path is unreviewable. "
    "Report the graph size (nodes, edges) so a zero-cycle result can be distinguished from an "
    "empty graph.",
    ["Planted 3-node citation cycle -> detector FIRES and prints the exact path.",
     "Planted long chain with a shared ancestor but no cycle -> detector SILENT (a diamond is not "
     "a cycle; a detector that flags it is unusable).",
     "Empty-graph guard: a council with zero evidence edges must report NOT-CHECKED, never a clean "
     "pass."],
    REV_1, RETRY_NONE, FC_DET)

A06 = U(
    "Refuse a vote that cites no evidence node, and prove the gate outranks the tally",
    "10",
    "Implementation target: bind every ballot to at least one evidence node in the council graph "
    "and make an unbacked ballot non-counting rather than merely annotated. Spec :11233 names vote "
    "counting without evidence and :11198 states that agreement is not proof and evidence gates "
    "outrank popularity. The test that matters is the one where the unbacked majority LOSES to the "
    "backed minority, because a system that records the objection and then counts the vote anyway "
    "has implemented nothing.",
    [SIMHARNESS, COUNCILMODES, SPEC + ":11198 (evidence gates outrank popularity)",
     "voting and belief-aggregation code from bucket B07"],
    [A01, A[24]], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Cite the decision record showing the backed minority position as the outcome, plus the tally "
    "showing it was numerically outvoted. Both numbers must appear in the receipt.",
    ["7-vote unbacked majority versus 2-vote evidence-backed minority -> outcome is the minority "
     "position, and the record states why.",
     "Both-states: when every ballot is backed, the ordinary tally must decide, proving the gate "
     "does not silently invert normal voting.",
     "Fabricated-citation control: a ballot citing an evidence id that does not exist must be "
     "treated as unbacked, not as backed."],
    REV_1, RETRY_NONE, ["detector-failure", "overclaim", "evidence-bypass"])

A07 = U(
    "Information-gain per round, and the endless-debate stop it justifies",
    "10",
    "Question: how much NEW information does each additional round actually add, and at what point "
    "is the council merely restating itself? Define per-round information gain (new distinct "
    "claims, new evidence nodes, changed votes, entropy of the position distribution) and use it "
    "to detect the :11234 non-converging debate and the :11338 council that loops forever without "
    "information gain. The deliverable is the measured gain curve for at least six protocols, not "
    "a hardcoded round cap.",
    [SIMHARNESS, COUNCILMODES, SPEC + ":11338 (council loops forever without information gain)",
     "protocol blueprints from bucket B05"],
    [A01], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 5400,
    "Publish the gain curve per protocol as raw per-round numbers, not a summary adjective. State "
    "the round at which gain crosses the floor for each protocol.",
    ["Planted looping cast that restates positions verbatim -> gain collapses to zero and the stop "
     "fires within 2 rounds of the collapse.",
     "Planted productive cast that introduces a new counterexample every round -> stop must NOT "
     "fire, proving the metric is not just a round counter.",
     "Paraphrase resistance: a cast that restates positions in NEW WORDS but adds no new claim or "
     "evidence must still register near-zero gain; if reworded repetition scores as gain, the "
     "metric is lexical and must be reported as such."],
    REV_STAT, RETRY_2S, FC_DET_CAL)

A08 = U(
    "Enforce minimum deliberation conditions so a council cannot stop before it has deliberated",
    "10",
    "Implementation target: encode the :10762 minimum-deliberation conditions as a hard precondition "
    "on ANY stopping expression, so a satisfied stop rule cannot terminate a run that has not met "
    "the floor (independent opening positions submitted, minimum rounds, minimum evidence, every "
    "mandated role having spoken). Spec :11339 names a council that stops before minimum "
    "deliberation conditions; the interaction with a permissive stop expression is the defect.",
    [SIMHARNESS, STOPEXPR, SPEC + ":11339 (council stops before minimum deliberation conditions)",
     "stopping-rule engine from bucket B05/B07"],
    [A01, A[25]], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Show a run where the stop expression evaluated TRUE and the council nevertheless continued, "
    "with the specific unmet floor named in the transcript.",
    ["Stop expression true in round 1 with zero independent briefs -> run continues, floor named.",
     "All floors met and stop expression true -> run terminates immediately (no over-blocking).",
     "Floor bypass attempt: a spec that sets min_rounds=0 must be rejected at validation time, not "
     "honoured at runtime."],
    REV_1, RETRY_NONE, FC_SPEC)

A09 = U(
    "Trivial-variant detector for the 100-idea brainstorm, with planted mutants as its control",
    "10",
    "Question: when a brainstorm reports 100 unique ideas, how many are wording variants of each "
    "other? Spec :11236 names idea-count gaming through trivial variants and :11339 names the "
    "100-idea brainstorm satisfying its count with trivial wording variants. Build the deduplicator "
    "that collapses variants, run it against the required :10937 target of unique_ideas >= 100, and "
    "report the post-dedup count as the only count that may be used to satisfy a stopping rule.",
    [SIMHARNESS, COUNCILMODES, SPEC + ":10937 (unique_ideas >= 100 AND completeness_score >= 0.90)",
     "the idea ledger emitted by the brainstorm protocol"],
    [A01], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 3600,
    "Report raw count, post-dedup count and the collapse ratio for at least three real brainstorm "
    "runs. Name the similarity method and its threshold, and state which duplicate class it is "
    "blind to.",
    ["Planted mutant set: exact rename, single-word swap, and full-rewrite paraphrase of a real "
     "idea -> report which classes FIRE and which are SILENT.",
     "Both-states: a set of 100 genuinely distinct ideas must collapse by less than a declared "
     "tolerance, proving the detector is not simply aggressive.",
     "Gaming simulation: a cast instructed to pad to 100 must be caught by the post-dedup count "
     "falling below the target."],
    REV_1, RETRY_NONE, ["detector-failure", "count-gaming", "overclaim"])

A10 = U(
    "Calibrate the novelty score against a labelled gold set instead of trusting the model that produced it",
    "10",
    "Question: does the runtime novelty score agree with human-labelled novelty, and by how much? "
    "Spec :11237 names duplicate ideas passing as novelty. Build a gold set of idea pairs labelled "
    "duplicate / variant / distinct, then report agreement (Cohen kappa) between the runtime score "
    "and the labels. A novelty score with kappa near chance is a decoration and must be demoted to "
    "advisory rather than allowed to gate a stopping rule.",
    ["labelled idea-pair gold set built for this unit", SIMHARNESS, COUNCILMODES,
     "the runtime novelty scorer from bucket B07"],
    [A09], role(OPUS, "calibration-analyst"), T_ANA, "local-parallel", 5400,
    "Report kappa with its confidence interval and the gold-set size. Publish the gold set itself "
    "so the number is reproducible; a kappa with no published labels cannot be checked.",
    ["Kappa computed on a held-out half of the gold set, not the half used for any tuning.",
     "Adversarial pairs: near-duplicates that differ only in a load-bearing qualifier must be "
     "labelled distinct, and the scorer measured on them separately.",
     "Demotion rule fires: with a seeded scorer forced below the kappa floor, the runtime must "
     "refuse to let novelty gate a stopping rule."],
    REV_STAT, RETRY_2S, FC_CAL)

A11 = U(
    "Prove the minority report survives all the way into the final synthesis artifact",
    "10",
    "Question: a dissent that is recorded in round 4 and absent from the final report has been "
    "dropped, not resolved. Trace a scripted dissenting position from its first appearance through "
    "every downstream artifact (transcript, argument ledger, decision record, synthesis, executive "
    "summary) and fail the run at the first artifact where it disappears. Spec :11238 names "
    "minority suppression and :11342 names the dissent or minority report being dropped.",
    [SIMHARNESS, SPEC + ":10767 (dissent/minority report is a required council output)",
     SPEC + ":11342", "the synthesis stage from bucket B07 phase 14"],
    [A01], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Name every artifact in the chain and give the byte offset or heading where the dissent appears "
    "in each. An assertion that dissent is preserved must cite the final artifact, not the "
    "transcript.",
    ["Scripted lone dissenter -> dissent present in all N downstream artifacts.",
     "Deletion control: remove the dissent-propagation step and the trace must FAIL, proving the "
     "trace is wired to real data.",
     "Summarisation squeeze: run the chain with an aggressive length cap and confirm dissent "
     "survives the cap or the cap is rejected."],
    REV_1, RETRY_NONE, ["dissent-loss", "detector-failure", "overclaim"])

A12 = U(
    "Test the judge and the moderator as single points of epistemic failure",
    "10",
    "Question: how much of the verdict is the panel and how much is the one seat that writes it "
    "down? Spec :11239 names moderator capture and :11342 names the judge becoming a single point "
    "of epistemic failure. Hold the full transcript fixed and swap ONLY the judge persona (and "
    "separately, the moderator), then measure verdict stability. High verdict variance under judge "
    "swap means the council is theatre around one decision-maker and must be reported as such.",
    [SIMHARNESS, COUNCILMODES, "judge/chair role definitions from bucket B05",
     "recorded transcripts from the protocol sweep"],
    [A01, A[38]], role(OPUS, "adversarial-refuter"), T_SIM, "local-parallel", 5400,
    "Report the verdict distribution over at least 5 judge personas on identical transcripts. A "
    "single swap is not a measurement of stability.",
    ["Judge-swap stability: identical transcript, 5 judges, report agreement rate.",
     "Moderator-capture probe: a moderator scripted to suppress one participant must be detected "
     "by the speaking-time and objection-routing audit.",
     "No-judge control: run the same transcript through mechanical aggregation and compare, to "
     "quantify how much the judge adds versus overrides."],
    REV_XV, RETRY_2S, FC_CAL)

A13 = U(
    "Detect strategic abstention and its interaction with quorum and weighted tallies",
    "10",
    "Question: can a participant change the outcome by NOT voting? Spec :11240 names strategic "
    "abstention. Enumerate, over the configured voting methods and quorum rules, every case where "
    "an abstention produces an outcome the same participant could not have obtained with any "
    "ballot, and require the runtime to flag those configurations at validation time rather than "
    "discovering them in a live decision.",
    [SIMHARNESS, SPEC + ":10930 (voting and belief aggregation options incl. abstention, quorum, delegation)",
     COUNCILMODES, "the tally implementation from bucket B07"],
    [A[24]], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 3600,
    "List the exact (method, quorum, weight) triples where abstention is strategically superior, "
    "each with the concrete ballot profile that demonstrates it.",
    ["Exhaustive small-profile search over methods x quorum x weights for abstention advantage.",
     "Negative control: a method with no quorum and equal weights must yield zero such cases; if "
     "the search reports some, the enumerator is wrong.",
     "Validation-time flag fires on a configuration known to be vulnerable."],
    REV_1, RETRY_NONE, ["detector-failure", "spec-gap", "overclaim"])

A14 = U(
    "Probe for hallucinated expertise before a seat is allowed to carry expert weight",
    "10",
    "Question: a seat labelled domain expert carries extra vote weight and extra deference; is the "
    "label backed by anything? Spec :11241 names hallucinated expertise. Administer a short "
    "calibration set of verifiable domain questions (with known answers and at least one "
    "unanswerable control) to any participant assigned an expert role, and refuse the weight "
    "premium when accuracy on the verifiable set is at or below the non-expert baseline.",
    ["domain calibration sets authored for this unit (with unanswerable controls)",
     COUNCILMODES, "expertise-ranked participant selection from bucket B05", SIMHARNESS],
    [A01], role(OPUS, "calibration-analyst"), T_XV, "local-serialized", 5400,
    "Report per-seat accuracy against the verifiable set AND the response to the unanswerable "
    "control. A seat that answers the unanswerable question confidently must be reported even if "
    "its accuracy is high.",
    ["Verifiable-set accuracy per expert seat versus a non-expert baseline seat.",
     "Unanswerable control: a question with no true answer must produce an explicit I-do-not-know; "
     "a confident answer is a finding.",
     "Weight-premium refusal fires when accuracy is at or below baseline."],
    REV_XV, RETRY_2S, FC_CAL, True)

A15 = U(
    "Conflict-of-interest declaration and the enforcement that makes it more than a form field",
    "10",
    "Implementation target: require every seat to declare conflicts (authored the artifact under "
    "review, owns the proposal, is the vendor being evaluated) and enforce the consequence the "
    "spec implies at :10924 - recusal, weight reduction, or exclusion from a partition. Spec "
    "adds hidden conflicts of interest at :11242. The test is that a conflicted seat CANNOT cast "
    "a counting vote on its own artifact, not that a warning appears.",
    [CS + " (conflicts field)", COUNCILMODES,
     SPEC + ":10924 (conflicts of interest, information partitioning)", SIMHARNESS],
    [A01], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Cite the tally showing the conflicted ballot excluded, and the audit line naming the conflict. "
    "A declared-but-counted ballot is a failure regardless of the warning text.",
    ["Author-reviews-own-artifact: ballot excluded from the tally.",
     "Undeclared conflict detected by provenance join (seat identity matches artifact author) even "
     "when the declaration field is empty.",
     "Both-states: an unconflicted seat on the same artifact must count normally."],
    REV_1, RETRY_NONE, ["detector-failure", "governance-bypass", "overclaim"])

A16 = U(
    "Information-partition leakage test for blind and partitioned council rounds",
    "10",
    "Question: when the spec partitions information so seat A cannot see evidence bundle B, does "
    "the runtime actually withhold it, and does it stay withheld through summaries, shared "
    "scratchpads, tool results and the moderator's own paraphrase? Spec :10924 lists information "
    "partitioning as a first-class control. Leakage through a summary is still leakage and is the "
    "path a naive implementation will take.",
    [CS + " (information partition)", SIMHARNESS,
     SPEC + ":10927 (blind independent first pass)", "context assembly code from bucket B07"],
    [A01], role(OPUS, "adversarial-refuter"), T_SIM, "local-parallel", 3600,
    "Plant a unique canary token in the withheld bundle and grep every artifact the partitioned "
    "seat can read. Report the canary token id and every path searched, so a zero-hit result is "
    "attributable to a real search.",
    ["Canary token planted in the withheld bundle -> zero hits in the partitioned seat's context.",
     "Detector control: plant the same canary in an ALLOWED bundle -> the search must find it, "
     "proving the search works.",
     "Summary path: force a moderator summary of the withheld bundle and re-run the search."],
    REV_SEC, RETRY_NONE, FC_SEC)

A17 = U(
    "Prompt injection carried by a participant artifact into a later council stage",
    "10",
    "Question: a participant writes a position paper containing instruction-shaped text; when a "
    "later stage reads that paper, does it obey it? Spec :11344 names a council transcript or "
    "participant artifact injecting instructions into later stages, and AGENTS.md holds that "
    "fetched and peer-produced content is untrusted DATA. Test the transcript, the idea ledger, the "
    "evidence bundle and tool results as injection carriers, and require the runtime to neutralise "
    "each, not just the obvious one.",
    [SPEC + ":11344", SIMHARNESS, "AGENTS.md section 9 (fetched content is untrusted data)",
     "the stage-to-stage context assembler from bucket B07"],
    [A01], role(OPUS, "adversarial-refuter"), T_SIM, "worktree-isolated", 5400,
    "Report the payload text, the carrier artifact and the downstream stage's behaviour verbatim "
    "for every carrier tested. A claim of immunity must enumerate the carriers actually exercised.",
    ["Injection payload in a position paper -> later stage does not execute it.",
     "Carrier matrix: transcript, idea ledger, evidence bundle, tool result, participant display "
     "name - each tested separately and reported separately.",
     "Positive control: a payload placed in the genuine instruction channel MUST be obeyed, "
     "proving the probe can observe obedience at all."],
    REV_SEC, RETRY_NONE, FC_SEC)

A18 = U(
    "Settle a council dispute with an executable test and prove the test outranks the consensus",
    "10",
    "Implementation target: wire the stop condition at :10942-style form where an executable check "
    "adjudicates a factual dispute, and prove the runtime accepts the test result over a "
    "contradicting unanimous vote. Spec :11244 names consensus that fails executable tests and "
    ":11198 says agreement is not proof. The distinguishing test is the one where 100 percent of "
    "seats are wrong and the harness still records the correct outcome.",
    [SPEC + ":11244", SPEC + ":11198", SIMHARNESS,
     "the executable-probe adapter that lets a council run a check"],
    [A01, A06], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Cite the disputed proposition, the probe command and its output, the unanimous vote, and the "
    "recorded outcome. All four must be in the receipt.",
    ["Unanimous-but-wrong panel versus a passing executable probe -> probe wins, dissent from the "
     "panel recorded as an error not a minority view.",
     "Probe-failure honesty: when the probe itself errors, the outcome must be NOT-CHECKED, never "
     "a silent fallback to the vote.",
     "Both-states: when the probe agrees with the panel, the record must show the probe as the "
     "reason, not the tally."],
    REV_1, RETRY_NONE, ["evidence-bypass", "detector-failure", "overclaim"])

A19 = U(
    "Speaking-quota enforcement and the dominance statistic that shows it is needed",
    "10",
    "Question: how much of the deliberation does the loudest seat own, and does the quota mechanism "
    "actually bound it? Spec :10944 names participant dominance. Measure share of turns, share of "
    "tokens, share of surviving claims and share of cited evidence per seat, then enforce the "
    "configured quota and re-measure. Share of SURVIVING CLAIMS is the metric that matters: a seat "
    "capped on turns can still dominate the outcome.",
    [SIMHARNESS, ANTIFAIL, CS + " (speaking quotas, turn lengths)",
     "turn scheduler from bucket B07"],
    [A01], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 3600,
    "Report all four share statistics per seat, before and after quota enforcement. Reporting only "
    "turn share would hide the outcome-dominance case.",
    ["Planted dominant persona -> pre-quota shares skewed, post-quota turn share bounded.",
     "Outcome dominance persists after the turn cap in at least one configuration, or the unit "
     "states it could not construct such a case and why.",
     "Both-states: a balanced cast must not be perturbed by the quota mechanism."],
    REV_STAT, RETRY_2S, FC_CAL)

A20 = U(
    "Minimum engagement and maximum inactivity: make a silent seat a failure, not a quiet pass",
    "10",
    "Implementation target: enforce the :10928 minimum-engagement and maximum-inactivity budgets so "
    "a seat that never speaks, never votes or never cites evidence is escalated, replaced or "
    "recorded as absent - never silently counted as consenting. Spec :10944 names silence as an "
    "anti-failure target. Consent-by-silence is the specific defect: an absent seat must not be "
    "folded into a consensus figure.",
    [CS + " (minimum engagement, maximum inactivity)", ANTIFAIL, SIMHARNESS,
     "consensus computation from bucket B07"],
    [A01, A[22]], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Show the consensus figure computed with the silent seat excluded and the escalation record. "
    "If the runtime counts silence as consent anywhere, quote that line.",
    ["Silent seat -> escalation fires and the seat is not counted as agreeing.",
     "Consent protocol distinction: under an explicit consent/no-objection protocol, silence has a "
     "DEFINED meaning; the test must show the two protocols behave differently and both are "
     "documented.",
     "Both-states: an engaged seat must not trigger the inactivity path."],
    REV_1, RETRY_NONE, FC_SPEC)

A21 = U(
    "Detect missing expertise on the panel and recruit an independent critic to fill it",
    "10",
    "Question: can the runtime notice that nobody on the panel knows the thing the decision turns "
    "on? Spec :10944 lists missing expertise, and :10924 allows dynamic recruitment. Build the "
    "coverage check that maps the decision's required competencies against declared seat "
    "competencies, fires on an uncovered competency, and recruits, then prove the recruited seat "
    "actually changes the deliberation rather than rubber-stamping it.",
    [SIMHARNESS, ANTIFAIL, SPEC + ":10924 (dynamic recruitment, replacement)",
     "the competency taxonomy from bucket B05"],
    [A01, A[22]], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 5400,
    "Name the uncovered competency, the recruitment trigger, and at least one claim in the "
    "post-recruitment transcript that exists only because of the new seat.",
    ["Panel with a deliberate competency hole -> gap detected and named.",
     "Recruitment efficacy: the recruited seat must contribute at least one new claim or "
     "counterexample, otherwise the recruitment is cosmetic and is reported as such.",
     "False-gap control: a fully covered panel must not trigger recruitment."],
    REV_1, RETRY_2S, FC_DET_CAL)

A22 = U(
    "Replace a participant mid-run and prove the council state survives the swap",
    "10",
    "Implementation target: implement and test the participant replacement path required at :10946 "
    "and :10924 - a seat is removed mid-deliberation (crash, recusal, quota breach, inactivity) and "
    "a replacement is seated with the correct information partition, the correct history, and "
    "without inheriting the departed seat's votes. The subtle defect is vote inheritance: the "
    "replacement must not silently carry forward ballots it never cast.",
    [SIMREQ, SPEC + ":10924 (replacement)", SIMHARNESS,
     "council state persistence from bucket B07"],
    [A01], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Show the vote ledger before and after the swap. The replacement's ballot count must start at "
    "zero for rounds it did not attend.",
    ["Mid-run replacement -> deliberation continues, history intact, no inherited ballots.",
     "Partition correctness: the replacement receives exactly the partition its role mandates, "
     "verified with the A16 canary.",
     "Crash-path replacement: kill a seat mid-turn and confirm the run recovers rather than "
     "hanging."],
    REV_1, RETRY_2S, ["state-corruption", "detector-failure", "overclaim"])

A23 = U(
    "Role mandate enforcement: permissions, speaking rights, vote rights, veto rights, incompatible roles",
    "10",
    "Question: are role mandates enforced by the runtime or merely described in the prompt? Spec "
    ":10925 enumerates role mandates, permissions, tool/source access, speaking rights, vote "
    "rights, veto rights and incompatible-role checks, and :10946 requires simulations proving role "
    "enforcement. Attempt every forbidden action from every role and require a runtime refusal; a "
    "role that only exists in the prompt is a suggestion and must be reported as unenforced.",
    [SPEC + ":10925 (role mandates and rights)", SIMREQ, SIMHARNESS,
     "role registry and permission checks from bucket B07"],
    [A01], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 5400,
    "Publish the full role x forbidden-action matrix with the observed result in every cell. A "
    "summary sentence is not the deliverable; the matrix is.",
    ["Every role attempts every forbidden action -> refusal in every prohibited cell.",
     "Permitted actions succeed in every allowed cell (no over-blocking).",
     "Incompatible-role assignment (e.g. same seat as proposer and judge) rejected at validation.",
     "Veto right exercised by a seat that holds it must actually block; exercised by one that does "
     "not must be refused."],
    REV_1, RETRY_2S, FC_SPEC)

A24 = U(
    "Property-test every voting and belief-aggregation method against its own axioms",
    "10",
    "Implementation target: for each method listed at :10930 (majority, supermajority, unanimity, "
    "consent, ranked-choice, score, approval, pairwise/Condorcet, juror, judge, weighted, Bayesian, "
    "veto, quorum, abstention, delegation), state the axioms it claims (unanimity/Pareto, "
    "monotonicity, independence where applicable, Condorcet consistency where claimed, weight "
    "monotonicity) and property-test each on randomly generated ballot profiles. Where an axiom "
    "cannot hold (Arrow, Condorcet cycles), the deliverable is the documented exception plus the "
    "runtime behaviour on a cycle - never a crash and never a silent arbitrary pick.",
    [SPEC + ":10930 (voting and belief aggregation)", "the tally implementation from bucket B07",
     "hypothesis or equivalent property-testing library", SIMHARNESS],
    ["B07"], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report, per method, the axioms tested, the number of generated profiles, and every "
    "counterexample found with its ballot profile. An untested axiom must be listed as NOT-CHECKED "
    "per method, not omitted.",
    ["Monotonicity property per method over at least 10k generated profiles.",
     "Condorcet cycle: the runtime must produce a documented, deterministic resolution and record "
     "that a cycle occurred.",
     "Mutation control: perturb one tally implementation (off-by-one in the majority threshold) and "
     "confirm the property suite goes red."],
    REV_STAT, RETRY_2S, ["detector-failure", "spec-gap", "overclaim"])

A25 = U(
    "Conformance-test the Boolean stopping-expression evaluator, including all six required examples",
    "10",
    "Implementation target: the AND/OR/NOT composable stopping expressions at :10931 and :10760 need "
    "an evaluator whose semantics are pinned by tests - operator precedence, short-circuit versus "
    "full evaluation of side-effecting terms, unknown-term handling, and the behaviour when a term "
    "is NOT-CHECKED rather than true or false. Then run the six executable examples verbatim from "
    ":10937-10942 as conformance cases.",
    [STOPEXPR, SPEC + ":10931 (composable AND/OR/NOT stopping expressions)",
     "the stopping-rule engine from bucket B07", SIMHARNESS],
    ["B07"], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 5400,
    "Each of the six spec examples must appear in the receipt with its parsed AST and its evaluated "
    "result on a fixture run. Paraphrasing an example is not running it.",
    ["Six spec examples parse and evaluate; ASTs published.",
     "Three-valued logic: a term that is NOT-CHECKED must not be silently coerced to false (which "
     "would let a stop rule pass by ignorance).",
     "Precedence tests for AND/OR/NOT mixtures with explicit expected values.",
     "Malformed expression is rejected at spec-validation time, not at round 12."],
    REV_1, RETRY_NONE, FC_SPEC)

A26 = U(
    "Give completeness_score a defensible definition, or refuse to let it gate anything",
    "10",
    "Question: the required stopping expression at :10937 contains completeness_score >= 0.90, so "
    "what is that number and against what is it validated? Define it operationally (coverage of "
    "declared subquestions, of required categories, of the evidence classes the objective names), "
    "then validate it against human-labelled completeness on a held-out set. If it cannot be "
    "validated, it must not appear in a stopping rule and the spec example must be flagged as "
    "under-specified.",
    [SPEC + ":10937", "labelled completeness gold set built for this unit",
     "the objective/coverage schema from " + CS, SIMHARNESS],
    [A25], role(OPUS, "calibration-analyst"), T_ANA, "local-parallel", 5400,
    "Publish the formula, the gold set, and the correlation with human labels. A score used in a "
    "gate with no validation evidence must be reported as UNVERIFIED in the receipt heading.",
    ["Correlation of the computed score with human labels on a held-out set, with interval.",
     "Adversarial padding: a deliberately padded output must NOT reach 0.90.",
     "Both-states: a genuinely complete output must reach it, or the threshold is unreachable and "
     "the gate is a permanent block."],
    REV_STAT, RETRY_2S, FC_CAL)

A27 = U(
    "Evidence saturation: build the detector and prove it is not silent in both states",
    "10",
    "Question: the stopping expression at :10941 turns on evidence_saturation == true, so the "
    "detector behind it must be shown to fire when saturation is real and stay silent when it is "
    "not. Define saturation as the marginal yield of new independent evidence per unit of search "
    "effort falling below a floor, and measure the yield curve on corpora where the answer is known "
    "by construction (a seeded corpus with a known number of distinct sources).",
    [SPEC + ":10941 (evidence_saturation == true OR time_minutes >= 180)",
     "seeded corpora with a known distinct-source count", SIMHARNESS,
     "the research stage adapters from bucket B07"],
    [A25], role(OPUS, "calibration-analyst"), T_ANA, "local-parallel", 5400,
    "Publish the yield curve for at least three corpora with different true source counts. Report "
    "the point at which the detector fired against the known ground truth.",
    ["Seeded corpus with 12 distinct sources -> detector fires only after the marginal yield "
     "collapses, and the fire point is reported against ground truth.",
     "Both-states control: a corpus still yielding new sources must NOT fire.",
     "Time-arm interaction: confirm the OR with time_minutes cannot mask a never-firing detector "
     "(the timeout arm must be logged distinctly from the saturation arm)."],
    REV_STAT, RETRY_2S, FC_DET_CAL)

A28 = U(
    "Make proof-of-impossibility falsifiable so it cannot become a polite word for giving up",
    "10",
    "Implementation target: the outcome at :10942 and :11276 requires a proof-of-impossibility "
    "record. Specify its mandatory contents - the exact claim shown unobtainable, the search space "
    "actually covered, the methods attempted with their outputs, the resource limit reached, and "
    "the concrete observation that WOULD refute the impossibility - and gate acceptance on all "
    "five. A record that cannot be refuted by any named observation is not a proof and must be "
    "rejected by the validator.",
    [SPEC + ":10942", SPEC + ":11276 (proof-of-impossibility in the research repair loop)",
     "the record schema from bucket B04/B07", SIMHARNESS],
    [A25], role(OPUS, "adversarial-refuter"), T_BUILD, "local-parallel", 3600,
    "Validate at least three real impossibility records produced elsewhere in the program and "
    "report which of the five mandatory elements each is missing.",
    ["Validator rejects a record with no refuting-observation field.",
     "Validator accepts a well-formed record (no over-blocking).",
     "Adversarial: a record whose refuting observation is unobservable in principle must be "
     "rejected as circular."],
    REV_XV, RETRY_NONE, ["overclaim", "spec-gap", "detector-failure"])

A29 = U(
    "Council-of-councils fan-in when the nested councils disagree about completion",
    "10",
    "Question: two subcouncils return, one says DONE and one says NOT DONE - what does the parent "
    "do? Spec :11343 names nested councils disagreeing on completion as a failure class and :10926 "
    "requires nested subcouncil and council-of-councils topologies. The parent must apply the ONE "
    "shared completion predicate (CC-0003) rather than a local rule, must not average the verdicts, "
    "and must preserve each subcouncil's dissent into its own output.",
    [SPEC + ":11343", SPEC + ":10926 (nested subcouncil, council-of-councils)", PRED,
     SIMHARNESS, "the shared reducer from CC-0003"],
    [A01, "CC-0003"], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 5400,
    "Show the parent decision record citing the shared reducer by module path, plus both "
    "subcouncil verdicts verbatim.",
    ["Split subcouncil verdicts -> parent applies the shared predicate and records both inputs.",
     "Averaging control: confirm the parent does NOT emit a midpoint or a majority-of-councils "
     "verdict when the predicate is unsatisfied.",
     "Dissent propagation: each subcouncil minority report is present in the parent output (reuses "
     "the A11 trace).",
     "Depth-2 nesting exercised, not just one level."],
    REV_1, RETRY_2S, ["detector-failure", "dissent-loss", "overclaim"])

A30 = U(
    "Pause, resume and deterministic replay of a council run",
    "10",
    "Implementation target: prove the :10946 pause/resume requirement and the :11194 replay "
    "requirement hold at the byte level - a run paused at round k and resumed must produce the same "
    "final transcript as an uninterrupted run on the same seed, and a replay from the persisted "
    "state must reproduce it again. Where true determinism is impossible (live model calls), the "
    "deliverable is the explicit boundary: which fields are guaranteed reproducible and which are "
    "recorded-but-not-reproducible.",
    [SIMREQ, SPEC + ":11194 (resume, replay, deterministic audit where possible)", SIMHARNESS,
     "the persistence layer from bucket B07"],
    # local-serialized, not local-parallel: the simulator arm is portable, but the
    # final test below exercises a LIVE-MODEL arm to establish which fields are
    # non-reproducible, and the scaling doctrine at :10575 keeps credentialed and
    # live-harness probes local and serialized.
    [A01], role(OPUS, "test-engineer"), T_SIM, "local-serialized", 5400,
    "Report three sha256 values: uninterrupted run, pause-resume run, replay-from-state run. Any "
    "divergence must be attributed to a named field, not waved off as nondeterminism.",
    ["Pause at round k, resume, compare final transcript hash to the uninterrupted run.",
     "Replay from persisted state reproduces the transcript.",
     "Torn-write control: kill the process mid-persist and confirm resume either recovers cleanly "
     "or fails loudly, never resumes from a half-written state.",
     "Live-model arm: document exactly which fields are non-reproducible and prove the rest are."],
    REV_WIN, RETRY_2S, ["nondeterminism", "state-corruption", "overclaim"])

A31 = U(
    "Score the council calibration report with proper scoring rules on resolved outcomes",
    "10",
    "Question: when the council says it is 80 percent confident, is it right 80 percent of the "
    "time? Spec :10767 requires a calibration report as a council output and :11196 requires "
    "post-run calibration. Build the resolution pipeline (forecast -> later ground truth) and score "
    "with Brier and log score plus a reliability diagram. Accuracy alone is not calibration, and a "
    "calibration report that never resolves against outcomes is a decoration.",
    [SPEC + ":10767 (calibration report)", SPEC + ":11196 (post-run calibration)",
     "resolved forecast pairs from prior program runs", SIMHARNESS],
    [A01], role(OPUS, "calibration-analyst"), T_ANA, "local-parallel", 5400,
    "Publish Brier score, log score, the reliability diagram bins with counts, and the number of "
    "resolved forecasts. A calibration claim on fewer than 30 resolved items must say so in the "
    "claim sentence.",
    ["Brier and log score computed over resolved forecasts with bin counts.",
     "Reference control: score a deliberately miscalibrated forecaster (always says 95 percent) and "
     "confirm the metric separates it from a calibrated one.",
     "Resolution honesty: unresolved forecasts are excluded and counted, never scored as correct."],
    REV_STAT, RETRY_2S, FC_CAL)

A32 = U(
    "Does weighted belief aggregation actually beat naive majority on a scored gold set",
    "10",
    "Question: the runtime offers weighted and Bayesian aggregation at :10930; on this program's own "
    "decision corpus, do they outperform an unweighted majority, and by how much? Run every "
    "aggregation method over the same set of resolved council decisions and rank them by proper "
    "score. If weighting does not beat majority, the extra machinery is unjustified complexity and "
    "the default must change.",
    ["resolved council decision corpus with known outcomes", SPEC + ":10930",
     "the aggregation implementations from bucket B07", SIMHARNESS],
    [A31, A24], role(OPUS, "statistician"), T_ANA, "cloud-batch", 5400,
    "Report the per-method score with confidence intervals and the paired test between the best "
    "method and naive majority. A ranking without an interval invites reading noise as a result.",
    ["Paired comparison of every aggregation method on identical decisions.",
     "Weight-source ablation: weights derived from calibration versus weights assigned by role, "
     "scored separately.",
     "Null control: random weights must not beat majority; if they do, the corpus is too small and "
     "the unit must report that instead of a ranking."],
    REV_STAT, RETRY_2S, FC_STAT)

A33 = U(
    "Measure whether anonymity and the blind first pass change anything",
    "10",
    "Question: :10924 and :10927 offer anonymity and a blind independent first pass; do they alter "
    "the outcome distribution, or are they ceremony? Run matched councils with identity revealed "
    "versus concealed and measure position independence in round 1, anchoring on the first speaker, "
    "and final-verdict divergence. A control that costs implementation complexity and changes "
    "nothing measurable should be reported honestly as such.",
    [SPEC + ":10927 (blind independent first pass)", SPEC + ":10924 (anonymity)", SIMHARNESS,
     "matched council configurations authored for this unit"],
    [A01], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 5400,
    "Report round-1 position independence (pairwise distance between opening statements) under both "
    "conditions with intervals, over at least 20 matched runs.",
    ["Anchoring probe: with identity revealed and a high-status first speaker, measure the shift in "
     "subsequent openings versus the blind condition.",
     "De-anonymisation control: confirm writing style or tool traces do not re-identify seats, "
     "which would make the anonymity nominal.",
     "Null result is an acceptable outcome and must be stated plainly if measured."],
    REV_STAT, RETRY_2S, FC_CAL)

A34 = U(
    "Deadlock detection, escalation, and the owner-intervention path",
    "10",
    "Implementation target: implement and test the :10762 deadlock, escalation, replacement and "
    "owner-intervention policies. Distinguish three states that look identical from outside - "
    "productive disagreement, genuine deadlock, and a stalled runtime - and require different "
    "handling for each. Escalating a productive disagreement destroys the dissent the council "
    "exists to surface; treating a stalled runtime as disagreement burns the whole budget.",
    [SPEC + ":10762 (deadlock, escalation, replacement, owner-intervention)",
     SPEC + ":11192 (deadlock resolution and escalation)", SIMHARNESS, "escalation policy from bucket B05"],
    [A01, A07], role(OPUS, "test-engineer"), T_SIM, "local-parallel", 3600,
    "Show the three-way classification on three scripted runs, and the distinct action taken in "
    "each. A single generic escalation for all three is the failure this unit exists to catch.",
    ["Productive disagreement -> no escalation, dissent preserved.",
     "Genuine deadlock -> escalation with the deadlocked proposition named.",
     "Stalled runtime (a seat that never returns) -> operational failure path, not a deliberation "
     "outcome.",
     "Owner-intervention record: when the owner is asked, the question must be one foundation-level "
     "question with a recommendation and a stated default, per :11364-11370."],
    REV_1, RETRY_2S, FC_SPEC)

A35 = U(
    "Delphi convergence: variance must fall without the panel simply herding",
    "10",
    "Question: Delphi is listed as a topology at :10926, and its whole premise is that iterated "
    "anonymous feedback improves estimates. Measure across rounds both the dispersion of estimates "
    "and the accuracy against ground truth on a scored question set. Falling dispersion with flat "
    "or worsening accuracy is herding, not convergence, and the runtime must be able to tell the "
    "difference before it reports a confident consensus.",
    ["scored question set with known answers", SPEC + ":10926 (Delphi topology)", SIMHARNESS,
     "the Delphi protocol blueprint from bucket B05"],
    [A01, A31], role(OPUS, "calibration-analyst"), T_SIM, "local-parallel", 5400,
    "Plot dispersion and accuracy per round as raw numbers. A convergence claim citing dispersion "
    "alone is exactly the overclaim this unit is designed to prevent.",
    ["Dispersion and accuracy per round on a scored set.",
     "Herding control: seed one confident-but-wrong participant and confirm the harness flags "
     "accuracy degradation while dispersion falls.",
     "Anonymity dependency: run with feedback attributed and unattributed and report the "
     "difference."],
    REV_STAT, RETRY_2S, FC_CAL)

A36 = U(
    "Are the vendor-diverse seats actually independent, or do they fail together",
    "10",
    "Question: model-diverse and vendor-diverse selection at :10753 buys nothing if the models share "
    "failure modes. On a question set with known answers, measure the conditional error correlation "
    "between vendors - when Claude is wrong, how often is Codex wrong on the SAME item - and report "
    "the effective number of independent seats rather than the nominal count. This is the single "
    "number that tells the owner whether a cross-vendor panel is real diversity or expensive "
    "duplication. Requires live paid API calls to both vendors, so it is serialized and gated.",
    ["question set with known answers spanning several domains",
     SPEC + ":10753 (model/vendor diversity)", "mcp__codex__codex adapter", SIMHARNESS],
    [A01], role(OPUS, "statistician"), T_XV, "local-serialized", 7200,
    "Report the joint error table (both right, both wrong, each alone wrong) with counts, the "
    "correlation coefficient, and the derived effective seat count. Also report token spend, since "
    "this unit consumes paid quota on two subscriptions.",
    ["Conditional error correlation over at least 100 scored items per vendor.",
     "Prompt-parity control: identical prompts and identical scoring, so a difference is not a "
     "harness artifact.",
     "Same-vendor baseline: two runs of the SAME model measure the noise floor that any "
     "cross-vendor correlation must be compared against."],
    REV_XV, RETRY_FLAKE, ["calibration-failure", "substrate-limit", "overclaim"], True)

A37 = U(
    "Conformance sweep over all 64 editable council presets",
    "10",
    "Implementation target: instantiate every one of the 64 presets required at :10765 and :11200-11225, "
    "validate each against the CouncilSpec schema, run each to a terminal state on the deterministic "
    "simulator, and assert the required outputs at :10767 are all present. Report per preset, not in "
    "aggregate: a sweep that says 64/64 pass without a per-preset table hides the preset that "
    "terminated by timeout. A sampled live-model arm follows the simulator arm and consumes paid "
    "quota, so it is owner-gated.",
    [SPEC + ":10765 (48 protocols and 64 presets)", SPEC + ":11200-11225 (required preset list)",
     SPEC + ":10767 (required council outputs)", "the 64 presets authored by bucket B05", SIMHARNESS],
    [A01, "B05"], role(OPUS, "test-engineer"), T_SIM, "cloud-batch", 10800,
    "Emit a per-preset table with terminal state, wall-clock, rounds used, and a present/absent mark "
    "for each of the required outputs. The named presets at :11200-11225 must each be identifiable "
    "in the table by name.",
    ["All 64 presets validate against the schema.",
     "All 64 reach a terminal state on the simulator; a timeout is a FAILED row, not a slow pass.",
     "Required-output completeness per preset (transcript, idea catalog, argument graph, evidence "
     "map, vote history, confidence evolution, dissent, unresolved questions, action plan).",
     "Named-preset coverage: every preset named at :11200-11225 exists, checked by set difference "
     "rather than by eye."],
    REV_1, RETRY_FLAKE, ["green-not-live", "detector-failure", "overclaim"], True)

A38 = U(
    "Terminal-state sweep over all 48 council protocol blueprints",
    "10",
    "Implementation target: run every one of the 48 protocol blueprints required at :10765 and :10946 "
    "under the deterministic simulator with a standard cast, and record for each the terminal state, "
    "the stopping term that fired, the round count and the protocol-specific invariant it claims "
    "(e.g. Oxford requires rebuttals, steelman-before-rebuttal requires a steelman preceding every "
    "rebuttal, jury requires deliberation without the judge). A protocol that reaches DONE without "
    "satisfying its own defining invariant is a renamed copy of another protocol and must be "
    "reported as such to protect the materially-distinct requirement.",
    [SPEC + ":10765", SIMREQ, SPEC + ":10927 (protocol list)",
     "the 48 protocol blueprints from bucket B05", SIMHARNESS],
    [A01, "B05"], role(OPUS, "test-engineer"), T_SIM, "cloud-batch", 10800,
    "Per-protocol table: terminal state, firing stop term, rounds, and PASS/FAIL on its declared "
    "defining invariant. Also report the pairwise distinctness check between protocols.",
    ["48/48 reach a terminal state; each row shows which stopping term fired.",
     "Defining-invariant assertion per protocol, authored from the blueprint text.",
     "Distinctness: pairwise comparison of executed stage sequences to catch two blueprints that "
     "are the same protocol under two names.",
     "Negative control: a deliberately broken blueprint (steelman stage removed) must FAIL its "
     "invariant, proving the invariants are wired."],
    REV_1, RETRY_FLAKE, ["green-not-live", "count-gaming", "overclaim"], True)

# ============================================================ LANE B (31 units)
# The benchmark and regression PLATFORM (deliverable 9, :10540) plus the phases
# that consume it. Phase-10 layers 33/34 are per-component RUNS and belong to
# slice part 2; this lane builds and governs the substrate they run on.

BENCH = "tools/bench/ (the benchmark and regression platform built by this lane)"
CASES = "command-center/bench/cases/ (the benchmark case corpus)"
RESULTS = "command-center/bench/results/ (append-only per-run results ledger)"

B01 = U(
    "Build the benchmark case corpus with provenance, difficulty strata and a held-out split",
    "10",
    "Implementation target: assemble the case set every later comparison runs on. Each case carries "
    "a stable id, the task input, a machine-checkable success oracle, provenance (where the case "
    "came from and whether it is derived from a real defect), a difficulty stratum, and a split tag "
    "(dev / test / held-out shadow). Spec :10540 names a benchmark and regression platform as a "
    "deliverable; without a corpus with an oracle per case, every later improvement claim is an "
    "opinion. Cases whose oracle is a model judgement rather than a deterministic check must be "
    "tagged so downstream analysis can separate them.",
    [SPEC + ":10540 (benchmark and regression platform)", FAILCLASSES,
     "prior defect corpus from bucket B02", "workflow benchmark cases implied at :10741"],
    ["B02"], role(OPUS, "benchmark-engineer"), T_BUILD, "worktree-isolated", 7200,
    "Report case count per stratum and per split, and the fraction with a deterministic oracle "
    "versus a judged oracle. A corpus summary with no oracle-type breakdown hides the weakest part "
    "of the platform.",
    ["Every case validates against the case schema and has a runnable oracle.",
     "Oracle sanity: each oracle must PASS a known-good solution and FAIL a known-bad one; an "
     "oracle that accepts both is removed from the corpus.",
     "Split disjointness computed by set intersection, not asserted.",
     "Provenance completeness: zero cases with an empty provenance field."],
    REV_1, RETRY_2S, ["detector-failure", "spec-gap", "overclaim"])

B02 = U(
    "Matched-case pairing so a fusion is compared against its sources on identical inputs",
    "2B",
    "Implementation target: Phase 2B step 7 at :10739 requires running source workflows and fused "
    "candidates on matched benchmark cases, and :10741 certifies only workflows that outperform or "
    "materially complement their sources. Build the pairing rule that selects the case subset every "
    "source can actually run (an intersection, not a union), records the excluded cases with the "
    "reason, and forbids a comparison whose intersection is below a minimum size. Comparing a "
    "fusion on cases its sources cannot even attempt is the arithmetic that manufactures a winner.",
    [SPEC + ":10739 (run source workflows and fused candidates on matched cases)",
     SPEC + ":10741 (certify only workflows that outperform or complement)", CASES,
     "the workflow candidate registry from bucket B04"],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 5400,
    "Publish, per comparison, the intersection size, the excluded case ids and the exclusion reason "
    "for each. A reported win with no exclusion list is not reviewable.",
    ["Intersection computed mechanically from per-workflow capability declarations.",
     "Below-minimum intersection blocks the comparison rather than reporting a low-n win.",
     "Asymmetric-capability control: a fusion that can run cases no source can must report those "
     "separately as complementarity, never folded into the head-to-head score."],
    REV_STAT, RETRY_NONE, FC_STAT)

B03 = U(
    "Pin determinism: seeds, model versions, environment capture and a run-to-run variance budget",
    "10",
    "Question: how much of a measured delta is the change, and how much is the harness moving under "
    "it? Capture and freeze everything that can vary (seed, model id and snapshot, temperature, "
    "tool versions, OS, locale, concurrency), then measure the null delta - the same configuration "
    "run twice - and publish it as the variance floor. Any improvement smaller than the variance "
    "floor is not a result, and the platform must refuse to report it as one.",
    [BENCH, CASES, "environment capture from lane C unit for admissibility",
     SPEC + ":10577 (stagger arrivals; arrival rate is a scheduler input)"],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report the null-delta distribution over at least 10 repeated identical runs, with its standard "
    "deviation. Every later improvement claim in this program must cite this floor.",
    ["Null-delta measurement: identical config run 10+ times, distribution published.",
     "Seed wiring proof: changing only the seed must change the result set, or the seed is inert.",
     "Environment drift alarm: a run whose captured environment differs from the baseline must be "
     "flagged, not silently compared."],
    REV_STAT, RETRY_SEED, ["nondeterminism", "statistical-invalidity", "overclaim"])

B04 = U(
    "Paired statistical comparison with a pre-registered effect size and sample size",
    "10",
    "Implementation target: replace ad-hoc before/after numbers with a paired test (bootstrap or "
    "permutation over per-case outcomes), a pre-registered minimum effect size, and a sample size "
    "computed before the run. Spec condition 8 at :11385 requires benchmark results showing the "
    "intended improvement without material regression, which is a statistical statement. The "
    "platform must emit an interval with every delta and must refuse to emit a bare point estimate.",
    [BENCH, CASES, STOP8, "per-case results from the results ledger"],
    [B01, B03], role(OPUS, "statistician"), T_BUILD, "cloud-batch", 7200,
    "Every reported delta carries an interval and the n it was computed from. Publish the "
    "pre-registration record (effect size and n) with a timestamp preceding the run.",
    ["Paired bootstrap over per-case outcomes; interval published.",
     "Pre-registration enforced: a comparison whose pre-registration postdates the run is rejected.",
     "Underpowered guard: when n is below the pre-registered size, the platform emits NOT-CHECKED "
     "rather than a delta.",
     "Known-effect control: inject a synthetic 10-point improvement and confirm the test detects "
     "it; inject zero effect and confirm it does not."],
    REV_STAT, RETRY_NONE, FC_STAT)

B05 = U(
    "Control the false-discovery rate when a tournament compares many candidates at once",
    "10",
    "Question: run 40 candidate workflows against a baseline at the 0.05 level and roughly two will "
    "look like winners by chance. Spec :11164 requires A/B and tournament benchmarking, so this is "
    "not hypothetical. Apply a multiple-comparison correction (Benjamini-Hochberg for discovery, "
    "Holm where a family-wise guarantee is needed), report both corrected and uncorrected results, "
    "and make the correction mandatory before any certification decision at :10741.",
    [SPEC + ":11164 (A/B and tournament benchmarking)", BENCH, RESULTS, SPEC + ":10741"],
    [B04], role(OPUS, "statistician"), T_ANA, "cloud-batch", 5400,
    "Report the number of comparisons in the family, the correction method, and both the corrected "
    "and uncorrected verdict counts. A certification list that shrinks after correction is the "
    "expected outcome and must be shown.",
    ["Correction applied across the full comparison family, family size reported.",
     "Null-tournament control: 40 identical candidates must yield approximately zero corrected "
     "discoveries; if it yields several, the pipeline is broken.",
     "Certification gate consumes the CORRECTED verdict, verified by mutating the gate to read the "
     "uncorrected one and confirming a test goes red."],
    REV_STAT, RETRY_NONE, FC_STAT)

B06 = U(
    "Tournament scheduling and the transitivity check that reveals an unstable ranking",
    "2B",
    "Implementation target: build the tournament scheduler (round-robin for small fields, Swiss for "
    "large, elimination only where budget forces it) and then TEST the resulting ranking for "
    "pairwise transitivity. Non-transitive results (A beats B, B beats C, C beats A) mean the "
    "single-number ranking is fiction and the field must be reported as a partial order. Spec "
    ":11164 asks for tournament benchmarking; a leaderboard that hides a rock-paper-scissors cycle "
    "is worse than no leaderboard.",
    [SPEC + ":11164", BENCH, CASES, "workflow candidates from bucket B04"],
    [B02, B04], role(OPUS, "benchmark-engineer"), T_BUILD, "cloud-batch", 7200,
    "Publish the full pairwise result matrix, not just the ranking. Report every detected cycle "
    "with its members.",
    ["Pairwise matrix computed and cycles enumerated.",
     "Planted-cycle control: three synthetic candidates constructed to be non-transitive must be "
     "detected as a cycle.",
     "Schedule equivalence: round-robin and Swiss on the same field must agree on the top entry, or "
     "the disagreement is reported as a finding about the field, not resolved by picking one."],
    REV_STAT, RETRY_2S, FC_STAT)

B07 = U(
    "Define material regression as a number, and wire it into the release gate",
    "15",
    "Implementation target: stopping condition 8 at :11385 turns on the phrase without material "
    "regression, which is currently unquantified. Set a per-metric non-inferiority margin (how much "
    "worse a secondary metric may get before a primary win is refused), decide it BEFORE running "
    "the comparison, and record it in the release checklist. An undefined margin is decided after "
    "the fact by whoever wants the release, which is the failure mode this unit removes.",
    [STOP8, "command-center/RELEASE-CHECKLIST.md", BENCH,
     "the metric inventory from B01 and B10"],
    [B04], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "The margin table must exist as a committed artifact with a timestamp preceding the release "
    "comparison. Cite its path and the commit that introduced it.",
    ["Margin table validates and covers every metric the release gate reads.",
     "Post-hoc-change alarm: modifying a margin after a comparison has run must be flagged in the "
     "release record, not silently accepted.",
     "Boundary cases: a candidate exactly at the margin must resolve deterministically and the "
     "chosen direction must be documented."],
    REV_1, RETRY_NONE, FC_SPEC)

B08 = U(
    "Capture the Phase-0 benchmark baseline as an immutable record anchored to a commit SHA",
    "0",
    "Implementation target: spec :10657 requires capturing benchmark baselines before changing "
    "behaviour. The Phase-0 ground lane measured that the working tree was mutating under the "
    "snapshot and concluded only the commit SHA is a valid rollback anchor. Apply the same "
    "discipline here: every baseline record binds to a commit SHA plus the captured environment, "
    "is written append-only, and is rejected if the tree was dirty at capture time.",
    [SPEC + ":10657 (capture benchmark baselines before changing behavior)",
     "command-center/BASELINE-SNAPSHOT.json", BENCH, "git status and rev-parse at capture time"],
    [B01, B03], role(OPUS, "benchmark-engineer"), T_BUILD, "local-serialized", 5400,
    "The baseline record must contain the commit SHA, the dirty/clean state, and the environment "
    "capture. A baseline captured against a dirty tree must be marked PROVISIONAL in the record "
    "itself, not merely mentioned in prose.",
    ["Dirty-tree capture is rejected or marked PROVISIONAL, proven by capturing against a "
     "deliberately dirty tree.",
     "Immutability: a second write to the same baseline id must fail.",
     "Round-trip: the baseline can be re-materialised from the SHA and reproduces the recorded "
     "metrics within the B03 variance floor."],
    REV_WIN, RETRY_NONE, ["state-corruption", "green-not-live", "overclaim"])

B09 = U(
    "Expire benchmark results that depend on a live external source",
    "10",
    "Question: a stored green from last week is not a control for today when the check queries a "
    "live advisory database, a marketplace index or a model endpoint that ships new snapshots. "
    "Classify every benchmark case by whether its oracle depends on an external live source, assign "
    "a staleness TTL per class, and make the platform refuse to cite an expired result as current "
    "evidence. The failure is subtle because the expired result is not wrong, it is merely no "
    "longer a measurement of today.",
    [CASES, RESULTS, BENCH, "the dependency classification from B01 provenance fields"],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "Publish the per-class TTL table and the count of currently expired results. A dashboard "
    "showing green must show the age of each green.",
    ["Expired result cannot satisfy a gate: prove by back-dating a result past its TTL.",
     "Live-dependency classification checked against the actual network calls each oracle makes, "
     "not against its declared class.",
     "Both-states: a hermetic case must NOT expire, so the TTL does not force pointless re-runs."],
    REV_1, RETRY_NONE, FC_GREEN)

B10 = U(
    "Account for tokens, wall-clock and spend per run so improvement is reported per unit cost",
    "10",
    "Implementation target: the objective function at :10487-10498 ranks resource efficiency last "
    "but does not make it invisible, and :10578 treats quota as a scheduler input. Record tokens "
    "in and out, wall-clock, tool calls and estimated spend per benchmark run, and report every "
    "quality delta alongside its cost delta. A workflow that is 2 percent better for 6 times the "
    "tokens is a different decision from one that is 2 percent better for free, and the platform "
    "must not hide which one it found.",
    [BENCH, RESULTS, SPEC + ":10487-10498 (objective function ordering)",
     SPEC + ":10578 (quota and arrival rate as scheduler inputs)"],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "Every result row carries cost fields. Report the quality-per-cost frontier for the current "
    "candidate set, not just the quality ranking.",
    ["Cost fields populated on 100 percent of rows; a run with missing cost data is rejected.",
     "Accounting accuracy: compare recorded tokens against the vendor-reported usage for the same "
     "run and report the discrepancy.",
     "Frontier computation: a dominated candidate (worse and more expensive) must be identified "
     "mechanically."],
    REV_1, RETRY_2S, ["accounting-error", "overclaim", "detector-failure"])

B11 = U(
    "Bound the measurement overhead of the harness itself",
    "10",
    "Question: how much of the measured latency is the thing being measured, and how much is the "
    "instrumentation around it? Measure the harness overhead directly (run a no-op case through the "
    "full pipeline), express it as a fraction of the smallest real case, and set a ceiling above "
    "which the platform must warn that its own overhead dominates. This is distinct from the "
    "product latency tests at :11022, which measure the product; this measures the ruler.",
    [BENCH, SPEC + ":11022 (latency and overhead tests - the product-side layer)",
     "profiling of the harness pipeline", RESULTS],
    [B03], role(OPUS, "benchmark-engineer"), T_ANA, "local-serialized", 3600,
    "Report absolute overhead in milliseconds and as a fraction of the p50 real case. State which "
    "pipeline stages dominate.",
    ["No-op case timing over 100 iterations, distribution reported.",
     "Overhead attribution per stage (setup, oracle, teardown, ledger write).",
     "Ceiling alarm fires when a case is faster than the harness overhead around it."],
    REV_WIN, RETRY_FLAKE, ["substrate-limit", "overclaim", "detector-failure"])

B12 = U(
    "Hold out a shadow case set that never informs development, and use it to detect benchmark overfitting",
    "12",
    "Question: after N iterations of the self-improvement loop, has the system improved, or has it "
    "learned the benchmark? Spec :11059 assigns a refuter to benchmark gaming. Maintain a shadow "
    "split that is never shown to implementers, never used for tuning and never reported until a "
    "release decision, then compare the dev-split gain against the shadow-split gain. A widening gap "
    "is overfitting and must block the improvement claim regardless of how good the dev numbers are.",
    [SPEC + ":11059 (benchmark gaming refuter)", CASES, RESULTS, LOOP16],
    [B01, B04], role(OPUS, "adversarial-refuter"), T_ANA, "cloud-batch", 5400,
    "Report the dev-versus-shadow gain gap over time as a series, not a single snapshot. Also report "
    "access control: who or what could have seen the shadow split, evidenced by file permissions and "
    "the access log.",
    ["Dev-versus-shadow gap tracked per improvement iteration.",
     "Leak audit: grep the program corpus, prompts and fixtures for shadow-case ids; any hit "
     "invalidates the split and forces a re-draw.",
     "Detector control: deliberately tune on a shadow case and confirm the gap widens detectably."],
    REV_XV, RETRY_NONE, FC_GAME)

B13 = U(
    "Contamination check: benchmark cases leaking into prompts, fixtures and the program corpus",
    "12",
    "Implementation target: a case whose answer already appears in a prompt template, a skill file, "
    "a memory note or a committed fixture is not measuring capability. Build the contamination "
    "scan that hashes case inputs and expected outputs and searches the entire program corpus and "
    "the live harness trees for near matches, then quarantines every contaminated case. This is "
    "distinct from B12, which measures the SYMPTOM (a dev/shadow gap); this finds the mechanism.",
    [CASES, "the program corpus and live harness trees", SPEC + ":11059",
     "near-duplicate matching with a declared threshold"],
    [B01], role(OPUS, "adversarial-refuter"), T_ANA, "local-parallel", 5400,
    "Report the number of paths searched, the matching method and threshold, and every contaminated "
    "case id with the path that contaminated it. A zero-hit result must be accompanied by the "
    "detector control.",
    ["Planted control: copy one case answer into a fixture and confirm the scan finds it.",
     "Near-match sensitivity: a paraphrased answer must also be caught, or the scan reports that it "
     "only catches verbatim leakage.",
     "Quarantine effect: a contaminated case must be excluded from scoring, proven by a score "
     "recomputation."],
    REV_XV, RETRY_NONE, FC_GAME)

B14 = U(
    "Goodhart probe: catch a metric that improves while the outcome it proxies gets worse",
    "12",
    "Question: every benchmark metric is a proxy. Pair each primary metric with an independent "
    "outcome judgement on the same runs (human-labelled or a deterministic end-state check that is "
    "NOT the metric), and monitor the correlation between them over improvement iterations. A "
    "metric whose correlation with the real outcome decays as the system optimises it has become a "
    "target rather than a measure, and the platform must raise that as a P1 rather than celebrate "
    "the metric gain.",
    ["paired outcome judgements over benchmark runs", RESULTS, BENCH, SPEC + ":11059"],
    [B12, B[15]], role(OPUS, "adversarial-refuter"), T_ANA, "cloud-batch", 5400,
    "Report the metric-to-outcome correlation per iteration as a series. A single correlation is a "
    "snapshot and cannot show decay, which is the entire phenomenon.",
    ["Correlation series across at least 5 improvement iterations.",
     "Synthetic Goodhart control: optimise a deliberately gameable metric and confirm the decay is "
     "detected.",
     "Metric retirement path: a decayed metric must be demotable without rewriting history in the "
     "results ledger."],
    REV_XV, RETRY_2S, FC_GAME)

B15 = U(
    "Measure judge-model agreement against deterministic oracles and mandate the oracle where one exists",
    "10",
    "Implementation target: where a benchmark case can be scored by an exact algorithm, the platform "
    "must use the algorithm; where only a model judgement is available, the platform must report the "
    "judge agreement rate that licenses trusting it. Measure Cohen kappa between the judge and the "
    "deterministic oracle on the subset where both exist, then extrapolate the error bar onto the "
    "judged-only subset. On this estate an LLM classification of a mechanical comparison measured 86 "
    "percent accurate with 100 percent of errors pointing one way, which is why oracle-first is a "
    "rule and not a preference.",
    [CASES, "deterministic oracles from B01", "the judge prompt and rubric", RESULTS],
    [B01], role(OPUS, "statistician"), T_ANA, "cloud-batch", 5400,
    "Report kappa with n, and the DIRECTION of judge errors (which way it is biased), because "
    "direction matters more than accuracy when the downstream action is a release decision.",
    ["Kappa on the overlap subset with per-class error direction.",
     "Oracle-first enforcement: a case with an available deterministic oracle that is scored by the "
     "judge must fail a lint check.",
     "Judge-swap: a second judge model on the same cases; disagreement between judges bounds how "
     "much either can be trusted."],
    REV_STAT, RETRY_2S, ["calibration-failure", "benchmark-gaming", "overclaim"])

B16 = U(
    "Derive the leaderboard mechanically from the results ledger and forbid hand-typed numbers",
    "10",
    "Implementation target: the leaderboard, the status dashboard and any table in a report that "
    "cites a benchmark figure must be generated from the append-only results ledger and stamped "
    "with the run ids that produced them. CC-0013 applies the same discipline to STATUS.md; this "
    "applies it to benchmark reporting specifically, where the temptation to paste a remembered "
    "number is highest. A figure with no resolvable run id fails the build.",
    [RESULTS, BENCH, "command-center/STATUS.md conventions from CC-0013",
     "report templates that cite benchmark numbers"],
    [B01, "CC-0013"], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "Every published figure resolves to a run id present in the ledger. Report the count of figures "
    "checked and the count that failed to resolve.",
    ["Hand-edit control: change one number in a generated table and confirm the build goes red.",
     "Orphan-figure scan across all report artifacts.",
     "Regeneration idempotence: regenerating from the same ledger reproduces byte-identical tables."],
    REV_1, RETRY_NONE, ["overclaim", "detector-failure", "green-not-live"])

B17 = U(
    "Keep an improvement only when the measurement says so, and prove the gate can say no",
    "16",
    "Implementation target: spec :11145-11146 requires keeping only changes proven to help and "
    "reverting neutral or harmful ones, and :11150 states no improvement is retained merely because "
    "an agent produced it. Implement the decision gate that consumes the B04 paired result and the "
    "B07 margin table and emits KEEP, REVERT or INSUFFICIENT-EVIDENCE. The third outcome is the one "
    "most implementations omit, and omitting it converts every underpowered run into a KEEP.",
    [LOOP16, SPEC + ":11150 (no improvement retained merely because an agent produced it)",
     BENCH, "the B07 margin table"],
    [B04, B07], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 5400,
    "Show one real change of each outcome class (KEEP, REVERT, INSUFFICIENT-EVIDENCE) decided by "
    "the gate. A gate that has only ever said KEEP is indistinguishable from a no-op.",
    ["Neutral change -> REVERT, proven on a synthetic no-op change.",
     "Underpowered run -> INSUFFICIENT-EVIDENCE, not KEEP.",
     "Genuine improvement -> KEEP with the interval cited.",
     "Bypass attempt: a change merged without a gate decision must be caught by an audit of the "
     "commit range against the decision ledger."],
    REV_1, RETRY_NONE, ["overclaim", "green-not-live", "detector-failure"])

B18 = U(
    "Prove the automatic revert actually restores the measured baseline",
    "16",
    "Question: the loop at :11146 reverts when a change is neutral or harmful, but a revert that "
    "leaves residue is worse than no revert because the baseline silently drifts. After every "
    "revert, re-run the baseline benchmark and require the result to fall within the B03 variance "
    "floor of the pre-change baseline, and separately require the working tree to match the "
    "pre-change SHA on the affected paths.",
    [LOOP16, BENCH, "the B08 immutable baseline records", "git diff against the pre-change SHA"],
    [B08, B17], role(OPUS, "test-engineer"), T_BUILD, "worktree-isolated", 5400,
    "Report both signals: the post-revert benchmark delta against the baseline, and the path-level "
    "diff against the pre-change SHA. One signal alone is the single-signal failure this program "
    "keeps hitting.",
    ["Revert a real change; both signals agree that the baseline is restored.",
     "Residue control: revert a change that also wrote a cache or a generated file, and confirm the "
     "residue is detected rather than absorbed.",
     "Revert of a revert returns to the changed state, proving the operation is not lossy."],
    REV_1, RETRY_NONE, ["state-corruption", "green-not-live", "overclaim"])

B19 = U(
    "Every closed defect must leave behind a regression case that would catch its return",
    "16",
    "Implementation target: step 10 of the loop at :11148 requires updating the benchmark so the "
    "same failure cannot silently return. Enforce it structurally: a defect record cannot move to "
    "CLOSED until a case exists whose oracle FAILS on the pre-fix commit and PASSES on the post-fix "
    "commit. Both runs must be recorded. A test written after the fix and never run against the "
    "broken state proves nothing, which is the ordinary way this requirement is satisfied on paper "
    "and violated in fact.",
    [SPEC + ":11148", CASES, "the defect register from bucket B10/B11",
     "the two-commit runner (pre-fix and post-fix)"],
    [B01], role(OPUS, "test-engineer"), T_BUILD, "worktree-isolated", 5400,
    "For each closed defect cite two run ids: the failing run on the pre-fix commit and the passing "
    "run on the post-fix commit. A single passing run is not admissible.",
    ["Closure blocked when the pre-fix run is missing.",
     "Both-states enforced automatically by the closure tool, not by reviewer discipline.",
     "Backfill census: report how many already-closed defects lack a pre-fix failing run and treat "
     "that number as debt, not as pass."],
    REV_1, RETRY_NONE, FC_GREEN)

B20 = U(
    "Meta-benchmark the self-improvement loop so it cannot quietly get worse at improving",
    "16",
    "Question: the loop at :11135-11150 is itself a system that can degrade - accepting more "
    "marginal changes, taking longer per iteration, or reverting good work. Track loop-level "
    "metrics across iterations (KEEP rate, post-KEEP regression rate, iterations per accepted "
    "improvement, mean time to revert) and treat a degrading trend as a defect in the loop rather "
    "than noise in the projects it operates on.",
    [LOOP16, RESULTS, "decision records emitted by B17", BENCH],
    [B17, B18], role(OPUS, "benchmark-engineer"), T_ANA, "local-parallel", 5400,
    "Report the loop metrics as a per-iteration series with at least 5 iterations. A single "
    "iteration cannot show a trend and must be reported as NOT-CHECKED for this unit.",
    ["Loop metric series computed from decision records, not hand-tallied.",
     "Post-KEEP regression rate: how often a KEEP is later reverted; a rising rate is the key alarm.",
     "Degradation control: inject a deliberately permissive gate and confirm the meta-benchmark "
     "detects the KEEP-rate jump."],
    REV_STAT, RETRY_2S, FC_CAL)

B21 = U(
    "Benchmark evidence on a marketplace listing must resolve to a real run",
    "6",
    "Implementation target: spec :10860 lists benchmark evidence as marketplace metadata. Define the "
    "evidence field as a reference (run id, case-set id, harness version, commit SHA) rather than a "
    "free-text claim, and make the marketplace linter reject a listing whose evidence does not "
    "resolve in the results ledger or whose harness version is no longer supported. Unverifiable "
    "performance claims are the marketplace-abuse vector at :11056.",
    [SPEC + ":10860 (marketplace benchmark evidence)", SPEC + ":11056 (marketplace abuse refuter)",
     RESULTS, "the marketplace linter from bucket B07 phase 6"],
    [B16], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 3600,
    "Cite the linter rule and a rejected fixture listing. A schema that permits free text anywhere "
    "in the evidence field must be reported as an open hole.",
    ["Listing with a fabricated run id is rejected.",
     "Listing with a valid but expired (B09) run is flagged as stale rather than accepted.",
     "Both-states: a well-formed listing with a resolvable run passes.",
     "Third-party listing case: evidence produced by a publisher we do not control must be marked "
     "unverified rather than silently trusted."],
    REV_SEC, RETRY_NONE, ["security-finding", "overclaim", "detector-failure"])

B22 = U(
    "Cross-vendor benchmark parity, and the abstraction leaks it exposes",
    "9",
    "Question: the same case set run through the Claude adapter and the Codex adapter should differ "
    "in RESULT, not in what was actually asked. Diff the effective request each adapter builds "
    "(prompt, tools offered, context assembled, timeout) and report every divergence, then run the "
    "parity benchmark. Spec :10983 forbids pretending full interchangeability where tools, context "
    "or permissions differ and requires degrading loudly; this unit produces the concrete list of "
    "what actually differs.",
    [SPEC + ":10983 (do not pretend full interchangeability; document abstraction leaks)",
     "the cross-vendor adapters from bucket B07 phase 9", CASES, "mcp__codex__codex adapter"],
    [B01], role(OPUS, "test-engineer"), T_XV, "local-serialized", 7200,
    "Publish the request-diff table before the score table. A score comparison presented without "
    "the request diff invites attributing an adapter defect to a model difference.",
    ["Request-level diff per adapter on identical cases.",
     "Score comparison on the subset where the request diff is empty.",
     "Loud degradation: a capability present in one adapter and absent in the other must produce an "
     "explicit unsupported result, never a silent fallback that scores as a failure."],
    REV_XV, RETRY_FLAKE, ["platform-divergence", "substrate-limit", "overclaim"], True)

B23 = U(
    "A tournament winner must decompose back into its sources, and the sources must be re-scored",
    "2B",
    "Implementation target: spec :10913 and :11170 require a fused workflow to preserve lineage and "
    "be decomposable back into its source mechanisms, and :11332 names workflow fusion losing a "
    "source capability. After a fusion wins, mechanically decompose it, re-run each recovered source "
    "component on the matched case set, and assert that the fusion covers every capability its "
    "sources had. A fusion that wins by dropping a rarely-exercised capability is a regression "
    "dressed as an improvement.",
    [SPEC + ":10913 (lineage and decomposition)", SPEC + ":11170", SPEC + ":11332", CASES,
     "the fusion engine from bucket B04"],
    [B02, B06], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report the capability set of each source, the capability set of the fusion, and the set "
    "difference. A non-empty difference is a blocking finding, not a footnote.",
    ["Capability set difference computed mechanically from stage/tool declarations.",
     "Decomposition round-trip: recovered components must run standalone.",
     "Lineage integrity: every fused stage names its source and license, checked by set membership.",
     "Loss control: deliberately drop a stage from a fusion and confirm the difference is detected."],
    REV_1, RETRY_2S, ["capability-loss", "detector-failure", "overclaim"])

B24 = U(
    "Benchmark the capability router on selection breadth and task success without context flooding",
    "8",
    "Implementation target: spec :10962-10963 requires measuring skill-use breadth and task success "
    "and a regression suite proving the router selects relevant capabilities WITHOUT flooding "
    "context. Build the two-sided benchmark: recall (was the right capability offered) and cost "
    "(how many tokens of capability description were injected). Optimising either alone produces a "
    "degenerate router - inject everything for perfect recall, or inject nothing for perfect cost.",
    [SPEC + ":10962-10963 (skill-use breadth, task success, no context flooding)",
     "the router from bucket B07 phase 8", CASES,
     SPEC + ":11330 (capability router fails to select an installed skill)"],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 5400,
    "Report recall and injected-token cost as a pair on every configuration. A recall figure with no "
    "cost figure is the degenerate result this unit exists to prevent.",
    ["Recall on a labelled task-to-capability gold set.",
     "Injected-token cost measured per task, not estimated.",
     "Flooding control: a configuration that injects the whole catalogue must show perfect recall "
     "and a cost that fails the budget, proving both axes are live.",
     "Known-miss case from :11330: an installed skill the router currently fails to select must be "
     "in the suite."],
    REV_1, RETRY_2S, FC_CAL)

B25 = U(
    "Benchmark deep-research quality on quota adherence and contradiction retention",
    "10",
    "Question: the research workflow at :11260-11278 is configured with favourable and unfavourable "
    "result quotas, contradiction search and a requirement to preserve negative and contradictory "
    "evidence. Build seeded corpora where the true distribution of supporting and contradicting "
    "sources is known by construction, then measure whether the workflow returns them in the "
    "configured proportion and whether contradictions survive into the final report. A research "
    "system that quietly drops disconfirming evidence still produces a confident, useless answer.",
    ["seeded corpora with known support/contradiction ratios",
     SPEC + ":11260-11278 (deep-research required configuration)", CASES, BENCH],
    [B01], role(OPUS, "benchmark-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report the configured quota, the returned proportion and the contradiction survival rate into "
    "the final artifact, per corpus. Survival into the intermediate notes does not count.",
    ["Quota adherence measured against a known ground-truth ratio.",
     "Contradiction survival traced to the FINAL report, not the working notes.",
     "Suppression control: a corpus where the contradicting evidence is stronger must not be "
     "reported as consensus.",
     "Proof-of-impossibility path exercised on a corpus where the asked-for evidence does not exist."],
    REV_1, RETRY_2S, ["evidence-bypass", "calibration-failure", "overclaim"])

B26 = U(
    "Resume an interrupted tournament without recomputing or double-counting",
    "10",
    "Implementation target: a tournament over hundreds of cases and dozens of candidates will be "
    "interrupted. Make the runner resumable at case granularity with idempotent result writes keyed "
    "by (candidate, case, harness version, seed), so a resume neither re-runs completed work nor "
    "appends a second result row for it. Double-counting is the silent variant: the tournament "
    "completes, the numbers are wrong, and nothing looks broken.",
    [BENCH, RESULTS, SPEC + ":10500 (resumable artifacts as the safe scaling mechanism)", CASES],
    [B06], role(OPUS, "harness-engineer"), T_BUILD, "worktree-isolated", 5400,
    "Compare the results ledger after an uninterrupted run against a kill-and-resume run: identical "
    "row count and identical per-cell values. Row count alone would miss a value change.",
    ["Kill at 40 percent and resume; ledger matches the uninterrupted run exactly.",
     "Idempotence: re-running a completed cell must not append a duplicate row.",
     "Partial-write control: kill mid-write and confirm the torn row is discarded rather than "
     "parsed as a result."],
    REV_WIN, RETRY_2S, ["state-corruption", "accounting-error", "overclaim"])

B27 = U(
    "Ten-times-scale benchmark: throughput, arrival rate and queue depth before the program relies on it",
    "10",
    "Question: spec :11080 asks what would break at 10x scale, and the program plans 2,048 work "
    "units. Drive the dispatcher at 10 times the planned arrival rate against stub workers and "
    "measure throughput, queue depth, scheduler latency, memory and the point at which staggering "
    "stops preventing the :11318 arrival-rate storm. Stub workers keep the cost bounded and isolate "
    "the SCHEDULER as the thing under test rather than the models.",
    [SPEC + ":11080 (what would break at 10x scale)", SPEC + ":11318 (429 arrival-rate storm)",
     "the dispatcher and scheduler from bucket B07 phase 9", "stub workers with scripted latency"],
    [B03], role(OPUS, "harness-engineer"), T_BUILD, "cloud-batch", 10800,
    "Report the saturation curve (offered rate versus completed rate) and the first failure mode "
    "observed, by name. A pass/fail with no curve does not tell the owner where the cliff is.",
    ["Saturation curve to at least 10x planned rate against stub workers.",
     "Backpressure works: offered rate above capacity must queue or shed deliberately, never "
     "silently drop units.",
     "Local-stability guard: the run must not be executed on the owner workstation at full rate; "
     "record the substrate actually used.",
     "Recovery: after the storm subsides, the scheduler must return to normal throughput."],
    REV_WIN, RETRY_2S, ["substrate-limit", "platform-divergence", "overclaim"], True)

B28 = U(
    "Make the results ledger append-only and prove a retroactive edit is detectable",
    "10",
    "Implementation target: every number this program cites eventually traces to the results ledger, "
    "so a silently mutated past result poisons every downstream claim. Make the ledger append-only "
    "with a per-row content hash chained to the previous row, and ship the verifier that detects "
    "insertion, deletion and in-place edit. This is the integrity substrate under B16 (generated "
    "tables) and B12 (overfitting series), both of which are worthless if history can move.",
    [RESULTS, "command-center/events/EVENTS.jsonl conventions",
     "the append-only event-log hardening from CC-0007", BENCH],
    [B01, "CC-0007"], role(OPUS, "harness-engineer"), T_BUILD, "local-serialized", 5400,
    "Show the verifier detecting all three tamper classes on a copy of the real ledger. Report the "
    "ledger row count and the verification wall-clock so the check is known to be practical.",
    ["Tamper controls: in-place edit, deleted row and inserted row each DETECTED.",
     "Clean ledger verifies silently (no false positive).",
     "Concurrent-writer safety on Windows: two writers appending simultaneously must not interleave "
     "a torn row, tested with real concurrent processes."],
    REV_WIN, RETRY_NONE, ["state-corruption", "security-finding", "detector-failure"])

B29 = U(
    "Stratified human spot-audit of benchmark verdicts, with an escalation threshold",
    "11",
    "Implementation target: mirror the Phase-11 rule at :11041 - sample the platform's own verdicts, "
    "re-adjudicate them by hand, and if the sampled error rate exceeds a pre-set threshold, expand "
    "re-verification to the entire affected class. Stratify the sample by oracle type (deterministic "
    "versus judged) and by verdict (pass versus fail), because a platform that is accurate on passes "
    "and wrong on failures has a specific, fixable bias that an unstratified sample averages away.",
    [SPEC + ":11041 (expand re-verification when the sampled error rate exceeds the threshold)",
     RESULTS, CASES, "the human adjudication protocol authored here"],
    [B15], role(OPUS, "benchmark-engineer"), T_ANA, "local-serialized", 7200,
    "Report the sample design (strata, sizes, selection method) BEFORE the error rate. An error rate "
    "from a convenience sample is not an error rate.",
    ["Stratified sample drawn by a recorded random seed, not by hand-picking.",
     "Error rate per stratum with intervals.",
     "Escalation fires: seed a stratum with known-bad verdicts above the threshold and confirm "
     "full-class re-verification is triggered."],
    REV_STAT, RETRY_NONE, ["calibration-failure", "overclaim", "detector-failure"], True)

B30 = U(
    "Compute stopping condition 8 from the ledger instead of asserting it in prose",
    "15",
    "Implementation target: condition 8 at :11385 must be a function over the results ledger, the "
    "B07 margin table and the B04 intervals, returning TRUE, FALSE or NOT-CHECKED with the "
    "supporting run ids attached. CC-0015 encodes the 21 conditions; this unit supplies the "
    "specific evaluator for the benchmark condition, which is the only one whose truth requires a "
    "statistical judgement rather than a file check. The default when data is missing must be "
    "NOT-CHECKED, never TRUE.",
    [STOP8, "command-center/COMPLETION-GATES.json", RESULTS, "the B07 margin table"],
    [B04, B07, "CC-0015"], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "The evaluator output must carry the run ids it consumed. A TRUE with no run ids is exactly the "
    "prose assertion this unit replaces.",
    ["Missing data -> NOT-CHECKED, proven by removing a required input.",
     "Regression beyond the margin -> FALSE even when the primary metric improved.",
     "Genuine improvement within margins -> TRUE with run ids.",
     "Determinism: two evaluations of the same ledger state agree."],
    REV_1, RETRY_NONE, ["overclaim", "green-not-live", "statistical-invalidity"])

B31 = U(
    "Adding cases to the corpus must not silently move the baseline",
    "10",
    "Question: the corpus will grow as defects are converted into cases by B19, and every addition "
    "changes the aggregate score even when nothing about the system changed. Version the case set, "
    "report every aggregate against its case-set version, and require any cross-version comparison "
    "to be computed on the intersection with the difference reported separately. Otherwise the "
    "self-improvement loop will read corpus growth as regression and revert good work.",
    [CASES, RESULTS, BENCH, "case additions produced by B19"],
    [B01, B19], role(OPUS, "benchmark-engineer"), T_BUILD, "local-parallel", 3600,
    "Show one cross-version comparison computed both naively and on the intersection, with the "
    "difference between the two numbers stated explicitly.",
    ["Case-set version stamped on every aggregate.",
     "Cross-version comparison refuses to run without an intersection.",
     "Growth control: add 20 hard cases to a static system and confirm the naive aggregate drops "
     "while the intersection aggregate does not."],
    REV_STAT, RETRY_NONE, FC_STAT)
# ============================================================ LANE C (27 units)
# Test-program infrastructure and meta-testing governance. Parts 1 and 2 author
# the per-layer tests; this lane governs the program those tests live in.

TREG = "command-center/TEST-REGISTRY.json"
CIWF = "the CI workflow files that declare test steps"

C01 = U(
    "Reconcile discovered tests against the registry: find orphan tests and ghost entries",
    "10",
    "Implementation target: CC-0014 binds tests to claims to units; this unit supplies the "
    "DISCOVERY side it depends on. Walk every tree the program owns (repo, live harness trees, "
    "worktrees) collecting executable tests by their real invocation, then compute two set "
    "differences: tests on disk with no registry entry (orphans, running but uncounted) and "
    "registry entries with no discoverable test (ghosts, counted but not running). A ghost entry is "
    "how a suite gets credit for coverage it does not have.",
    [TREG, "the repo and live harness trees", "CC-0014 test-claim binding contract",
     "pytest and vitest collection output as the discovery source"],
    ["CC-0014"], role(OPUS, "harness-engineer"), T_ANA, "local-serialized", 5400,
    "Report both set sizes with the full id lists, plus the number of paths walked. A zero-orphan "
    "claim requires the walker to have visited the trees where orphans would live, so name them.",
    ["Detector control: plant a test file outside the registry and confirm it appears as an orphan.",
     "Ghost control: add a registry entry for a nonexistent test and confirm it is reported.",
     "Walker completeness: the reserved-device-name and long-path cases from C10 must not silently "
     "truncate the walk (a crashed walker reporting zero looks like a clean tree)."],
    REV_WIN, RETRY_NONE, ["detector-failure", "green-not-live", "overclaim"])

C02 = U(
    "Census every suite for a declared negative control and fail the ones that have none",
    "10",
    "Implementation target: spec :11026 requires every important test suite to include negative "
    "controls or mutations proving it detects the defect it claims to detect, and stopping "
    "condition 5 at :11382 turns on that coverage. Build the census that, for each registered "
    "suite, resolves its declared negative control to an actual executable artifact and records "
    "whether that control has ever been observed to FAIL. A declared-but-never-run control is "
    "equivalent to no control and must be counted as such.",
    [NEGCTL, SPEC + ":11382 (mutation and negative-control coverage demonstrate detector validity)",
     TREG, "run history from the results ledger"],
    [C01], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 5400,
    "Report three counts: suites with no declared control, suites with a declared control that has "
    "never been observed failing, and suites with a control observed failing. Only the third counts "
    "as covered.",
    ["Census resolves every declaration to a path plus a run id, or marks it unresolved.",
     "Planted control: register a suite with a fake control path and confirm the census flags it.",
     "Both-states: a suite with a genuine, observed-failing control passes without manual "
     "intervention."],
    REV_1, RETRY_NONE, FC_GREEN)

C03 = U(
    "Ship a reusable both-states fixture so a detector must fire on the broken state before it is trusted",
    "0",
    "Implementation target: spec :10658 requires verifying detectors against known-broken and "
    "known-good controls. Provide it as a shared fixture rather than a convention: a helper that "
    "takes a detector, a known-good state and a known-broken state, asserts SILENT then FIRES, and "
    "records both observations in the receipt. A probe that is silent in both states measures "
    "nothing, and on this estate that exact failure reached the point of being reported as "
    "verification, so the discipline needs to be a callable, not a reminder.",
    [SPEC + ":10658 (verify detectors against known-broken and known-good controls)",
     "the shared test-support package", TREG, NEGCTL],
    [], role(OPUS, "harness-engineer"), T_BUILD, "worktree-isolated", 3600,
    "The fixture itself must be exercised by a self-test that includes a deliberately silent "
    "detector and confirms the fixture REJECTS it. A fixture that cannot fail is the same bug one "
    "level up.",
    ["Self-test: a detector silent in both states is rejected by the fixture.",
     "Self-test: a detector that fires in both states (always-on) is also rejected.",
     "Adoption census: report how many registered detectors currently use the fixture versus a "
     "hand-rolled control."],
    REV_1, RETRY_NONE, FC_DET)

C04 = U(
    "Conformance-test the shared completion predicate one condition at a time",
    "4",
    "Implementation target: the predicate at :10631-10644 has 12 conditions, and a reducer that "
    "ignores one of them still returns TRUE on every healthy input, so ordinary tests cannot see "
    "the hole. Author one mutation per condition that violates exactly that condition while "
    "satisfying the other eleven, and require the reducer to return FALSE on each. Twelve targeted "
    "mutations is the only construction that proves all twelve are wired.",
    [PRED, "the shared reducer from CC-0003", "command-center/COMPLETION-GATES.json",
     SPEC + ":10646 (exit code zero alone is never success)"],
    ["CC-0003"], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 5400,
    "Publish a 12-row table: condition, the mutation used, and the reducer verdict. A summary "
    "sentence claiming all twelve are covered without the table is not evidence.",
    ["Twelve single-condition mutations, each producing FALSE.",
     "Healthy input produces TRUE (no over-rejection).",
     "Condition independence: each mutation must violate exactly one condition, verified by "
     "evaluating all twelve on each mutant.",
     "The specific case at :10646 - exit code zero with a missing artifact - is one of the twelve."],
    REV_1, RETRY_NONE, FC_DET)

C05 = U(
    "Differential-test two completion-predicate implementations against each other on identical inputs",
    "10",
    "Question: spec :11314 names two completion predicates disagreeing as a failure class. CC-0004 "
    "statically detects a fan-in site that rolls its own check; this unit is the runtime "
    "differential for the implementations that legitimately exist in different runtimes (the local "
    "python reducer, any JavaScript or shell reimplementation in a monitor, and the cloud "
    "dispatcher). Feed both the same corpus of unit states, including malformed and partial ones, "
    "and require byte-identical verdicts.",
    [SPEC + ":11314 (two completion predicates disagree)", "the shared reducer from CC-0003",
     "monitor and dispatcher reducer implementations", "a corpus of unit states incl. malformed"],
    ["CC-0003", "CC-0004"], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 5400,
    "Report the corpus size, the number of disagreements and every disagreeing input verbatim. Zero "
    "disagreements on a corpus with no malformed inputs is not a result.",
    ["Differential over a corpus that deliberately includes partial artifacts, missing sentinels "
     "and torn JSON.",
     "Divergence control: patch one implementation to skip a condition and confirm the differential "
     "detects it.",
     "Implementation census: if only one implementation exists, report that as NOT-CHECKED rather "
     "than passing the unit trivially."],
    REV_XV, RETRY_NONE, FC_DET)

C06 = U(
    "Validate that every evidence anchor in a receipt actually resolves",
    "10",
    "Implementation target: this program requires file:line anchors, exact commands with output, or "
    "an explicit inferred-from statement on every load-bearing claim. Build the validator that "
    "parses receipt evidence fields and checks each anchor: the file exists at that revision, the "
    "line number is within range, the quoted command appears in the recorded transcript, and the "
    "URL has an archived copy. An anchor that does not resolve is a fabricated citation, and it is "
    "cheaper to catch mechanically than in review.",
    [RECEIPT_SCHEMA, "receipts produced across the program", "the artifact manifest from CC-0009",
     "git object access for revision-pinned anchors"],
    ["CC-0002", "CC-0009"], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 5400,
    "Report anchors checked, resolved, unresolved and unparseable, with the unresolved list in full. "
    "Line-range checks must use the file AT THE CITED REVISION, not the current working tree.",
    ["Planted bad anchors: nonexistent file, out-of-range line, command never run - each DETECTED.",
     "Valid anchors pass (no false positives on real receipts).",
     "Revision correctness: an anchor valid at its cited commit but stale at HEAD must pass, "
     "proving the validator reads the right bytes."],
    REV_1, RETRY_NONE, ["detector-failure", "overclaim", "fabricated-citation"])

C07 = U(
    "Prove every declared CI test step actually executed in the last green run",
    "10",
    "Question: a workflow can declare 60 test steps and execute 28 of them because earlier steps "
    "short-circuit, matrix legs are skipped, or a condition never matches - and the run still "
    "reports green. Parse the CI definitions for declared test steps, parse the actual run logs for "
    "executed ones, and report the difference. This exact gap was measured on this repo during the "
    "Phase-0 baseline lane and is invisible from the badge.",
    [CIWF, "CI run logs and job summaries via gh", TREG,
     "the Phase-0 baseline finding that 32 of 60 declared steps were never executed"],
    [C01], role(OPUS, "test-engineer"), T_ANA, "local-serialized", 5400,
    "Report declared count, executed count and the unexecuted list by step name and job. A green "
    "badge is not evidence any particular step ran.",
    ["Set difference between declared and executed steps for the latest green run.",
     "Skip-reason attribution per unexecuted step (conditional false, matrix exclusion, earlier "
     "failure, cancelled).",
     "Detector control: add a step that cannot run and confirm it appears in the unexecuted list."],
    REV_1, RETRY_NONE, FC_GREEN)

C08 = U(
    "Test the installed entry point, not just the module: console-script versus python -m parity",
    "10",
    "Implementation target: running a suite as python -m pytest imports from the working tree, while "
    "CI and end users invoke the installed console script, which resolves through packaging "
    "metadata. A packaging regression (missing entry point, wrong package data, an import that only "
    "works from the source directory) is invisible to the first and fatal to the second. Run the "
    "critical suites both ways and diff outcomes; the Phase-0 baseline lane flagged this as a "
    "known blind spot in its own method.",
    ["the console-script entry points declared in packaging metadata", CIWF, TREG,
     "a clean virtualenv with the package installed from a built artifact"],
    [C07], role(OPUS, "test-engineer"), T_BUILD, "worktree-isolated", 5400,
    "Report both invocations verbatim with their exit codes and collected counts. Equal exit codes "
    "with different collected counts is a real divergence and must not be read as parity.",
    ["Both invocations on the same commit; collected count and outcome compared.",
     "Fresh-venv install path exercised, not the editable install.",
     "Break control: remove an entry point and confirm the console-script arm fails while the "
     "python -m arm still passes, demonstrating the blind spot is real."],
    REV_WIN, RETRY_NONE, ["packaging-defect", "green-not-live", "detector-failure"])

C09 = U(
    "Run the test tooling against the committed blob, not the Windows working tree",
    "10",
    "Implementation target: on this box the working tree is CRLF and the committed blob is LF, and "
    "formatters, hash gates and content assertions can decide differently on the two. The measured "
    "trap is worse than it sounds: git archive returns the CRLF worktree bytes, so the recipe most "
    "people reach for verifies the wrong bytes. Make the harness read via git cat-file -p or git "
    "show for any check whose result depends on file content, and ship the both-states proof.",
    ["git cat-file and git show as the blob source", "the CRLF/LF divergence measured on this repo",
     "command-center/RELEASE-CHECKLIST.md (which currently prescribes git archive)",
     "the content-dependent gates in tools/command-center/"],
    [], role(OPUS, "harness-engineer"), T_BUILD, "local-serialized", 5400,
    "Show the byte counts and hashes from all three routes (git archive, git cat-file, working "
    "tree) for at least one real file, so the divergence is demonstrated rather than asserted.",
    ["Three-route comparison on a file with known line count; CRLF counts reported.",
     "Gate parity: a content gate must return the same verdict locally and in CI on the same commit.",
     "Control: a file that is byte-identical under LF normalisation must be shown identical, "
     "proving the difference measured is line endings and not content."],
    REV_WIN, RETRY_NONE, FC_WIN)

C10 = U(
    "Harden the harness file walker against reserved device names, long paths and junctions",
    "10",
    "Implementation target: the Phase-0 baseline enumerator crashed with a ValueError on a file "
    "literally named NUL, and a swallowed crash would have reported every count as zero, which "
    "reads as trees are empty. Harden the walker used by the test and census tooling: extended-length "
    "prefixes for long paths, safe handling of reserved device names, junction and symlink loop "
    "detection, and a fail-closed rule that an incomplete walk is an error rather than a small "
    "number. Product-side long-path behaviour is slice part 2 layer 29; this is the instrument.",
    ["the measured NUL crash from the Phase-0 baseline lane",
     "Windows reserved device names and the extended-length prefix", "the census walkers in lane C",
     SPEC + ":11017 (long-path tests - the product-side layer)"],
    [C01], role(OPUS, "harness-engineer"), T_BUILD, "local-serialized", 5400,
    "Create the hostile fixture tree (reserved name, 300-character path, junction loop) and report "
    "the walker result on each. A walker that completes must report the count of entries it could "
    "not read, never silently skip them.",
    ["Hostile fixture tree walked without crashing and without silent omission.",
     "Fail-closed: an unreadable entry produces an error result, not a reduced count.",
     "Loop detection: a junction cycle terminates rather than recursing.",
     "Regression: the exact NUL case that crashed the baseline enumerator is in the fixture."],
    REV_WIN, RETRY_NONE, FC_WIN)

C11 = U(
    "Quarantine flaky tests and treat a flake as a defect rather than absorbing it in retries",
    "10",
    "Implementation target: measure per-test flake rate by rerunning the suite N times on an "
    "unchanged commit, publish the ranked list, and route anything above the threshold into a "
    "quarantine lane that still RUNS and still reports but cannot block. The rule that matters is "
    "the accounting one: a quarantined test is open debt with an owner and a deadline, not a "
    "solved problem, and a retry policy that hides flakes converts a real intermittent defect into "
    "invisible noise.",
    [TREG, "N repeated runs on an unchanged commit", RESULTS,
     "the retry policy declared across this catalog"],
    [C01], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report per-test flake rate with the number of repetitions behind it. A flake rate from fewer "
    "than 20 runs must be labelled provisional.",
    ["Flake rate measured over at least 20 identical runs.",
     "Quarantine does not hide: quarantined results still appear in the report with their status.",
     "Debt accounting: every quarantined test has an owner and an age, and the age is reported.",
     "Control: inject a coin-flip test and confirm it is detected and quarantined."],
    REV_1, RETRY_FLAKE, ["flake", "green-not-live", "overclaim"])

C12 = U(
    "Prove the impacted-test selector never omits a test the full suite would have failed",
    "10",
    "Question: selecting only impacted tests is only safe if selection is sound. Build the "
    "differential: for a corpus of mutations, run BOTH the selected subset and the full suite, and "
    "assert that every mutation caught by the full suite is also caught by the subset. Any mutation "
    "the full suite catches and the subset misses is an unsound selector and the selection rule must "
    "be tightened or abandoned for that path.",
    ["the deterministic test selector (dependency or coverage-map based)",
     "a mutation corpus over the product source", TREG, "full-suite baseline results"],
    [C01, C02], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 7200,
    "Report mutations caught by full suite, caught by subset, and the miss list. Also report the "
    "time saved, because an unsound selector that saves nothing is doubly pointless.",
    ["Soundness differential over at least 100 mutations.",
     "Miss list published with the file each missed mutation touched.",
     "No-ML rule: the selector must be deterministic (dependency graph or coverage map); a "
     "predictive selector is out of scope and must be rejected if found.",
     "New-file case: a test added but not yet in the coverage map must default to SELECTED."],
    REV_1, RETRY_2S, ["detector-failure", "green-not-live", "overclaim"])

C13 = U(
    "Read the coverage threshold from the project SSOT and emit NOT-CHECKED when there is none",
    "10",
    "Implementation target: coverage thresholds live in a per-project .coverage-thresholds.json and "
    "its enforcement command, never in an agent's memory. Build the resolver that locates the file "
    "for the project under test, runs its declared enforcement command, and - when no such file "
    "exists - emits NOT-CHECKED and surfaces it, rather than folding the absence into a silent pass "
    "or blocking a project that was never coverage-gated. Both failure directions are live: a "
    "hardcoded command from another project is a dead command here.",
    [".coverage-thresholds.json wherever the project defines one", TREG,
     "the enforcement command declared inside that file", CIWF],
    [C01], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 3600,
    "Report, per project in scope, whether the file exists, the command it declares, and the result "
    "or NOT-CHECKED. A single aggregate coverage number across projects with different thresholds "
    "is meaningless and must not be emitted.",
    ["Project WITH the file: the declared command runs and its exit code is reported.",
     "Project WITHOUT the file: NOT-CHECKED emitted and surfaced, never a pass.",
     "Wrong-project control: the resolver must not apply one project's command to another, proven "
     "by a two-project fixture."],
    REV_1, RETRY_NONE, ["green-not-live", "overclaim", "detector-failure"])

C14 = U(
    "Census the default arguments that no test ever exercises",
    "10",
    "Question: a module can report full line coverage while every one of its default parameter "
    "values is dead, because each call site passes the argument explicitly. The measured instance "
    "on this estate is a constant whose default was reverted from 1024 to 512 with a fully green "
    "suite. Build the census: for every function with defaults, determine whether any test invokes "
    "it WITHOUT that argument, and report the defaults that are never exercised as an explicit "
    "coverage hole that line coverage cannot see.",
    ["AST analysis of default parameters across the product source", "test invocation traces",
     "the measured DEFAULT_MIN_BYTES mutation that survived a green suite", TREG],
    [C02], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 5400,
    "Report the count of defaults, the count exercised, and the unexercised list with file:line. A "
    "coverage percentage without this census overstates protection.",
    ["Census over all functions with default parameters.",
     "Mutation confirmation on a sample: change an unexercised default and confirm the suite stays "
     "green, proving the hole is real rather than theoretical.",
     "Both-states: change an EXERCISED default and confirm the suite goes red."],
    REV_1, RETRY_NONE, FC_GREEN)

C15 = U(
    "Flag any snapshot updated in the same change as the code it is supposed to guard",
    "10",
    "Implementation target: a golden file regenerated alongside the code it verifies has stopped "
    "being a test and become a transcript. Build the check that, for every commit or PR, "
    "intersects the set of changed snapshot files with the set of changed source files they cover, "
    "and requires an explicit, reviewed justification when the intersection is non-empty. Blanket "
    "snapshot regeneration is the mechanism by which a suite stays green through a behaviour change.",
    ["snapshot and golden files in the repo", "the coverage map linking snapshots to sources",
     "git diff over the change under review", TREG],
    [C01], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 3600,
    "Report the intersection per change with the file pairs named. A justification field that is "
    "empty or boilerplate must be reported as unjustified.",
    ["Planted case: change a source and regenerate its snapshot in one commit -> FLAGGED.",
     "Legitimate case: a snapshot updated for an intentional, documented behaviour change passes "
     "with its justification recorded.",
     "Unrelated-change control: changing a snapshot and an unrelated source must not flag."],
    REV_1, RETRY_NONE, FC_GREEN)

C16 = U(
    "Make fixture scanners match semantic role rather than payload text",
    "10",
    "Implementation target: a fixture that DOCUMENTS a forbidden pattern necessarily CONTAINS that "
    "pattern, so any scanner matching raw text will flag the documentation and miss nothing real. "
    "This use-versus-mention defect has hit this estate roughly eight times, mostly inside the "
    "verification probes themselves. Rebuild the program's fixture and content scanners to match on "
    "role - the parsed field, the tool-call verb, the AST node - and prove the rebuild on the "
    "historical false positives.",
    ["the historical false positives where payload text was matched instead of the verb",
     "the fixture and content scanners across the program", "AST and structured-field parsers", TREG],
    [C03], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 5400,
    "Report, for each rebuilt scanner, its result on the historical false-positive corpus AND on a "
    "true-positive corpus. Fixing false positives by loosening the scanner into uselessness is the "
    "obvious wrong repair, so both numbers are mandatory.",
    ["Historical false-positive corpus -> zero flags after the rebuild.",
     "True-positive corpus -> every real instance still flagged.",
     "Self-reference: this unit's own receipt will contain the forbidden patterns as examples and "
     "must not be flagged by the scanner it ships."],
    REV_1, RETRY_NONE, FC_DET)

C17 = U(
    "Per-test hard timeout, suite wall-clock budget and shard balance",
    "10",
    "Implementation target: one hung test blocks a batch, and on a shared runner it blocks every "
    "sibling. Impose a per-test hard timeout that produces a FAILED result rather than a hang, a "
    "suite-level budget that is measured rather than hoped for, and a sharding assignment balanced "
    "by measured duration rather than by file count. Report the slowest 20 tests, because a budget "
    "with no attribution cannot be acted on.",
    [TREG, "measured per-test durations from the results ledger",
     SPEC + ":11317 (one hung unit blocks a large batch)", "the shard assignment configuration"],
    [C01, C11], role(OPUS, "harness-engineer"), T_BUILD, "cloud-batch", 5400,
    "Report the duration distribution, the slowest 20 tests by name, and the per-shard totals. A "
    "shard imbalance above a declared ratio is a finding.",
    ["Hung-test control: a test that sleeps past the timeout must produce FAILED, not a stuck run.",
     "Budget measured on a real full run, not estimated from a subset.",
     "Shard balance computed from measured durations; report the max/min shard ratio."],
    REV_WIN, RETRY_FLAKE, ["substrate-limit", "flake", "overclaim"])

C18 = U(
    "Register every random seed and flag tests that pass on only one of them",
    "10",
    "Implementation target: a test that quietly depends on a fixed seed passes forever and protects "
    "nothing outside that seed. Introduce a seed registry (every test declares whether it is "
    "seed-sensitive and why), then run the suite across a set of seeds and report every test whose "
    "outcome varies. Seed-varying tests split into two classes that must be handled differently: a "
    "genuinely flaky test (C11) and a test whose ASSERTION is too narrow for the behaviour it "
    "claims to cover.",
    ["the global seed configuration", TREG, "repeated suite runs across a seed set",
     "the flake data from C11"],
    [C11], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 5400,
    "Report the seeds used and the per-test outcome matrix across them. A single-seed green run "
    "cannot support any claim about seed independence.",
    ["Suite run across at least 10 seeds; outcome matrix published.",
     "Classification of every varying test as flaky or narrow-assertion, with the evidence for the "
     "classification.",
     "Control: plant a seed-dependent test and confirm it is detected."],
    REV_STAT, RETRY_SEED, ["nondeterminism", "flake", "detector-failure"])

C19 = U(
    "Detect order-dependence by randomising execution order with a planted control",
    "10",
    "Question: does any test pass only because another ran first? Run the suite in randomised order "
    "across multiple permutations, bisect any failure to the minimal ordered pair that reproduces "
    "it, and report each pair as shared-state leakage rather than as a flake. Order-dependence is "
    "distinct from seed sensitivity (C18) and from flakiness (C11) and is repaired differently - it "
    "is almost always a fixture that mutates global state.",
    [TREG, "randomised-order runner support", "the flake and seed data from C11 and C18",
     "the bisection procedure authored here"],
    [C11, C18], role(OPUS, "test-engineer"), T_BUILD, "cloud-batch", 5400,
    "Report the permutations run, every failing permutation and the minimal reproducing pair for "
    "each. A pass across three permutations is weak evidence and must be labelled as such.",
    ["At least 10 permutations executed.",
     "Bisection to a minimal ordered pair for every failure found.",
     "Planted control: add a test that writes global state another test reads, and confirm the "
     "randomised runner surfaces it."],
    REV_1, RETRY_2S, ["state-corruption", "flake", "detector-failure"])

C20 = U(
    "Prove parallel test execution does not contaminate a shared tree, index or temp directory",
    "10",
    "Implementation target: parallel agents and parallel test workers on this estate share one git "
    "index and one temp root, and a broad staging command sweeps a sibling's work. For the test "
    "program specifically: assert that no two workers write the same path, that every worker uses "
    "an isolated temp root and worktree, and that a worker cannot stage or commit. Run the audit "
    "with real concurrency, because a collision that needs two simultaneous writers cannot be found "
    "by a sequential run.",
    ["the parallel test runner configuration", "worktree isolation from the git-worktree tooling",
     "temp-root allocation per worker", TREG],
    [C17], role(OPUS, "harness-engineer"), T_BUILD, "worktree-isolated", 5400,
    "Report the write-path map per worker and the intersection between workers. Also confirm no "
    "worker process has git write capability, evidenced by the attempted operation being refused.",
    ["Real concurrent run with per-worker write tracing; path intersection must be empty.",
     "Collision control: force two workers onto one temp root and confirm the audit detects it.",
     "Staging refusal: a worker attempting to stage must fail, protecting sibling work."],
    REV_WIN, RETRY_2S, ["state-corruption", "data-loss-risk", "detector-failure"])

C21 = U(
    "Build the requirement-to-test traceability matrix and report both empty directions",
    "10",
    "Implementation target: CC-0024 binds owner requirements and numeric floors to UNITS; this unit "
    "binds them to TESTS. Produce the matrix requirement x test and report both empty directions: "
    "requirements with no test that could falsify them, and tests that trace to no requirement. The "
    "first direction is a coverage hole; the second is either dead weight or an undocumented "
    "requirement, and both need an owner decision rather than a silent default.",
    ["the requirement inventory from CC-0024", TREG, "the claim registry", C01 + " discovery output"],
    ["CC-0024", C01], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 5400,
    "Publish the matrix with both empty-direction lists in full. Counts alone cannot be acted on; "
    "the requirement ids and test ids are the deliverable.",
    ["Matrix computed by set operations over declared links, not by reading prose.",
     "Untested-requirement list is non-empty or the completeness of the requirement inventory is "
     "itself questioned in the receipt.",
     "Link validity: every declared link resolves to a real requirement id and a real test id."],
    REV_1, RETRY_NONE, ["spec-gap", "overclaim", "detector-failure"])

C22 = U(
    "Prove each of the 21 program stopping conditions can actually be made false",
    "14",
    "Implementation target: CC-0015 encodes the 21 conditions at :11376-11398 as machine-checkable "
    "predicates. This unit does not re-encode them; it attacks them. For each encoded predicate, "
    "author a mutation of program state that MUST flip it to FALSE. A predicate no mutation can "
    "flip is unfalsifiable and is therefore decorative - it will read TRUE at release time "
    "regardless of the world. Condition 13 is already known to be unsatisfiable as written under "
    "PR-ONLY release mode, which is the opposite pathology and must be reported alongside.",
    [SPEC + ":11376-11398 (21 stopping conditions)", "the predicates encoded by CC-0015",
     "command-center/COMPLETION-GATES.json", "the PR-ONLY release decision"],
    ["CC-0015"], role(OPUS, "adversarial-refuter"), T_BUILD, "local-parallel", 5400,
    "Publish a 21-row table: condition, mutation applied, predicate verdict. Any row where the "
    "verdict did not flip is a finding with the condition named.",
    ["21 mutations, one per condition; each must flip its predicate.",
     "Unflippable conditions reported individually, not aggregated.",
     "Permanently-unsatisfiable conditions (condition 13 under PR-ONLY) reported as a separate "
     "class requiring an owner decision, not silently marked NOT-CHECKED."],
    REV_XV, RETRY_NONE, ["spec-gap", "overclaim", "detector-failure"])

C23 = U(
    "Detect vacuous tests that assert nothing",
    "10",
    "Implementation target: scan the test corpus by AST for tests with no assertion, assertions on "
    "constants, assertions on a mock that the same test configured, and try/except blocks that "
    "swallow the failure they were meant to detect. These pass forever and inflate every coverage "
    "and count metric the program reports. The scan must be AST-based rather than textual so that a "
    "test which merely mentions the word assert in a string is not counted as asserting.",
    ["AST scan over the test corpus", TREG, "the coverage figures those tests contribute to",
     "the use-versus-mention discipline from C16"],
    [C16], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 3600,
    "Report each vacuous class with counts and the full file:line list. Report also the coverage "
    "percentage recomputed with vacuous tests excluded, which is the number that matters.",
    ["Planted controls for each vacuous class -> all DETECTED.",
     "Genuine tests -> zero false positives, checked against a sample of known-good tests.",
     "Recomputed coverage excluding vacuous tests reported next to the headline figure."],
    REV_1, RETRY_NONE, FC_GREEN)

C24 = U(
    "Census tests that mock the very boundary they claim to verify",
    "10",
    "Question: a test for the HTTP client that mocks the HTTP client verifies the mock. Build the "
    "census that, for each test, compares its declared subject against the set of objects it "
    "patches, and flags every case where the subject is inside the patched set. This is distinct "
    "from C23 (which finds tests asserting nothing) - these tests assert plenty, just about a "
    "double. The output is a prioritised list for conversion to contract or integration tests, not "
    "an instruction to delete them.",
    ["AST scan for patch/mock targets per test", "the declared subject of each test from the registry",
     TREG, "the contract-test layer authored in slice part 1"],
    [C23], role(OPUS, "test-engineer"), T_ANA, "local-parallel", 3600,
    "Report flagged tests with the subject and the patched target that overlaps it. A raw mock "
    "count is not the finding; the subject-inside-patched-set overlap is.",
    ["Planted control: a test that patches its own subject -> DETECTED.",
     "Legitimate mocking of a NEIGHBOUR dependency -> not flagged.",
     "Prioritisation: flagged tests ranked by the severity of what they claim to cover."],
    REV_1, RETRY_NONE, FC_GREEN)

C25 = U(
    "Fail closed when a test run collects nothing",
    "10",
    "Implementation target: a run that collects zero tests exits zero and reports green, and a "
    "benchmark over an empty input set returns a clean, meaningless result - both measured on this "
    "estate. Add the floor: every registered suite declares a minimum expected test count, and a "
    "run below it FAILS regardless of exit code. Same rule for any measurement over a collection: "
    "an empty input is an error, never a pass.",
    [TREG, "collected-count output from each runner", CIWF,
     "the measured empty-input benchmarks that returned a meaningless green"],
    [C01, C13], role(OPUS, "test-engineer"), T_BUILD, "local-parallel", 3600,
    "Report the declared minimum and the observed collected count for every suite. A suite with no "
    "declared minimum is itself a finding.",
    ["Zero-collected run FAILS, proven by pointing a runner at an empty directory.",
     "Below-minimum run FAILS, proven by deselecting most of a suite.",
     "Normal run passes; the floor must not become a nuisance gate.",
     "Empty-input rule applied to at least one non-test measurement (a census or a benchmark) as "
     "well, since the defect class is not specific to pytest."],
    REV_1, RETRY_NONE, FC_GREEN)

C26 = U(
    "Resolve every tests-pass claim in the program corpus to a real run id, and reject the ones that cannot",
    "14",
    "Implementation target: Phase 14 at :11096 requires meta-review for claims of completion not "
    "backed by the shared predicate. Sweep every artifact in the program corpus for claims of the "
    "form tests pass, suite is green, coverage is N percent, or verified, and require each to "
    "resolve to a run id in the results ledger with a matching commit. Unresolvable claims are "
    "defects filed against their authoring unit. On this estate the dominant failure is recall, not "
    "detection - the evidence usually exists and was never read - so the sweep must attempt "
    "resolution before declaring a claim unbacked.",
    [SPEC + ":11096 (claims of completion not backed by the shared predicate)", RESULTS, TREG,
     "the full program corpus of receipts, reports and status documents"],
    # NOTE: B[16] not "B16" -- bare BNN in an emitted dependency means the BUCKET
    # code (B01..B13, per RES-2/WFA-2 convention), never a lane-B unit alias. The
    # assembly assert rejects any bare BNN outside B01..B13 to keep that separation
    # mechanical rather than a naming convention nobody enforces.
    [C06, B[16]], role(OPUS, "adversarial-refuter"), T_ANA, "local-parallel", 5400,
    "Report claims found, resolved, unresolved and contradicted (a claim whose cited run actually "
    "failed). The contradicted class is the most severe and must be listed first.",
    ["Claim extraction validated against a hand-labelled sample for recall, so the sweep is not "
     "silently missing claim phrasings.",
     "Resolution attempted against the ledger before any unbacked verdict.",
     "Contradiction control: plant a claim citing a failed run and confirm it is caught.",
     "Use-versus-mention: a document DESCRIBING this defect class must not be flagged as making the "
     "claim (reuses C16)."],
    REV_XV, RETRY_NONE, ["overclaim", "detector-failure", "green-not-live"])

C27 = U(
    "Refuse a result that carries no environment record",
    "10",
    "Implementation target: a measurement without its environment cannot be compared to anything "
    "later, and every cross-platform or CRLF surprise in this program traces to comparing results "
    "taken under conditions nobody wrote down. Define the mandatory environment record (OS build, "
    "shell, interpreter version, package versions of the tools that decide, git core.autocrlf, "
    "locale, timezone, concurrency, and the commit SHA) and make a result without it inadmissible "
    "as evidence rather than merely undocumented.",
    ["the environment capture helper", RESULTS, TREG,
     "the CRLF and shell divergences measured on this box"],
    # B[3] (TST-0297, the determinism/environment-capture unit), NOT bare "B03"
    # which would resolve to the deep-research BUCKET. Same collision class as the
    # B16 case above; this one is nastier because B03 IS a valid bucket code, so
    # the id-shape assert accepts it. The intent cross-check below is what catches it.
    [C09, B[3]], role(OPUS, "harness-engineer"), T_BUILD, "local-serialized", 3600,
    "Show one admitted result with a complete record and one rejected result missing a field. "
    "Report the fraction of existing results in the ledger that would be inadmissible under this "
    "rule, since that is the real debt figure.",
    ["Missing-field rejection proven for each mandatory field.",
     "Complete record admitted.",
     "Backfill census: fraction of historical results lacking a record, reported as debt rather "
     "than retroactively accepted.",
     "Cross-shell: the same measurement taken under pwsh7 and Git Bash must produce records that "
     "differ in the shell field and agree elsewhere."],
    REV_WIN, RETRY_NONE, FC_WIN)


# ------------------------------------------------------------------ assembly
KEYS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
        "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
        "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
        "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
        "failure_classification", "owner_approval_required"]
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9",
          "10", "11", "12", "13", "14", "15", "16"}
BUCKETS = {"B%02d" % i for i in range(1, 14)}


def main():
    ids = [u["id"] for u in UNITS]
    idset = set(ids)
    assert len(ids) == len(idset), "duplicate ids"
    assert ids == EXPECTED, ("id sequence drift: %s vs expected %s"
                             % (ids[:2] + ids[-2:], EXPECTED[:2] + EXPECTED[-2:]))
    assert len(ids) == 96, "expected 96 units, built %d" % len(ids)
    for u in UNITS:
        assert list(u.keys()) == KEYS, "field drift on %s" % u["id"]
        assert u["phase"] in PHASES, "bad phase on %s: %s" % (u["id"], u["phase"])
        assert u["execution_substrate"] in SUBSTRATES, "bad substrate on %s" % u["id"]
        assert u["completion_sentinel"] == "SUCCESS:" + u["id"]
        assert u["output_path"].endswith(u["id"] + ".json")
        assert isinstance(u["owner_approval_required"], bool)
        assert u["timeout_seconds"] >= 1800
        assert len(u["tests_required"]) >= 3, "thin tests on %s" % u["id"]
        assert len(u["inputs"]) >= 3, "thin inputs on %s" % u["id"]
        for d in u["dependencies"]:
            ok = (d in idset) or d in BUCKETS or re.fullmatch(r"(CC|IMP|RES|WFA|AUD)-\d{4}", d)
            assert ok, "unresolvable dependency %r on %s" % (d, u["id"])
            # INTENT CROSS-CHECK for the BNN namespace collision. A bare BNN is
            # shape-valid as a bucket code AND is the author's alias for a lane-B
            # unit, so shape alone cannot tell the two apart -- exactly the defect
            # F-B-02 records at program scale. Require a bucket dependency to be
            # corroborated by the unit's own inputs naming that bucket. This caught
            # a real mis-resolution (TST-0352 -> "B03" meaning TST-0297).
            if d in BUCKETS:
                corroborated = any(("bucket " + d) in s for s in u["inputs"])
                assert corroborated, (
                    "dependency %r on %s is shaped like a BUCKET but no input names "
                    "'bucket %s' -- if a lane-B UNIT was meant, use B[n]" % (d, u["id"], d))
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(UNITS, fh, indent=1, ensure_ascii=True)
        fh.write("\n")
    print("wrote %s units to %s" % (len(UNITS), OUT))
    print("first=%s last=%s" % (ids[0], ids[-1]))

    # in-slice near-duplicate self-check (same tokenizer/threshold as _control_dedup.py)
    stop = set(("the a an and or of to in for that this with must be is are on by not it its as "
                "at from into then than which what when where unit units work spec target "
                "question implementation council test tests").split())

    def toks(t):
        return {w for w in re.findall(r"[a-z0-9_.-]{3,}", t.lower()) if w not in stop}

    def jac(a, b):
        ta, tb = toks(a), toks(b)
        return len(ta & tb) / max(1, len(ta | tb))

    def text(u):
        return u["title"] + " " + u["question_or_target"]

    pairs = sorted(((jac(text(a), text(b)), a["id"], b["id"])
                    for a, b in combinations(UNITS, 2)), reverse=True)
    print("top-5 lexical Jaccard pairs (threshold 0.55):")
    for s, x, y in pairs[:5]:
        print("  %.3f  %s ~ %s  %s" % (s, x, y, "FIRES" if s >= 0.55 else "ok"))


if __name__ == "__main__":
    main()
