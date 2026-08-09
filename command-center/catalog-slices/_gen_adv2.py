#!/usr/bin/env python3
"""Generate ADV-2.json - bucket B10 (adversarial / security / privacy / legal /
stale-premise / groupthink), slice 2 of 2, units 129-144.

DESIGN NOTE (read before editing):

The 128 units of ADV-1 are not on disk yet, and the 12 sibling slices that ARE on
disk already carry the *design*, *implementation*, *research* and *test* of nearly
every obvious adversarial target (marketplace typosquat -> ARC-0020/TST-0218,
canary secret scan -> TST-0206, stored-green decay -> TST-0235, benchmark gaming ->
TST-0110/WFA-0116, council anti-failure controls -> CNL-0059/0086/0087/0097/0100,
licence compatibility -> RES-0135/IMP-0157, prompt injection -> WFA-0121/IMP-0480).

So this slice is NOT organised by refuter CLASS (that would duplicate both ADV-1
and the other buckets). It is organised by adversarial MECHANISM - the technique
the refuter uses - and every unit uses a DIFFERENT one:

  C  refuter-corps calibration measurement          -> ADV-0129
  D  novelty accounting / re-assertion subtraction   -> ADV-0130
  H  cross-artifact contradiction mining             -> ADV-0131
  S  consensus-vs-executable-test divergence         -> ADV-0132
  E  refuted-premise blast-radius closure            -> ADV-0133
  O  supersession-chain / temporal-validity walk     -> ADV-0134
  A  evasion synthesis against a behavioural gate    -> ADV-0135
  F  runtime independence attestation                -> ADV-0136
  P  program-scale shared-premise correlation        -> ADV-0137
  I  authority provenance (decision laundering)      -> ADV-0138
  U  build-environment supply chain                  -> ADV-0139
  V  owner-gate bypass path enumeration              -> ADV-0140
  B  detector coverage algebra (uncovered domain)    -> ADV-0141
  M  re-identification attack on redacted output     -> ADV-0142
  N  third-party CONTENT redistribution legality     -> ADV-0143
  T  compliance-trace completeness on a policy gate  -> ADV-0144

A and B are deliberately kept apart: A synthesises a hostile input that PASSES a
gate; B computes the input domain the gate never sees at all. A canary cannot find
a B-class hole and a coverage census cannot find an A-class one.
"""
from __future__ import annotations

import json
import pathlib

OUT = pathlib.Path(__file__).with_name("ADV-2.json")

SENT = ("SUCCESS:{id} emitted only when the artifact at output_path exists, is non-empty, "
        "parses against output_schema, and {post}. Any other terminal state is "
        "FAILED:{id} <classification> with the diagnostic tail attached.")

UNITS: list[dict] = []

# A sibling unit id is a DECAYING reference. Measured while authoring this slice on
# 2026-08-09: RES-2.json was renumbered mid-flight and four ids silently retargeted
# to semantically unrelated units (the Tor/onion legal-gate unit read as RES-0154 at
# one moment and RES-0138 minutes later; RES-0154 then meant "refuter role design").
# A dangling id is loud; a retarget is silent, which is strictly worse. So every
# sibling id used as a machine-read dependency carries its expected title here, and
# _resolve_adv2_refs.py turns a retarget into a hard failure instead of a surprise.
ANCHORS = {
    "ARC-0062": "A9 (maximal hybrid): Prove no hybrid entry path bypasses the single permission evaluator",
    "AUD-0065": "Event-ledger and basic-memory durable-state inventory",
    "AUD-0075": "Stale-premise sweep over pinned ground-truth facts with mechanically different re-probes",
    "AUD-0078": "Secret and PII scan of the program corpus and command-center artifacts",
    "AUD-0080": "Permission-surface audit: allow-lists and hook bypass paths",
    "CC-0018": "Rank claims by independent evidence, and prove repetition cannot raise a rank",
    "CNL-0021": "Participant replacement and duplicate-independence detection",
    "IMP-0479": "Telemetry and privacy contract implementation with an executable redaction proof",
    "RES-0061": "Characterize the prompt-payload supply-chain risk where a config file IS an instruction",
    "RES-0084": "Solve the 100-unique-idea counting problem without trivial-variant gaming",
    "RES-0119": "Conduct the lawful public-Tor sweep under the safety policy, or prove it adds nothing",
    "RES-0124": "Determine the privacy and data-protection surface if this toolchain is ever published",
    "RES-0125": "Determine the provenance and licensing obligations for AI-generated blueprint content",
    "RES-0133": "Secret-scanner coverage gap on markdown, prompt and transcript artifacts",
    "RES-0138": "Lawful public-Tor/onion research stage: sandbox design, logging contract and legal gate",
    "RES-0154": "Refuter role design: incentives, success metric, and measured yield versus finder agents",
    "TST-0009": "Evidence-anchor resolvability validator: every anchor must actually resolve",
    "TST-0015": "Estate-specific mutation-operator library",
    "TST-0213": "No code path in the toolchain can revoke, rotate or unset a credential",
    "WFA-0077": "Enumerate exactly which decisions in this bucket require owner approval and which are already settled",
    "WFA-0079": "Emit provenance and licence graph v2 with full referential closure and fetched licences",
}


def u(**kw):
    kw["completion_sentinel"] = SENT.format(id=kw["id"], post=kw.pop("post"))
    anchors = {}
    for dep in kw["dependencies"]:
        if dep in ANCHORS:
            anchors[dep] = ANCHORS[dep]
        elif not (dep.startswith("B") and dep[1:].isdigit()) and not dep.startswith("ADV-"):
            raise SystemExit(f"{kw['id']}: dependency {dep} has no title anchor")
    kw["dependency_anchors"] = anchors
    kw["bucket"] = "B10"
    kw["slice"] = "ADV-2of2"
    UNITS.append(kw)


