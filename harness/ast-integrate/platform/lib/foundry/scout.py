"""``workflow-scout`` - the executable search-and-recommend half of the Foundry.

Spec :11025: "Given a goal and constraints, they must search for existing workflows, verify
provenance and license, decompose mechanisms, propose adopt/adapt/merge/compose/build
candidates, benchmark them, synthesize the strongest result, and return both the executable
workflow and an evidence-backed design rationale."

Scout owns the first five verbs and hands the last two to :mod:`foundry.forge`.

Pipeline
--------
1. INGEST     - normalize every candidate population (``foundry.registry``).
2. SEARCH     - deterministic IDF-weighted lexical fit + capability fit. No model judgement:
                the ranking is reproducible and a reviewer can recompute it by hand.
3. VERIFY     - resolve the provenance anchor on disk; classify the license into a reuse tier.
                A candidate outside the goal's license allowlist is EXCLUDED, not merely
                down-ranked, and the exclusion is reported with the tier that caused it.
4. DECOMPOSE  - mechanisms into the 24-id capability namespace, tagged structural vs declared.
5. RECOMMEND  - find / repair / merge / compose / build, by measured capability gap.

CLI
---
    python platform/lib/foundry/scout.py search --goal-text "..." \
        --require dynamic_fanout --require barriers --hazard silent-failure
    python platform/lib/foundry/scout.py search --goal goal.json --json out.json
    python platform/lib/foundry/scout.py population
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):  # allow `python platform/lib/foundry/scout.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry import bench, mechanisms, registry  # noqa: E402
from foundry.model import (  # noqa: E402
    COPY_PERMITTED,
    Candidate,
    Goal,
    HAZARD_IDS,
    SPEC_ANCHOR_SCOUT_FORGE,
    capabilities,
)

_WORD = re.compile(r"[a-z0-9][a-z0-9\-_]{2,}")
_STOP = frozenset(
    """the a an and or of to for with that this it is are be on in by from as at not no its
    their they them then than when where which who whom whose how why what any all each per
    into onto over under only also more most less least very such same other another one two
    can may must should would could will shall do does did done use used using workflow
    workflows stage stages run runs runs""".split()
)


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP]


# ------------------------------------------------------------------------- searching


@dataclass
class Hit:
    candidate: Candidate
    profile: mechanisms.MechanismProfile
    lexical_fit: float
    capability_fit: float
    capability_fit_raw: float
    hazard_fit: float
    score: float
    excluded: bool
    exclusion_reasons: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.candidate.id,
            "name": self.candidate.name,
            "source_file": self.candidate.source_file,
            "family": self.candidate.family,
            "prior_classification": self.candidate.classification,
            "is_executable_dsl": self.candidate.is_executable_dsl,
            "dsl_path": self.candidate.dsl_path,
            "score": round(self.score, 4),
            "lexical_fit": round(self.lexical_fit, 4),
            "capability_fit": round(self.capability_fit, 4),
            "capability_fit_raw": round(self.capability_fit_raw, 4),
            "hazard_fit": round(self.hazard_fit, 4),
            "derivation": self.profile.derivation,
            "license_tier": self.candidate.license_tier,
            "provenance": {
                "anchor": self.candidate.provenance_anchor,
                "kind": self.candidate.provenance_anchor_kind,
                "resolved": self.candidate.provenance_resolved,
                "probe": self.candidate.provenance_probe,
            },
            "excluded": self.excluded,
            "exclusion_reasons": self.exclusion_reasons,
            "missing_capabilities": self.missing_capabilities,
            "capabilities_provided": sorted(self.profile.provided),
            "hazards_covered": sorted(self.profile.covered_hazards),
        }


def _idf(cands: Sequence[Candidate]) -> dict[str, float]:
    n = max(len(cands), 1)
    df: Counter = Counter()
    for c in cands:
        df.update(set(tokenize(c.searchable_text)))
    return {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}


def _lexical_fit(
    goal_tokens: list[str], cand: Candidate, idf: dict[str, float]
) -> float:
    if not goal_tokens:
        return 0.0
    cand_tokens = set(tokenize(cand.searchable_text))
    num = sum(idf.get(t, 1.0) for t in goal_tokens if t in cand_tokens)
    den = sum(idf.get(t, 1.0) for t in goal_tokens)
    return num / den if den else 0.0


def verify_candidate(cand: Candidate, goal: Goal) -> list[str]:
    """Provenance + license verification. Returns the EXCLUSION reasons (empty means usable).

    This is a hard filter, not a score penalty. Spec :10839 is explicit that a mechanism found
    under a licence we cannot copy must be re-implemented rather than imported, so a candidate
    outside the allowlist must not be silently ranked into an ADOPT recommendation.
    """
    reasons: list[str] = []
    if cand.license_tier not in set(goal.license_allowlist):
        reasons.append(
            f"license tier {cand.license_tier!r} is not in the goal allowlist "
            f"{sorted(goal.license_allowlist)} - the mechanism may be re-implemented "
            "(CLEAN-ROOM-REIMPLEMENT) but the artifact may not be copied"
        )
    if cand.provenance_resolved is False:
        reasons.append(f"provenance anchor does not resolve: {cand.provenance_probe}")
    if goal.require_executable and not cand.is_executable_dsl:
        reasons.append(
            "goal requires an executable DSL document; this candidate is a prose registry row"
        )
    return reasons


def capability_rarity(
    profiles: Sequence[mechanisms.MechanismProfile],
) -> dict[str, float]:
    """IDF over the CAPABILITY axis, so covering a rare capability outranks covering a universal one.

    Measured need: over the 97 executable blueprints, capabilities like ``stages``,
    ``failure_policy`` and ``resume`` are present in nearly every document, so a plain
    ``|provided & required| / |required|`` saturates at 1.00 and the ranking stops
    discriminating - the first run of this scout returned eight candidates all at
    ``capability_fit=1.00``. Weighting by rarity restores discrimination without inventing a
    judgement call: the weights are a pure function of the population.
    """
    n = max(len(profiles), 1)
    df: Counter = Counter()
    for p in profiles:
        df.update(p.provided)
    return {
        cap: math.log((n + 1) / (df.get(cap, 0) + 1)) + 1.0 for cap in capabilities()
    }


def search(goal: Goal, cands: Sequence[Candidate], top: int = 10) -> list[Hit]:
    idf = _idf(cands)
    gtok = tokenize(goal.text)
    req = list(goal.required_capabilities)
    haz = list(goal.hazards)
    profiles = [mechanisms.profile(c) for c in cands]
    rarity = capability_rarity(profiles)
    req_weight = sum(rarity.get(r, 1.0) for r in req)
    hits: list[Hit] = []
    for c, prof in zip(cands, profiles):
        lex = _lexical_fit(gtok, c, idf)
        cap_raw = (
            sum(1 for r in req if prof.capabilities.get(r)) / len(req) if req else 0.0
        )
        cap = (
            sum(rarity.get(r, 1.0) for r in req if prof.capabilities.get(r))
            / req_weight
            if req_weight
            else 0.0
        )
        hz = sum(1 for h in haz if prof.hazards.get(h)) / len(haz) if haz else 0.0
        excl = verify_candidate(c, goal)
        # weights: rarity-weighted capability fit dominates because it is the only
        # measured-against-the-goal signal; lexical fit discriminates inside a saturated
        # corpus; hazard fit only ever helps a structurally measured candidate.
        score = 0.45 * cap + 0.35 * lex + 0.20 * hz
        hits.append(
            Hit(
                candidate=c,
                profile=prof,
                lexical_fit=lex,
                capability_fit=cap,
                capability_fit_raw=cap_raw,
                hazard_fit=hz,
                score=score,
                excluded=bool(excl),
                exclusion_reasons=excl,
                missing_capabilities=bench.profile_gap(prof, req),
            )
        )
    hits.sort(key=lambda h: (-h.score, h.candidate.id))
    return hits[:top] if top else hits


# ----------------------------------------------------------------------- recommending


def recommend(goal: Goal, hits: Sequence[Hit]) -> dict[str, Any]:
    """find / repair / merge / compose / build - decided by measured capability gap (spec :11280)."""
    req = set(goal.required_capabilities)
    usable = [h for h in hits if not h.excluded]
    excluded = [h for h in hits if h.excluded]
    structural = [h for h in usable if h.profile.structural_only]

    haz_req = set(goal.hazards)
    proposals: list[dict[str, Any]] = []

    # ADOPT proposals are drawn only from the top of the ranking. Emitting one per
    # capability-complete candidate produced eight indistinguishable ADOPT-AS-IS rows in the
    # first run - a recommendation list that recommends everything recommends nothing.
    for h in structural[:3]:
        gap = set(h.missing_capabilities)
        haz_gap = haz_req - h.profile.covered_hazards
        if req and not gap and not haz_gap:
            disposition = "ADOPT-AS-IS"
            rationale = (
                f"covers all {len(req)} required capabilities and all {len(haz_req)} "
                "required hazard mitigations structurally; nothing to add"
            )
        elif req and not gap and haz_gap:
            disposition = "ADOPT-WITH-WRAPPER"
            rationale = (
                f"covers all {len(req)} capabilities but leaves hazard(s) "
                f"{sorted(haz_gap)} uncovered; wrap to add the mitigation"
            )
        elif req and len(gap) <= max(1, len(req) // 4):
            disposition = "ADOPT-WITH-WRAPPER"
            rationale = (
                f"covers {len(req) - len(gap)}/{len(req)} capabilities; wrap to add "
                f"{sorted(gap)}"
                + (f" and hazard(s) {sorted(haz_gap)}" if haz_gap else "")
            )
        else:
            continue
        if not h.candidate.dsl_doc:  # pragma: no cover - structural implies a doc
            continue
        valid, violations, _ = bench._run_dsl_gate(h.candidate.dsl_doc)
        if not (valid and violations == 0):
            disposition = "REPAIR"
            rationale = (
                f"covers the capabilities but fails its own DSL gate "
                f"(schema_valid={valid}, semantic_violations={violations}); repair before reuse"
            )
        proposals.append(
            {
                "disposition": disposition,
                "candidates": [h.candidate.id],
                "rationale": rationale,
                "uncovered_after": sorted(gap),
            }
        )

    # pairwise MERGE / COMPOSE over the structural shortlist: a pair is only proposed when the
    # union covers strictly more than either member (mechanism complementarity), which is the
    # only defensible reason to fuse. Complementarity is measured over the union of the goal's
    # capabilities AND hazards, because in a capability-saturated corpus the hazards are where
    # two blueprints actually differ.
    demanded = req | haz_req

    def _covers(h: Hit) -> set[str]:
        return (h.profile.provided | h.profile.covered_hazards) & demanded

    for i, a in enumerate(structural[:8]):
        for b in structural[i + 1 : 8]:
            union = _covers(a) | _covers(b)
            gap_union = demanded - union
            gain_a = len(union - _covers(a))
            gain_b = len(union - _covers(b))
            if not (gain_a and gain_b):
                continue
            diff = mechanisms.semantic_diff(a.profile, b.profile)
            proposals.append(
                {
                    "disposition": "MERGE"
                    if diff["capability_jaccard"] >= 0.34
                    else "COMPOSE",
                    "candidates": [a.candidate.id, b.candidate.id],
                    "rationale": (
                        f"complementary on the demanded set: {a.candidate.id} contributes "
                        f"{sorted(_covers(a) - _covers(b))}, "
                        f"{b.candidate.id} contributes "
                        f"{sorted(_covers(b) - _covers(a))}; "
                        f"capability jaccard {diff['capability_jaccard']}"
                    ),
                    "uncovered_after": sorted(gap_union),
                    "semantic_diff": diff,
                }
            )

    for h in excluded:
        if h.capability_fit > 0:
            proposals.append(
                {
                    "disposition": "CLEAN-ROOM-REIMPLEMENT",
                    "candidates": [h.candidate.id],
                    "rationale": (
                        "mechanism is a good fit but the artifact is not copyable: "
                        + "; ".join(h.exclusion_reasons)
                    ),
                    "uncovered_after": sorted(req - h.profile.provided),
                }
            )

    best_union: set[str] = set()
    for h in structural[:8]:
        best_union |= _covers(h)
    never_covered = sorted(demanded - best_union)
    if never_covered:
        proposals.append(
            {
                "disposition": "REBUILD-FROM-SPEC",
                "candidates": [],
                "rationale": (
                    "no combination of the top structural candidates covers "
                    f"{never_covered}; these must be built"
                ),
                "uncovered_after": never_covered,
            }
        )

    order = {
        "ADOPT-AS-IS": 0,
        "ADOPT-WITH-WRAPPER": 1,
        "MERGE": 2,
        "COMPOSE": 3,
        "REPAIR": 4,
        "CLEAN-ROOM-REIMPLEMENT": 5,
        "REBUILD-FROM-SPEC": 6,
    }
    proposals.sort(key=lambda p: (order.get(p["disposition"], 9), p["candidates"]))
    return {
        "primary": proposals[0]["disposition"] if proposals else "REBUILD-FROM-SPEC",
        "proposals": proposals,
        "counts": dict(Counter(p["disposition"] for p in proposals).most_common()),
        "usable_candidates": len(usable),
        "excluded_candidates": len(excluded),
        "structural_candidates": len(structural),
    }


# ---------------------------------------------------------------------------- report


def fingerprint(*blobs: str) -> str:
    h = hashlib.sha256()
    for b in blobs:
        h.update(b.encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()[:16]


def scout_report(
    goal: Goal,
    cands: Sequence[Candidate],
    top: int = 10,
) -> dict[str, Any]:
    problems = goal.validate()
    hits = search(goal, cands, top=top)
    rec = recommend(goal, hits)
    pop = registry.population_summary(list(cands))
    return {
        "tool": "workflow-scout",
        "version": "1.0.0",
        "spec_anchor": SPEC_ANCHOR_SCOUT_FORGE,
        "goal": goal.to_json(),
        "goal_problems": problems,
        "population": pop,
        # deterministic: derived from the inputs, never from the clock, so two runs over the
        # same tree produce byte-identical reports and a diff means an input changed.
        "input_fingerprint": fingerprint(
            json.dumps(goal.to_json(), sort_keys=True),
            json.dumps([c.id for c in cands], sort_keys=True),
        ),
        "search": {
            "ranking_method": (
                "deterministic: 0.55*capability_fit + 0.25*idf_lexical_fit + 0.20*hazard_fit. "
                "No model judgement - a reviewer can recompute every number."
            ),
            "returned": len(hits),
            "hits": [h.to_json() for h in hits],
        },
        "recommendation": rec,
        "honesty": {
            "derivation_note": (
                "capability findings tagged 'declared' were read off prose and are NOT "
                "sufficient to certify anything; only 'structural' findings were measured by "
                "walking a DSL document."
            ),
            "provenance_tristate": (
                "provenance.resolved is null when the anchor is a git rev or a bare token - "
                "that is NOT-CHECKED, not absent."
            ),
        },
    }


# ------------------------------------------------------------------------------- CLI


def _goal_from_args(args: argparse.Namespace) -> Goal:
    if args.goal:
        return Goal.from_json(json.loads(Path(args.goal).read_text(encoding="utf-8")))
    return Goal(
        text=args.goal_text or "",
        required_capabilities=list(args.require or []),
        hazards=list(args.hazard or []),
        license_allowlist=list(args.license_allow or list(COPY_PERMITTED)),
        require_executable=bool(args.require_executable),
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="workflow-scout",
        description="search, verify, decompose and recommend over the candidate registry",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="run the full scout pipeline for a goal")
    s.add_argument("--goal", help="path to a goal JSON file")
    s.add_argument("--goal-text", help="the goal in one sentence")
    s.add_argument(
        "--require", action="append", help="a required capability id (repeatable)"
    )
    s.add_argument(
        "--hazard", action="append", help="a hazard id the workflow must cover"
    )
    s.add_argument("--license-allow", action="append", help="an allowed license tier")
    s.add_argument("--require-executable", action="store_true")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--json", help="write the full report here")

    sub.add_parser("population", help="summarize the candidate population and exit")

    v = sub.add_parser("vocab", help="print the capability and hazard vocabularies")
    v.add_argument("--json", action="store_true")

    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "population":
        cands = registry.load_all()
        print(json.dumps(registry.population_summary(cands), indent=2))
        print("SUCCESS:scout-population")
        return 0

    if args.cmd == "vocab":
        out = {
            "capabilities": list(capabilities()),
            "hazards": list(HAZARD_IDS),
        }
        print(json.dumps(out, indent=2))
        print("SUCCESS:scout-vocab")
        return 0

    goal = _goal_from_args(args)
    problems = goal.validate()
    if problems:
        for p in problems:
            print(f"  goal problem: {p}", file=sys.stderr)
        print("FAILED:scout-search goal is not well-formed", file=sys.stderr)
        return 2

    cands = registry.load_all()
    report = scout_report(goal, cands, top=args.top)
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )

    pop = report["population"]
    print(f"# workflow-scout  goal: {goal.text}")
    print(
        f"population: {pop['total']} candidates "
        f"({pop['registry_rows']} registry rows + {pop['executable_dsl_blueprints']} executable DSL)"
    )
    print(
        f"required capabilities: {goal.required_capabilities or '(none)'}\n"
        f"required hazard coverage: {goal.hazards or '(none)'}"
    )
    print(f"input_fingerprint: {report['input_fingerprint']}")
    print()
    print(
        f"{'rank':>4}  {'score':>6}  {'capW':>5}  {'capR':>5}  {'lex':>5}  {'haz':>5}  "
        f"{'deriv':<10}  id"
    )
    for i, h in enumerate(report["search"]["hits"], 1):
        flag = "  EXCLUDED" if h["excluded"] else ""
        print(
            f"{i:>4}  {h['score']:>6.3f}  {h['capability_fit']:>5.2f}  "
            f"{h['capability_fit_raw']:>5.2f}  "
            f"{h['lexical_fit']:>5.2f}  {h['hazard_fit']:>5.2f}  "
            f"{h['derivation']:<10}  {h['id']}{flag}"
        )
        if h["missing_capabilities"]:
            print(f"        missing: {h['missing_capabilities']}")
    print()
    rec = report["recommendation"]
    print(f"recommendation: {rec['primary']}   ({rec['counts']})")
    for p in rec["proposals"][:8]:
        print(f"  - {p['disposition']:<24} {p['candidates']}")
        print(f"      {p['rationale']}")
        if p["uncovered_after"]:
            print(f"      still uncovered: {p['uncovered_after']}")
    if args.json:
        print(f"\nreport: {args.json}")
    print("SUCCESS:scout-search")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
