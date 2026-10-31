"""Ranking: independent evidence, cross-domain convergence, severity, decision impact.

THE RANKING RULE, and the thing it is built to REFUSE
----------------------------------------------------
`repetition_count` (how many raw records ended up in a canonical cluster) is COMPUTED and
PUBLISHED but carries WEIGHT ZERO.  Repetition across agents that read the same stale input
is ONE signal, not N.  `test_corpusnorm.py::test_repetition_has_zero_weight` proves it by cloning a
cluster's supporting records 10x and asserting the score is bit-identical; that mutation test
is the only thing that makes this paragraph a claim rather than an intention.

The four scored axes (each 0-3, weights below):

A1 INDEPENDENT EVIDENCE (weight 3) -- how many MECHANICALLY DISTINCT evidence kinds are
   attached, counted once per KIND no matter how many records carry it:
     +1 executed command output (a fenced block containing a shell prompt or a real value)
     +1 a file:line anchor
     +1 a both-states / detector-control / mutation probe
     +1 a second independent probe or cross-vendor confirmation
   Four different kinds on one claim outrank forty records asserting it with none.

A2 CROSS-DOMAIN CONVERGENCE (weight 2) -- how many INDEPENDENT LINEAGES arrive at the
   mechanism.  A lineage is a (record_class, source-document-family) pair, and the two
   anti-repetition corrections are applied BEFORE counting:
     * all records from one source document collapse to one lineage;
     * a document that is a declared consolidation of another (07-OPTION-UNIVERSE.md over the
       five lane docs) does NOT count as a second lineage -- that is the same authors
       re-reading their own output, the exact failure this unit was told to avoid.
   So an option card + an independently-written adversarial verify doc + a lane measurement
   scores 3; the same option restated in the consolidation scores 1.

A3 SEVERITY (weight 2) -- declared severity where the corpus states one, else derived from an
   explicit security/data-loss/unsatisfiable-gate marker, else `unrated` (scores 0, and is
   reported as unrated rather than silently treated as low).

A4 DECISION IMPACT (weight 3) -- does resolving it unblock work:
     +1 flagged OWNER-DECISION / on the grill queue
     +1 named as a dependency by >=1 other claim (dependency in-degree > 0)
     +1 touches a security guard, a credential path, or a gate that other claims gate on
     +1 declared blocker/track-now/MUST-DO-NOW, or an UNSATISFIABLE stopping condition

VERIFICATION STATUS is carried, never folded into the score: a REFUTED claim keeps its rank
so the dead end stays visible instead of silently vanishing (AGENTS.md §3).
"""

from __future__ import annotations

import re

WEIGHTS = {
    "independent_evidence": 3,
    "cross_domain_convergence": 2,
    "severity": 2,
    "decision_impact": 3,
}
REPETITION_WEIGHT = 0  # non-negotiable; asserted by test_repetition_has_zero_weight

_SEV_RANK = {"critical": 3, "high": 3, "medium": 2, "med": 2, "low": 1, "info": 0}

# Executed output appears BOTH inside fenced blocks and as bare prompt lines in this corpus.
# Requiring the fence scored a record citing `$ python probe.py / passed` as carrying zero
# evidence kinds, which is wrong: the prompt line IS the executed-output signal.
_RE_CMD_BLOCK = re.compile(
    r"```[^`]*?(?:^\s*\$ |^\s*>>> |^\s*PS |passed|failed|=== )"
    r"|^\s*\$ \S"
    r"|^\s*PS [A-Z]:"
    r"|\b\d+ passed\b",
    re.M | re.S,
)
_RE_FILELINE = re.compile(r"[\w./-]+\.(?:py|json|md|mjs|js|ps1|sh|ya?ml):\d+")
_RE_BOTHSTATES = re.compile(
    r"both[- ]states|both[- ]directions|detector control|negative control|known[- ]broken|"
    r"mutation|must be RED|red today|green after|control =|control:",
    re.I,
)
_RE_SECOND_PROBE = re.compile(
    r"second(?:,| ) ?(?:mechanically )?independent signal|independent(?:ly)? (?:probe|verif|corrobor|method|reproduc)|"
    r"cross[- ]vendor|two probes|my own tooling|did NOT run the peer",
    re.I,
)
_RE_OWNER = re.compile(
    r"OWNER[- ]?DECISION\W{0,4}(?:YES|yes)|owner decision:?\**\s*YES", re.I
)
_RE_SECURITY = re.compile(
    r"security guard|credential|secret|deny\.py|no-force-push|junction|crcp|git-crypt|"
    r"privilege|exfil|redact",
    re.I,
)
_RE_BLOCKER = re.compile(
    r"\bblocker\b|MUST DO NOW|track:? *now|unsatisfiable|BLOCKS:|gate(?:s)? (?:on|the)|"
    r"cannot proceed|fail-closed",
    re.I,
)
_RE_DATALOSS = re.compile(
    r"data loss|deletes? \d+|wipe|truncat|destroy|silently delet|drops? \d+ live|0 bytes",
    re.I,
)
_RE_UNSAT = re.compile(
    r"unsatisfiable|impossible by construction|can never|unreachable by construction",
    re.I,
)


