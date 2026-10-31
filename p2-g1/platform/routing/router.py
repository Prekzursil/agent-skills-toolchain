#!/usr/bin/env python
"""Phase 8 ROUTER - fusion, confidence, conflicts, overrides, explanation, fallback.

Implements the remaining spec clauses (`_USER-PROMPTS.md:10948-10963`):
top-k injection with confidence, conflict resolution, user overrides, an explanation of
WHY a capability was selected, and a fallback when none fits.

THREE DESIGN COMMITMENTS WORTH ARGUING WITH
-------------------------------------------
1. **Confidence is MARGIN-based, not score-based.** A high similarity score with six
   equally-high rivals is not confidence, it is a tie. `confidence()` therefore reads
   the gap between the winner and the runner-up (plus absolute strength), so "0.9 but
   ambiguous" and "0.9 and unrivalled" report differently. A score reported as
   confidence is the calibration error that makes top-k injection untrustworthy.

2. **Conflict resolution never deletes a capability.** Superseded/rejected records are
   DEMOTED and annotated, not filtered out. The spec opens with "do not prune
   capabilities merely because they were rarely used"; silently dropping a rejected
   candidate that is the only thing matching a query is the same failure with a
   different justification. `Decision.conflicts` records every demotion so the reasoning
   is auditable instead of invisible.

3. **The fallback is a RECORD, not a shrug.** When nothing clears threshold, the router
   returns `fits=False` plus the near-misses and the reason each fell short. A silent
   empty result teaches nothing; a capability GAP is the single most useful signal for
   deciding what to build next, and `metrics.py` aggregates exactly that.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from . import descriptions, rules, semantic
from .index import CLASS_PRECEDENCE, Capability, Index, discover

# --------------------------------------------------------------------------- tuning

#: Fusion: final = W_RULE * rule_score + W_SEM * semantic_score.
#: Rule-weighted higher because a rule hit is literal evidence (the user typed the
#: name) while a semantic score is an inference.
W_RULE = 0.55
W_SEM = 0.45

# SELECTION IS A TWO-SIGNAL AND-GATE, not a single threshold.
#
# A single scalar cannot serve both jobs, and the measured sweep proves it. Over the
# 57-query set, one threshold traded the two requirements against each other monotonically:
#
#     thr   gold-hit@5   abstain(L3)
#     0.06     0.706        0.000     <- finds things, injects on nonsense
#     0.15     0.647        0.500
#     0.34     0.255        0.833     <- stays quiet, finds almost nothing
#
# The two requirements are answering different questions. "Is anything here relevant AT
# ALL?" is ABSOLUTE (does the query's vocabulary exist in the corpus). "Which of these is
# the right one?" is RELATIVE (does one record stand out from its 911 peers). Collapsing
# them onto one number forces a choice between abstaining and routing.
#
# So a candidate must clear BOTH:
#   * SCORE_FLOOR  - an absolute floor. "Capital of Mongolia" clears it nowhere, so the
#                    fallback fires.
#   * Z_THRESHOLD  - `mu + Z*sd` over this query's own score distribution. A genuine
#                    match stands out from the corpus mean even when its absolute score
#                    is modest, which is the normal case for a multi-term query (no single
#                    record contains every word the user typed).
#
# This mirrors `hooks/semantic-router/route.py:188` (`thr = max(FLOOR, mu + K_SD*sd)`),
# which reached the same conclusion on the same estate. Adopting a proven local design
# beats re-deriving a worse one. Both values below are swept in `derive_thresholds()`.
SCORE_FLOOR = float(os.environ.get("ROUTING_FLOOR") or 0.18)
Z_THRESHOLD = float(os.environ.get("ROUTING_Z") or 4.0)

#: Retained as the legacy single-knob override. When set, it replaces the AND-gate
#: entirely -- used by `derive_thresholds()` to reproduce the sweep above.
SELECT_THRESHOLD: float | None = (
    float(os.environ["ROUTING_THRESHOLD"])
    if os.environ.get("ROUTING_THRESHOLD")
    else None
)

#: Per-class cap inside one decision, so a single class cannot fill the whole k budget.
#: Without it, 328 skill records swamp every query and the 102 blueprints become
#: unreachable -- the exact "cannot select the full repertoire" failure the spec names.
CLASS_CAP = {"skill": 4, "workflow": 3, "candidate": 2, "preset": 2, "protocol": 2}
DEFAULT_CLASS_CAP = 2

#: Conflict resolution operates on the top `max(k*8, WORKING_SET_MIN)` candidates.
#: Large enough that a demoted capability can still be overtaken by a legitimate rival
#: (so the demotion has somewhere to land), small enough that the pairwise sibling check
#: is cheap and the audit trail stays readable.
WORKING_SET_MIN = 40

#: Multiplicative demotions. Applied to score, recorded in `conflicts`.
DEMOTE_SUPERSEDED = 0.35
DEMOTE_REJECTED = 0.55
DEMOTE_REDUNDANT_SIBLING = 0.80

_OVERRIDE_RX = re.compile(
    r"(?:^|\s)(?:use|force|prefer)\s+(?:the\s+)?"
    r"([a-z][a-z0-9._/-]{2,})"
    r"(?:\s+(?:skill|workflow|blueprint|protocol|preset|command|agent|plugin))?",
    re.I,
)
_BAN_RX = re.compile(
    r"(?:^|\s)(?:(?:do\s+not|don't|dont|never|avoid)\s+use\s+(?:the\s+)?|no\s+)"
    r"([a-z][a-z0-9._/-]{2,})",
    re.I,
)


# --------------------------------------------------------------------------- results


@dataclass
class Candidate:
    cap: Capability
    rule_score: float
    sem_score: float
    fused: float
    final: float
    rule_hits: list[rules.RuleHit] = field(default_factory=list)
    demotions: list[str] = field(default_factory=list)
    forced: bool = False

    def why(self) -> str:
        """One-line human explanation of WHY this capability was selected.

        Quotes literal matched evidence when a rule fired; otherwise names the lane and
        says so plainly. It must never imply evidence it does not have -- an unhedged
        "because it matches X" on a pure similarity hit is a fabricated justification.
        """
        parts: list[str] = []
        for h in sorted(self.rule_hits, key=lambda h: -abs(h.weight))[:3]:
            if h.weight > 0:
                parts.append(f"{h.rule}={h.evidence!r} (w={h.weight:.2f})")
        # Report which lane actually CARRIED the decision, not merely which rules
        # fired. A 0.15 class-hint presented as the reason for a selection that was
        # really driven by similarity is a misleading explanation even though every
        # token in it is true -- so the dominant contribution is named explicitly.
        rule_share = W_RULE * self.rule_score
        sem_share = W_SEM * self.sem_score
        if parts and rule_share >= sem_share:
            head = "matched " + ", ".join(parts)
        elif parts:
            head = (
                f"lexical-semantic similarity (sem={self.sem_score:.2f}) carried this; "
                f"weak literal support: " + ", ".join(parts)
            )
        elif self.sem_score > 0:
            head = f"lexical-semantic similarity only (no literal match), sem={self.sem_score:.2f}"
        else:  # pragma: no cover - defensive; a 0/0 candidate never reaches selection
            head = "no positive evidence"
        if self.forced:
            head = "USER OVERRIDE (forced) - " + head
        for d in self.demotions:
            head += f"; demoted: {d}"
        return head

    def as_dict(self) -> dict:
        return {
            "id": self.cap.id,
            "cls": self.cap.cls,
            "invoke": self.cap.invoke,
            "final": round(self.final, 4),
            "rule": round(self.rule_score, 4),
            "semantic": round(self.sem_score, 4),
            "card_bytes": self.cap.card_bytes,
            "why": self.why(),
            "rule_hits": [h.as_dict() for h in self.rule_hits],
            "anchor": self.cap.anchor,
        }


@dataclass
class Decision:
    """One routing decision. Serializable; `to_dict` is the audit record."""

    query: str
    k: int
    fits: bool
    confidence: float
    confidence_band: str
    selected: list[tuple[Capability, float]] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    overrides: dict[str, list[str]] = field(default_factory=dict)
    near_misses: list[dict] = field(default_factory=list)
    fallback: dict | None = None
    #: How the selection cut was computed (floor vs adaptive, mu/sd, which bound bound).
    #: Exposed because "why did nothing get selected" is unanswerable without it.
    threshold_stats: dict = field(default_factory=dict)

    @property
    def injected_bytes(self) -> int:
        return len("\n".join(c.card for c, _s in self.selected).encode("utf-8"))

    @property
    def ids(self) -> list[str]:
        return [c.id for c, _s in self.selected]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "k": self.k,
            "fits": self.fits,
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band,
            "selected": [
                c.as_dict() for c in self.candidates if c.cap.id in set(self.ids)
            ],
            "injected_bytes": self.injected_bytes,
            "conflicts": self.conflicts,
            "overrides": self.overrides,
            "near_misses": self.near_misses,
            "fallback": self.fallback,
            "threshold_stats": self.threshold_stats,
        }


# --------------------------------------------------------------------- confidence

#: Sherman-Kent-aligned bands (AGENTS.md 7). Reported alongside the number so a caller
#: cannot read a bare 0.62 as "probably right" without the calibrated label.
BANDS = (
    (0.80, "almost-certain"),
    (0.55, "likely"),
    (0.40, "roughly-even"),
    (0.22, "unlikely"),
    (0.00, "remote"),
)


def band(x: float) -> str:
    for lo, name in BANDS:
        if x >= lo:
            return name
    return "remote"  # pragma: no cover - BANDS ends at 0.0, so unreachable


def confidence(ranked: list[Candidate], threshold: float) -> float:
    """Margin-aware confidence in the TOP selection.

    strength = how far the winner clears the EFFECTIVE selection cut for this query.
    margin   = how far it clears the runner-up.
    A lone strong hit scores high; a strong hit in a six-way tie does not.

    `threshold` is passed in rather than read from a module global: the cut is now
    per-query (`Router.effective_threshold`), so a global would calibrate confidence
    against a bar that was not the one actually applied.
    """
    if not ranked:
        return 0.0
    top = ranked[0].final
    if top <= 0:
        return 0.0
    runner = ranked[1].final if len(ranked) > 1 else 0.0
    strength = min(1.0, top / max(threshold * 2.0, 1e-9))
    margin = (top - runner) / top if top > 0 else 0.0
    return max(0.0, min(1.0, 0.6 * strength + 0.4 * margin))


# --------------------------------------------------------------------------- router


@dataclass
class Router:
    index: Index
    model: semantic.SemanticModel
    rule_ctx: rules.RuleContext | None = None
    _by_id: dict[str, Capability] = field(default_factory=dict)
    _name_idx: dict[str, list[Capability]] = field(default_factory=dict)

    # ---------------------------------------------------------------- build
    @classmethod
    def build(
        cls,
        index: Index | None = None,
        *,
        enrich: bool = True,
        use_expansion: bool = semantic.EXPANSION_DEFAULT,
        use_ngram: bool = True,
    ) -> Router:
        idx = index if index is not None else discover()
        if enrich:
            descriptions.enrich(idx)
        model = semantic.SemanticModel.fit(
            idx, use_expansion=use_expansion, use_ngram=use_ngram
        )
        name_idx: dict[str, list[Capability]] = {}
        for r in idx.records:
            name_idx.setdefault(r.name.lower(), []).append(r)
            # Also index the bare invoke token ("/reframe" -> "reframe") so an override
            # written the way a user types it resolves.
            name_idx.setdefault(r.invoke.lower().lstrip("/"), []).append(r)
        return cls(
            index=idx,
            model=model,
            rule_ctx=rules.RuleContext.build(idx),
            _by_id=idx.by_id(),
            _name_idx=name_idx,
        )

    # ---------------------------------------------------------------- overrides
    def parse_overrides(self, query: str) -> dict[str, list[str]]:
        """Extract explicit user overrides from the query text.

        Bans are parsed BEFORE forces and win any collision: "use the design-studio
        skill but do not use design-review-loop" must not force the banned one. A
        force-wins policy would let a stale habit phrase override an explicit refusal.
        """
        banned: list[str] = []
        for m in _BAN_RX.finditer(query):
            for cap in self._name_idx.get(m.group(1).lower().lstrip("/"), []):
                if cap.id not in banned:
                    banned.append(cap.id)
        forced: list[str] = []
        for m in _OVERRIDE_RX.finditer(query):
            tok = m.group(1).lower().lstrip("/")
            for cap in self._name_idx.get(tok, []):
                if cap.id not in forced and cap.id not in banned:
                    forced.append(cap.id)
        return {"forced": forced, "banned": banned}

    # ---------------------------------------------------------------- conflicts
    def _apply_conflicts(self, cands: list[Candidate]) -> list[dict]:
        """Demote superseded, rejected, and redundant-sibling candidates in place.

        Never removes. Returns the audit trail.
        """
        log: list[dict] = []
        present = {c.cap.id for c in cands}
        for c in cands:
            cap = c.cap
            if cap.superseded_by:
                c.final *= DEMOTE_SUPERSEDED
                c.demotions.append(f"superseded_by {cap.superseded_by}")
                log.append(
                    {
                        "kind": "superseded",
                        "loser": cap.id,
                        "winner": cap.superseded_by,
                        "action": f"score x{DEMOTE_SUPERSEDED}",
                        "resolved_by": "tombstone declared in the capability's own text",
                    }
                )
            if str(cap.classification).upper() in ("REJECT", "REJECTED"):
                c.final *= DEMOTE_REJECTED
                c.demotions.append(f"registry classification {cap.classification}")
                log.append(
                    {
                        "kind": "rejected-classification",
                        "loser": cap.id,
                        "action": f"score x{DEMOTE_REJECTED}",
                        "resolved_by": "registry verdict; kept reachable, not pruned",
                    }
                )
        # Same-class near-duplicates: when one name is a SEGMENT-BOUNDED PREFIX of
        # another ("reframe" vs "reframe-video-cutting"), the more specific name is the
        # better answer and the generic sibling is redundant context.
        #
        # MEASURED DEFECT: the first version tested bare substring containment
        # (`bn in an`), which fired on `doc` inside `docker-*`, `cs` inside `docs`,
        # `data` inside `database-*` -- 40+ bogus demotions per query, and O(n^2) over
        # ~900 candidates. Requiring `an.startswith(bn + "-")` makes the relation mean
        # what the comment always claimed it meant.
        pos = {c: i for i, c in enumerate(CLASS_PRECEDENCE)}
        for a in cands:
            for b in cands:
                if a is b or a.cap.cls != b.cap.cls:
                    continue
                an, bn = a.cap.name.lower(), b.cap.name.lower()
                if len(bn) < 4 or not an.startswith(f"{bn}-"):
                    continue
                if abs(a.final - b.final) > 0.15:
                    continue
                b.final *= DEMOTE_REDUNDANT_SIBLING
                b.demotions.append(f"less specific than {a.cap.id}")
                log.append(
                    {
                        "kind": "redundant-sibling",
                        "loser": b.cap.id,
                        "winner": a.cap.id,
                        "action": f"score x{DEMOTE_REDUNDANT_SIBLING}",
                        "resolved_by": "name specificity (loser's name is a prefix of the winner's)",
                    }
                )
        for c in cands:
            if c.cap.id in present:
                c.final = max(c.final, 0.0)
            # Deterministic secondary key for equal finals.
            c.rule_score = c.rule_score
        cands.sort(key=lambda c: (-c.final, pos.get(c.cap.cls, 99), c.cap.id))
        return log

    # ---------------------------------------------------------------- route
    def effective_threshold(
        self,
        scores: list[float],
        *,
        threshold: float | None = None,
        floor: float | None = None,
        z: float | None = None,
    ) -> tuple[float, dict]:
        """Resolve the AND-gate to one comparable cut, plus the stats that produced it.

        Returned as a single number because the two conditions are both lower bounds, so
        `max(floor, mu + z*sd)` is exactly equivalent to requiring both -- and keeping it
        as one value means `near_misses` can report a real "short by" distance.
        """
        explicit = SELECT_THRESHOLD if threshold is None else threshold
        if explicit is not None:
            return explicit, {
                "mode": "explicit-single-threshold",
                "threshold": explicit,
            }
        f = SCORE_FLOOR if floor is None else floor
        zz = Z_THRESHOLD if z is None else z
        # Statistics over the WHOLE corpus, including the zero-scoring records. Using
        # only positive-scoring candidates would compute mu/sd over a self-selected
        # population and shift the bar with every query's candidate count.
        n = max(len(self.index.records), 1)
        padded = scores + [0.0] * (n - len(scores))
        mu = sum(padded) / n
        var = sum((x - mu) ** 2 for x in padded) / n
        sd = var**0.5
        adaptive = mu + zz * sd
        return max(f, adaptive), {
            "mode": "and-gate",
            "floor": f,
            "z": zz,
            "mu": round(mu, 5),
            "sd": round(sd, 5),
            "adaptive": round(adaptive, 5),
            "binding": "floor" if f >= adaptive else "adaptive",
        }

    def route(
        self,
        query: str,
        k: int = 5,
        *,
        threshold: float | None = None,
        floor: float | None = None,
        z: float | None = None,
    ) -> Decision:
        ov = self.parse_overrides(query)
        rule_hits = rules.match(query, self.index, self.rule_ctx)
        sem = self.model.score(query)

        cands: list[Candidate] = []
        for cap in self.index.records:
            if cap.id in ov["banned"]:
                continue
            hits = rule_hits.get(cap.id, [])
            rs = rules.score_of(hits) if hits else 0.0
            ss = sem.get(cap.id, 0.0)
            fused = W_RULE * rs + W_SEM * ss
            if fused <= 0 and cap.id not in ov["forced"]:
                continue
            c = Candidate(
                cap=cap,
                rule_score=rs,
                sem_score=ss,
                fused=fused,
                final=fused,
                rule_hits=hits,
            )
            if cap.id in ov["forced"]:
                # A user override is an instruction, not a hint: it bypasses threshold
                # and conflict demotion entirely. Its provenance is recorded so an
                # explanation never presents a forced pick as an inferred one.
                c.forced = True
                c.final = max(c.final, 1.0)
            cands.append(c)

        # WORKING SET. Conflict resolution runs only over the candidates that could
        # plausibly be selected, for two reasons:
        #   (a) correctness of the AUDIT TRAIL -- demoting a capability ranked 400th
        #       is not a "conflict", and logging it buried the three real conflicts
        #       under ~50 irrelevant lines (measured on the first smoke run);
        #   (b) cost -- the sibling check is pairwise, so running it over every
        #       positive-scoring record was ~810k comparisons per query.
        # Anything outside the working set is already far below threshold, so no
        # demotion could have changed the outcome.
        cands.sort(key=lambda c: (-c.fused, c.cap.id))
        working, tail = (
            cands[: max(k * 8, WORKING_SET_MIN)],
            cands[max(k * 8, WORKING_SET_MIN) :],
        )
        conflicts = self._apply_conflicts(working)
        cands = working + tail

        thr, thr_stats = self.effective_threshold(
            [c.final for c in cands], threshold=threshold, floor=floor, z=z
        )

        # top-k with per-class caps and mirror-duplicate suppression
        selected: list[Candidate] = []
        per_cls: dict[str, int] = {}
        taken_equiv: set[str] = set()
        for c in cands:
            if len(selected) >= k:
                break
            if c.final < thr and not c.forced:
                continue
            # A mirror duplicate adds a second card for a capability already injected.
            # MEASURED: 23 such pairs exist in the live inventory (verified equivalent at
            # token-Jaccard >= 0.842, 20 of them exactly 1.000), so this is wasted context
            # by construction, not a judgement call. Suppressed AFTER threshold so the
            # better-scoring copy of the pair is the one that survives.
            if c.cap.equiv_key and c.cap.equiv_key in taken_equiv and not c.forced:
                conflicts.append(
                    {
                        "kind": "equivalent-duplicate",
                        "loser": c.cap.id,
                        "winner": c.cap.equiv_key,
                        "action": "suppressed from injection",
                        "resolved_by": "content-verified mirror of an already-selected capability",
                    }
                )
                continue
            cap_n = CLASS_CAP.get(c.cap.cls, DEFAULT_CLASS_CAP)
            if per_cls.get(c.cap.cls, 0) >= cap_n and not c.forced:
                continue
            per_cls[c.cap.cls] = per_cls.get(c.cap.cls, 0) + 1
            if c.cap.equiv_key:
                taken_equiv.add(c.cap.equiv_key)
            selected.append(c)

        conf = confidence(
            [c for c in cands if c.final >= thr or c.forced] or cands, thr
        )
        fits = bool(selected)
        near = [
            {
                "id": c.cap.id,
                "final": round(c.final, 4),
                "short_by": round(thr - c.final, 4),
                "why_not": f"below selection threshold {thr}",
            }
            for c in cands[: k + 3]
            if c.final < thr
        ][:5]

        fallback = None
        if not fits:
            fallback = self.fallback(query, cands, thr)

        return Decision(
            query=query,
            k=k,
            fits=fits,
            confidence=conf,
            confidence_band=band(conf),
            selected=[(c.cap, c.final) for c in selected],
            candidates=cands,
            conflicts=conflicts,
            overrides=ov,
            near_misses=near,
            fallback=fallback,
            threshold_stats=thr_stats,
        )

    # ---------------------------------------------------------------- fallback
    def fallback(self, query: str, cands: list[Candidate], thr: float) -> dict:
        """Structured no-fit record.

        Names the generic path to take AND the nearest misses, so the caller has
        somewhere to go and the gap is logged for `metrics.capability_gaps()`.
        """
        top = cands[0] if cands else None
        return {
            "fits": False,
            "reason": (
                "no capability cleared the selection threshold"
                if top
                else "no capability produced any positive signal"
            ),
            "threshold": thr,
            "best_score": round(top.final, 4) if top else 0.0,
            "generic_path": [
                "proceed with first-principles tools (Read/Grep/Bash) and no capability injection",
                "if the task recurs, this query is a CAPABILITY GAP - see metrics.capability_gaps()",
            ],
            "nearest": [
                {"id": c.cap.id, "final": round(c.final, 4)} for c in cands[:3]
            ],
            "injected_bytes": 0,
        }

    # ---------------------------------------------------------------- explain
    def explain(self, query: str, k: int = 5) -> str:
        d = self.route(query, k=k)
        lines = [
            f"QUERY: {query}",
            f"CONFIDENCE: {d.confidence:.3f} ({d.confidence_band})   FITS: {d.fits}   "
            f"INJECTED: {d.injected_bytes} B",
        ]
        if d.overrides["forced"] or d.overrides["banned"]:
            lines.append(f"OVERRIDES: {d.overrides}")
        by_id = {c.cap.id: c for c in d.candidates}
        for i, (cap, sc) in enumerate(d.selected, 1):
            lines.append(f"  {i}. {cap.id}  score={sc:.3f}  [{cap.card_bytes} B]")
            lines.append(f"     WHY: {by_id[cap.id].why()}")
            lines.append(f"     CARD: {cap.card}")
        for c in d.conflicts:
            lines.append(
                f"  CONFLICT {c['kind']}: {c.get('loser')} -> {c.get('resolved_by')}"
            )
        if not d.fits:
            lines.append(f"  FALLBACK: {json.dumps(d.fallback)}")
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    r = Router.build()
    if argv and argv[0] == "--explain":
        print(r.explain(" ".join(argv[1:]) or "reframe a video to vertical"))
        return 0
    if argv and argv[0] == "--json":
        print(json.dumps(r.route(" ".join(argv[1:])).to_dict(), indent=2))
        return 0
    print(f"SUCCESS:routing-router units={len(r.index)}")
    return 0


def as_dict(obj: Any) -> dict:  # pragma: no cover - convenience for callers
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)
