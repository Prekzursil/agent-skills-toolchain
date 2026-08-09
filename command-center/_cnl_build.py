#!/usr/bin/env python3
"""Generate CNL-1.json: 128 Phase-2C council-design work units.

Mechanical builder. Each row declares only what is DISTINCT about the unit;
the builder fills the 19 spec-mandated fields. Emits EXACTLY the 19 fields
(no extras) because "strict plugin parser rejects unknown fields" is a named
failure class in the spec (_USER-PROMPTS.md:11302).
"""

import json
import os
import re
import sys
from collections import Counter

OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "catalog-slices", "CNL-1.json"
)

CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SPEC = CORPUS + "/_USER-PROMPTS.md"
SCH11 = CORPUS + "/11-COUNCIL-SPECIFICATION.schema.json"
MD11 = CORPUS + "/11-COUNCIL-SPECIFICATION.md"
CARDS = CORPUS + "/11-COUNCIL-OPTION-CARDS.md"
PPJ = CORPUS + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
PPM = CORPUS + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
LIVESKILL = "C:/Users/Prekzursil/.claude/skills/council/SKILL.md"
REPOSKILL = "skills/council/SKILL.md"

S_2C = SPEC + ":10746-10767"
S_7A = SPEC + ":10915-10946"
S_PROD = SPEC + ":11172-11244"
S_FAIL = SPEC + ":11335-11347"
S_PRED = SPEC + ":10627-10648"
S_STOP = SPEC + ":11372-11399"
S_SCALE = SPEC + ":10570-10584"

SCHEMA_DESIGN = "command-center/schema/council-design-note.schema.json"
SCHEMA_SPEC = "command-center/schema/councilspec.v2.schema.json"
SCHEMA_PRESET = "command-center/schema/council-preset.schema.json"
SCHEMA_SIM = "command-center/schema/council-simulation-spec.schema.json"
SCHEMA_DET = "command-center/schema/council-detector-spec.schema.json"

ART = "command-center/design/council/"

OPUS = {
    "vendor": "anthropic",
    "model": "opus",
    "role": "council-systems-designer",
    "basis": "feedback_opus_not_sonnet_subagents - all substantive subagents default to Opus",
}


def A(role, vendor="anthropic", model="opus", basis=None):
    return {
        "vendor": vendor,
        "model": model,
        "role": role,
        "basis": basis
        or (
            "cross-vendor independence required by " + SPEC + ":10579"
            if vendor != "anthropic"
            else "feedback_opus_not_sonnet_subagents - Opus for substantive design"
        ),
    }


XV = "openai"  # cross-vendor authorship for adversarial/detector lanes
XVM = "gpt-5-codex"

RETRY_DEFAULT = (
    "two strikes then pivot: after the 2nd failure on the same hypothesis, "
    "enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). "
    "Max 3 attempts, then emit FAILED:<id> with the diagnostic tail."
)
RETRY_DETECTOR = (
    "two strikes then pivot, PLUS a mandatory detector-control retry: if the "
    "both-states control does not fire on the planted-bad fixture, the attempt "
    "does not count as a failure of the mechanism - fix the fixture first, once. "
    "Max 3 mechanism attempts (AGENTS.md 4b)."
)
RETRY_OWNER = (
    "no autonomous retry past attempt 1 - if the owner gate is unanswered the unit "
    "parks as BLOCKED with a named question, it does not guess a default."
)
RETRY_SIM = (
    "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle (scripted-participant "
    "replay, transcript diff, counter assertion) - a re-run of the same oracle does not "
    "count as an attempt (rules/common/single-signal-verification.md)."
)

FC_BASE = ["spec-underspecified", "overclaim", "detector-failure", "dependency-blocked"]
FC_DET = ["detector-failure", "uncontrolled-silence", "gameable-metric", "overclaim"]
FC_METRIC = [
    "unfalsifiable-metric",
    "gameable-metric",
    "overclaim",
    "spec-underspecified",
]
FC_DUP = [
    "mechanism-duplicate",
    "spec-underspecified",
    "overclaim",
    "dependency-blocked",
]
FC_OWNER = ["owner-blocked", "spec-underspecified", "overclaim"]
FC_SIM = ["detector-failure", "uncontrolled-silence", "green-not-live", "overclaim"]

REV_DEFAULT = (
    "one independent adversarial reviewer in a fresh context who never saw the "
    "author's reasoning; reviewer must produce a counterexample instance or state "
    "REFUTED-NOT-ATTEMPTED."
)
REV_XV = (
    "one cross-vendor reviewer (openai/gpt-5-codex) who MUST re-run the both-states control "
    "themselves before signing; a review that did not execute the control is rejected."
)
REV_MECH = (
    "one reviewer who re-derives the result mechanically from the fixtures (independent "
    "recount / re-tabulation), not by reading the author's argument; a disagreement in "
    "the number blocks the unit."
)
REV_PRESET = (
    "one reviewer who instantiates the preset against a fixture task and shows it "
    "produces a role/vote/stop profile measurably DIFFERENT from its nearest sibling "
    "preset in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json (nearest sibling named explicitly)."
)
REV_OWNER = (
    "one independent adversarial reviewer PLUS explicit owner sign-off recorded in "
    "command-center/OWNER-DECISIONS.md before the unit closes."
)

TESTS_BOTH = (
    "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on "
    "the known-good one, both runs recorded verbatim"
)
TESTS_SCHEMA = (
    "jsonschema Draft202012Validator run over every affected record, with the exact "
    "error count recorded (0 expected) and one deliberately-invalid record proving "
    "the validator is not vacuous"
)

# ---------------------------------------------------------------------------
# ROWS: (key, title, question, substrate, deps, extra)
#   extra keys: oa(owner_approval) tests rev art schema to(timeout) role vendor
#               model ev inputs fc
# ---------------------------------------------------------------------------
R = []


def u(key, title, q, sub, deps, **kw):
    R.append(dict(key=key, title=title, q=q, sub=sub, deps=list(deps), **kw))


CORE_IN = [S_2C, S_7A, SCH11, PPJ]

# ---------------- LANE A - CouncilSpec type system (11) --------------------
u(
    "A01",
    "CouncilSpec v2 root envelope that supersedes Council Charter v1",
    "What is the minimal CouncilSpec v2 root envelope such that every one of the 58 protocol "
    "records and 72 preset records in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json validates against it, "
    "AND a v1 Council Charter document (13 properties, 12 required) migrates forward with zero "
    "information loss - and which v1 property must change shape for that to be true?",
    "worktree-isolated",
    ["B02"],
    schema=SCHEMA_SPEC,
    to=3600,
    tests=[
        TESTS_SCHEMA,
        "round-trip test: v1 charter -> v2 -> v1 is byte-identical after canonical key ordering",
        "a v1 document with an unknown extra field must be REJECTED, proving additionalProperties is live",
    ],
    rev=REV_MECH,
    fc=FC_BASE,
    ev="two mechanically independent signals: (1) jsonschema Draft202012Validator reports 0 errors "
    "over all 130 catalogue records, run recorded verbatim; (2) an independent field-set diff "
    "(python set algebra over v1 properties vs v2 properties) showing which keys moved and that "
    "none was dropped. Cite " + SCH11 + " and PPJ record ids.",
)

u(
    "A02",
    "Resolve the measured v1-schema / catalogue non-intersection",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json produces 13 errors against 11-COUNCIL-SPECIFICATION."
    "schema.json and their top-level key sets do not intersect AT ALL (0 of 12 required keys "
    "present) - is the correct repair ONE schema with a discriminated union on artifact type, or "
    "TWO schemas plus a typed reference edge, and what falsifiable criterion decides it rather than "
    "taste?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        TESTS_SCHEMA,
        "the losing option must be implemented far enough to demonstrate the exact failure the "
        "criterion predicts (a paper comparison is not evidence)",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="reproduce the 13-error measurement independently (do NOT cite the file's own "
    "schema_relationship prose as the signal - it is the claim under test), then a second "
    "signal from validating C-M01 alone (claimed 14 errors, 4 of 20 keys recognised).",
)

