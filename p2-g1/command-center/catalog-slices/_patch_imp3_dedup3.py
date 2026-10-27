"""Third and final de-dup pass: cede ALL of phase 7 to IMP-2 and deepen phase 7A.

WHY (measured, not inferred): IMP-2.json is 128 units of PURE phase 7 and covers the
typed workflow runtime end to end - Subworkflow/Loop/HumanCheckpoint/DynamicFanOut nodes
(IMP-0129..0132), the typed param model and load-time coercion (0133-0134), routing,
tool permissions, source policy, failure policy, repair loop, retry (0135-0140), cache
key, dry-run, estimator, replay format, resume model, export/import, migration
(0141-0147), the executors (0216-0219, 0227-0229), rate-limit admission and quota-aware
scheduling (0220-0221), per-unit pipeline isolation (0222), worktree provisioning (0223),
the resumable ledger and crash recovery (0224-0225), reducer wiring at every fan-in
(0226), the blueprint conformance harness (0231), the material-distinctness blocking gate
(0232) and the 40-flagship tier (0233). Its own last unit, IMP-0256, reads "Register the
9 council-protocol blueprints as delegating entries owned by Phase 7A" - an explicit
hand-off of phase 7A to this slice.

Token-Jaccard scored my nearest IMP-2 neighbour at 0.222 and reported ZERO overlaps above
0.45. That is the THIRD time in this unit that lexical similarity failed to see a
mechanism-level duplicate (IMP-4 phase 8/9, WFA-2 phase 2B, now IMP-2 phase 7). Recorded
as a finding: lexical near-duplicate detection is not fit for cross-slice catalog dedup.

ACTION: delete all 34 phase-7 units, add 24 genuinely distinct phase-7A units covering
council-runtime surface nobody holds, keep the 2 gap-fill stragglers and the 4 phase-16
units. Final count 118, NOT 128 - I could not find 128 non-duplicate units for this
bucket once three siblings' territory was excluded, and padding to 128 would manufacture
exactly the false coverage the spec forbids at line 10568.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IMP-3.json")
data = json.loads(io.open(SRC, encoding="utf-8").read())
assert len(data) == 128

CORP = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SPEC = CORP + "/_USER-PROMPTS.md"
A_PRED = SPEC + ":10627-10648"
A_P7A = SPEC + ":10915-10946"
A_P2C = SPEC + ":10746-10767"
A_CPROD = SPEC + ":11172-11244"
A_FAIL = SPEC + ":11298-11347"
A_OWNER = SPEC + ":11349-11370"
C_SPEC = CORP + "/11-COUNCIL-SPECIFICATION.md"
C_SCHEMA = CORP + "/11-COUNCIL-SPECIFICATION.schema.json"
C_PROTO = CORP + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
P7A = [A_P7A, A_P2C, A_CPROD, C_SPEC, C_SCHEMA]

R_PIVOT = ("two strikes then pivot (AGENTS.md 4b): after two failures sharing an error "
           "fingerprint, enumerate >=2 alternative designs before a third attempt")
R_NORETRY = ("no automatic retry on schema-invalid or contract-violation - the contract is "
             "frozen by B06; fix the spec via versioned migration or escalate to the owner")
REV_SOLO = ("one independent adversarial reviewer in a fresh context who did not author the "
            "module and starts from the tests, not the author's summary")
REV_OWNER = ("one independent adversarial reviewer plus an explicit owner sign-off block in the "
             "receipt; the reviewer may not grant the owner half")
T_W = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
T_WP = ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "PowerShell"]
M_OPUS = {"vendor": "anthropic", "model": "opus", "role": "implementer"}
M_ARCH = {"vendor": "anthropic", "model": "opus", "role": "runtime-architect"}

# a survivor dependency that pointed into ceded phase-7 territory is repointed at the
# IMP-2 unit that now owns the mechanism; anything unmapped falls back to the bucket code
# B07 and is printed, never silently dropped.
P7_OWNER = {
    "IMP-0257": "IMP-0129", "IMP-0258": "IMP-0129", "IMP-0259": "IMP-0230",
    "IMP-0260": "IMP-0134", "IMP-0261": "IMP-0217", "IMP-0262": "IMP-0219",
    "IMP-0263": "IMP-0226", "IMP-0264": "IMP-0216", "IMP-0265": "IMP-0218",
    "IMP-0266": "IMP-0140", "IMP-0267": "IMP-0139", "IMP-0268": "IMP-0145",
    "IMP-0269": "IMP-0228", "IMP-0270": "IMP-0229", "IMP-0271": "IMP-0227",
    "IMP-0272": "IMP-0143", "IMP-0273": "IMP-0137", "IMP-0274": "IMP-0135",
    "IMP-0275": "IMP-0138", "IMP-0276": "IMP-0195", "IMP-0277": "IMP-0220",
    "IMP-0278": "IMP-0224", "IMP-0279": "IMP-0138", "IMP-0354": "IMP-0231",
    "IMP-0355": "IMP-0230", "IMP-0356": "IMP-0222", "IMP-0357": "IMP-0224",
    "IMP-0358": "IMP-0215", "IMP-0359": "IMP-0147", "IMP-0360": "IMP-0217",
    "IMP-0361": "IMP-0222", "IMP-0362": "IMP-0207", "IMP-0363": "IMP-0223",
    "IMP-0364": "IMP-0223",
}

NEW = []


def add(title, q, inputs, deps, ev, tests, **kw):
    NEW.append(dict(title=title, q=q, inputs=inputs, deps=deps, ev=ev, tests=tests, kw=kw))


add("Hybrid human and agent participation with asynchronous human turns",
    "Implement tools/council/participants/human.py so a council can seat humans alongside agents, "
    "with asynchronous turn windows, reminders, timeout-to-proxy and an explicit human-only mode "
    "(spec 10922). Falsifiable question: when a human seat times out, does the council substitute a "
    "proxy position and record it AS a proxy, or does the human's silence become an unmarked "
    "abstention that shifts the tally?",
    P7A + [A_OWNER],
    ["CL-REGISTRY", "CL-TALLY"],
    "1) a tally recomputation with and without the proxy, both recorded in the artifact; 2) an "
    "artifact scan confirming every proxied turn carries a proxy-origin marker.",
    ["unit: async window, reminder, timeout and proxy paths",
     "negative control: strip the proxy marker and assert a human silence becomes indistinguishable "
     "from a human abstention, proving the marker is load-bearing"],
    sub="local-serialized", tools=T_WP, oa=True, rev=REV_OWNER,
    fc=["owner-blocked", "overclaim", "detector-failure", "uncontrolled-silence"])

add("Secret ballot with a verifiable tally",
    "Implement tools/council/vote/secret.py so votes can be cast without revealing the voter, while "
    "the tally remains independently recomputable from committed ballots. Falsifiable question: can "
    "a third party recompute the published tally from the committed ballots WITHOUT learning who "
    "cast which ballot?",
    P7A + [A_P2C],
    ["CL-TALLY", "CL-ANON"],
    "1) an independent recomputation of the tally from the commitment set; 2) a de-anonymisation "
    "attempt from the same data reporting accuracy against chance.",
    ["unit: commit, reveal and tally verification",
     "security: de-anonymisation attempt must be at chance",
     "negative control: commit ballots in submission order and assert the attack accuracy rises"],
    rev=REV_OWNER)

add("Strategic-voting and strategic-abstention detection",
    "Implement tools/council/antifail/strategic.py detecting ballots inconsistent with a "
    "participant's own stated reasoning, and abstentions timed to change a quorum outcome. "
    "Falsifiable question: does the detector separate a genuine change of mind (reasoning updated "
    "before the vote) from strategic misreporting (reasoning unchanged, ballot inconsistent)?",
    P7A + [SPEC + ":11240"],
    ["CL-TALLY", "CL-ARGGRAPH"],
    "1) a labelled corpus of 50 ballot/reasoning pairs with precision and recall reported "
    "separately; 2) a quorum-sensitivity computation identifying abstentions that were pivotal.",
    ["control: labelled strategic-vs-sincere corpus",
     "negative control: a sincere change of mind must NOT be flagged (false-positive rate "
     "published)"])

add("Lossless transcript compaction for long councils",
    "Implement tools/council/artifacts/compact.py compressing a long transcript for re-injection "
    "while guaranteeing that every claim, objection and dissent survives by id. Falsifiable "
    "question: after compaction, how many claim ids from the full transcript are unreachable from "
    "the compacted form, and is the answer zero or merely small?",
    P7A + [A_CPROD],
    ["CL-STORE", "CL-ARGGRAPH", "CL-DISSENT"],
    "1) a claim-id reachability count full-vs-compacted, required zero loss; 2) a downstream "
    "decision recomputed from the compacted form and compared with the full-form decision.",
    ["invariant: zero claim-id loss across compaction",
     "negative control: drop one dissent during compaction and assert the reachability count FIRES"],
    to=2700)

add("Evidence retrieval under context overflow",
    "Implement tools/council/evidence/retrieve.py so when the deliberation exceeds a participant's "
    "context, evidence is retrieved on demand rather than truncated away. Falsifiable question: on "
    "a council that overflows context, does a participant still cite evidence introduced in early "
    "rounds, measured as the early-round citation rate with and without retrieval?",
    P7A,
    ["CL-CONTEXT", "CL-EVMAP"],
    "1) early-round citation rate with retrieval on and off, same council; 2) a retrieval log "
    "showing which anchors were fetched per turn.",
    ["experiment: early-round citation rate, both configurations",
     "negative control: disable retrieval and assert early-round citations collapse, proving the "
     "measurement is sensitive"],
    to=2700)

add("Cross-council participant memory policy",
    "Implement tools/council/participants/memory.py deciding, per spec, whether a participant "
    "carries knowledge of prior councils, and enforcing that choice. Falsifiable question: does a "
    "memory-enabled participant import a prior council's CONCLUSION as a prior, thereby destroying "
    "the independence the current council assumes?",
    P7A + [A_CPROD],
    ["CL-REGISTRY", "CL-INDEP"],
    "1) first-round brief similarity to the prior council's conclusion, memory on versus off; 2) a "
    "delivered-prompt scan for prior-conclusion text under the memory-off setting, required zero.",
    ["unit: memory scope enforcement per participant",
     "negative control: leak the prior conclusion under memory-off and assert the prompt scan "
     "FIRES"])

add("Decision-lineage export into the program decision log",
    "Implement tools/council/outcomes/lineage_export.py writing each binding council decision into "
    "the program decision log with its inputs, deciding rule, tally, dissents and supersession "
    "links. Falsifiable question: when a later council overturns an earlier decision, does the "
    "earlier entry acquire a supersession marker, or does the log hold two contradictory live "
    "decisions?",
    P7A + [CORP + "/17-DECISION-LOG.md"],
    ["CL-CLAIMS", "CL-PRECEDENT"],
    "1) a contradiction scan over the decision log listing live pairs that disagree; 2) an "
    "overturn fixture producing a supersession marker on the older entry.",
    ["unit: lineage record schema and supersession links",
     "negative control: overturn without marking and assert the contradiction scan FIRES"],
    to=2700)

add("Pre-flight cost estimate with an owner budget gate",
    "Implement tools/council/budget/preflight.py estimating a council's token, wall-clock and "
    "external-call cost before it starts and refusing to launch above the owner's declared ceiling "
    "without approval. Falsifiable question: over 20 recorded councils, how often did the actual "
    "cost exceed the pre-flight estimate, and by how much at the 90th percentile?",
    P7A + [SPEC + ":11355"],
    ["CL-GOVERNOR"],
    "1) an estimate-versus-actual table over 20 recorded councils with the p90 overrun published; "
    "2) a ceiling-breach fixture that must refuse to launch.",
    ["calibration: estimate vs actual, p90 overrun reported",
     "negative control: remove the gate and assert the over-ceiling council launches"],
    to=2700, oa=True, rev=REV_OWNER,
    fc=["owner-blocked", "overclaim", "detector-failure", "dependency-blocked"])

add("Council abort and kill-switch with a safe partial artifact",
    "Implement tools/council/abort.py so the owner can stop a running council at any point and "
    "still receive a truthful partial artifact labelled as aborted. Falsifiable question: is an "
    "aborted council's artifact ever consumable as if it were a completed decision, and does abort "
    "corrupt the append-only event log mid-write?",
    P7A + [A_PRED, A_FAIL],
    ["CL-STORE", "CL-OUTCOMES"],
    "1) a downstream-consumer check refusing the aborted artifact as a decision; 2) an event-log "
    "integrity check after aborting at 20 random points mid-write.",
    ["chaos: abort at 20 random points, log parses every time",
     "negative control: strip the aborted label and assert a consumer accepts it as complete"],
    sub="local-serialized", tools=T_WP)

add("Tie-break policy engine",
    "Implement tools/council/vote/tiebreak.py providing explicit, declared tie-break rules (chair "
    "casting vote, seniority, recorded-seed coin flip, escalation, or no-decision) rather than an "
    "implicit ordering artifact. Falsifiable question: on an exact tie, is the outcome reproducible "
    "from the recorded rule and seed, and is 'no-decision' actually reachable rather than nominal?",
    P7A,
    ["CL-TALLY", "CL-OUTCOMES"],
    "1) a tie fixture resolved twice from the same recorded seed with identical results; 2) a "
    "policy census proving each rule is reachable in at least one test.",
    ["unit: every tie-break rule exercised",
     "negative control: remove the seed record and assert reproducibility FAILS"],
    to=1800)

add("Compound-question decomposition into subcouncils",
    "Implement tools/council/decompose.py splitting a compound question into independently "
    "deliberable sub-questions and recomposing the answers. Falsifiable question: does recomposition "
    "ever produce an answer that no sub-council supports, and are cross-sub-question dependencies "
    "detected before splitting?",
    P7A,
    ["CL-NESTED", "CL-ARGGRAPH"],
    "1) a support check tracing the composed answer to sub-answers; 2) a dependency-detection pass "
    "over the split, listing sub-questions whose answers interact.",
    ["unit: split and recompose on 8 compound fixtures",
     "negative control: split a genuinely coupled question and assert the dependency pass FIRES"],
    to=2700, model=M_ARCH)

add("Charter completeness check on the final answer",
    "Implement tools/council/outcomes/completeness.py asserting the final artifact contains every "
    "output the charter declared required (positions, idea ledger, argument graph, votes, dissent, "
    "unknowns, experiments, recommendation, calibration). Falsifiable question: which required "
    "outputs are missing most often across recorded councils, and can the check be satisfied by an "
    "empty section that merely exists?",
    P7A + [SPEC + ":10767"],
    ["CL-STORE", "CL-DISSENT"],
    "1) a per-output presence and non-vacuity table across 20 recorded councils; 2) a vacuous "
    "section fixture that must FAIL.",
    ["census: required-output presence per council, missing ones listed",
     "negative control: an empty-but-present section must FAIL the non-vacuity test"],
    to=1800)

add("Charter validation: measurable success criteria",
    "Implement tools/council/charter.py rejecting a charter whose success criteria cannot be "
    "evaluated by any runtime metric. Falsifiable question: for each charter field, is there a "
    "concrete evaluator, or does the council launch with an aspiration it can never satisfy - the "
    "same defect class as a stopping condition that is unsatisfiable by construction?",
    P7A + [SPEC + ":10921"],
    ["CL-SPEC", "CL-STOPEXPR"],
    "1) a criterion-to-evaluator binding census with unbound criteria listed; 2) a launch attempt "
    "with an unbindable criterion, expected refused.",
    ["unit: binding census over all charter fields",
     "negative control: an unsatisfiable-by-construction criterion must be refused at launch, not "
     "discovered at stop time"],
    to=1800, retry=R_NORETRY)

add("Risk-class routing to stricter protocol and quorum floors",
    "Implement tools/council/risk.py mapping a declared risk class onto minimum protocol strength, "
    "quorum, evidence standard and reviewer count. Falsifiable question: can a high-risk decision "
    "be taken under a low-risk configuration by declaring the risk class late, and is the class "
    "immutable once deliberation starts?",
    P7A + [C_PROTO],
    ["CL-SPEC", "CL-TALLY"],
    "1) a mutation attempt changing the risk class mid-run, expected refused with an event; 2) a "
    "floor-enforcement matrix across the risk classes.",
    ["unit: floors enforced per risk class",
     "negative control: allow late reclassification and assert the immutability test FAILS"],
    to=1800)

add("Preset inheritance and templating",
    "Implement tools/council/presets/inherit.py so a preset can extend another with declared "
    "overrides, without copy-paste divergence across the 72 measured presets. Falsifiable question: "
    "when a base preset changes, do all descendants inherit the change, and can inheritance "
    "silently weaken a child's anti-sycophancy or evidence settings?",
    P7A + [C_PROTO],
    ["CL-PRESETS"],
    "1) a propagation test mutating a base and re-resolving every descendant; 2) a weakening check "
    "comparing each resolved child's safety-relevant fields against its base.",
    ["unit: single and multi-level inheritance resolution",
     "negative control: weaken a child's evidence standard via inheritance and assert the check "
     "FIRES"],
    to=1800)

add("Role-template registry with custom-role authoring",
    "Implement tools/council/roles/templates.py providing reusable role templates plus a path to "
    "author a custom role that still satisfies the mandate contract (spec 11177). Falsifiable "
    "question: can a custom role be authored that grants itself rights no template allows, and is "
    "template drift from the mandate schema detected?",
    P7A + [SPEC + ":11177"],
    ["CL-MANDATE"],
    "1) a schema-conformance pass over every template and custom role; 2) a rights-escalation "
    "attempt through a custom role, expected refused.",
    ["unit: template resolution and custom-role validation",
     "negative control: author a rights-escalating role and assert refusal"],
    to=1800)

add("Recusal workflow with quorum recomputation",
    "Implement tools/council/integrity/recusal.py handling declare-recuse-replace, recomputing "
    "quorum and preserving the recused participant's pre-recusal contributions. Falsifiable "
    "question: after a recusal, does any vote cast by the recused participant still count toward "
    "the decision?",
    P7A,
    ["CL-COI", "CL-TALLY", "CL-REPLACE"],
    "1) a tally recomputation excluding recused ballots, compared against the recorded tally; 2) an "
    "artifact census proving pre-recusal contributions were retained, not deleted.",
    ["unit: recusal lifecycle and quorum recomputation",
     "negative control: leave a recused ballot in the tally and assert the recomputation FIRES"],
    to=1800)

add("Participant preparation and research-requirement enforcement",
    "Implement tools/council/prep.py enforcing the spec's preparation/research requirements before "
    "a participant may speak, and verifying the preparation actually happened. Falsifiable "
    "question: is preparation verified by an artifact (sources read, notes produced) or merely by "
    "the participant asserting it did the reading?",
    P7A + [SPEC + ":10754"],
    ["CL-KERNEL", "CL-EVMAP"],
    "1) a preparation artifact per participant with resolvable source anchors; 2) a tool-call log "
    "corroborating that the sources were actually fetched.",
    ["unit: prep gate blocks an unprepared participant",
     "negative control: assert preparation without fetching and assert the tool-call corroboration "
     "FIRES"],
    to=2700)

add("Cross-examination pairing scheduler with bounded depth",
    "Implement tools/council/protocol/crossexam.py scheduling who examines whom, bounding depth and "
    "guaranteeing every substantive position is examined at least once. Falsifiable question: which "
    "positions went unexamined in recorded councils, and does the scheduler favour examining weak "
    "positions while leaving the dominant one unchallenged?",
    P7A + [A_P2C],
    ["CL-SOCRATIC", "CL-ORDER"],
    "1) an examination-coverage matrix per position; 2) a correlation between position popularity "
    "and examination count, reported with its sign.",
    ["unit: pairing schedule completeness",
     "measurement: popularity-versus-examination correlation published",
     "negative control: a deliberately unexamined position must be reported as a coverage gap"],
    to=1800)

add("Council re-run answer-stability measurement",
    "Implement tools/council/stability.py re-running the same council specification N times and "
    "reporting how often the decision changes. Falsifiable question: what is the answer-stability "
    "rate for each preset, and is any preset producing a different decision on a majority of "
    "re-runs while still reporting high confidence?",
    P7A + [C_PROTO],
    ["CL-DETERMINISM", "CL-CALIB"],
    "1) decision-change rate over N>=10 re-runs per preset; 2) the reported confidence compared "
    "against the observed stability, with disagreements listed.",
    ["measurement: per-preset stability rate published, including unflattering ones",
     "negative control: a deterministic fixture council must show 100 percent stability, proving "
     "the harness is not injecting noise itself"],
    to=5400, sub="cloud-batch")

add("Evidence-standard tier enforcement per preset",
    "Implement tools/council/evidence/standard.py enforcing a preset's declared evidence tier "
    "(for example executable-proof-only, peer-reviewed-only, any-cited) at the point a claim is "
    "admitted. Falsifiable question: does a claim below the declared tier ever reach a binding "
    "decision, and is tier classification done on the source's type rather than on the claimant's "
    "assertion about it?",
    P7A + [A_CPROD],
    ["CL-EVGATE", "CL-EVMAP"],
    "1) a tier-classification pass over every admitted claim with the classifier's input field "
    "named; 2) an under-tier claim fixture that must be refused.",
    ["unit: each tier enforced on a labelled claim set",
     "negative control: classify by the claimant's assertion instead of the source type and assert "
     "the labelled set shows misclassification"])

add("Council-initiated owner question packet",
    "Implement tools/council/owner_ask.py so a council that hits a genuinely owner-controlled "
    "decision emits ONE foundation-level question with a recommendation, the strongest tradeoff and "
    "the default if unanswered, then suspends (spec 11364-11370). Falsifiable question: does the "
    "council ever ask about something already settled in the decision log, and does it ask more "
    "than one question at a time?",
    P7A + [A_OWNER, CORP + "/17-DECISION-LOG.md"],
    ["CL-PRECEDENT", "CL-ABORT"],
    "1) a decision-log lookup proving the question is unanswered before it is emitted; 2) a "
    "one-question-at-a-time assertion over the emitted packet.",
    ["unit: packet schema requires recommendation, tradeoff and default",
     "control: a question already answered in the log must be suppressed",
     "negative control: emit two questions and assert the packet check FAILS"],
    sub="local-serialized", tools=T_WP, oa=True, rev=REV_OWNER,
    fc=["owner-blocked", "overclaim", "stale-premise", "detector-failure"])

add("Participant-count sensitivity analysis",
    "Implement tools/council/sensitivity.py re-running a decision at several seat counts to test "
    "whether the answer depends on N rather than on the evidence. Falsifiable question: at which "
    "seat count does the decision stabilise, and is the configured default above or below that "
    "point?",
    P7A + [A_P2C],
    ["CL-ELASTIC", "CL-STABILITY"],
    "1) a decision-versus-N curve per question with the stabilisation point identified; 2) the "
    "configured default compared against the measured stabilisation point.",
    ["measurement: decision-versus-N curve published",
     "negative control: an evidence-decisive question should stabilise at a low N; if it does not, "
     "report that the protocol is N-sensitive rather than tuning N until it looks stable"],
    to=5400, sub="cloud-batch")

add("Divergence-to-convergence phase transition gate",
    "Implement tools/council/phases.py making the transition from divergence to convergence an "
    "explicit, gated event that cannot occur until the divergence quotas are met. Falsifiable "
    "question: in recorded councils, how often did convergence begin before the divergence quota "
    "was satisfied, and is the gate enforcing or merely reporting?",
    P7A + [A_CPROD],
    ["CL-TARGETS", "CL-PREMATURE"],
    "1) a transition-event log with the quota values at transition time; 2) an attempted early "
    "transition that must be refused rather than warned about.",
    ["unit: transition blocked until quotas met",
     "negative control: downgrade the gate to a warning and assert an early transition occurs, "
     "proving enforcement is what carries the behaviour"],
    to=1800)

# ---------------------------------------------------------------------------
# stable symbolic anchors -> current ids, so new units can reference council
# units that are about to be renumbered
ANCH = {
    "CL-SPEC": "CouncilSpec JSON Schema", "CL-KERNEL": "Council runtime kernel",
    "CL-REGISTRY": "Participant registry", "CL-ANON": "Anonymity layer",
    "CL-COI": "Conflict-of-interest declaration", "CL-CONTEXT": "Per-seat context assembly",
    "CL-MANDATE": "Role mandate model", "CL-ORDER": "Speaking-order strategy engine",
    "CL-NESTED": "Nested subcouncil spawn", "CL-SOCRATIC": "Socratic cross-examination",
    "CL-GOVERNOR": "Budget governor", "CL-TARGETS": "Target evaluator",
    "CL-TALLY": "Majority, supermajority", "CL-EVGATE": "Evidence gate overriding popularity",
    "CL-STOPEXPR": "Boolean stopping-expression", "CL-OUTCOMES": "Outcome kinds",
    "CL-DISSENT": "Dissent and minority-report", "CL-ARGGRAPH": "Argument graph builder",
    "CL-EVMAP": "Evidence map, citation graph", "CL-STORE": "Transcript and event store",
    "CL-PREMATURE": "Premature-convergence detector", "CL-INDEP": "Behavioural independence audit",
    "CL-PRESETS": "Preset store, loader", "CL-CALIB": "Post-run calibration report",
    "CL-PRECEDENT": "Precedent retrieval", "CL-CLAIMS": "Council-claim registration",
    "CL-DETERMINISM": "Live-run determinism", "CL-REPLACE": "Participant replacement",
    "CL-ELASTIC": "Elastic scaling",
}
# anchors that point at units created in THIS batch, resolved after ids are assigned
ANCH_NEW = {"CL-ABORT": "Council abort and kill-switch",
            "CL-STABILITY": "Council re-run answer-stability"}
ANCH.update(ANCH_NEW)

FAM7A = dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
             retry=R_PIVOT, prof="council-runtime-module",
             fc=["schema-invalid", "overclaim", "detector-failure", "dependency-blocked"])

built = []
for n in NEW:
    kw = n["kw"]
    built.append({
        "id": None, "title": n["title"], "phase": "7A", "question_or_target": n["q"],
        "inputs": n["inputs"], "dependencies": list(n["deps"]),
        "assigned_model_vendor_role": kw.get("model", FAM7A["model"]),
        "tool_permissions": kw.get("tools", FAM7A["tools"]),
        "execution_substrate": kw.get("sub", FAM7A["sub"]),
        "timeout_seconds": kw.get("to", FAM7A["to"]),
        "output_path": None,
        "output_schema": ("command-center/schema/receipt.schema.json profile=%s "
                          "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
                          "test_ids[], negative_control_ids[], reviewer_verdict, "
                          "residual_unknowns[])" % kw.get("prof", FAM7A["prof"])),
        "evidence_requirement": n["ev"], "tests_required": n["tests"],
        "reviewer_requirement": kw.get("rev", FAM7A["rev"]),
        "completion_sentinel": None, "retry_policy": kw.get("retry", FAM7A["retry"]),
        "failure_classification": kw.get("fc", FAM7A["fc"]),
        "owner_approval_required": kw.get("oa", False),
    })

keep7a = [u for u in data if u["phase"] == "7A"]
keep89 = [u for u in data if u["phase"] in ("8", "9")]
keep16 = [u for u in data if u["phase"] == "16"]
dropped = [u["id"] for u in data if u["phase"] == "7"]
assert len(keep7a) == 88 and len(keep89) == 2 and len(keep16) == 4 and len(dropped) == 34

final = keep7a + built + keep89 + keep16
unmapped = []
oldnew = {}
for i, u in enumerate(final):
    u["_new"] = "IMP-%04d" % (257 + i)
    if u["id"]:
        oldnew[u["id"]] = u["_new"]

# resolve symbolic anchors against the FINAL id assignment (covers both pre-existing
# council units and units created in this same batch)
anchor_id = {}
for k, frag in ANCH.items():
    for u in final:
        if u["title"].startswith(frag):
            anchor_id[k] = u["_new"]
            break
missing = sorted(set(ANCH) - set(anchor_id))
assert not missing, "unresolved anchors: %s" % missing

for u in final:
    nd = []
    for d in u["dependencies"]:
        if d in anchor_id:
            nd.append(anchor_id[d])
        elif d in oldnew:
            nd.append(oldnew[d])
        elif d in P7_OWNER:
            nd.append(P7_OWNER[d])
        elif d.startswith("IMP-") and d in set(dropped):
            unmapped.append(d)
            nd.append("B07")
        else:
            nd.append(d)
    seen = set()
    u["dependencies"] = [x for x in nd if not (x in seen or seen.add(x))]
for u in final:
    u["id"] = u.pop("_new")
    u["output_path"] = "command-center/receipts/%s.json" % u["id"]
    u["completion_sentinel"] = "SUCCESS:%s" % u["id"]

with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(final, fh, indent=2, ensure_ascii=True)
    fh.write("\n")
ph = {}
for u in final:
    ph[u["phase"]] = ph.get(u["phase"], 0) + 1
print("dropped_phase7=%d added_7A=%d n=%d phases=%s first=%s last=%s unmapped_p7_deps=%s"
      % (len(dropped), len(built), len(final), sorted(ph.items()),
         final[0]["id"], final[-1]["id"], sorted(set(unmapped))))
