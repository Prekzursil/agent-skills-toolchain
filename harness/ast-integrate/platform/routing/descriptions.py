#!/usr/bin/env python
"""Phase 8 - "improve descriptions for routing" (`_USER-PROMPTS.md:10953`).

A description is a ROUTING ARTIFACT, not prose. It is read by a matcher, so the
properties that make it good are measurable:

  1. **Trigger coverage** - does it say WHEN to use this? (`Use when ...`, `Triggers ...`)
  2. **Scope negation** - does it say when NOT to? An anti-trigger prevents a
     confusable neighbour from stealing the query, and is the single highest-value
     field the live corpus under-populates (measured: 152/912 records carry one).
  3. **Distinctive vocabulary** - terms that are RARE across the corpus. A description
     built only from corpus-common words ("use", "code", "file", "project") cannot be
     discriminated from its neighbours no matter how good the matcher is.
  4. **Length discipline** - long descriptions are a real, measured context cost on
     this estate: one live skill description is 1,750 chars, 5.9x the corpus median.
     Under this router that cost is already contained (only the byte-capped `card` is
     ever injected), so length is scored as a MATCHING-DILUTION defect, not a context
     one: padding lowers the relative weight of the terms that actually discriminate.

WHAT THIS MODULE DOES *NOT* DO
------------------------------
It does not rewrite descriptions in place. Editing 328 live SKILL.md files from a
routing unit would be an unreviewable mass mutation of the owner's harness, and
`harness-vcs-hygiene.md` makes the repo the source of truth for those trees. Instead
it emits a ranked, evidence-carrying IMPROVEMENT REPORT (`--report`) naming the exact
missing field per capability, and it applies the improvements that are safe and
in-scope: it SYNTHESIZES routing aliases for the platform inventory, which this unit
owns, from structural metadata already in the blueprint/protocol JSON.

The distinction matters: a routing gain that requires editing 328 files the unit does
not own is a recommendation; a routing gain computed from metadata already present is
a deliverable.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .index import Capability, Index

_TOK = re.compile(r"[a-z0-9][a-z0-9+#.]{1,}")

#: Words that carry no routing signal. Kept deliberately small: an aggressive stoplist
#: throws away real domain terms ("test", "build", "review" ARE discriminative here).
STOP = frozenset(
    """a an the and or of to in on for with is are be this that it as at by from your you
i we us our use using used when whether not no into over under via per any all only just
like such than then do does doing help need needs want wants make makes get gets set sets
new add also more most can could should would may might will must its their them what
which who how why where here there about please if but so very really now today
""".split()
)


def tokens(text: str) -> list[str]:
    return [
        t for t in _TOK.findall((text or "").lower()) if t not in STOP and len(t) > 1
    ]


@dataclass(frozen=True)
class DescScore:
    """Per-capability routing-quality score. `total` is 0..1, higher is better."""

    has_trigger: bool
    has_anti_trigger: bool
    distinctive_terms: int
    distinctiveness: float
    chars: int
    length_penalty: float
    total: float
    missing: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "has_trigger": self.has_trigger,
            "has_anti_trigger": self.has_anti_trigger,
            "distinctive_terms": self.distinctive_terms,
            "distinctiveness": round(self.distinctiveness, 4),
            "chars": self.chars,
            "length_penalty": round(self.length_penalty, 4),
            "total": round(self.total, 4),
            "missing": list(self.missing),
        }


#: A term appearing in more than this FRACTION of records is corpus-common and cannot
#: discriminate. 0.02 of 912 records is ~18 records: a term in 19+ capabilities is a
#: domain word, not an identifier.
COMMON_DF_FRACTION = 0.02

#: Description length past which padding starts diluting the discriminative terms.
#: Anchored on the measured corpus median rather than a guess (see `corpus_stats`).
SOFT_CHAR_BUDGET = 400


def corpus_stats(idx: Index) -> dict:
    """Document frequency + length distribution over the whole index."""
    df: Counter[str] = Counter()
    lengths: list[int] = []
    for r in idx.records:
        df.update(set(tokens(r.routing_text)))
        lengths.append(len(r.routing_text))
    lengths.sort()
    n = len(lengths)
    return {
        "n": n,
        "df": df,
        "median_chars": lengths[n // 2] if n else 0,
        "p90_chars": lengths[int(n * 0.9)] if n else 0,
        "max_chars": lengths[-1] if n else 0,
    }


def score(cap: Capability, stats: dict) -> DescScore:
    """Score one capability's description AS A ROUTING ARTIFACT."""
    df: Counter[str] = stats["df"]
    n = max(stats["n"], 1)
    cutoff = max(2, int(n * COMMON_DF_FRACTION))
    toks = set(tokens(cap.routing_text))
    distinctive = {t for t in toks if df.get(t, 0) <= cutoff}
    # Mean IDF over the record's own terms: how sharply this text stands out.
    idf = [math.log(n / max(df.get(t, 1), 1)) for t in toks] or [0.0]
    distinctiveness = sum(idf) / len(idf) / math.log(max(n, 2))

    chars = len(cap.routing_text)
    length_penalty = min(
        1.0, max(0.0, (chars - SOFT_CHAR_BUDGET) / (SOFT_CHAR_BUDGET * 9))
    )

    missing: list[str] = []
    if not cap.triggers:
        missing.append("trigger")
    if not cap.anti_triggers:
        missing.append("anti_trigger")
    if len(distinctive) < 3:
        missing.append("distinctive_vocabulary")
    if length_penalty > 0.5:
        missing.append("length_discipline")

    total = (
        0.30 * bool(cap.triggers)
        + 0.25 * bool(cap.anti_triggers)
        + 0.25 * min(1.0, len(distinctive) / 8.0)
        + 0.20 * min(1.0, distinctiveness * 2.0)
    ) * (1.0 - 0.35 * length_penalty)

    return DescScore(
        has_trigger=bool(cap.triggers),
        has_anti_trigger=bool(cap.anti_triggers),
        distinctive_terms=len(distinctive),
        distinctiveness=distinctiveness,
        chars=chars,
        length_penalty=length_penalty,
        total=total,
        missing=tuple(missing),
    )