u(
    "A03",
    "Charter block: the typed fields a compiler actually branches on",
    "Which charter fields (objective, risk tier, desired output, success criteria, consensus intent) "
    "does the council compiler need as ENUMS rather than prose in order to auto-select a protocol, "
    "and for each prose field that survives, what is the fallback when the compiler cannot branch?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=1800,
    tests=[
        "for each enum, a compiler-branch table test proving every value routes somewhere and no "
        "value falls through to a silent default",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "A04",
    "Owner-constraint block and its precedence over auto-composition",
    "When an owner constraint (budget ceiling, forbidden source class, mandatory human seat) "
    "contradicts what auto-composition would choose, what is the precedence rule, and how does the "
    "spec make the override VISIBLE rather than silently winning?",
    "local-parallel",
    ["A01", "A03"],
    schema=SCHEMA_SPEC,
    to=1800,
    oa=True,
    tests=[
        "a conflict fixture where the owner constraint and the auto-composer disagree must "
        "produce a recorded override entry, not just a different roster",
        "a constraint that cannot be satisfied at all must yield BLOCKED, never a quiet relaxation",
    ],
    rev=REV_OWNER,
    fc=FC_OWNER,
    retry=RETRY_OWNER,
    ev="cite "
    + SPEC
    + ":11349-11370 (owner interaction rules) plus a worked conflict instance.",
)

u(
    "A05",
    "Participant descriptor type: the 9 per-seat dials",
    "What is the complete participant descriptor type covering model, vendor, expertise, role, "
    "authority, vote weight, tools, effort and context - and which of those nine can be left "
    "unspecified without making two seats behaviourally indistinguishable?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=1800,
    tests=[
        "an indistinguishability test: two seats differing in NO dial must be flagged as a "
        "duplicate seat, not silently accepted",
        TESTS_SCHEMA,
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite the existing $defs.seat in "
    + SCH11
    + " and show, field by field, which of the nine "
    "spec dials it already carries and which it lacks.",
)

u(
    "A06",
    "Information-partition lattice: who may see what, when",
    "How is an information partition expressed so that a blind first pass, a staged evidence "
    "release, and a fishbowl observer ring are all instances of ONE lattice type rather than three "
    "special cases - and what is the leak check that proves a partition held?",
    "local-parallel",
    ["A05"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a leak probe: inject a partition-violating reference into a scripted transcript and "
        "prove the checker catches it",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
    retry=RETRY_DETECTOR,
)

u(
    "A07",
    "Anonymity levels and their effect on attribution",
    "What anonymity levels does the runtime need (named / pseudonymous / fully blind / blind-then-"
    "revealed), and for each, how are votes and dissent attributed in the audit record without "
    "defeating the anonymity that made the round independent?",
    "local-parallel",
    ["A06"],
    schema=SCHEMA_SPEC,
    to=1800,
    tests=[
        "a de-anonymisation probe: given a pseudonymous transcript plus the vote history, can an "
        "adversary re-identify a participant? the test must attempt it and record the result",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "A08",
    "Budget block: 12 dials and the exhaustion semantics",
    "For each of the 12 budget dials (effort, time, tokens, tool calls, sources, experiments, turns, "
    "speaking quotas, minimum engagement, maximum inactivity, rebuttal depth, escalation), does "
    "exhaustion HARD-STOP the council or DEGRADE it - and which choice silently corrupts the "
    "stopping rule if made wrong?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "for every dial, an exhaustion fixture proving the declared behaviour actually occurs",
        "a test proving budget exhaustion cannot masquerade as consensus",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "A09",
    "Target block: which of the 8 targets are measurable as written",
    "Of the eight declared targets (unique-idea, category, novelty, diversity, coverage, objection, "
    "counterexample, evidence), which have NO measurable definition as written in the spec, and for "
    "each of those, what is the smallest operational definition that a machine can compute and an "
    "adversary cannot trivially game?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "for each target, a gaming attempt: produce input that maximises the metric while "
        "obviously failing the intent; a metric that cannot be gamed in the attempt must have the "
        "attempt recorded as evidence, not asserted",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_METRIC,
    vendor=XV,
    model=XVM,
)

u(
    "A10",
    "Stopping-expression grammar and STATIC validation",
    "What grammar covers AND / OR / NOT plus ANY, ALL and weighted forms, and which expression "
    "errors (unbound variable, never-satisfiable conjunction, always-true tautology) can be caught "
    "STATICALLY before a single round runs?",
    "worktree-isolated",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a parser test over all 6 required executable examples from "
        + SPEC
        + ":10937-10942",
        "an unsatisfiable expression (x AND NOT x) must be rejected at parse time, not discovered "
        "after 12 rounds",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_BASE,
    ev="cite the existing $defs.stopping_expr in "
    + SCH11
    + " and state exactly which of the 6 "
    "required examples it can and cannot express today.",
)

u(
    "A12",
    "Replay state model: what must be serialised for deterministic replay",
    "What is the minimal serialised state such that a paused council resumes to a byte-identical "
    "transcript, and which sources of nondeterminism (sampling temperature, tool-call ordering, "
    "wall-clock, participant recruitment) must be captured as seeds rather than re-derived?",
    "local-parallel",
    ["A01", "A08"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a replay test: same seed twice yields byte-identical transcripts",
        "a negative control: perturbing ONE captured seed must change the transcript, proving the "
        "seed is actually load-bearing and not decorative",
    ],
    rev=REV_MECH,
    fc=FC_SIM,
    retry=RETRY_SIM,
)

# ---------------- LANE B - participant selection (10) ----------------------
u(
    "B01",
    "Exact roster resolution and capability negotiation on the live estate",
    "When a CouncilSpec names an exact model/vendor seat that is not reachable on this machine, does "
    "the runtime substitute, degrade loudly, or refuse - and what does a live probe of the currently "
    "mounted vendors (anthropic in-session, openai via the codex MCP) actually report today?",
    "local-serialized",
    ["A05"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "probe each declared vendor and record the verbatim reachability result",
        "an unreachable-seat fixture must produce a LOUD degradation record, never a silent "
        "same-vendor substitution",
    ],
    rev=REV_DEFAULT,
    fc=["dependency-blocked", "green-not-live", "overclaim", "detector-failure"],
    inputs=[LIVESKILL, SPEC + ":10983"],
    ev="a live reachability probe (recorded verbatim, no credential values printed) AND a second "
    "independent signal from the mounted-server inventory; per AGENTS.md 9 this unit performs "
    "READ-ONLY credential diagnosis only.",
)

u(
    "B02",
    "Auto-composed council: the selector and its mandatory explanation record",
    "Given only a task description and a risk tier, what algorithm selects roles, protocol, voting "
    "method and stopping rule - and what is the explanation record that makes every auto-chosen dial "
    "individually contestable by the owner rather than a black-box roster?",
    "local-parallel",
    ["A03", "C01"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "for 10 fixture tasks spanning the risk tiers, the selector output plus its explanation "
        "must let a reviewer reconstruct WHY each dial was chosen with no access to the selector",
        "an explanation-completeness check: every dial that differs from the default must carry a "
        "reason, and a missing reason FAILS the unit",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite "
    + SPEC
    + ":10765 (general-purpose auto-composed council that explains every choice).",
)

u(
    "B03",
    "Calibration-ranked selection needs a calibration store that does not exist yet",
    "Calibration-ranked participant selection presupposes a per-participant calibration history - "
    "what is the minimum store schema, how is it populated on cold start without inventing scores, "
    "and what does the selector do for a participant with zero history?",
    "local-parallel",
    ["A05", "H06"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a cold-start fixture: zero-history participants must NOT be ranked as average by default; "
        "the chosen behaviour must be explicit and tested",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_METRIC,
)

u(
    "B04",
    "Expertise-ranked selection: representing expertise without asserting it",
    "How is claimed expertise represented and matched to a task such that the match is checkable, "
    "and what evidence must accompany an expertise claim before the selector may weight it?",
    "local-parallel",
    ["A05"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=["a fabricated-expertise fixture must fail the evidence bar", TESTS_BOTH],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "B05",
    "Random and stratified selection with replay-safe seeding",
    "What is the sampling frame for random and stratified participant selection, and how is the seed "
    "captured so a replayed council draws the identical roster while a fresh run does not?",
    "local-parallel",
    ["A05", "A12"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "same seed -> identical roster; different seed -> different roster (both directions "
        "asserted, because only asserting the first cannot detect a frozen sampler)"
    ],
    rev=REV_MECH,
    fc=FC_SIM,
)

u(
    "B06",
    "Stakeholder-balanced selection: the taxonomy and the balance metric",
    "What stakeholder taxonomy does a balance constraint range over, and what metric decides that a "
    "roster is balanced rather than merely diverse in a way nobody can dispute?",
    "local-parallel",
    ["A05"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "a deliberately unbalanced roster must score worse than a balanced one, and the threshold "
        "must be declared before the fixtures are scored",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_METRIC,
)

u(
    "B07",
    "Model and vendor diversity selection under a real quota ceiling",
    "Cross-vendor seats consume a SECOND paid subscription - what diversity objective is worth that "
    "spend, at what council risk tier does vendor diversity become mandatory rather than optional, "
    "and what happens when the quota for the second vendor is exhausted mid-council?",
    "local-serialized",
    ["A05", "B01"],
    schema=SCHEMA_DESIGN,
    to=1800,
    oa=True,
    tests=[
        "a quota-exhaustion fixture mid-council must degrade loudly and preserve the partial "
        "artifact, never silently re-seat the same vendor twice",
        "a same-base-model-twice roster must be flagged as NOT vendor-diverse",
    ],
    rev=REV_OWNER,
    fc=FC_OWNER,
    retry=RETRY_OWNER,
    ev="cite "
    + SPEC
    + ":10579 (multiple providers for independence) and the standing manual "
    "budget-pacing position; emit NOT-CHECKED for any quota figure not actually measured.",
)

u(
    "B08",
    "Adversarial selection without manufacturing fake disagreement",
    "How do you seat participants with genuinely conflicting priors while preventing the failure "
    "where the council performs disagreement it does not hold - what distinguishes a real prior "
    "conflict from an assigned debating position?",
    "local-parallel",
    ["A05", "D05"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a theatre probe: an assigned-position roster and a real-prior roster must produce "
        "measurably different convergence behaviour; if they do not, the mechanism is unproven",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
)

u(
    "B09",
    "Elastic scaling: mid-council recruitment and catch-up briefing",
    "When a council scales from its minimum to a larger roster mid-run, what does the newcomer see - "
    "and how is a late arrival prevented from either anchoring on the existing consensus or voting "
    "without the context the others earned?",
    "local-parallel",
    ["A05", "A06"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a late-arrival fixture must show the newcomer's first position is NOT correlated with "
        "the standing majority above chance",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_DET,
)

u(
    "B10",
    "Participant replacement and duplicate-independence detection",
    "When a seat dies or is replaced mid-council, what happens to its votes and its ideas - and "
    "separately, how does the runtime detect that two nominally different seats are the same base "
    "model and therefore not independent evidence?",
    "local-parallel",
    ["A05", "B09"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a mid-round death fixture: the council must reach a defined state, not hang",
        "a same-base-model pair must be detected; a genuinely different pair must NOT be flagged "
        "(both directions)",
    ],
    rev=REV_MECH,
    fc=FC_DET,
)

# ---------------- LANE C - roles (8) ---------------------------------------
u(
    "C01",
    "Role mandate schema: obligations vs permissions vs rights",
    "What are the three distinct things a role grants (an obligation the participant MUST discharge, "
    "a permission it MAY use, a right nobody may deny it), and which of the existing $defs.role "
    "fields conflates them?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "an unmet-obligation fixture must fail the role check while an unused permission must not",
        TESTS_SCHEMA,
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite $defs.role in " + SCH11 + " field by field.",
)

u(
    "C03",
    "Vote rights and the provenance of every non-equal weight",
    "Under what conditions may a seat's vote weight differ from 1.0, and what provenance record must "
    "accompany the weight so an auditor can challenge it after the decision is made?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_SPEC,
    to=1800,
    tests=[
        "an unjustified non-equal weight must be rejected at spec validation, before the council "
        "runs",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_BASE,
)

u(
    "C04",
    "Veto rights: scope, override path and abuse detection",
    "What may a veto actually block (an option, a decision, a whole council), what is the override "
    "path when a veto is exercised in bad faith, and how is repeated vetoing distinguished from "
    "principled minority dissent?",
    "local-parallel",
    ["C01", "H02"],
    schema=SCHEMA_DESIGN,
    to=2700,
    oa=True,
    tests=[
        "a serial-vetoer fixture must be distinguishable from a consistent principled dissenter, "
        "with the discriminating feature named",
        TESTS_BOTH,
    ],
    rev=REV_OWNER,
    fc=FC_OWNER,
    retry=RETRY_OWNER,
)

u(
    "C05",
    "Chair powers and capture resistance",
    "What agenda and turn-allocation powers does a chair hold, and what structural limit prevents "
    "moderator capture - given that the chair also writes or approves the synthesis?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a captured-chair fixture (chair systematically favours one position) must be detected by "
        "the declared limit, and an even-handed chair must NOT trip it"
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "C06",
    "Judge and juror separation to remove the single epistemic point of failure",
    "The spec names the moderator or judge becoming a single point of epistemic failure as a "
    "required regression case - what separation of the judge role from the juror role actually "
    "removes that single point of epistemic failure rather than relabelling it?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a corrupted-judge fixture: with the separation in place, one bad judge must NOT be able "
        "to determine the outcome alone; measure how many roles must be corrupted"
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
    ev="cite "
    + SPEC
    + ":11342 and show the corruption threshold as a computed number.",
)

u(
    "C07",
    "Proposer, critic and synthesiser triad mandates",
    "What exactly does each of the three roles owe the council, and what is the rule that stops a "
    "synthesiser from quietly becoming a third critic or a second proposer?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "a role-drift fixture where the synthesiser injects a new proposal must be caught",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_DET,
)

u(
    "C08",
    "Role-template library and the custom-role authoring contract",
    "What is the minimum set of role templates that covers the 58 catalogued protocols, and what "
    "must a user supply to author a custom role that the incompatible-role checker can still reason "
    "about?",
    "local-parallel",
    ["C01", "C09"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "coverage check: every role named across the 58 protocol records maps to a template or is "
        "listed as an explicit gap - counted mechanically, not eyeballed"
    ],
    rev=REV_MECH,
    fc=FC_DUP,
)

u(
    "C09",
    "Incompatible-role and conflict-of-interest checker as a constraint solver",
    "Which role pairs are structurally incompatible on one seat (proposer judging its own proposal, "
    "critic voting on its own objection), and can the check be expressed as constraints a solver "
    "discharges rather than a hand-written if-ladder that silently misses a pair?",
    "worktree-isolated",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "every declared incompatible pair must be rejected AND every compatible pair accepted, "
        "enumerated exhaustively over the template set (mechanical, not sampled)",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_DET,
)

# ---------------- LANE D - topologies (8) ----------------------------------
u(
    "D02",
    "Chair-led topology and agenda control",
    "What does a chair-led topology change about information flow versus a flat council, and at what "
    "roster size does chair-led become necessary rather than merely tidier?",
    "local-parallel",
    ["C05"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "a size-sweep simulation showing where chair-led beats flat on a declared metric, with "
        "the crossover reported as a number"
    ],
    rev=REV_MECH,
    fc=FC_BASE,
)

u(
    "D03",
    "Flat, committee and caucus grouping: when structure helps and when it fragments",
    "Flat peer, committee and caucus are the same topology family at different grouping granularity - "
    "what is the parameter that unifies them, and at what setting does sub-grouping start losing "
    "cross-group information instead of adding parallelism?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a fragmentation probe: measure information that exists in one caucus and never reaches "
        "the plenary; a topology claiming no loss must demonstrate the measurement"
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "D04",
    "Proposer-critic-judge pipeline topology",
    "In a strict pipeline where each stage sees only the previous stage's output, what information is "
    "structurally lost by the time the judge decides, and is that loss the point or a defect?",
    "local-parallel",
    ["C07"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "an information-loss measurement comparing pipeline judge input against full-transcript "
        "judge input on the same fixture"
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "D05",
    "Red/blue adversarial topology with asymmetric mandates",
    "Red and blue are not symmetric (one attacks, one defends) - what asymmetry in budget, evidence "
    "standard and win condition makes the exercise informative rather than a scripted loss for "
    "whichever side was given less time?",
    "local-parallel",
    ["C01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a symmetry-swap control: swapping which side gets the larger budget must not "
        "deterministically swap the winner; if it does, the topology measures budget not truth"
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
)

u(
    "D06",
    "Jury topology: deciders who did not argue",
    "What must a jury see and NOT see, who controls what evidence reaches it, and what stops the "
    "evidence-presenter from becoming the real decision-maker?",
    "local-parallel",
    ["C06", "A06"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a gatekeeper probe: vary only what the presenter forwards and measure how much the "
        "verdict moves; a large movement means the presenter, not the jury, decides"
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "D07",
    "Delphi topology: iterated anonymous estimates with controlled feedback",
    "What feedback is returned between Delphi rounds (median only, full distribution, arguments), and "
    "which choice produces genuine revision rather than regression to the reported median?",
    "local-parallel",
    ["A07"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a herding control: compare estimate variance across rounds under each feedback mode; "
        "collapsing variance with no new evidence is herding, not convergence"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "D08",
    "Pairwise tournament topology: bracket, seeding and tie-break",
    "How are options seeded into a pairwise bracket, and how is the well-known dependence of bracket "
    "outcomes on seeding order prevented from silently determining the winner?",
    "local-parallel",
    ["G08"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a seeding-permutation sweep: run the same option set under N seedings and report how "
        "often the winner changes; a stable claim requires the number"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "D09",
    "Nested subcouncils and council-of-councils fan-in",
    "When nested councils return conflicting verdicts, what is the fan-in rule - and is a parent "
    "council permitted to overrule a child whose evidence it never read?",
    "local-parallel",
    ["D03", "H03"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "a disagreeing-children fixture must reach a defined outcome, including the legitimate "
        "outcome of irreducible disagreement",
        "a parent overruling a child must be forced to cite the child's evidence, tested",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite "
    + SPEC
    + ":11343 (nested councils disagree on completion) as the regression anchor.",
)

# ---------------- LANE E - protocol runtime semantics (13) -----------------
FAMILIES = [
    (
        "E01",
        "DELIBERATIVE",
        6,
        "P01 free-form-moderated-panel, P02 round-robin, P03 fishbowl, P04 consensus-conference, "
        "P05 rotating-chair, P06 nominal-group-technique",
        "For each of the 6 DELIBERATIVE protocol records, what is the executable turn-by-turn runtime "
        "semantics - and which of the 6 cannot be executed as written because its stopping condition "
        "is stated in prose that no evaluator can read?",
    ),
    (
        "E02",
        "ADVERSARIAL",
        7,
        "P07 oxford-debate, P08 red-blue-team, P09 dialectical-inquiry, P10 mandated-devils-advocate, "
        "P11 team-b-competitive-estimate, P12 adversarial-collaboration, P13 hostile-cross-examination",
        "For each of the 7 ADVERSARIAL protocol records, what enforcement makes the attack real rather "
        "than performed - specifically, what artifact must the attacking role produce that a "
        "cooperative participant could not fake?",
    ),
    (
        "E03",
        "JUDICIAL",
        6,
        "P14 judge-and-jury, P15 claim-by-claim-adjudication, P16 grand-jury-threshold, "
        "P17 jury-with-allowed-hung, P18 two-key-dual-control, P19 rfc-last-call",
        "For each of the 6 JUDICIAL protocol records, what is the admissibility standard for evidence "
        "and who rules on admissibility without becoming the decider?",
    ),
    (
        "E04",
        "ANONYMOUS",
        6,
        "P20 delphi-anonymous-rounds, P21 wideband-delphi-estimation, P22 brainwriting-635, "
        "P23 silent-start-pooling, P24 surprisingly-popular-bts, P25 blind-reevaluation",
        "For each of the 6 ANONYMOUS protocol records, at what exact point is anonymity lifted, and "
        "what leaks identity before that point (writing style, tool traces, timing)?",
    ),
    (
        "E05",
        "GENERATIVE",
        7,
        "P26 brainstorming-swarm, P27 design-charrette, P28 morphological-analysis, "
        "P29 triz-contradiction, P30 six-hats-rotation, P31 constraint-relaxation, "
        "P32 counterfactual-council",
        "For each of the 7 GENERATIVE protocol records, what separates a generation round from a "
        "critique round mechanically, and what stops critique from leaking into generation and "
        "suppressing the idea count?",
    ),
    (
        "E06",
        "FORECASTING",
        5,
        "P33 prediction-tournament, P34 scenario-planning, P35 reference-class-planning-poker, "
        "P36 calibration-tournament, P37 pairwise-comparison",
        "For each of the 5 FORECASTING protocol records, what is the resolution criterion and the "
        "scoring rule, and which forecasts in the catalogue are unresolvable as written?",
    ),
    (
        "E07",
        "TRADECRAFT",
        7,
        "P38 analysis-of-competing-hypotheses, P39 key-assumptions-check, "
        "P40 quality-of-information-check, P41 deception-detection, P42 argument-mapping, "
        "P43 premortem, P44 postmortem-5whys-causal",
        "For each of the 7 TRADECRAFT protocol records (structured analytic techniques), what is the "
        "concrete artifact each produces, and which duplicate another family's mechanism under a "
        "different name?",
    ),
    (
        "E08",
        "ENGINEERING-REVIEW",
        7,
        "P45 scientific-peer-review, P46 architecture-review-board, P47 incident-war-room, "
        "P48 kill-the-company (war-game), P49 socratic-interrogation, P50 evidence-clerk-led, "
        "P51 timeboxed-spike-council",
        "For each of the 7 ENGINEERING-REVIEW protocol records, what executable oracle (test, build, "
        "measurement) settles a disputed claim, and which review protocols have no oracle at all?",
    ),
    (
        "E09",
        "META-COMPOSITION",
        7,
        "P52 nested-subcouncils-meta-council, P53 escalation-ladder, P54 cross-vendor-mirrored, "
        "P55 shadow-council, P56 minority-report-mandatory, P57 stopping-rule-tournament, "
        "P58 owner-in-the-loop-stepwise",
        "For each of the 7 META-COMPOSITION protocol records, what are the composition preconditions, "
        "and which pairs of composed protocols conflict on turn control or on stopping?",
    ),
]
E13Q = (
    "What primitives (sequence, splice, nest, repeat-until) compose two protocols into a custom "
    "one, how is divergence-before-convergence enforced as an ordering constraint the composer "
    "cannot accidentally violate, and - measured independently - which protocols named in the "
    "spec's own list have NO card among the 58 (a first pass finds steelman and negotiation "
    "absent) so must be authored rather than composed?"
)
for k, fam, n, art, q in FAMILIES:
    u(
        k,
        "Executable runtime semantics for the %d %s protocols" % (n, fam),
        "Ranging over exactly these %d records, named so no member can fall through a family "
        "mis-assignment (%s): %s" % (n, art, q),
        "local-parallel",
        ["A01", "A10", "C01"],
        schema=SCHEMA_DESIGN,
        to=3600,
        tests=[
            "for every one of the %d records, either an executable turn schedule or an explicit "
            "NOT-EXECUTABLE verdict naming the missing element - counted mechanically against the "
            "family count in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json" % n,
            TESTS_BOTH,
        ],
        rev=REV_MECH,
        fc=FC_DUP,
        ev="enumerate the family members by their P-ids from "
        + PPJ
        + " (family=%s, expected n=%d) "
        "and confirm the count independently before designing; every verdict cites its record id."
        % (fam, n),
    )

u(
    "E10",
    "Turn-taking and speaking-order engine as one shared primitive",
    "Round-robin order, speaking rights, turn length and per-seat speaking quotas are four dials on "
    "one scheduler - what is that scheduler's contract, and what happens to a seat that is entitled "
    "to speak but has nothing to add?",
    "worktree-isolated",
    ["C01", "A08"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a quota-starvation fixture: a dominant seat must be throttled without silencing a "
        "legitimately prolific one; both directions asserted",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "E11",
    "Response obligations and rebuttal depth",
    "When is a participant OBLIGED to respond to a specific argument, how deep may rebuttal chains "
    "go before the depth budget cuts them, and what marks an argument as answered versus ignored?",
    "local-parallel",
    ["E10"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "an ignored-argument fixture: an unanswered obligation must be visible in the argument "
        "graph, not silently dropped at synthesis",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "E12",
    "Steelman enforcement: how do you MEASURE that a steelman happened",
    "Steelman-before-rebuttal is required by the spec - what machine-checkable property distinguishes "
    "a genuine steelman from a one-line concession followed by the prepared attack?",
    "local-parallel",
    ["E11"],
    schema=SCHEMA_DET,
    to=2700,
    tests=[
        "a fake-steelman fixture (token concession) must FAIL the check while a genuine one passes",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
)

u(
    "E13",
    "Protocol composition primitives, phase ordering, and the spec-vs-corpus protocol gap",
    E13Q,
    "worktree-isolated",
    ["E09", "A10"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "a composition that places convergence before divergence must be REJECTED at compile time",
        "every META-COMPOSITION card must be expressible in the primitives or listed as a gap",
        "the spec-vs-corpus protocol gap must be recomputed independently rather than inherited "
        "from this brief: enumerate the spec's named protocols and set-subtract the 58 card names",
    ],
    rev=REV_MECH,
    fc=FC_DUP,
)

# ---------------- LANE F - idea quality (6) --------------------------------
u(
    "F01",
    "Semantic unique-idea counter: the anti-gaming core",
    "What deduplication mechanism decides that two ideas are the SAME idea - and given that lexical "
    "Jaccard was measured to fire at 0.93-1.00 on renames but cannot see a full rewrite, what second "
    "mechanically different signal must corroborate the count before it gates a stopping rule?",
    "worktree-isolated",
    ["A09"],
    schema=SCHEMA_DET,
    to=3600,
    tests=[
        "planted mutants: exact rename, paraphrase, one-parameter fork and full rewrite of the "
        "same mechanism must ALL be caught as duplicates; a genuinely distinct idea must not be",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
    ev="the planted-mutant control is the evidence; report per-mutant-class recall as numbers, and "
    "scope the claim to the classes actually planted (an unplanted class is NOT-CHECKED).",
)

u(
    "F02",
    "Adversarial attack on the unique-idea counter (count gaming)",
    "Acting as an adversary paid per idea, what is the cheapest sequence of trivial variants that "
    "inflates the unique-idea count past 100 while adding no information - and does the F01 counter "
    "survive that attack?",
    "local-parallel",
    ["F01"],
    schema=SCHEMA_DET,
    to=2700,
    tests=[
        "the attack must be EXECUTED against the F01 counter and its result reported as a number; "
        "an attack that was designed but not run is NOT-CHECKED, not a pass"
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
    ev="cite "
    + SPEC
    + ":11339 (100-idea brainstorm satisfies the count with trivial wording "
    "variants) as the named failure this unit must reproduce before claiming a defense.",
)

u(
    "F03",
    "Novelty scoring against a prior-art corpus",
    "Novel relative to WHAT - what prior-art corpus does a novelty score compare against, and how "
    "does the score avoid punishing a correct idea merely because it was already known?",
    "local-parallel",
    ["F01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a known-good idea already present in the corpus must score low on novelty and high on "
        "quality, proving the two axes are separable",
        TESTS_BOTH,
    ],
    rev=REV_DEFAULT,
    fc=FC_METRIC,
)

u(
    "F04",
    "Category taxonomy, coverage and diversity as one measurement",
    "What taxonomy do category targets range over, how is coverage computed against it, and does a "
    "high coverage score distinguish genuine spread from many ideas clustered in one popular "
    "category?",
    "local-parallel",
    ["F01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a clustered fixture (all ideas in 2 categories) must score lower than a spread fixture "
        "at the same raw count",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "F06",
    "Saturation versus quota-filling at the 100-idea target",
    "How does the runtime distinguish REAL idea saturation (the next round adds nothing) from a "
    "council padding to hit a declared number - and which of the two should stop the round?",
    "local-parallel",
    ["F01", "I03"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a padding fixture and a saturated fixture must be told apart by the declared signal, "
        "both directions recorded"
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "F07",
    "Idea ledger schema and per-participant provenance",
    "What does the idea ledger record so that an idea can be traced to its originator, its "
    "duplicates, its supporters and its fate in the final synthesis - and what is the check that no "
    "idea silently disappears between ledger and synthesis?",
    "local-parallel",
    ["F01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a disappearing-idea probe: remove one idea from the synthesis and prove the check "
        "catches the gap",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_DET,
)

# ---------------- LANE G - voting and aggregation (12) ---------------------
u(
    "G01",
    "Synthesis-only mode: when taking no vote is the correct design",
    "For which decision types is a vote actively harmful (it manufactures a number where none exists), "
    "and what does synthesis-only owe the reader in place of a tally?",
    "local-parallel",
    ["C03"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "a fixture where voting and synthesis-only disagree, with the reason attributed to the "
        "method rather than the participants"
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "G02",
    "Majority, supermajority and their interaction with quorum",
    "How do threshold and quorum interact when seats abstain or are replaced mid-council - and can a "
    "supermajority threshold be met by a shrinking denominator rather than by persuasion?",
    "local-parallel",
    ["C03", "B10"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a shrinking-denominator fixture must be detected: the same ballots with fewer seats must "
        "not silently cross the threshold",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "G03",
    "Unanimity and the instant-unanimity suspicion trigger",
    "The spec requires that suspiciously fast unanimity triggers blind re-evaluation - what exactly "
    "is 'suspiciously fast', measured in what units, and what is the false-positive cost when a "
    "council is unanimous because the answer is genuinely obvious?",
    "local-parallel",
    ["C03", "J01"],
    schema=SCHEMA_DET,
    to=2700,
    tests=[
        "both states: a genuinely-obvious fixture must NOT trigger re-evaluation while a "
        "sycophantic one must; report the false-positive rate as a number"
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
    ev="cite "
    + SPEC
    + ":10944 and "
    + SPEC
    + ":11336 - the trigger is mandated, its threshold is not.",
)

u(
    "G04",
    "Consent / no-objection and the admissibility bar for an objection",
    "In a consent decision any objection blocks - so what makes an objection admissible, and what "
    "stops one participant from holding the council hostage with an unfalsifiable concern?",
    "local-parallel",
    ["C03", "C04"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "an unfalsifiable objection must be ruled inadmissible while a concrete counterexample "
        "must stand; both directions"
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
)

u(
    "G05",
    "Ranked-choice tabulation and its known pathologies",
    "What is the exact IRV tabulation procedure including elimination ties, and which pathologies "
    "(non-monotonicity, later-no-harm violation) can actually occur at council roster sizes of 3-15?",
    "cloud-batch",
    ["C03"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a non-monotonicity fixture at a realistic roster size: raising a candidate on one ballot "
        "must be shown either to be harmless or to flip the winner - reported as a worked example, "
        "not a citation"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "G06",
    "Cardinal ballots (approval and score) and cross-participant scale calibration",
    "Approval is score voting restricted to {0,1} - what does the shared cardinal tabulation look "
    "like, and how are scores comparable across participants who anchor their scales differently?",
    "cloud-batch",
    ["C03"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a scale-drift fixture: two participants with identical preferences but different anchors "
        "must not produce a different winner after calibration",
        TESTS_BOTH,
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "G08",
    "Pairwise / Condorcet tabulation and the cycle rule",
    "What is the completion rule when the pairwise matrix contains a Condorcet cycle, and is the "
    "chosen rule declared BEFORE the ballots are seen so it cannot be picked to favour an outcome?",
    "cloud-batch",
    ["C03"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a constructed 3-cycle must be resolved by the declared rule, and swapping in a different "
        "completion rule must be shown to change the winner - proving the choice is load-bearing"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "G09",
    "Weighted voting: weight provenance and post-hoc audit",
    "Given a decided council, can an auditor recompute the outcome under equal weights and see how "
    "much of the decision the weighting alone produced - and is that delta published with the result?",
    "local-parallel",
    ["C03", "G02"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "for every weighted fixture, the equal-weight counterfactual must be computed and "
        "reported; a decision that flips under equal weights must be flagged"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "G10",
    "Bayesian belief aggregation: linear versus logarithmic pooling",
    "Which pooling rule aggregates participant credences, and what does the rule assume about "
    "independence that a council of same-vendor models measurably violates?",
    "cloud-batch",
    ["C03", "J01"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "a correlated-participants fixture must show the pooled confidence is overstated under "
        "the independence assumption, quantified"
    ],
    rev=REV_XV,
    fc=FC_METRIC,
    vendor=XV,
    model=XVM,
)

u(
    "G11",
    "Abstention semantics and strategic-abstention detection",
    "Does an abstention reduce the denominator, count as a no, or park the decision - and how is a "
    "principled abstention (no expertise) told apart from a strategic one (avoiding a recorded "
    "position)?",
    "local-parallel",
    ["G02"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "both directions on the principled-versus-strategic discriminator",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "G12",
    "Delegation and proxy voting without delegation cycles",
    "When a seat delegates its vote, what prevents a delegation cycle and what prevents one "
    "delegate from silently accumulating a controlling share of the weight?",
    "cloud-batch",
    ["G09"],
    schema=SCHEMA_DESIGN,
    to=1800,
    tests=[
        "a constructed delegation cycle must be detected before tabulation",
        "an accumulation fixture must trip a concentration cap",
    ],
    rev=REV_MECH,
    fc=FC_DET,
)

u(
    "G13",
    "Evidence outranks popularity: the executable-test override of a majority",
    "The spec states agreement is not proof and evidence gates outrank popularity - what is the exact "
    "mechanism by which one failing executable test overturns a unanimous vote, and who is permitted "
    "to declare a test load-bearing?",
    "local-parallel",
    ["C03"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "a unanimous-but-refuted fixture: the council votes YES, a test fails, and the recorded "
        "outcome must NOT be YES",
        "a converse control: an irrelevant failing test must not be able to veto a sound decision",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite "
    + SPEC
    + ":11198 (agreement is not proof; evidence gates outrank popularity) and "
    + SPEC
    + ":11244 (consensus that fails executable tests).",
)

# ---------------- LANE H - consensus and outcomes (7) ----------------------
u(
    "H01",
    "What number is 0.95 consensus",
    "The required stopping example says consensus >= 0.95 - consensus of WHAT, computed how, over "
    "which population, and does a 0.95 with one silent participant mean the same as a 0.95 with one "
    "reasoned dissent?",
    "local-parallel",
    ["G02"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "two fixtures that both compute to 0.95 by the naive formula but differ in dissent quality "
        "must be distinguishable by the final definition"
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
    ev="cite "
    + SPEC
    + ":10938; the metric is used as a stopping gate before it is ever defined, "
    "which is the gap this unit closes.",
)

u(
    "H02",
    "Minority report generation and mandatory preservation",
    "What triggers a mandatory minority report, what must it contain to be more than a footnote, and "
    "what structural rule prevents it from being dropped between transcript and final synthesis?",
    "local-parallel",
    ["H01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a dropped-dissent probe: a synthesis omitting a recorded dissent must FAIL the check",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
    ev="cite "
    + SPEC
    + ":11341 (dissent/minority report is dropped) as the regression anchor.",
)

u(
    "H03",
    "Irreducible disagreement: when to stop trying to converge",
    "What distinguishes a disagreement that more rounds would resolve from one that no amount of "
    "deliberation can - and what evidence must accompany an irreducible-disagreement verdict so it is "
    "not simply fatigue relabelled?",
    "local-parallel",
    ["H01", "I09"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "an information-gain trace must be attached: declaring irreducibility while gain is still "
        "positive must FAIL"
    ],
    rev=REV_DEFAULT,
    fc=FC_METRIC,
)

u(
    "H04",
    "Outcome taxonomy: 6 spec variants against the 17-value enum already in use",
    "The spec names 6 outcome variants (decision, conditional decision, no-decision, irreducible "
    "disagreement, dissent-with-minority-report, proof of impossibility) while $defs.outcome in the "
    "v1 schema carries 17 values that all 72 presets already use - are these two taxonomies at "
    "different granularity or genuinely different sets, and what is the mapping (including any value "
    "with no home on either side)?",
    "local-parallel",
    ["A01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a total mapping table computed mechanically: every one of the 17 enum values maps to "
        "exactly one of the 6 variants or is reported as unmapped",
        TESTS_SCHEMA,
    ],
    rev=REV_MECH,
    fc=FC_DUP,
    ev="enumerate the 17 $defs.outcome values from "
    + SCH11
    + " and the 6 variants from "
    + SPEC
    + ":10932 independently before mapping; the p1-floors lane measured 0 values used "
    "outside the enum in either direction - re-derive that rather than inheriting it.",
)

u(
    "H05",
    "Proof of impossibility: what actually constitutes proof",
    "One required stopping expression is proof_of_impossibility == true - what class of evidence "
    "discharges it, and how is 'we could not find it' prevented from being recorded as 'it cannot be "
    "found'?",
    "local-parallel",
    ["I08"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a searched-but-not-exhaustive fixture must FAIL to qualify as proof while an exhaustive "
        "enumeration must pass; both directions"
    ],
    rev=REV_XV,
    fc=FC_DET,
    vendor=XV,
    model=XVM,
)

u(
    "H06",
    "Confidence trajectory and the post-run calibration report",
    "What is recorded per round so that a calibration report can later ask whether stated confidence "
    "tracked correctness - and what resolution source settles that, given most council decisions have "
    "no ground truth for months?",
    "local-parallel",
    ["H01"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a deferred-resolution fixture: the record must remain scoreable after the fact without "
        "the original session",
        "a council with no resolvable outcome must be marked UNSCOREABLE rather than counted as "
        "calibrated",
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
)

u(
    "H07",
    "Decision lineage: decomposing a decision back to the ideas that made it",
    "Can a final recommendation and its action plan be decomposed back through synthesis, votes, "
    "arguments, option cards and claims to the originating ideas - and what link in that chain "
    "(idea -> option card -> claim -> argument -> vote -> decision -> action plan) is missing today "
    "so the trace breaks?",
    "local-parallel",
    ["F07"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a decomposition test over a scripted council: every sentence of the recommendation must "
        "resolve to at least one ledger entry, and an orphan sentence must FAIL the check"
    ],
    rev=REV_MECH,
    fc=FC_DET,
)

# ---------------- LANE I - stopping rules (10) -----------------------------
u(
    "I01",
    "Stopping-expression runtime evaluation semantics",
    "At what cadence is a stopping expression evaluated (mid-turn, end-of-turn, end-of-round), must "
    "it be side-effect free, and what happens when a predicate becomes true and then false again "
    "before the round ends?",
    "worktree-isolated",
    ["A10"],
    schema=SCHEMA_SPEC,
    to=2700,
    tests=[
        "a flapping-predicate fixture must produce a deterministic outcome",
        "an expression with a side effect must be REJECTED, proving purity is enforced not assumed",
    ],
    rev=REV_MECH,
    fc=FC_BASE,
)

u(
    "I02",
    "Minimum deliberation conditions that outrank any early stop",
    "Which floors (minimum rounds, minimum independent briefs, minimum evidence) must hold before ANY "
    "stopping expression may fire, and what is the audit record when a floor blocks a satisfied stop "
    "condition?",
    "local-parallel",
    ["I01"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a satisfied-but-floored fixture must continue and record why",
        "the floor must be provably unable to run forever - a floor with no ceiling is a hang",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="cite "
    + SPEC
    + ":11338 (council stops before minimum deliberation conditions).",
)

STOPS = [
    (
        "I03",
        "unique_ideas >= 100 AND completeness_score >= 0.90",
        "What makes this expression executable end to end - specifically, which component of "
        "completeness_score is not yet defined anywhere, and does the conjunction ever become "
        "satisfiable if the idea counter and the completeness scorer disagree about what an idea is?",
        ["F01", "F04", "I01"],
    ),
    (
        "I04",
        "consensus >= 0.95 AND no_new_objection_rounds >= 2",
        "How is no_new_objection_rounds counted when an objection is restated in different words - "
        "and does the counter reset on a genuinely new objection from a newly recruited participant?",
        ["H01", "I01", "F01"],
    ),
    (
        "I05",
        "unanimity == true OR max_rounds == 12",
        "This disjunction terminates on a timer if persuasion fails - what does the outcome record say "
        "when the timer, not agreement, ended the council, and is that outcome distinguishable from a "
        "real unanimity in downstream consumers?",
        ["G03", "I01"],
    ),
    (
        "I06",
        "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        "Who declares a counterexample load-bearing and who may declare it resolved - and what stops "
        "the same participant from doing both?",
        ["G13", "I01", "C09"],
    ),
    (
        "I07",
        "evidence_saturation == true OR time_minutes >= 180",
        "What measurement establishes evidence saturation rather than search fatigue, and what is the "
        "both-states control proving the saturation detector is not silent in both states?",
        ["I01", "J05"],
    ),
    (
        "I08",
        "proof_of_impossibility == true",
        "What must be on disk for this single-term expression to evaluate true, and what is the "
        "negative control proving it cannot be satisfied by an unsuccessful search?",
        ["I01"],
    ),
]
for k, expr, q, deps in STOPS:
    u(
        k,
        "Executable stopping example: %s" % expr,
        q,
        "worktree-isolated",
        deps,
        schema=SCHEMA_SPEC,
        to=2700,
        tests=[
            "the expression must FIRE on a fixture where it is true and stay SILENT on a fixture "
            "where it is false - a detector silent in both states measures nothing",
            "a parse test proving the expression is accepted by the A10 grammar unchanged",
        ],
        rev=REV_MECH,
        fc=FC_DET,
        retry=RETRY_DETECTOR,
        ev="the expression is quoted verbatim from "
        + SPEC
        + ":10937-10942; cite the line and the "
        "two fixture runs verbatim.",
    )

u(
    "I09",
    "Deadlock detection and the escalation ladder",
    "What signature identifies a deadlocked council (as distinct from a slow but progressing one), "
    "and what is the ordered escalation ladder - recruit, replace, reframe, escalate to owner - with "
    "the trigger for each rung?",
    "local-parallel",
    ["I01", "J05"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a slow-but-progressing fixture must NOT be declared deadlocked; a genuinely stuck one must",
        TESTS_BOTH,
    ],
    rev=REV_XV,
    fc=FC_DET,
)

u(
    "I10",
    "Owner intervention, pause and resume mid-deliberation",
    "What may an owner change mid-council without invalidating the run (adding evidence, extending a "
    "budget) versus what forces a restart (changing the question, replacing the chair) - and where is "
    "that boundary recorded so the audit trail stays honest?",
    "local-serialized",
    ["A12", "A04"],
    schema=SCHEMA_DESIGN,
    to=2700,
    oa=True,
    tests=[
        "an invalidating change must force a recorded restart rather than a quiet continuation",
        "a resumed council must replay to the same state up to the intervention point",
    ],
    rev=REV_OWNER,
    fc=FC_OWNER,
    retry=RETRY_OWNER,
)

# ---------------- LANE J - anti-failure controls (15) ----------------------
JD = [
    (
        "J01",
        "Echo chamber: measuring independence loss",
        "What measurement shows that participants stopped reasoning independently - and can it "
        "distinguish genuine convergence on a correct answer from mutual anchoring?",
        ["A06", "B10"],
        True,
    ),
    (
        "J02",
        "Sycophancy toward the chair or the owner",
        "What signature distinguishes a participant agreeing because the chair said it from one "
        "agreeing because the argument was good, given both produce the same vote?",
        ["C05"],
        True,
    ),
    (
        "J03",
        "Participant dominance and airtime concentration",
        "At what concentration of airtime or accepted-idea share does one participant dominate, and "
        "does throttling the dominant seat improve or degrade decision quality on fixtures?",
        ["E10"],
        False,
    ),
    (
        "J04",
        "Silence and the minimum-engagement floor",
        "What is the difference between a participant with nothing to add and one that has "
        "disengaged, and what does the runtime do about each?",
        ["E10", "A08"],
        False,
    ),
    (
        "J05",
        "Circular debate: information gain per round",
        "How is per-round information gain computed, and what gain threshold means the debate is "
        "circling rather than converging?",
        ["F01"],
        True,
    ),
    (
        "J06",
        "Role collapse: participants behaving identically",
        "What behavioural distance metric shows that the critic has started behaving like the "
        "proposer - and what is the distance between two seats that genuinely agree?",
        ["C07"],
        True,
    ),
    (
        "J07",
        "Missing expertise detection and the recruitment trigger",
        "How does a council notice that nobody present can answer the question, rather than "
        "confidently answering it wrongly - and what triggers recruitment?",
        ["B04", "B09"],
        True,
    ),
    (
        "J08",
        "Strategic voting detection",
        "What pattern in the ballot history indicates a participant voted against its stated "
        "position to influence the tabulation, and can it be distinguished from an honest revision?",
        ["G05", "G11"],
        True,
    ),
    (
        "J09",
        "Evidence-free majority blocker",
        "What is the minimum evidence attachment for a vote to count, and what happens to a majority "
        "assembled entirely from votes that cite nothing?",
        ["G13"],
        False,
    ),
    (
        "J10",
        "Premature convergence and forced re-divergence",
        "What signal shows a council converged before exploring the space, and what re-divergence "
        "intervention actually recovers the lost breadth rather than performing a second round?",
        ["F04", "I02"],
        True,
    ),
    (
        "J11",
        "Endless debate cap and graceful degradation",
        "When a council hits its hard cap without a decision, what is emitted so the work is not "
        "lost - and is that artifact distinguishable from a real no-decision outcome?",
        ["I09", "H04"],
        False,
    ),
    (
        "J12",
        "Lost dissent: diffing the transcript against the synthesis",
        "Which dissent present in the transcript failed to appear in the synthesis - computed as a "
        "diff, not judged by the synthesiser who dropped it?",
        ["H02", "H07"],
        True,
    ),
    (
        "J13",
        "Weak synthesis and circular citation in the argument graph",
        "Which synthesis sentences are unsupported by any edge in the argument graph, and separately, "
        "which citation chains form a cycle that manufactures support out of nothing?",
        ["H07"],
        True,
    ),
    (
        "J15",
        "Hallucinated expertise and hidden conflicts of interest",
        "What probe catches a participant asserting expertise it does not have, and what declaration "
        "plus cross-check catches an undeclared conflict of interest?",
        ["B04", "C09"],
        True,
    ),
    (
        "J16",
        "Prompt injection through participant artifacts and transcripts",
        "A council transcript is fetched content that later stages consume - what boundary treats it "
        "as untrusted DATA, and what is the executable proof that an injected instruction inside a "
        "participant's contribution does not steer a downstream stage?",
        ["A06", "M04"],
        True,
    ),
]
for k, ttl, q, deps, xv in JD:
    u(
        k,
        ttl,
        q,
        "local-parallel",
        deps,
        schema=SCHEMA_DET,
        to=2700,
        tests=[
            "a planted-defect fixture where the pathology IS present: the detector must FIRE",
            "a clean fixture where it is absent: the detector must be SILENT - report the "
            "false-positive rate as a number, not as an adjective",
            "a detector-control step proving the detector can find a KNOWN-PRESENT instance before "
            "any absence is reported",
        ],
        rev=REV_XV,
        fc=FC_DET,
        retry=RETRY_DETECTOR,
        vendor=(XV if xv else "anthropic"),
        model=(XVM if xv else "opus"),
        role="council-anti-failure-detector-designer",
        ev="two mechanically independent signals required: the planted-bad run AND the known-good "
        "run, both recorded verbatim. Per rules/common/single-signal-verification.md a probe that "
        "is silent in both states measures nothing and the unit FAILS.",
        inputs=[S_PROD, S_FAIL, PPJ],
    )

# ---------------- LANE K - presets (16) ------------------------------------
u(
    "K01",
    "A preset is a typed delta over CouncilSpec, not a fork",
    "What is the preset type such that the 20 keys already carried by the 72 catalogued presets "
    "(including editable_dials and default_binding) express a DELTA over a base spec - and what "
    "happens to a preset when the base CouncilSpec version bumps?",
    "worktree-isolated",
    ["A01", "H04"],
    schema=SCHEMA_PRESET,
    to=3600,
    tests=[
        TESTS_SCHEMA,
        "a base-version bump must either migrate every preset or list the ones it cannot, "
        "counted mechanically over all 72",
        "a preset that silently overrides a non-editable dial must be REJECTED",
    ],
    rev=REV_MECH,
    fc=FC_DUP,
    ev="enumerate the 20 preset keys from "
    + PPJ
    + " independently (do not trust this brief's count) "
    "and map each to base / delta / metadata.",
)

u(
    "K02",
    "Preset-protocol binding matrix and the mechanical distinctness proof",
    "Which of the 58 protocols does each of the 72 presets bind, and can >=64 presets be PROVEN "
    "materially distinct by an algorithm over their bound protocol set, role set, voting method and "
    "stopping expression - rather than asserted by reading their names?",
    "local-parallel",
    ["K01"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "the distinctness computation must be an executable script whose output is the pair count "
        "and the nearest-neighbour list; any pair below the distinctness threshold must be named "
        "and either merged or justified",
        "a planted duplicate (a preset copied with a renamed id) must be caught by the same script",
    ],
    rev=REV_MECH,
    fc=FC_DUP,
    ev="the floor is >=64 presets ("
    + SPEC
    + ":10765) against 72 present; report the surviving "
    "distinct count as a computed number and disclose the metric's blind spot inline.",
)

PRESETS = [
    (
        "K03",
        "Generative preset family: 100-idea brainstorm and innovation moonshot",
        "What preset configuration reliably produces 100 genuinely distinct ideas - and how do the "
        "brainstorm and the moonshot presets differ in their novelty-versus-feasibility weighting "
        "rather than merely in their name?",
        ["F01", "F06", "E05"],
        3600,
    ),
    (
        "K04",
        "Gated review-board family: design/plan critique and release go-no-go",
        "These boards all render a verdict against a rubric - what parameterises the family (rubric "
        "source, evidence contract, who may override a FAIL), and at what point does a go-no-go board "
        "stop being the same mechanism as a design critique board?",
        ["E08", "G04"],
        3600,
    ),
    (
        "K06",
        "Anonymous peer-review preset with an author rebuttal round",
        "What does the peer-review preset need that a generic critique board does not - anonymity "
        "lifting, reviewer recruitment, and a bounded author rebuttal - and how is reviewer capture "
        "prevented when only two reviewers are seated?",
        ["E04", "A07"],
        2700,
    ),
    (
        "K07",
        "Code-review tribunal backed by an executable oracle",
        "This is the one review preset with a real oracle - how does a failing test override a "
        "majority of reviewer opinion, and what happens when the test itself is the disputed artifact?",
        ["G13", "E08"],
        2700,
    ),
    (
        "K08",
        "Security red/blue council preset",
        "What asymmetric budgets, evidence standards and win conditions does the red/blue preset set, "
        "and what stops the exercise from concluding that the defended system is secure merely because "
        "red ran out of time?",
        ["D05", "E02"],
        2700,
    ),
    (
        "K09",
        "Incident lifecycle family: live war room and retrospective postmortem",
        "The same root-cause reasoning runs under two very different clocks - what changes between "
        "the live war-room preset (act now, evidence later) and the retrospective root cause / "
        "postmortem one (evidence first, no action pressure), and which of the two may skip the "
        "minimum deliberation floor?",
        ["I02", "E07"],
        2700,
    ),
    (
        "K11",
        "Strategy and constrained prioritisation family",
        "Direction-setting under uncertainty and ranking under a fixed budget are different decisions - "
        "which voting method suits each, and why is ranked-choice a trap for a prioritisation whose "
        "options are not mutually exclusive?",
        ["G05", "G06"],
        2700,
    ),
    (
        "K12",
        "Requirements council: elicitation plus conflict reconciliation",
        "How does the preset separate eliciting what stakeholders want from reconciling requirements "
        "that contradict - and what outcome type does an unreconcilable pair produce?",
        ["B06", "H03"],
        2700,
    ),
    (
        "K13",
        "Normative boards: ethics/legal review and the risk committee",
        "One board asks may we, the other asks how exposed are we - what different evidence standards "
        "and outcome types does each need, and what happens when the legal board says no and the risk "
        "committee says the exposure is acceptable?",
        ["H04", "C04"],
        2700,
    ),
    (
        "K14",
        "Forecasting and expert-elicitation preset with a proper scoring rule",
        "Which proper scoring rule scores the forecasts, what is the resolution source and date, and "
        "what does the preset do with a forecast that can never resolve?",
        ["D07", "E06", "H06"],
        2700,
    ),
    (
        "K15",
        "Jury family: evidence adjudication and benchmark-results jury",
        "Both juries decide on presented evidence - what does the benchmark jury need in addition, "
        "given that a benchmark result is a number an interested party produced and can game?",
        ["D06", "E03"],
        2700,
    ),
    (
        "K16",
        "Multi-interest family: negotiation, mediation, adversarial collaboration and lay panel",
        "These four seat participants with non-aligned interests or no expertise - what distinguishes "
        "negotiation (parties bargain directly) from mediation (a neutral third party reframes "
        "interests), what protects a lay stakeholder panel from being steered by the expert presenting "
        "to it, and what makes adversarial collaboration produce a shared pre-registered test rather "
        "than a split verdict?",
        ["B06", "B08"],
        3600,
    ),
    (
        "K18",
        "Standing watch council: long-running, trigger-woken, low-intensity",
        "A standing council is mostly asleep - what wakes it, what state does it carry between "
        "wakings, and how does it avoid re-litigating a question it already settled six weeks ago?",
        ["A12", "H07"],
        2700,
    ),
    (
        "K19",
        "General-purpose auto-composed council preset (the flagship)",
        "For an arbitrary owner request with no preset named, what does the auto-composer produce, "
        "how does it explain every dial it chose, and what is the owner's one-step override path?",
        ["B02", "K02"],
        3600,
    ),
]
for k, ttl, q, deps, to in PRESETS:
    u(
        k,
        ttl,
        q,
        "local-parallel",
        ["K01"] + deps,
        schema=SCHEMA_PRESET,
        to=to,
        tests=[
            "instantiate the preset against a fixture task and record the resulting roster, "
            "protocol schedule, voting method and stopping expression",
            "a nearest-sibling differential: show the produced profile differs measurably from the "
            "closest existing preset in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, naming that sibling",
            TESTS_SCHEMA,
        ],
        rev=REV_PRESET,
        fc=FC_DUP,
        role="council-preset-designer",
        ev="map the preset to the catalogued C-id(s) it supersedes or extends; a preset with no "
        "sibling named is unproven, and a preset whose differential is only its name is a "
        "mechanism-duplicate and must be merged.",
        inputs=[PPJ, PPM, S_PROD],
    )

# ---------------- LANE L - simulation and calibration design (7) -----------
u(
    "L01",
    "Deterministic scripted-participant simulation harness",
    "What is the fake-participant substrate that makes every later council simulation deterministic - "
    "scripted positions, scripted votes, scripted refusals - and what proves the harness itself is not "
    "the thing under test?",
    "worktree-isolated",
    ["A12", "I01"],
    schema=SCHEMA_SIM,
    to=3600,
    tests=[
        "the harness must reproduce a recorded transcript byte-identically twice",
        "a harness self-test: a deliberately broken runtime must FAIL the harness, proving the "
        "harness is not vacuously green",
    ],
    rev=REV_MECH,
    fc=FC_SIM,
    retry=RETRY_SIM,
    role="council-simulation-designer",
)

u(
    "L02",
    "Role-enforcement and participant-replacement simulation",
    "Does the runtime actually enforce role mandates and survive a mid-round replacement - "
    "demonstrated by a scripted participant that deliberately violates its mandate and one that dies "
    "mid-vote?",
    "local-parallel",
    ["L01", "C01", "B10"],
    schema=SCHEMA_SIM,
    to=2700,
    tests=[
        "the violating participant must be caught; a compliant one must not be flagged",
        "the mid-vote death must reach a defined state within the declared timeout, never a hang",
    ],
    rev=REV_MECH,
    fc=FC_SIM,
    retry=RETRY_SIM,
    role="council-simulation-designer",
)

u(
    "L03",
    "Voting-method differential simulation over one ballot set",
    "Run one fixed set of ballots through every implemented voting method - on how many fixtures do "
    "the methods disagree about the winner, and which method is most sensitive to a single flipped "
    "ballot?",
    "cloud-batch",
    ["L01", "G05", "G06", "G08", "G10"],
    schema=SCHEMA_SIM,
    to=3600,
    tests=[
        "the disagreement rate must be reported as a computed number over a declared fixture set",
        "a single-ballot-flip sensitivity sweep per method, reported as a table",
    ],
    rev=REV_MECH,
    fc=FC_METRIC,
    role="council-simulation-designer",
    ev="this is a MECHANICAL comparison - write and run the tabulator; an LLM judgement of which "
    "method wins is not acceptable evidence here (rules/common/fan-out-contract.md C4).",
)

u(
    "L04",
    "Dissent-preservation simulation with a planted dropped dissent",
    "Given a scripted council containing exactly one dissent, does that dissent survive into the "
    "synthesis - and does the check FAIL when the dissent is deliberately removed?",
    "local-parallel",
    ["L01", "H02", "J12"],
    schema=SCHEMA_SIM,
    to=2700,
    tests=[
        "planted-drop: removing the dissent must turn the check red",
        "control: an intact run must be green - a check green in both states measures nothing",
    ],
    rev=REV_XV,
    fc=FC_SIM,
    retry=RETRY_DETECTOR,
    role="council-simulation-designer",
)

u(
    "L05",
    "Stopping-rule both-states simulation across all six required expressions",
    "For each of the six required stopping expressions, does it fire exactly when true and never when "
    "false - reported as a 6x2 outcome table rather than a summary sentence?",
    "worktree-isolated",
    ["L01", "I03", "I04", "I05", "I06", "I07", "I08"],
    schema=SCHEMA_SIM,
    to=3600,
    tests=[
        "all twelve cells of the 6x2 table must be populated with a verbatim run result; an "
        "unpopulated cell is NOT-CHECKED and blocks the unit"
    ],
    rev=REV_MECH,
    fc=FC_SIM,
    retry=RETRY_SIM,
    role="council-simulation-designer",
)

u(
    "L06",
    "Pause, resume and deterministic replay simulation",
    "Does a council paused at an arbitrary round resume to a byte-identical transcript - and does "
    "perturbing exactly one captured seed change it, proving the replay is real rather than cached?",
    "local-parallel",
    ["L01", "A12", "I10"],
    schema=SCHEMA_SIM,
    to=2700,
    tests=[
        "identical-seed replay must be byte-identical",
        "single-seed perturbation must diverge - asserting only the first cannot detect a frozen "
        "or cached transcript",
    ],
    rev=REV_MECH,
    fc=FC_SIM,
    retry=RETRY_SIM,
    role="council-simulation-designer",
)

u(
    "L07",
    "Council-of-councils fan-in simulation including the disagreement case",
    "When three child councils return two PASS and one REFUTED, what does the parent emit - and does "
    "the simulation prove the parent read the child evidence rather than counting verdicts?",
    "local-parallel",
    ["L01", "D09"],
    schema=SCHEMA_SIM,
    to=3600,
    tests=[
        "a split-children fixture must produce the declared outcome",
        "an evidence-blind parent must be detectable: perturb only the child EVIDENCE while "
        "holding verdicts fixed; a parent whose output does not move is counting votes",
    ],
    rev=REV_XV,
    fc=FC_SIM,
    retry=RETRY_SIM,
    role="council-simulation-designer",
    ev="cite "
    + SPEC
    + ":11343; the fan-in gate rule that a digest is a claim and not a receipt "
    "applies to child councils exactly as to subagents.",
)

# ---------------- LANE M - runtime integration contracts (5) ---------------
u(
    "M01",
    "Council as a first-class workflow type on the SINGLE control plane",
    "The spec forbids importing a second orchestration runtime - what is the council's integration "
    "contract with the existing workflow system such that a council is a workflow type rather than a "
    "parallel engine, and which council capability has no home in the current plane?",
    "local-parallel",
    ["A01", "E13"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "an inventory check: every council capability maps to a workflow primitive or is listed "
        "as a required extension - counted mechanically",
        "a duplicate-control-plane probe: any council feature that would need its own scheduler "
        "must be named explicitly",
    ],
    rev=REV_DEFAULT,
    fc=FC_DUP,
    ev="cite "
    + SPEC
    + ":10727 (do not import a second orchestration runtime) and "
    + SPEC
    + ":10483 (do not create duplicate control planes).",
    inputs=[REPOSKILL, SPEC + ":10727", SPEC + ":10917"],
)

u(
    "M02",
    "Council result against the shared 12-condition completion predicate",
    "Which of the 12 completion conditions can a council output actually satisfy, and for each one it "
    "cannot (independent reviewer PASS, downstream consumers can read it), what is the council-"
    "specific discharge?",
    "local-parallel",
    ["A01", "H07"],
    schema=SCHEMA_DESIGN,
    to=2700,
    tests=[
        "a condition-by-condition table with a discharge or an explicit NOT-APPLICABLE for all 12",
        "a council output missing its sentinel must FAIL the predicate, proving the wiring is live",
    ],
    rev=REV_MECH,
    fc=FC_BASE,
    inputs=[S_PRED, S_2C],
    ev="cite "
    + S_PRED
    + " verbatim for each of the 12 conditions; exit code zero alone is never "
    "success and a plausible digest is not a receipt.",
)

u(
    "M03",
    "Cross-vendor participant adapter boundary and loud degradation",
    "What breaks when a participant vendor lacks a capability the CouncilSpec assumes (tool access, "
    "context length, structured output) - and what is the degradation record that preserves the work "
    "artifact instead of pretending interchangeability?",
    "local-serialized",
    ["B01", "B07"],
    schema=SCHEMA_DESIGN,
    to=2700,
    oa=True,
    tests=[
        "a capability-gap fixture must produce a LOUD degradation record and preserve the partial "
        "artifact",
        "a silent-substitution attempt must be detectable in the audit record",
    ],
    rev=REV_OWNER,
    fc=FC_OWNER,
    retry=RETRY_OWNER,
    ev="cite "
    + SPEC
    + ":10983 (do not pretend full interchangeability; degrade loudly). Live vendor "
    "probing is READ-ONLY per AGENTS.md 9 - never print a credential value.",
    inputs=[SPEC + ":10965-10983", LIVESKILL],
)

u(
    "M04",
    "Audit, replay, privacy and persistence contract for council transcripts",
    "What may a persisted council transcript contain, what must be redacted before it is written, and "
    "what is the executable scan proving no credential or private datum entered a council artifact?",
    "local-serialized",
    ["A12", "A07"],
    schema=SCHEMA_SPEC,
    to=3600,
    oa=True,
    tests=[
        "a planted-secret scan: a transcript seeded with a synthetic token-shaped string must be "
        "caught before persistence; a clean transcript must pass",
        "a retention test proving the declared retention actually deletes",
    ],
    rev=REV_OWNER,
    fc=["owner-blocked", "detector-failure", "overclaim", "green-not-live"],
    retry=RETRY_OWNER,
    role="council-security-and-privacy-designer",
    ev="cite "
    + SPEC
    + ":11345 (credentials or decrypted secrets enter an artifact bundle) and "
    "AGENTS.md 9. Use a SYNTHETIC token-shaped fixture - never a live credential.",
)

u(
    "M05",
    "CLI, SDK and structured builder ergonomics, including invalid-spec errors",
    "Can an owner express all five natural-language goals from the spec (brainstorm until 100 unique "
    "ideas; argue until all agree or 12 rounds; 90 percent consensus with a mandatory minority "
    "report; continue until no new counterexample for two rounds; stop only after an executable test "
    "settles it) - and what does the tool say when the spec they wrote is invalid?",
    "local-parallel",
    ["A10", "K19"],
    schema=SCHEMA_DESIGN,
    to=3600,
    tests=[
        "all five goals must round-trip from natural language to a valid CouncilSpec and back to a "
        "human-readable restatement; a goal that cannot round-trip is a named gap",
        "an invalid spec must produce an error naming the offending path, not a stack trace",
    ],
    rev=REV_DEFAULT,
    fc=FC_BASE,
    ev="the five goals are quoted at "
    + SPEC
    + ":11198; cite the line and show each round-trip.",
)

# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------
keys = [r["key"] for r in R]
assert len(keys) == len(set(keys)), "duplicate lane key: %s" % (
    [k for k in keys if keys.count(k) > 1],
)

idmap = {r["key"]: "CNL-%04d" % (i + 1) for i, r in enumerate(R)}
BUCKETS = {"B01", "B02", "B03"}

units = []
for i, r in enumerate(R):
    uid = "CNL-%04d" % (i + 1)
    deps = []
    for d in r["deps"]:
        if d in BUCKETS:
            deps.append(d)
        else:
            if d not in idmap:
                raise SystemExit("unresolved dep %s in %s" % (d, r["key"]))
            deps.append(idmap[d])
    slug = re.sub(r"[^a-z0-9]+", "-", r["title"].lower()).strip("-")[:58]
    schema = r.get("schema", SCHEMA_DESIGN)
    ext = (
        ".schema.json"
        if schema == SCHEMA_SPEC and r["sub"] == "worktree-isolated"
        else ".md"
    )
    inputs = [SPEC + ":10746-10767", SPEC + ":10915-10946", SCH11, PPJ]
    inputs += [x for x in r.get("inputs", []) if x not in inputs]
    tests = list(r.get("tests", [TESTS_BOTH]))
    tests.append(
        "negative control recorded verbatim: state what the check does on the state it is "
        "meant to reject"
    )
    units.append(
        {
            "id": uid,
            "title": r["title"],
            "phase": "2C",
            "question_or_target": r["q"],
            "inputs": inputs,
            "dependencies": deps,
            "assigned_model_vendor_role": {
                "vendor": r.get("vendor", "anthropic"),
                "model": r.get("model", "opus"),
                "role": r.get("role", "council-systems-designer"),
                "basis": (
                    "cross-vendor independence for a detector/adversarial unit ("
                    + SPEC
                    + ":10579)"
                )
                if r.get("vendor") == XV
                else "feedback_opus_not_sonnet_subagents - Opus for substantive design units",
            },
            "tool_permissions": (
                ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell"]
                if r["sub"] in ("worktree-isolated", "local-serialized")
                else ["Read", "Grep", "Glob", "Write", "Bash"]
            ),
            "execution_substrate": r["sub"],
            "timeout_seconds": r.get("to", 1800),
            "output_path": ART + uid + "-" + slug + ext,
            "output_schema": schema,
            "evidence_requirement": r.get(
                "ev",
                "two mechanically independent signals per rules/common/single-signal-verification.md: "
                "each load-bearing claim cites a file:line or a reproducible command plus its verbatim "
                "output, and the second signal must use a DIFFERENT mechanism (different shell, "
                "different data field, different measurement) than the first.",
            ),
            "tests_required": tests,
            "reviewer_requirement": r.get("rev", REV_DEFAULT),
            "completion_sentinel": "SUCCESS:" + uid,
            "retry_policy": r.get("retry", RETRY_DEFAULT),
            "failure_classification": r.get("fc", FC_BASE),
            "owner_approval_required": bool(r.get("oa", False)),
        }
    )

# ------------------------- self-checks -------------------------------------
FIELDS = [
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
]
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {
    "0",
    "1",
    "2",
    "2A",
    "2B",
    "2C",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7A",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
}

errs = []
for x in units:
    if list(x.keys()) != FIELDS:
        errs.append("%s field set/order mismatch: %s" % (x["id"], list(x.keys())))
    if x["phase"] not in PHASES:
        errs.append("%s bad phase" % x["id"])
    if x["execution_substrate"] not in SUBS:
        errs.append("%s bad substrate" % x["id"])
    if not x["question_or_target"].rstrip().endswith("?"):
        errs.append("%s question_or_target is not a question" % x["id"])
    if len(x["question_or_target"]) < 80:
        errs.append("%s question too short to be exact" % x["id"])
    if not x["inputs"] or not x["dependencies"] or not x["tests_required"]:
        errs.append("%s empty required list" % x["id"])

ids = [x["id"] for x in units]
if len(ids) != len(set(ids)):
    errs.append("duplicate ids")

# acyclicity over intra-slice dependency edges (a cycle deadlocks the scheduler)
_adj = {x["id"]: [d for d in x["dependencies"] if d.startswith("CNL-")] for x in units}
_st = {}


def _cyc(n, path):
    _st[n] = 1
    for m in _adj.get(n, []):
        if _st.get(m) == 1:
            return path + [n, m]
        if _st.get(m) is None:
            r = _cyc(m, path + [n])
            if r:
                return r
    _st[n] = 2
    return None


for _n in _adj:
    if _st.get(_n) is None:
        _c = _cyc(_n, [])
        if _c:
            errs.append("dependency cycle: %s" % " -> ".join(_c))
            break
paths = [x["output_path"] for x in units]
if len(paths) != len(set(paths)):
    errs.append("duplicate output_path")

# near-duplicate scan: token Jaccard over title+question
STOP = set(
    "what which the a an of and or to for is are how does do that this it in on by with "
    "not no its their than then when where who whom whose must may can be been being as at "
    "from into over under after before between one two both each every any all rather "
    "there here so such but if while during against per via given only also more most "
    "less least same different other another such about upon within without across".split()
)


def toks(x):
    return set(
        w
        for w in re.findall(
            r"[a-z0-9]+", (x["title"] + " " + x["question_or_target"]).lower()
        )
        if w not in STOP and len(w) > 2
    )


pairs = []
for i in range(len(units)):
    ti = toks(units[i])
    for j in range(i + 1, len(units)):
        tj = toks(units[j])
        inter = len(ti & tj)
        un = len(ti | tj)
        if un:
            jac = inter / un
            if jac >= 0.42:
                pairs.append(
                    (
                        round(jac, 3),
                        units[i]["id"],
                        units[j]["id"],
                        units[i]["title"][:52],
                        units[j]["title"][:52],
                    )
                )
pairs.sort(reverse=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(units, f, indent=2, ensure_ascii=True)
    f.write("\n")

print("WROTE", OUT)
print("UNITS", len(units))
print("ERRORS", len(errs))
for e in errs[:25]:
    print("  ERR", e)
print("NEAR-DUP PAIRS (jaccard>=0.42):", len(pairs))
for p in pairs[:15]:
    print("  DUP", p)
print("substrate:", dict(Counter(x["execution_substrate"] for x in units)))
print(
    "vendor:", dict(Counter(x["assigned_model_vendor_role"]["vendor"] for x in units))
)
print("owner_gate:", sum(1 for x in units if x["owner_approval_required"]))
print("timeouts:", dict(Counter(x["timeout_seconds"] for x in units)))
print("schemas:", dict(Counter(x["output_schema"].split("/")[-1] for x in units)))
print(
    "dep-fanin top:",
    Counter(d for x in units for d in x["dependencies"]).most_common(6),
)
print("no-dep units:", [x["id"] for x in units if not x["dependencies"]])
sys.exit(1 if errs else 0)
