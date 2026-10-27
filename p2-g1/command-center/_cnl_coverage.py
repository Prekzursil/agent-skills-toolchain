#!/usr/bin/env python3
"""Coverage probe: do the 128 CNL units actually cover the spec's own enumerations?

Mechanical set-membership, not judgement. Any term with no hit is reported as a
NAMED GAP rather than folded into a pass.
"""

import json

P = "C:/Users/Prekzursil/source/ast-integrate/command-center/catalog-slices/CNL-1.json"
U = json.load(open(P, encoding="utf-8"))

BLOB = " ".join(
    (
        x["title"]
        + " "
        + x["question_or_target"]
        + " "
        + " ".join(x["tests_required"])
        + " "
        + x["evidence_requirement"]
        + " "
        + x["reviewer_requirement"]
    ).lower()
    for x in U
)


def hits(term):
    """A term counts as covered if any of its alternates appears."""
    for alt in term.split("|"):
        if alt.strip().lower() in BLOB:
            return True
    return False


GROUPS = {
    "decision/voting methods (spec 10930)": [
        "synthesis-only",
        "majority",
        "supermajority",
        "unanimity",
        "consent|no-objection",
        "ranked-choice",
        "score",
        "approval",
        "pairwise|condorcet",
        "juror",
        "judge",
        "weighted",
        "bayesian",
        "veto",
        "quorum",
        "abstention",
        "delegation",
    ],
    "topologies (spec 10926)": [
        "flat",
        "chair-led",
        "committee",
        "caucus",
        "proposer-critic-judge",
        "red/blue",
        "jury",
        "delphi",
        "pairwise tournament",
        "subcouncil",
        "council-of-councils",
    ],
    "protocols (spec 10927)": [
        "blind independent first pass|blind first pass",
        "brainstorm",
        "round-robin",
        "nominal-group",
        "socratic",
        "oxford",
        "cross-examination",
        "steelman",
        "premortem",
        "scenario",
        "war-game|war game",
        "six-hats",
        "fishbowl",
        "betting|prediction",
        "negotiation",
        "mediation",
        "jury",
        "custom",
    ],
    "anti-failure controls (spec 10944 / 11227)": [
        "echo chamber",
        "sycophan",
        "dominance",
        "silence",
        "circular",
        "role collapse",
        "missing expertise",
        "strategic vot",
        "evidence-free",
        "premature convergence",
        "endless debate",
        "count gaming|trivial variant",
        "lost dissent|dropped",
        "weak synthesis",
        "circular citation",
        "hallucinated expertise",
        "conflict of interest",
        "prompt injection",
        "instant unanimity|suspiciously fast|fast unanimity",
    ],
    "outcomes (spec 10932)": [
        "dissent",
        "minority report",
        "irreducible disagreement",
        "no-decision",
        "conditional",
        "proof of impossibility|proof_of_impossibility",
    ],
    "artifacts (spec 10933)": [
        "transcript",
        "idea catalog|idea ledger",
        "option card",
        "argument graph",
        "evidence map|evidence",
        "vote history|ballot history",
        "confidence",
        "decision lineage",
        "action plan",
        "unresolved",
        "resumable|resume",
    ],
    "selection modes (spec 10923)": [
        "exact",
        "automatic|auto-compos",
        "calibration-ranked",
        "expertise-ranked",
        "random",
        "stratified",
        "stakeholder-balanced",
        "model-diverse|vendor diversity",
        "adversarial selection|adversarial",
    ],
    "required stopping examples (spec 10937-10942)": [
        "unique_ideas >= 100",
        "consensus >= 0.95",
        "unanimity == true",
        "quality_gate == pass",
        "evidence_saturation == true",
        "proof_of_impossibility == true",
    ],
    "budget dials (spec 10928)": [
        "effort",
        "time",
        "token",
        "tool call",
        "source",
        "experiment",
        "turn",
        "speaking quota",
        "minimum engagement",
        "inactivity",
        "rebuttal depth",
        "escalation",
    ],
    "targets (spec 10929)": [
        "unique-idea|unique_ideas|unique idea",
        "categor",
        "novelty",
        "diversity",
        "coverage",
        "objection",
        "counterexample",
        "evidence",
    ],
    "named presets (spec 11200-11225)": [
        "100-idea|100 unique ideas",
        "architecture review|design/plan critique|design critique",
        # term-list fix (disclosed): the slice writes "peer-review" hyphenated, so the
        # space-only form was a DETECTOR artifact, not a content gap.
        "peer review|peer-review",
        "code-review tribunal|code review",
        "red/blue",
        "war room",
        "root-cause|root cause",
        "strategy",
        "requirements",
        "plan critique|plan-review|plan review",
        "release",
        "ethics|legal",
        "risk committee|risk",
        "prioritis|prioritiz",
        "forecast",
        "stakeholder",
        "negotiation",
        "adversarial collaboration",
        "evidence adjudication|adjudication",
        "benchmark",
        "moonshot",
        "postmortem",
        "standing watch",
        "auto-composed",
    ],
    "council regression failure classes (spec 11335-11344)": [
        "collapse into one viewpoint|role collapse",
        "instant unanimity|fast unanimity",
        "loops forever|endless debate",
        "minimum deliberation",
        "trivial wording variant|trivial variant",
        "ignores evidence|evidence-free",
        "minority report",
        "single point of epistemic failure",
        "nested councils disagree|disagreeing-children|split-children",
        "injects instructions|prompt injection",
    ],
}