# --------------------------------------------------------------------- enrichment

#: Structural field -> the natural-language phrasing a query is likely to use. These
#: are SYNTHESIZED aliases: the platform JSON already declares the fact structurally
#: (`kind`, `family`, `risk_tier`, `classification`), but a query says it in prose.
#: Adding the prose form to routing_text is a description improvement that costs no
#: hand-authored content and touches no file this unit does not own.
STRUCTURAL_ALIASES = {
    "blueprint-flagship": "flagship reference blueprint workflow recipe pipeline",
    "blueprint": "workflow blueprint recipe pipeline orchestration plan",
    "blueprint-meta": "meta workflow workflow-about-workflows generator",
    "blueprint-sub": "reusable subworkflow fragment composable step",
    "blueprint-shared": "shared reusable subworkflow fragment library",
    "blueprint-forged": "fused forged synthesized composite workflow",
    "protocol": "council protocol deliberation panel debate multi-agent review structure",
    "preset": "council preset editable configured panel ready-made deliberation",
    "mcp-server": "mcp server tool family backend integration",
}

CLASSIFICATION_ALIASES = {
    "ADOPT": "adopted recommended proven vetted",
    "DISTILL": "distill borrow pattern partial adopt framing only",
    "REJECT": "rejected not adopted declined superseded do not use",
    "REJECTED": "rejected not adopted declined superseded do not use",
    "BUILD": "build ourselves net-new implement",
    "VENDOR": "vendor third-party dependency import",
}


def enrich(idx: Index) -> int:
    """Append synthesized structural aliases to `routing_text` in place.

    Returns the number of records enriched. Idempotent: an alias already present is
    not re-appended, so calling `enrich` twice cannot inflate term frequencies (which
    would silently skew every IDF in the corpus).
    """
    touched = 0
    for r in idx.records:
        add: list[str] = []
        for key in (r.family, *(r.tags or ())):
            alias = STRUCTURAL_ALIASES.get(str(key))
            if alias:
                add.append(alias)
        alias = CLASSIFICATION_ALIASES.get(str(r.classification).upper())
        if alias:
            add.append(alias)
        if r.cls in ("protocol", "preset") and "council" not in r.routing_text.lower():
            add.append("council deliberation")
        add = [a for a in add if a not in r.routing_text]
        if add:
            r.routing_text = f"{r.routing_text} {' '.join(add)}"
            touched += 1
    return touched


def report(idx: Index, limit: int = 25) -> dict:
    """Ranked improvement report. Worst routing-quality capabilities first."""
    stats = corpus_stats(idx)
    scored = []
    for r in idx.records:
        s = score(r, stats)
        r.desc_quality = s.as_dict()
        scored.append((s.total, r, s))
    scored.sort(key=lambda t: (t[0], t[1].id))

    miss: Counter[str] = Counter()
    for _t, _r, s in scored:
        miss.update(s.missing)
    by_cls: dict[str, list[float]] = {}
    for t, r, _s in scored:
        by_cls.setdefault(r.cls, []).append(t)

    return {
        "corpus": {
            "n": stats["n"],
            "median_routing_chars": stats["median_chars"],
            "p90_routing_chars": stats["p90_chars"],
            "max_routing_chars": stats["max_chars"],
        },
        "mean_score": round(sum(t for t, _r, _s in scored) / max(len(scored), 1), 4),
        "mean_score_by_class": {
            c: round(sum(v) / len(v), 4) for c, v in sorted(by_cls.items())
        },
        "missing_field_counts": dict(miss.most_common()),
        "worst": [
            {
                "id": r.id,
                "score": round(t, 4),
                "missing": list(s.missing),
                "anchor": r.anchor,
            }
            for t, r, s in scored[:limit]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import sys

    from .index import discover

    argv = list(sys.argv[1:] if argv is None else argv)
    idx = discover()
    if not idx.records:
        print("FAILED:routing-descriptions empty-index")
        return 1
    n = enrich(idx)
    rep = report(idx)
    rep["enriched_records"] = n
    print(json.dumps(rep, indent=2))
    print(f"SUCCESS:routing-descriptions enriched={n} mean_score={rep['mean_score']}")
    return 0