def score_independent_evidence(texts: list[str]) -> tuple[int, list[str]]:
    """Count DISTINCT evidence KINDS across a cluster (once per kind, not per record)."""
    blob = "\n".join(texts)
    kinds = []
    if _RE_CMD_BLOCK.search(blob):
        kinds.append("executed-command-output")
    if _RE_FILELINE.search(blob):
        kinds.append("file-line-anchor")
    if _RE_BOTHSTATES.search(blob):
        kinds.append("both-states-or-mutation-control")
    if _RE_SECOND_PROBE.search(blob):
        kinds.append("second-independent-probe")
    return min(len(kinds), 3), kinds


def lineage_of(
    source_file: str,
    record_class: str,
    consolidation_parent: str,
    children: tuple[str, ...],
) -> str:
    """Collapse a record to its INDEPENDENT lineage key.

    The consolidation parent is folded onto its children so that restating an option in the
    consolidated universe does not manufacture a second lineage.
    """
    fam = source_file
    if source_file == consolidation_parent:
        fam = "07-OPTIONS-lanes"
    elif source_file in children:
        fam = "07-OPTIONS-lanes"
    return f"{record_class}@{fam}"


def score_convergence(lineages: set[str]) -> int:
    return min(len(lineages), 3)


def score_severity(sev_raw: list[str], texts: list[str]) -> tuple[int, str]:
    best, label = -1, "unrated"
    for s in sev_raw:
        r = _SEV_RANK.get((s or "").lower())
        if r is not None and r > best:
            best, label = r, (s or "").lower()
    if best >= 0:
        return best, label
    blob = "\n".join(texts)
    if _RE_DATALOSS.search(blob) or _RE_SECURITY.search(blob):
        return 3, "derived-high (data-loss or security marker)"
    if _RE_UNSAT.search(blob):
        return 2, "derived-medium (unsatisfiable construct)"
    return 0, "unrated"


def score_decision_impact(
    texts: list[str], in_degree: int, classes: set[str]
) -> tuple[int, list[str]]:
    blob = "\n".join(texts)
    reasons = []
    n = 0
    if _RE_OWNER.search(blob) or "grill" in classes:
        n += 1
        reasons.append("owner-decision-or-grill-queue")
    if in_degree > 0:
        n += 1
        reasons.append(f"dependency-in-degree={in_degree}")
    if _RE_SECURITY.search(blob):
        n += 1
        reasons.append("security-or-credential-surface")
    if _RE_BLOCKER.search(blob) or _RE_UNSAT.search(blob):
        n += 1
        reasons.append("declared-blocker-or-unsatisfiable")
    return min(n, 3), reasons


def composite(axes: dict[str, int]) -> int:
    return sum(WEIGHTS[k] * v for k, v in axes.items() if k in WEIGHTS)


MAX_COMPOSITE = sum(w * 3 for w in WEIGHTS.values())


def normalise_confidence(raw: str) -> dict:
    """Sherman-Kent band -> {band, low, high}.  Never invents a band that is not stated."""
    if not raw:
        return {"band": "unstated", "low": None, "high": None}
    low = raw.lower()
    m = re.search(r"(\d{2})\s*[-–]\s*(\d{2})", low)
    lo, hi = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    for band, default in (
        ("almost certain", (90, 99)),
        ("almost-certain", (90, 99)),
        ("likely", (55, 80)),
        ("roughly even", (45, 55)),
        ("roughly-even", (45, 55)),
        ("even", (45, 55)),
        ("unlikely", (20, 45)),
        ("remote", (1, 20)),
    ):
        if band in low:
            return {
                "band": band.replace(" ", "-"),
                "low": lo if lo is not None else default[0],
                "high": hi if hi is not None else default[1],
            }
    if lo is not None:
        return {"band": "numeric-only", "low": lo, "high": hi}
    return {"band": "unstated", "low": None, "high": None}


_VERDICT_MAP = {
    "CONFIRMED": "CONFIRMED",
    "CONFIRMED-BY-JOIN": "PARTIAL",
    "REFUTED": "REFUTED",
    "PARTIAL": "PARTIAL",
    "PARTIALLY-CONFIRMED": "PARTIAL",
    "NOT-CHECKED": "NOT-CHECKED",
    "NOT CHECKED": "NOT-CHECKED",
    "UNVERIFIED": "NOT-CHECKED",
    "BLOCKED": "BLOCKED",
    "SUPERSEDED": "SUPERSEDED",
    "DECIDED": "DECIDED",
    "UNSTATED": "NOT-CHECKED",
}


def normalise_verification(verdicts: list[str], classes: set[str]) -> str:
    """Cluster verification status.

    Precedence is deliberate: REFUTED beats CONFIRMED, because a cluster containing a
    refutation must not present as verified just because another record asserts it.
    A design-only record class never reports CONFIRMED -- it was never executed.
    """
    norm = {_VERDICT_MAP.get((v or "").upper(), "NOT-CHECKED") for v in verdicts if v}
    for pref in ("REFUTED", "BLOCKED", "PARTIAL", "CONFIRMED", "DECIDED", "SUPERSEDED"):
        if pref in norm:
            if pref == "CONFIRMED" and classes <= {
                "option_universe",
                "option_lane",
                "blueprint",
                "protocol",
                "preset",
                "council_card",
                "mechanism_card",
                "arch_candidate",
                "archaeology",
            }:
                return "DESIGN-ONLY"
            return pref
    if classes <= {
        "option_universe",
        "option_lane",
        "blueprint",
        "protocol",
        "preset",
        "council_card",
        "mechanism_card",
        "arch_candidate",
        "archaeology",
    }:
        return "DESIGN-ONLY"
    return "NOT-CHECKED"