total = 0
covered = 0
gaps = []
print("COVERAGE OF SPEC ENUMERATIONS BY THE 128-UNIT SLICE")
print("=" * 62)
for g, terms in GROUPS.items():
    c = [t for t in terms if hits(t)]
    m = [t for t in terms if not hits(t)]
    total += len(terms)
    covered += len(c)
    print("%-52s %2d/%2d" % (g, len(c), len(terms)))
    for t in m:
        gaps.append((g, t))
print("=" * 62)
print(
    "TOTAL: %d/%d spec-enumerated terms present (%.1f%%)"
    % (covered, total, 100.0 * covered / total)
)
if gaps:
    print("\nNAMED GAPS (reported, not folded into a pass):")
    for g, t in gaps:
        print("  GAP  [%s] %s" % (g, t))
else:
    print("\nNo gaps in the probed enumerations.")

# DETECTOR CONTROL: the probe must report a gap for a term that is genuinely absent.
sentinel = "quantum annealing tie-break"
print(
    "\nDETECTOR CONTROL: known-absent sentinel %r -> hit=%s (must be False)"
    % (sentinel, hits(sentinel))
)
known_present = "minority report"
print(
    "DETECTOR CONTROL: known-present term %r -> hit=%s (must be True)"
    % (known_present, hits(known_present))
)

# which units carry an owner gate, for the orchestrator
print("\nOWNER-GATED UNITS (owner_approval_required=true):")
for x in U:
    if x["owner_approval_required"]:
        print("  %s  %s" % (x["id"], x["title"][:76]))

# startable-today set (only bucket deps, no intra-slice deps)
ready = [x["id"] for x in U if not any(d.startswith("CNL-") for d in x["dependencies"])]
print(
    "\nUNITS WITH NO INTRA-SLICE DEPENDENCY (start as soon as B02 lands): %d %s"
    % (len(ready), ready)
)

# longest dependency chain within the slice
dep = {x["id"]: [d for d in x["dependencies"] if d.startswith("CNL-")] for x in U}
memo = {}


def depth(n):
    if n in memo:
        return memo[n]
    memo[n] = 1 + max([depth(m) for m in dep[n]] or [0])
    return memo[n]


d = {n: depth(n) for n in dep}
mx = max(d.values())
print(
    "LONGEST INTRA-SLICE DEPENDENCY CHAIN: %d levels; deepest: %s"
    % (mx, [n for n in d if d[n] == mx])
)
print(
    "units per level:",
    {lv: sum(1 for v in d.values() if v == lv) for lv in sorted(set(d.values()))},
)