# ---------------------------------------------------------------- 129 (C)
u(
    id="ADV-0129",
    title="Refuter-corps calibration: planted-defect recall and evidence-stripped verdict polarity",
    phase="12",
    question_or_target=(
        "What are this program's refuter corps' measured recall on planted defects of known "
        "severity, and its measured default-verdict polarity when the evidence is insufficient - "
        "and does either number justify treating a refuter PASS as evidence? Spec 11062 requires "
        "refuters to default to REFUTED on insufficient evidence; the estate has measured the "
        "opposite tendency (of 225 audit findings actually checked, 42 percent were REFUTED while "
        "the producing agents self-rated confidence high on 89 percent)."
    ),
    inputs=[
        "the refutation queue produced by the rest of bucket B10 (ADV-1 slice, units 1-128)",
        "RES-0154 refuter role design: incentives, success metric, measured yield versus finder agents",
        "TST-0015 estate-specific mutation-operator library (source of the planted defects)",
        "CLAIM-REGISTRY.json entries already adjudicated, for the evidence-stripped arm",
        "spec _USER-PROMPTS.md:11062 (refuters default to REFUTED) and :11064 (strongest remaining caveat)",
    ],
    dependencies=["B10", "RES-0154", "TST-0015", "ADV-0130"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "calibration-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="cloud-batch",
    timeout_seconds=7200,
    output_path="command-center/adversarial/ADV-0129-refuter-calibration.json",
    output_schema="command-center/schema/calibration-report.schema.json",
    evidence_requirement=(
        "Two arms, both required. ARM 1 (recall): inject at least 24 defects drawn from the "
        "TST-0015 operator library into the refutation input stream, blind to the refuters, "
        "stratified P0/P1/P2; report per-refuter recall with a Wilson interval, not a point "
        "estimate. ARM 2 (polarity): re-serve at least 24 ALREADY-adjudicated claims with their "
        "evidence anchors stripped and record the verdict; the correct answer is REFUTED or "
        "NOT-CHECKED, and any PASS is a polarity violation. Record every refuter's self-rated "
        "confidence alongside its verdict and compute a Brier score per refuter. Report error "
        "DIRECTION separately from accuracy - a corps that is 86 percent accurate with 100 "
        "percent of its errors pointing at false-pass is worse than a less accurate balanced one."
    ),
    tests_required=[
        "negative control: an evidence-COMPLETE copy of each ARM 2 claim must come back CONFIRMED; "
        "if the stripped and complete copies get the same verdict the harness is measuring nothing",
        "detector control: one planted defect must be a KNOWN-DETECTED class (a literal hardcoded "
        "token) and must be caught by every refuter; a corps that misses it invalidates the run "
        "rather than scoring zero recall",
        "confounder control: planted defects must be indistinguishable from real ones in formatting, "
        "path depth and author metadata - prove it by having one reviewer try to identify the plants "
        "from the stream alone and scoring them at chance",
    ],
    reviewer_requirement=(
        "one reviewer with the plant list and the random seed who re-draws the stratified sample and "
        "confirms it is byte-identical, plus one reviewer who independently re-computes the Wilson "
        "intervals and Brier scores from the raw verdict table"
    ),
    post=("both arms are recorded with their raw verdict tables, the Wilson intervals and Brier "
          "scores are reproducible from those tables, and the error-direction split is reported "
          "separately from the accuracy figure"),
    retry_policy=(
        "no blind retry. A re-run is permitted only as flake measurement and EVERY run's outcome is "
        "recorded; a corps that scores well on run 3 of 3 is reported as 1/3, never as the result"
    ),
    failure_classification=["false-pass", "evidence-theatre", "calibration-drift", "detector-failure"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 130 (D)
u(
    id="ADV-0130",
    title="Novelty accounting: subtract already-declared structure before a refutation is credited",
    phase="12",
    question_or_target=(
        "For every refutation filed by bucket B10, is the asserted edge (claim -> contradicting "
        "claim, unit -> unstated dependency, risk -> uncovered artifact) ALREADY present in "
        "DEPENDENCY-GRAPH.json, PHASE-GRAPH.json, CLAIM-REGISTRY.json, RISK-REGISTER.md or "
        "UNKNOWNS-REGISTER.md - i.e. is it a re-assertion of declared structure rather than a "
        "finding? Measured on this estate: 29 raw adversarial edges collapsed to 7 novel ones "
        "once declared structure was subtracted."
    ),
    inputs=[
        "every refutation record emitted by bucket B10",
        "DEPENDENCY-GRAPH.json and PHASE-GRAPH.json (the declared edge set)",
        "CLAIM-REGISTRY.json duplicate-of / support / contradiction edges",
        "RISK-REGISTER.md and UNKNOWNS-REGISTER.md",
        "rules/common/fan-out-contract.md section B (subtract declared structure first)",
    ],
    dependencies=["B10", "B01", "CC-0018"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "graph-adjudicator"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="local-parallel",
    timeout_seconds=2700,
    output_path="command-center/adversarial/ADV-0130-novelty-accounting.json",
    output_schema="command-center/schema/novelty-ledger.schema.json",
    evidence_requirement=(
        "Mechanical set arithmetic, not judgement: normalise every refutation to a typed triple "
        "(subject_id, relation, object_id), normalise the declared graphs to the same triple space, "
        "and emit NOVEL = filed MINUS declared with the exact matching rule written down. Report "
        "|filed|, |declared|, |NOVEL| and the collapse ratio. Any triple that cannot be normalised "
        "is reported as UNNORMALISABLE with its raw text - never silently counted as novel."
    ),
    tests_required=[
        "planted re-assertion: inject 5 refutations that restate an edge already in "
        "DEPENDENCY-GRAPH.json verbatim; all 5 must land in the SUBTRACTED set",
        "planted novelty: inject 5 refutations asserting an edge absent from every declared graph; "
        "all 5 must survive into NOVEL. A run where either planted set is misclassified is a "
        "detector failure and the collapse ratio may not be cited",
        "use-vs-mention control: a refutation whose PROSE quotes an existing edge while ASSERTING a "
        "different one must survive as novel - matching on payload text instead of the typed triple "
        "is the failure mode this test exists to catch",
    ],
    reviewer_requirement=(
        "one reviewer who re-implements the set subtraction from the typed triples in a different "
        "language or tool and must reach the identical NOVEL set; a reviewer who only re-reads this "
        "unit's output has verified nothing"
    ),
    post=("the NOVEL set is reproducible by an independent re-implementation of the subtraction and "
          "both planted control sets classify correctly"),
    retry_policy=(
        "two strikes then pivot (AGENTS.md 4b): after the second failure carrying the same "
        "normalisation error fingerprint, enumerate at least 2 mechanically different triple "
        "extractors before any third attempt"
    ),
    failure_classification=["re-assertion-inflation", "use-vs-mention", "detector-failure"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 131 (H)
u(
    id="ADV-0131",
    title="Cross-artifact contradiction mining: two program artifacts that cannot both be true",
    phase="12",
    question_or_target=(
        "Which PAIRS of program artifacts assert mutually exclusive facts about the same subject - "
        "for example a decision log stating a defect is open in the present tense while the fixed "
        "file proves it closed, a charter floor stated as N while the audit measured M, or a "
        "manifest listing an artifact the filesystem does not hold? Enumerate every contradicting "
        "pair with both anchors, and rank by whether a downstream unit consumes the wrong side."
    ),
    inputs=[
        "the full command-center tree (13 documents plus events/, sources/, catalog-slices/)",
        "every bucket artifact registered in ARTIFACT-MANIFEST.json",
        "OPTION-ID-RESOLUTION.json and PROMPT-ONE-FLOOR-AUDIT.json (two known reconciliation surfaces)",
        "rules/common/single-signal-verification.md (a self-contradicting output is a detector "
        "failure, not a finding)",
    ],
    dependencies=["B01", "B02", "ADV-0133"],
    assigned_model_vendor_role={"model": "gpt-5-codex", "vendor": "openai", "role": "contradiction-miner"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "mcp__codex__codex"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0131-cross-artifact-contradictions.json",
    output_schema="command-center/schema/contradiction-pairs.schema.json",
    evidence_requirement=(
        "Every reported contradiction carries BOTH file:line anchors verbatim plus the extracted "
        "proposition from each side and the reason they are exclusive (numeric mismatch, "
        "present-tense-versus-resolved, existence-versus-absence, or scope collision). Numeric and "
        "existence contradictions are settled MECHANICALLY (parse the numbers, stat the path) and "
        "never by reading; only tense and scope collisions are adjudicated by an agent, and those "
        "are tagged ADJUDICATED so the mechanical subset can be trusted on its own. Cross-vendor "
        "dispatch rule: pass the prompt by FILE with --ignore-user-config, block on the call, and "
        "require the output-last-message file to exist and parse before reporting SUCCESS."
    ),
    tests_required=[
        "seeded pair: plant one numeric contradiction and one existence contradiction in a scratch "
        "copy of the tree; both must be found with correct anchors",
        "false-positive control: plant one pair that LOOKS contradictory but is scoped differently "
        "(the same count over two different denominators, each stating its denominator); reporting "
        "it is a false positive and caps this unit at PARTIAL",
        "the known live instance is the acceptance case: 17-DECISION-LOG.md:175 states the M-NN "
        "option-id collision in the present tense while 13-ARCHITECTURE-CANDIDATES.md holds zero "
        "bare M-NN tokens. A run that does not surface this pair has a broken detector",
    ],
    reviewer_requirement=(
        "one fresh-context reviewer from the OTHER vendor than the executor who is given only the "
        "anchor pairs, with the extracted propositions withheld, and must re-derive the exclusivity "
        "before seeing this unit's reasoning"
    ),
    post=("the known live 17-DECISION-LOG.md:175 instance appears in the output, the false-positive "
          "control is absent, and every pair carries two verbatim file:line anchors"),
    retry_policy=(
        "one retry only when the failure classifies as environment-transient (codex arg-limit, "
        "severed stream, runner eviction); on win-arg-limit retry ONCE with --ignore-user-config and "
        "a prompt file. A logic or evidence failure is never retried, it is filed"
    ),
    failure_classification=["contradiction-unresolved", "stale-premise", "severed-stream", "false-positive"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 132 (S)
u(
    id="ADV-0132",
    title="Consensus-versus-executable-test divergence rate on the program's own agreed conclusions",
    phase="12",
    question_or_target=(
        "Take a stratified sample of conclusions this program treats as SETTLED BY AGREEMENT (no "
        "executable test attached) and settle each one with an executable test written by an agent "
        "who does not see the agreed answer. What fraction of agreed conclusions the test refutes "
        "is the program's agreement-is-not-evidence rate, and it is the number that says whether "
        "any un-tested consensus in this program may be cited. Spec 11244 and 11198: agreement is "
        "not proof; evidence gates outrank popularity."
    ),
    inputs=[
        "CLAIM-REGISTRY.json filtered to verification_status in {agreed, consensus, not-tested}",
        "COMPLETION-GATES.json (the shared completion predicate, to classify what counts as settled)",
        "TEST-REGISTRY.json (to exclude conclusions that already carry an executable settling test)",
        "spec _USER-PROMPTS.md:11198 and :11244",
    ],
    dependencies=["B01", "B09", "TST-0009"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "adversarial-refuter"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    execution_substrate="worktree-isolated",
    timeout_seconds=7200,
    output_path="command-center/adversarial/ADV-0132-consensus-vs-test-divergence.json",
    output_schema="command-center/schema/divergence-report.schema.json",
    evidence_requirement=(
        "Blind construction: the test author is given the QUESTION and the raw inputs, never the "
        "agreed answer, and files a predicted outcome BEFORE running. Report, per sampled "
        "conclusion, the agreed answer, the pre-registered prediction, the executed result and the "
        "verdict (AGREEMENT-HELD / AGREEMENT-REFUTED / TEST-INCONCLUSIVE). The headline number is "
        "the refuted fraction with its interval and the sampling frame stated; an inconclusive test "
        "counts as inconclusive, never as held."
    ),
    tests_required=[
        "the sample must include at least 3 conclusions the program is MOST confident in - a "
        "divergence study drawn only from weak claims measures the sampling, not the program",
        "negative control: include 2 conclusions that already have a passing executable test; the "
        "blind author's test must agree with the existing one, otherwise the test-authoring arm "
        "itself is unreliable and no divergence figure may be reported",
        "mutation control: for one sampled conclusion, invert the underlying fixture and confirm "
        "the blind test goes red - a test that is green in both states settles nothing",
    ],
    reviewer_requirement=(
        "two independent reviewers who do not see each other's verdict until both are filed: one "
        "re-runs the blind tests from the recorded fixtures, one audits the pre-registration "
        "timestamps to prove the prediction preceded the run. A disagreement escalates to raw-source "
        "adjudication, never to a majority vote"
    ),
    post=("every sampled conclusion carries a pre-registered prediction whose timestamp precedes the "
          "test run, the negative control agrees with the pre-existing tests, and the mutation "
          "control went red"),
    retry_policy=(
        "zero retries on the verdict. The first blind observation IS the result; a later run that "
        "disagrees is recorded as a DISCREPANCY (spec 11039), never used to overwrite the first"
    ),
    failure_classification=["evidence-free-consensus", "overclaim", "test-inconclusive", "sampling-bias"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 133 (E)
u(
    id="ADV-0133",
    title="Refuted-premise blast radius: force re-derivation of everything that inherited a dead premise",
    phase="12",
    question_or_target=(
        "For each premise this program has REFUTED, what is the complete set of artifacts, work "
        "units, decisions, dependency edges and downstream conclusions that were authored while it "
        "was believed - and has each one been re-derived or explicitly confirmed unaffected? A "
        "refuted premise that is deleted from its source document but left standing in nine "
        "downstream artifacts has not been remediated (AGENTS.md 9b applied to premises rather "
        "than to code)."
    ),
    inputs=[
        "AUD-0075 stale-premise sweep output (the list of premises and their re-probe verdicts)",
        "ADV-0134 supersession-chain output (premises retired by a later record)",
        "the full artifact set in ARTIFACT-MANIFEST.json with authorship timestamps",
        "events/EVENTS.jsonl (when each premise was first asserted and when it was refuted)",
        "the pinned program brief, whose F-B-02 entry is a live example of an inherited dead premise",
    ],
    dependencies=["AUD-0075", "ADV-0134", "B02"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "stale-premise-refuter"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "mcp__basic-memory__search_notes"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0133-premise-blast-radius.json",
    output_schema="command-center/schema/blast-radius.schema.json",
    evidence_requirement=(
        "Per refuted premise emit a closure set built from three joins, all three required: (1) "
        "textual - every artifact containing the premise's canonical token or a stated paraphrase; "
        "(2) temporal - every artifact authored between first-assertion and refutation timestamps "
        "in the same lane; (3) structural - every artifact reachable along declared dependency "
        "edges from an artifact in set 1. Report the three sets and their union, and mark each "
        "member RE-DERIVED, CONFIRMED-UNAFFECTED or OPEN with the anchor that settles it. An OPEN "
        "member is a P1 defect attached to the premise, not a note."
    ),
    tests_required=[
        "worked acceptance case: the M-NN option-id collision. The closure must include "
        "17-DECISION-LOG.md, the pinned program brief and every downstream unit brief that quoted "
        "the 31-way collision as live; a closure that returns only the source document is a "
        "one-directional read and fails",
        "negative control: a premise that was CONFIRMED (not refuted) must produce an empty closure "
        "set; a detector that returns members for a healthy premise is matching text, not status",
        "join-completeness control: delete the structural join and confirm the closure SHRINKS on "
        "the worked case - if it does not, the structural join is inert and must be repaired before "
        "any closure is reported complete",
    ],
    reviewer_requirement=(
        "one reviewer who is given ONLY the refuted premise and the raw artifact tree and must "
        "independently build the closure before being shown this unit's set; the two closures are "
        "diffed and any member found by only one side is an OPEN item, not a tie"
    ),
    post=("every refuted premise has a three-join closure set with each member marked RE-DERIVED, "
          "CONFIRMED-UNAFFECTED or OPEN, and the M-NN worked case reaches beyond its source document"),
    retry_policy=(
        "resumable: on interruption restart from the last completed premise closure and record the "
        "resume boundary in the receipt; never restart from zero and silently discard partial closures"
    ),
    failure_classification=["stale-premise", "incomplete-remediation", "one-directional-read"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 134 (O)
u(
    id="ADV-0134",
    title="Supersession-chain integrity: a retired record still being cited as current",
    phase="1",
    question_or_target=(
        "Walk every supersession edge across the program's durable stores - basic-memory notes with "
        "superseded_by / valid_as_of frontmatter, CLAIM-REGISTRY duplicate-of edges, decision-log "
        "entries revised by a later entry, and rules or skills marked RETIRED - and answer: which "
        "SUPERSEDED records are still cited by a live artifact as if current, and which chains are "
        "broken (a superseded_by pointing at a permalink that does not resolve, or a cycle)?"
    ),
    inputs=[
        "basic-memory vault notes carrying superseded_by or valid_as_of",
        "CLAIM-REGISTRY.json duplicate-of and contradiction edges",
        "OWNER-DECISIONS.md and the Prompt One decision log revision history",
        "the RETIRED markers in the repo (AgentBridge block, codex stub retirement lane, "
        "CODEX-STUB-RETIREMENT-LANE.md)",
    ],
    dependencies=["B01", "AUD-0065"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "corpus-normalizer"},
    tool_permissions=[
        "Read", "Grep", "Glob", "Write", "Bash",
        "mcp__basic-memory__search_notes", "mcp__basic-memory__read_note",
    ],
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path="command-center/adversarial/ADV-0134-supersession-integrity.json",
    output_schema="command-center/schema/supersession-graph.schema.json",
    evidence_requirement=(
        "Emit the supersession graph as explicit edges (old_id, new_id, declared_at, store) and run "
        "three mechanical checks over it: RESOLVE (every superseded_by target exists), ACYCLIC (no "
        "cycle), and CITED-CURRENT (no live artifact cites a node that has an outgoing superseded_by "
        "edge without also naming the successor). Each violation carries the citing file:line and "
        "the successor that should have been cited. Read-only against the vault - this unit reports, "
        "it does not rewrite any note."
    ),
    tests_required=[
        "known-present control: the AgentBridge retirement is a real supersession with a live "
        "successor pair (~/CLAUDE.md and ~/AGENTS.md both restate it); the walker must find that "
        "edge or it is not reading the store it claims to read",
        "planted broken chain: add a scratch record whose superseded_by points at a non-existent "
        "permalink and confirm RESOLVE fires",
        "planted cycle: two scratch records superseding each other must trip ACYCLIC; a walker that "
        "hangs instead of reporting is a failure, not a timeout",
    ],
    reviewer_requirement=(
        "one reviewer whose only job is to re-run the DETECTOR CONTROLS - the planted broken chain "
        "and the planted cycle - and confirm both fire; a reviewer who only re-reads the graph has "
        "verified nothing"
    ),
    post=("the three checks each report a count with their violation lists, and both planted "
          "controls fired during the same run that produced those counts"),
    retry_policy=(
        "at most 3 attempts, each with a DIFFERENT store adapter or query path; the receipt must "
        "name what changed between attempts or the attempt does not count"
    ),
    failure_classification=["stale-premise", "broken-lineage", "detector-failure"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 135 (A)
u(
    id="ADV-0135",
    title="Anti-groupthink control evasion: a council that IS collapsed but defeats every shipped trigger",
    phase="7A",
    question_or_target=(
        "Can a deliberation that is genuinely collapsed - one viewpoint, no independent reasoning - "
        "be constructed so that every shipped anti-failure control reports HEALTHY? Build the "
        "evading councils and run them against CNL-0059 instant-unanimity, CNL-0086 echo chamber, "
        "CNL-0087 sycophancy, CNL-0097 lost dissent and CNL-0120 dissent preservation. Any control "
        "that passes an evading council is REFUTED as a safeguard, whatever its unit tests say."
    ),
    inputs=[
        "the shipped council runtime and its anti-failure control implementations (bucket B07 / IMP)",
        "CNL-0059, CNL-0086, CNL-0087, CNL-0097, CNL-0099, CNL-0120 as the controls under attack",
        "RES-0084 (trivial-variant idea-count gaming) and RES-0081 (measured sycophancy magnitude) "
        "as the attack vocabulary",
        "spec _USER-PROMPTS.md:10944 and :11227-11244 (the failure list the controls claim to cover)",
    ],
    dependencies=["B05", "B07", "RES-0084"],
    assigned_model_vendor_role={"model": "gpt-5-codex", "vendor": "openai", "role": "groupthink-red-team"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Edit", "Bash", "mcp__codex__codex", "mcp__codex__codex-reply"],
    execution_substrate="cloud-batch",
    timeout_seconds=7200,
    output_path="command-center/adversarial/ADV-0135-antigroupthink-evasion.json",
    output_schema="command-center/schema/evasion-corpus.schema.json",
    evidence_requirement=(
        "Ship an executable evasion corpus of at least 5 distinct attacks with the transcript each "
        "produced and the control's verdict on it: (1) manufactured trivial disagreement that keeps "
        "the unanimity counter below threshold while the substantive position is single; (2) a "
        "recorded dissent that is verbatim-preserved but semantically void, defeating a "
        "preservation check that measures presence; (3) role-diverse prompts whose outputs converge "
        "to one argument, defeating a role-collapse check that measures declared roles; (4) "
        "independent first-pass briefs that are independently GENERATED but share one retrieved "
        "source, defeating an echo-chamber check that measures generation independence; (5) "
        "confidence trajectories shaped to look like convergence-after-debate. Each attack states "
        "the control it defeats and the exact assertion in that control that it slips past."
    ),
    tests_required=[
        "negative control per attack: a genuinely healthy council with the same participant count, "
        "topology and round budget must NOT be flagged by the control - an attack that only works by "
        "also breaking healthy councils has found a false-positive, not an evasion",
        "each surviving evasion must be converted into a regression fixture and filed against the "
        "owning CNL/IMP unit, so the repaired control cannot silently lose the coverage again",
        "control-of-the-control: at least one attack must be one the shipped controls DO catch, "
        "proving the harness can observe a firing control and is not silent in both states",
    ],
    reviewer_requirement=(
        "one fresh-context adversarial reviewer from the OTHER vendor than the executor who is given "
        "the transcripts WITHOUT the attack labels and must classify each as healthy or collapsed; "
        "a reviewer who agrees with the shipped control on an evading transcript corroborates the "
        "evasion rather than refuting it"
    ),
    post=("at least 5 distinct attacks are recorded with per-control verdicts, every attack has a "
          "passing healthy-council negative control, and the control-of-the-control attack was "
          "caught by the shipped safeguards in the same run"),
    retry_policy=(
        "one retry executed by a red-teamer from the other vendor; if the two runs disagree about "
        "whether a control fired, escalate to raw-transcript adjudication rather than a third run"
    ),
    failure_classification=["groupthink", "safeguard-evasion", "false-negative-control", "detector-failure"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 136 (F)
u(
    id="ADV-0136",
    title="Runtime independence attestation: what actually answered versus what the config declared",
    phase="7A",
    question_or_target=(
        "For every seat, reviewer slot and confirmation unit this program declares INDEPENDENT or "
        "CROSS-VENDOR, does a runtime attestation prove the answering process was actually a "
        "different vendor, model, context and seed - or is independence asserted only in the "
        "config? The estate has a measured instance of the confound: a comparison believed to be "
        "GPT-5.x versus Opus was in fact sonnet-driver versus opus-driver, because the dispatching "
        "agent's model was never attested."
    ),
    inputs=[
        "CouncilSpec instances and the seated-participant records they produced",
        "every reviewer_requirement field in WORK-UNIT-CATALOG.json that says cross-vendor",
        "the cross-vendor adapter negotiation records (ARC-0091 abstraction-leak declaration)",
        "rules/common/cross-vendor-dispatch.md section 5 (model floor and the measured confound)",
        "CNL-0021 duplicate-independence detection and CNL-0029 conflict-of-interest solver as the "
        "CONFIG-side checks this unit is testing from the runtime side",
    ],
    dependencies=["B05", "B09", "CNL-0021"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "independence-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "mcp__codex__codex"],
    execution_substrate="local-parallel",
    timeout_seconds=3600,
    output_path="command-center/adversarial/ADV-0136-independence-attestation.json",
    output_schema="command-center/schema/attestation-ledger.schema.json",
    evidence_requirement=(
        "Independence is attested from the RESPONSE SIDE, never from the request side. Per seat "
        "record: the transport actually used, the vendor endpoint that answered, the model "
        "identifier the runtime reported back, the context digest the seat was given, and the "
        "prompt-file digest. Then compute three violations: SAME-TUPLE (two allegedly independent "
        "seats share vendor+model+context digest), DECLARED-ONLY (a cross-vendor slot with no "
        "response-side vendor record at all - which counts as a violation, not as unknown), and "
        "DRIVER-CONFOUND (the dispatching agent's own model differs across arms of a comparison). "
        "An absent attestation is adverse-inference: treat it as SAME-TUPLE until measured."
    ),
    tests_required=[
        "planted collusion: seat the same model twice under two different role labels and confirm "
        "SAME-TUPLE fires; a checker that reads the label instead of the tuple will pass it",
        "planted driver confound: run one comparison arm from a different driver model and confirm "
        "DRIVER-CONFOUND fires",
        "adverse-inference control: strip the response-side record from one genuinely cross-vendor "
        "seat and confirm it is reported as DECLARED-ONLY rather than silently passing",
    ],
    reviewer_requirement=(
        "one reviewer who re-derives the attestation from the raw transport logs alone, without this "
        "unit's ledger, and must reach the same three violation sets"
    ),
    post=("every declared-independent seat carries a response-side attestation record or is reported "
          "as DECLARED-ONLY, and all three planted controls fired"),
    retry_policy=(
        "no blind retry. Every attestation attempt is recorded including failures to obtain a "
        "response-side identifier; a seat that fails attestation 3 times is filed as DECLARED-ONLY, "
        "never retried into a pass"
    ),
    failure_classification=["independence-violation", "hidden-coi", "single-signal", "adverse-inference"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 137 (P)
u(
    id="ADV-0137",
    title="Program-scale shared-premise correlation: 2048 units, one spec reading, one pinned brief",
    phase="12",
    question_or_target=(
        "How concentrated is this program's evidence base? Compute, over every work unit's inputs "
        "and every artifact's cited anchors, the distribution of ORIGINATING sources, and identify "
        "the premises on which the largest number of units depend transitively. For the top N "
        "load-bearing shared premises, commission an independent re-derivation from raw source by "
        "an agent that has never seen the pinned brief. This is the program's own groupthink: a "
        "single spec reading and a single pinned brief propagated to every lane, where N agents "
        "agreeing is still one lens if they read the same input."
    ),
    inputs=[
        "WORK-UNIT-CATALOG.json plus every catalog-slices/*.json inputs array",
        "the pinned program brief and the Phase-0 ground digests distributed to all lanes",
        "_USER-PROMPTS.md:10473-11437 (the single spec reading every lane inherited)",
        "rules/common/single-signal-verification.md rule 5 (a subagent finding is a single signal too)",
    ],
    dependencies=["B01", "B02", "ADV-0130"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "epistemic-concentration-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="local-parallel",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0137-premise-concentration.json",
    output_schema="command-center/schema/concentration-report.schema.json",
    evidence_requirement=(
        "Report a source-dependency histogram (units per originating source), the transitive "
        "load-bearing rank of each shared premise, and a Gini-style concentration figure with the "
        "counting rule stated. Then, for the top 5 premises by rank, attach an independent "
        "re-derivation performed by an agent whose context contains the RAW source only - no brief, "
        "no digest, no sibling artifact - and diff its conclusion against the propagated one. A "
        "premise whose independent re-derivation disagrees is escalated to ADV-0133 for blast-radius "
        "closure in the same run."
    ),
    tests_required=[
        "context-hygiene control: prove the re-deriving agent's context did NOT contain the brief, "
        "by fingerprinting its input bundle; a re-derivation contaminated by the brief is not "
        "independent and its agreement is worthless",
        "planted-disagreement control: for one premise, hand the re-deriver a deliberately altered "
        "raw source and confirm the diff fires; a diff that reports agreement on altered input is "
        "measuring nothing",
        "the histogram must be reproducible from the catalog files by a second script written "
        "without reference to the first",
    ],
    reviewer_requirement=(
        "one reviewer who re-computes the concentration figure from the raw catalog files with an "
        "independently written counter, plus one reviewer who audits the re-deriver's input bundle "
        "for brief contamination; both file before either sees the other"
    ),
    post=("the concentration histogram is reproducible by an independent counter, the top-5 "
          "re-derivations each carry a proven-clean input bundle, and any disagreement was handed "
          "to ADV-0133"),
    retry_policy=(
        "two strikes then pivot (AGENTS.md 4b): a second failure with the same counting fingerprint "
        "requires at least 2 mechanically different counting strategies before a third attempt"
    ),
    failure_classification=["groupthink", "single-signal", "premise-concentration", "context-contamination"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 138 (I)
u(
    id="ADV-0138",
    title="Authority provenance: every binding owner decision must trace to a verbatim owner utterance",
    phase="12",
    question_or_target=(
        "For every entry in OWNER-DECISIONS.md and every decision the program treats as BINDING, "
        "does a verbatim owner utterance exist at a citable anchor that says it - or did the "
        "program author its own mandate and then obey it? Enumerate each binding decision with its "
        "source anchor and classify OWNER-STATED, OWNER-IMPLIED-BY-INFERENCE or PROGRAM-AUTHORED. "
        "A PROGRAM-AUTHORED binding decision is authority laundering and must be re-put to the owner "
        "before anything downstream of it is treated as settled."
    ),
    inputs=[
        "OWNER-DECISIONS.md and every 'binding'/'already decided' assertion in the command-center tree",
        "_USER-PROMPTS.md in full (the owner utterance corpus) and the session decision log",
        "OWNER-QUESTION-PACKET.md (questions asked) and any recorded answers",
        "WFA-0077 (which decisions in that bucket require owner approval) as an adjacent, "
        "non-overlapping input: WFA-0077 asks WHICH need approval, this unit asks whether the ones "
        "already claimed as approved actually were",
        "spec _USER-PROMPTS.md:11349-11370 (owner interaction rules) and :10526 (do not re-ask "
        "answered questions - which only holds if the answer exists)",
    ],
    dependencies=["B01", "WFA-0077"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "authority-provenance-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="local-serialized",
    timeout_seconds=3600,
    output_path="command-center/adversarial/ADV-0138-authority-provenance.json",
    output_schema="command-center/schema/decision-provenance.schema.json",
    evidence_requirement=(
        "One row per binding decision with: the decision as the program states it, the quoted owner "
        "text with file:line, the classification, and - for OWNER-IMPLIED-BY-INFERENCE - the exact "
        "inference step written out so the owner can reject it in one reading. Matching is on the "
        "SEMANTIC decision, not on keyword overlap: an owner utterance that mentions the topic "
        "without deciding it classifies as PROGRAM-AUTHORED. Scope note: this unit reads the owner "
        "corpus, it never asks the owner anything and never modifies OWNER-DECISIONS.md."
    ),
    tests_required=[
        "known-present control: the PR-ONLY release mode and the DELETE-ALL retirement scope are "
        "recorded owner decisions; both must classify OWNER-STATED with a resolvable anchor, or the "
        "matcher is broken",
        "planted laundering: insert a scratch binding decision with no owner utterance behind it and "
        "confirm it classifies PROGRAM-AUTHORED",
        "use-vs-mention control: a decision whose topic is MENTIONED in an owner utterance that "
        "explicitly defers it must classify PROGRAM-AUTHORED, not OWNER-STATED - keyword matching "
        "is exactly the failure this test exists to catch",
    ],
    reviewer_requirement=(
        "owner sign-off is required in addition to one cross-vendor reviewer, because the output "
        "may invalidate a decision the program has been executing against; the reviewer files first "
        "and the owner adjudicates only the PROGRAM-AUTHORED rows"
    ),
    post=("every binding decision carries a classification and, where OWNER-STATED, a verbatim quote "
          "with a resolvable file:line; the two known-present decisions classified correctly and the "
          "planted laundering was caught"),
    retry_policy=(
        "zero retries. The first classification pass IS the record; a later pass that reclassifies a "
        "row is appended as a DISCREPANCY with both readings preserved, never overwritten"
    ),
    failure_classification=["authority-laundering", "scope-drift", "use-vs-mention", "unapproved-action"],
    owner_approval_required=True,
)

# ---------------------------------------------------------------- 139 (U)
u(
    id="ADV-0139",
    title="Build-environment supply chain: the agent runtime that produced every artifact is itself untrusted",
    phase="12",
    question_or_target=(
        "What could a hostile skill, MCP server, hook, plugin or repo-local agent config in THIS "
        "program's execution environment have done to the artifacts it produced - and is there any "
        "evidence it did? The threat is not a malicious package we ship, it is a compromised "
        "toolchain that authored the evidence. Enumerate every component with write or network "
        "capability that loaded during the program, its provenance and pin, and the artifacts it "
        "could have touched. Report only - propose no removal and change no configuration."
    ),
    inputs=[
        "the live MCP server inventory and per-server tool surface (AUD-0060)",
        "the live skill, hook and plugin inventory (AUD-0058, AUD-0080 permission-surface audit)",
        "any .claude/, .codex/, .mcp.json, AGENTS.md or CLAUDE.md inside CLONED or vendored trees "
        "the program ran inside (AGENTS.md section 9, CVE-2026-47751 class)",
        "RES-0061 (a config file IS an instruction: the prompt-payload supply-chain risk class)",
        "ARC-0013 (the generator as a supply-chain node) as the adjacent BUILD-time surface this "
        "unit does not re-cover; this unit's scope is the AGENT runtime, not the code generator",
    ],
    dependencies=["B02", "RES-0061", "AUD-0080"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "security-refuter"},
    tool_permissions=["Read", "Grep", "Glob", "Bash"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0139-build-environment-supply-chain.json",
    output_schema="command-center/schema/runtime-trust-inventory.schema.json",
    evidence_requirement=(
        "A component-by-component table: name, source (first-party / marketplace / vendored / "
        "cloned repo), pin or commit, load trigger, declared capability, observed capability, and "
        "the artifact classes it could have written. Capability is measured from the tool surface "
        "and the transport, not from the component's own description. Two independent signals are "
        "required for any 'did not load' claim - a config reading AND a process or session-log "
        "observation - because a config key at the wrong scope is inert and has already produced a "
        "false 'disabled' verdict on this estate. Strictly read-only: name what should be "
        "quarantined and hand it to the owner; quarantining is not this unit's action."
    ),
    tests_required=[
        "detector control on the load question: pick one component KNOWN to load and one KNOWN to be "
        "disabled and confirm the two-signal probe separates them; a probe that reports the same for "
        "both is measuring the config file, not the runtime",
        "planted config: place a benign marker instruction in a scratch clone's AGENTS.md, run an "
        "agent inside it, and confirm the marker is observed being auto-loaded - this proves the "
        "cloned-repo-config channel is real on this box rather than assumed",
        "artifact-attribution control: for one artifact, prove from the event log which components "
        "were live when it was written; an attribution that cannot be reconstructed is reported as "
        "UNATTRIBUTED rather than assumed clean",
    ],
    reviewer_requirement=(
        "one security reviewer who authored none of the scanned configuration, plus a mechanical "
        "re-enumeration of the component inventory from a different entry point (process table "
        "rather than settings files, or the reverse) on the same session"
    ),
    post=("every loaded component has a provenance row with two-signal load evidence, the "
          "planted-config channel test ran, and any unattributable artifact is listed as UNATTRIBUTED"),
    retry_policy=(
        "one retry only when the failure classifies as environment-transient (a server not up, a "
        "session not yet started); an inability to attest a component is filed as UNKNOWN-CAPABILITY, "
        "never retried until it passes"
    ),
    failure_classification=["supply-chain", "untrusted-config-autoload", "single-signal", "unattributed-artifact"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 140 (V)
u(
    id="ADV-0140",
    title="Owner-gate bypass enumeration across all five owner-controlled action classes",
    phase="12",
    question_or_target=(
        "For each owner-controlled action the spec names - public publishing, unbounded or paid "
        "external spend, credential rotation, deleting user data, changing security posture, and "
        "creating public repositories or organizations - enumerate EVERY code path, workflow node, "
        "hook, adapter and CLI entry point that can reach it, and prove each one crosses the "
        "approval gate. A path that reaches the action without the gate is a P0 regardless of how "
        "unlikely it is to be taken."
    ),
    inputs=[
        "the shipped plugin, marketplace, foundry and council code (buckets B07 implementation)",
        "the human-checkpoint executor (IMP-0218) and the owner-approval field across the catalog",
        "TST-0213 (no code path can revoke/rotate a credential) as the ONE action class already "
        "covered by a dedicated test; this unit covers the other five and must not re-file the "
        "credential class as a new finding",
        "spec _USER-PROMPTS.md:10482 and :11353-11362 (the owner-controlled action list)",
    ],
    dependencies=["B07", "TST-0213", "ARC-0062"],
    assigned_model_vendor_role={"model": "gpt-5-codex", "vendor": "openai", "role": "security-refuter"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "mcp__codex__codex"],
    execution_substrate="worktree-isolated",
    timeout_seconds=7200,
    output_path="command-center/adversarial/ADV-0140-owner-gate-bypass.json",
    output_schema="command-center/schema/gate-reachability.schema.json",
    evidence_requirement=(
        "Reachability is computed, not read: build a call/dispatch graph from every entry point to "
        "every sink that performs one of the five action classes, and report each path with the "
        "gate node it crosses or the absence of one. Sinks are identified by EFFECT (a network write "
        "to a publish endpoint, a spend-incurring API, a destructive filesystem call, a "
        "permission-widening config write), never by function name, because a rename defeats a "
        "name-based sink list. Every ungated path is executed in a disposable worktree against a "
        "fake sink to prove it is genuinely reachable and not a graph artifact."
    ),
    tests_required=[
        "planted bypass: add a scratch entry point that reaches a publish sink without the "
        "checkpoint and confirm the enumeration finds it",
        "rename control: rename a known gated sink and confirm the effect-based sink identification "
        "still classifies it; a detector that loses the sink on rename is name-based and must be "
        "repaired before its zero-findings result is citable",
        "no real sink may be executed: every proof-of-reachability run targets a fake sink and the "
        "receipt records the substitution",
    ],
    reviewer_requirement=(
        "one reviewer from the other vendor who independently enumerates the sinks by effect from "
        "the raw source, without this unit's sink list, and diffs the two sink sets; a sink found by "
        "only one side is an open item"
    ),
    post=("every one of the five action classes has an enumerated path set, each ungated path was "
          "proven reachable against a fake sink, and the rename control still classified the sink"),
    retry_policy=(
        "two strikes then pivot: after the second graph-construction failure with the same "
        "fingerprint, switch to a different extraction strategy (dynamic tracing rather than static "
        "graph, or the reverse) before a third attempt"
    ),
    failure_classification=["unapproved-action", "gate-bypass", "reachability-gap", "name-based-detector"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 141 (B)
u(
    id="ADV-0141",
    title="Secret and PII detector coverage algebra: the input domain the shipped scanners never see",
    phase="12",
    question_or_target=(
        "Not 'does the scanner catch a planted token' (TST-0206 and IMP-0458 already prove that on "
        "the covered path) but 'what is in the artifact universe that the scanner is never handed?' "
        "Compute COVERED = the set of paths, file types, encodings and container formats the "
        "shipped secret and PII gates actually read, subtract it from PRODUCED = every byte any "
        "release or program artifact can contain, and require every element of the difference to be "
        "either brought into coverage or declared out of contract with a written reason."
    ),
    inputs=[
        "the shipped gates: IMP-0004 credential-exposure gate, IMP-0458 secret-scrub gate, "
        "IMP-0113 package linter secrets check, and their configured include/exclude globs",
        "TST-0206 canary-seeded scan (the covered-path proof this unit deliberately does not repeat)",
        "RES-0133 secret-scanner coverage gap on markdown, prompt and transcript artifacts",
        "the produced-artifact universe: wheels and packed archives, __pycache__, caches, "
        "content-addressed blob store, event logs, resumable checkpoints, git-crypt-decrypted "
        "worktree state, base64 or gzip-embedded payloads, and Windows reserved-name paths",
    ],
    dependencies=["B07", "RES-0133", "AUD-0078"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "coverage-algebra-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0141-scanner-coverage-algebra.json",
    output_schema="command-center/schema/coverage-difference.schema.json",
    evidence_requirement=(
        "COVERED is measured by INSTRUMENTING the gate - log every path it opens during a full run - "
        "not by reading its glob configuration, because a glob that never matches looks identical to "
        "one that matches nothing. PRODUCED is enumerated from the filesystem and from inside every "
        "container format (archive members, wheel contents, compressed blobs) to at least one "
        "nesting level. Emit COVERED, PRODUCED, and DIFFERENCE with a per-element disposition. "
        "Enumeration must survive Windows reserved device names via the extended-length prefix - a "
        "path named NUL has already crashed an enumerator on this estate and a swallowed crash "
        "would report an empty and reassuring difference set."
    ),
    tests_required=[
        "enumerator control: place a file under a Windows reserved device name and one inside a "
        "nested archive, and confirm both appear in PRODUCED; an enumerator that silently drops "
        "either produces a false-clean difference",
        "instrumentation control: point the gate at a directory it is configured to exclude and "
        "confirm that directory does NOT appear in COVERED; if it does, the instrumentation is "
        "recording intent rather than behaviour",
        "end-to-end falsification: place a canary token in one element of DIFFERENCE and confirm the "
        "shipped gate does not find it - this converts the coverage gap from an inference into an "
        "executed demonstration. The canary is a synthetic non-credential string, never a real one",
    ],
    reviewer_requirement=(
        "one reviewer who re-derives COVERED by a mechanically different route (filesystem access "
        "auditing or strace-equivalent rather than in-process logging) and must reach the same set; "
        "a disagreement means one instrumentation is lying and neither result may be cited"
    ),
    post=("COVERED was measured by instrumentation rather than configuration, every element of "
          "DIFFERENCE carries a disposition, and the end-to-end canary demonstrated at least one "
          "gap or proved the difference set empty by execution"),
    retry_policy=(
        "resumable: the enumeration checkpoints per container format; on interruption resume at the "
        "last completed format and record the boundary. Never restart with a narrowed scope to make "
        "the run finish"
    ),
    failure_classification=["coverage-gap", "detector-failure", "privacy-leak", "silent-crash"],
    owner_approval_required=False,
)

# ---------------------------------------------------------------- 142 (M)
u(
    id="ADV-0142",
    title="Re-identification attack on the redacted and publishable artifact set",
    phase="15",
    question_or_target=(
        "Given only the artifacts this program intends to make readable outside the owner's machine, "
        "can an outsider re-identify the owner, reconstruct the machine and account layout, or "
        "identify a third party whose content appears in the corpus - by JOINING across artifacts "
        "rather than by finding any single unredacted string? Presence scanning (AUD-0078) and the "
        "redaction proof (IMP-0479) both operate per-artifact; this unit attacks the union."
    ),
    inputs=[
        "the publishable artifact set as defined by the release checklist under the binding PR-ONLY "
        "release mode, plus anything a PR diff, CI log or uploaded artifact would expose",
        "IMP-0479 telemetry/privacy contract implementation with its redaction proof",
        "AUD-0078 secret and PII scan output (the per-artifact presence baseline)",
        "RES-0124 privacy and data-protection surface if this toolchain is ever published",
        "the quasi-identifier inventory: absolute paths, usernames, hostnames, repo names, timezone "
        "and timestamp patterns, model/account tiers, unusual tool combinations, prose style",
    ],
    dependencies=["B13", "IMP-0479", "RES-0124", "AUD-0078"],
    assigned_model_vendor_role={"model": "gpt-5-codex", "vendor": "openai", "role": "privacy-refuter"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "mcp__codex__codex"],
    execution_substrate="local-serialized",
    timeout_seconds=5400,
    output_path="command-center/adversarial/ADV-0142-reidentification-attack.json",
    output_schema="command-center/schema/reidentification-assessment.schema.json",
    evidence_requirement=(
        "Run the attack, do not model it. The attacking agent is given ONLY the publishable set - no "
        "session context, no brief, no memory tools - and must file its best identification with the "
        "join chain that produced it and a confidence band. Report k-anonymity-style figures per "
        "quasi-identifier class where computable, and for each successful join the minimum set of "
        "artifacts that would have to be withheld or altered to break it. Any recovered identifier "
        "is reported by CLASS and location, never reproduced verbatim in the artifact. This unit "
        "does not perform external lookups against real people or third-party services."
    ),
    tests_required=[
        "context-hygiene control: fingerprint the attacking agent's input bundle to prove it "
        "contained no session context; an attacker that already knows the owner proves nothing",
        "negative control: run the same attack against a synthetically generated artifact set with "
        "no real identifiers and confirm the attacker fails; an attacker that 'succeeds' on synthetic "
        "data is pattern-matching, not re-identifying",
        "join-necessity control: for each successful identification, withhold the named minimum set "
        "and re-run - the join must fail, otherwise the named minimum is wrong and the remediation "
        "advice would be useless",
    ],
    reviewer_requirement=(
        "owner sign-off in addition to one reviewer, because the output determines what may leave the "
        "machine; the reviewer verifies the input-bundle hygiene fingerprint before reading any finding"
    ),
    post=("the attacker's input bundle is fingerprinted clean, the synthetic negative control failed "
          "to identify anyone, and every successful join names a minimum withhold set that was "
          "re-tested and broke the join"),
    retry_policy=(
        "one retry only, and only to widen the attacker's artifact set (never to narrow it). A "
        "failed identification is a result to record, not a failure to retry away"
    ),
    failure_classification=["privacy-leak", "reidentification", "legal-exposure", "context-contamination"],
    owner_approval_required=True,
)

# ---------------------------------------------------------------- 143 (N)
u(
    id="ADV-0143",
    title="Third-party CONTENT redistribution: what in the corpus may lawfully leave the machine",
    phase="15",
    question_or_target=(
        "Independent of software licence compatibility (RES-0135, IMP-0157, WFA-0139 cover the code "
        "and workflow licence lattice), what CONTENT in the program corpus is third-party expression "
        "or third-party personal data - quoted vendor documentation, scraped marketplace and forum "
        "text, transcript excerpts containing other people's messages, AI-generated text of "
        "uncertain provenance - and under the binding PR-ONLY release mode, which classes may be "
        "redistributed, which must be summarised rather than quoted, and which must be excluded "
        "entirely?"
    ),
    inputs=[
        "the program corpus and every artifact that quotes an external source verbatim",
        "the provenance and licence graph from bucket B04 (WFA-0079) for the code-side lattice this "
        "unit consumes but does not recompute",
        "RES-0125 provenance and licensing obligations for AI-generated blueprint content",
        "RES-0121 upstream LICENSE files and the NOASSERTION set",
        "the binding owner decision: release mode is PR-ONLY (which narrows but does not eliminate "
        "the redistribution surface, because a PR diff and its CI logs are still a publication)",
    ],
    dependencies=["B04", "RES-0125", "WFA-0079"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "legal-reviewer"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash", "WebFetch", "mcp__search-hub__web_search_exa"],
    execution_substrate="local-parallel",
    timeout_seconds=7200,
    output_path="command-center/adversarial/ADV-0143-content-redistribution.json",
    output_schema="command-center/schema/redistribution-adjudication.schema.json",
    evidence_requirement=(
        "One adjudication row per CONTENT CLASS, not per file: class, an exemplar with file:line, "
        "estimated extent (byte share and count), the legal basis considered (licence term, quotation "
        "or fair-dealing argument, data-protection basis, platform terms), the verdict "
        "(REDISTRIBUTABLE / SUMMARISE-ONLY / EXCLUDE / NEEDS-OWNER-DECISION), and the exact residual "
        "risk if the verdict is wrong. Verbatim third-party expression is quantified by an extent "
        "measurement, never by an impression. This is an engineering risk assessment for the owner, "
        "explicitly not legal advice, and every row states which side of that line it sits on."
    ),
    tests_required=[
        "class-completeness control: sample 30 random artifact chunks and classify each; any chunk "
        "that fits no declared class means the class taxonomy is incomplete and the adjudication is "
        "reported as PARTIAL until the taxonomy covers the sample",
        "extent-measurement control: plant a known-length third-party quotation and confirm the "
        "extent measurement recovers its length within tolerance; an extent figure that cannot "
        "recover a known plant is not a measurement",
        "verdict-stability control: two independent reviewers adjudicate the same 10 rows blind; "
        "agreement below a pre-registered threshold means the criteria are underspecified and must "
        "be sharpened before the verdicts are used",
    ],
    reviewer_requirement=(
        "owner sign-off in addition to two independent reviewers who adjudicate blind and file before "
        "seeing each other; the owner decides every NEEDS-OWNER-DECISION row and no row is escalated "
        "with a recommendation missing"
    ),
    post=("every content class carries a verdict with a measured extent and a stated residual risk, "
          "the 30-chunk completeness sample found no unclassifiable chunk, and inter-reviewer "
          "agreement met the pre-registered threshold"),
    retry_policy=(
        "no blind retry on a verdict. A changed verdict is appended with both readings and the reason "
        "for the change; the earlier verdict is never deleted, because a silently revised legal "
        "position hides the reasoning the owner needs"
    ),
    failure_classification=["legal-exposure", "redistribution-risk", "privacy-leak", "taxonomy-incomplete"],
    owner_approval_required=True,
)

# ---------------------------------------------------------------- 144 (T)
u(
    id="ADV-0144",
    title="Controversial-source compliance trace: every Tor-derived claim labeled, corroborated and legally reviewed",
    phase="2",
    question_or_target=(
        "The Tor/onion and other controversial source classes are opt-in, sandboxed, logged and "
        "restricted to lawful public research, and their claims must be LABELED and independently "
        "corroborated with a mandatory legal/safety review before output. RES-0138 designs that gate "
        "and RES-0119 executes the sweep; this unit audits the resulting COMPLIANCE TRACE: for every "
        "claim in the research corpus whose lineage touches a controversial source, do the label, "
        "the corroborating independent source, the audit-log entry and the pre-output review record "
        "all exist and resolve - or has an unlabeled claim already propagated downstream?"
    ),
    inputs=[
        "the research claim corpus with source lineage (bucket B03 output)",
        "RES-0138 sandbox design, logging contract and legal gate; RES-0119 the executed sweep",
        "the sandbox audit log and the owner opt-in record for each controversial source class",
        "spec _USER-PROMPTS.md:11280-11296 (the Tor/onion safety policy) and :11362 (enabling "
        "controversial source classes is owner-controlled)",
    ],
    dependencies=["B03", "RES-0138", "RES-0119"],
    assigned_model_vendor_role={"model": "opus", "vendor": "anthropic", "role": "compliance-trace-auditor"},
    tool_permissions=["Read", "Grep", "Glob", "Write", "Bash"],
    execution_substrate="worktree-isolated",
    timeout_seconds=2700,
    output_path="command-center/adversarial/ADV-0144-controversial-source-compliance.json",
    output_schema="command-center/schema/compliance-trace.schema.json",
    evidence_requirement=(
        "Trace completeness is computed over the lineage graph, not sampled: for every claim whose "
        "transitive lineage includes a controversial source, require four resolvable records - the "
        "label on the claim itself, at least one corroborating source from a DIFFERENT class, the "
        "audit-log entry for the fetch, and the pre-output legal/safety review. Report the count of "
        "complete traces and one row per incomplete trace naming exactly which of the four is "
        "missing. A claim whose lineage cannot be resolved at all counts as INCOMPLETE, never as "
        "out of scope. This unit reads logs and lineage only; it performs no Tor or onion access."
    ),
    tests_required=[
        "detector control: plant a scratch claim with a controversial-source lineage and none of the "
        "four records, and confirm all four gaps are reported; a trace checker that reports 'complete' "
        "for an empty record set is inverted",
        "corroboration-independence control: plant a corroborating source that resolves back to the "
        "SAME origin and confirm it does NOT satisfy the corroboration requirement - same-origin "
        "corroboration is the failure mode this record exists to prevent",
        "propagation control: for one incomplete trace, follow it downstream and report every "
        "artifact that consumed the unlabeled claim; a compliance report that stops at the claim "
        "understates the exposure",
    ],
    reviewer_requirement=(
        "one reviewer who re-walks the lineage graph from the raw research records rather than from "
        "this unit's trace table, plus owner sign-off on the opt-in record for every controversial "
        "class that appears in the lineage at all"
    ),
    post=("every controversial-lineage claim has a four-record verdict, the same-origin corroboration "
          "control was rejected, and each incomplete trace lists its downstream consumers"),
    retry_policy=(
        "one retry only when the failure is environment-transient (a log store unavailable). A "
        "missing compliance record is a finding to file, never a condition to retry until it appears"
    ),
    failure_classification=["legal-exposure", "unlabeled-claim", "circular-corroboration", "audit-gap"],
    owner_approval_required=True,
)


# ------------------------------------------------------------------ write
def main() -> int:
    text = json.dumps(UNITS, indent=1, ensure_ascii=True) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {OUT} units={len(UNITS)} bytes={len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
