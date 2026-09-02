"""Deterministic synthetic catalogues for TST-0240.

Every catalogue of size N plants the same five query-relevant capabilities
and N-5 distractors with long unique bodies. Top-k injection should stay
flat; flood injection should grow with N and blow the ceiling.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.inject import (  # noqa: E402
    CEILING_TOKENS,
    DEFAULT_K,
    POLICY_FLOOD,
    POLICY_TOPK,
    Capability,
    inject,
)

QUERY = (
    "review this git commit for leaked secrets and credential files "
    "before merge"
)

SIZES = (10, 60, 110, 160, 210, 500)
ADD50_BASE = 10
ADD50_PLUS = 60  # exactly +50 installed capabilities

RELEVANT_SPECS = (
    (
        "skill.git-secrets",
        "Git secrets review",
        "review git commit leaked secrets credential files before merge",
    ),
    (
        "skill.cred-scan",
        "Credential file scanner",
        "credential files secrets scan git commit leaked tokens",
    ),
    (
        "skill.merge-gate",
        "Merge secret gate",
        "before merge review git commit for leaked secrets",
    ),
    (
        "skill.token-leak",
        "Token leak hunter",
        "leaked secrets credential files git commit review",
    ),
    (
        "skill.pre-merge-secrets",
        "Pre-merge secrets check",
        "git commit review leaked secrets credential files merge",
    ),
)

_FILLER = (
    "anise basil chive dill elder fennel ginger hyssop indigo jasmine "
    "kale lemon mint nutmeg oregano parsley quinoa radish saffron thyme "
    "ume vanilla walnut yarrow zucchini almond barley cacao durian "
    "endive fig guava honey iceberg jicama kelp lentils mango nori "
    "olive papaya quinoa rhubarb sesame tamarind ugli vetiver wasabi "
    "xigua yogurt zaatar"
).split()


def _body(cap_id: str, words: int = 140) -> str:
    seq = []
    n = len(_FILLER)
    seed = sum(ord(ch) for ch in cap_id) * 17 + 3
    for i in range(words):
        seq.append(_FILLER[(seed + i * 13) % n])
        if (i + 1) % 12 == 0:
            seq.append(f"{cap_id}-para-{i}")
    return " ".join(seq) + "."


def relevant_caps() -> list[Capability]:
    out = []
    for cid, name, desc in RELEVANT_SPECS:
        out.append(
            Capability(
                id=cid,
                name=name,
                description=desc,
                body=_body(cid, 160),
            )
        )
    return out


def build_catalog(n: int) -> list[Capability]:
    if n < len(RELEVANT_SPECS):
        raise ValueError(f"n={n} smaller than planted relevant set")
    caps = relevant_caps()
    for i in range(n - len(caps)):
        cid = f"skill.filler.{i:04d}"
        caps.append(
            Capability(
                id=cid,
                name=f"Unrelated cookbook {i}",
                description=(
                    f"unrelated pasta baking recipe number {i} "
                    "herb garden notes with no git secrets"
                ),
                body=_body(cid, 140),
            )
        )
    return caps


def measure_n(n: int, *, policy: str = POLICY_TOPK) -> dict:
    result = inject(QUERY, build_catalog(n), k=DEFAULT_K, policy=policy)
    d = result.as_dict()
    d.pop("block", None)
    d["block_chars"] = len(result.block)
    d["n"] = n
    return d


def growth_curve(sizes: tuple[int, ...] = SIZES) -> list[dict]:
    return [measure_n(n, policy=POLICY_TOPK) for n in sizes]


def loglog_slope(ns: list[int], tokens: list[int]) -> float:
    if len(ns) != len(tokens) or len(ns) < 2:
        raise ValueError("need paired n and tokens")
    if any(v <= 0 for v in ns + tokens):
        raise ValueError("n and tokens must be positive")
    lx = [math.log(x) for x in ns]
    ly = [math.log(y) for y in tokens]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    num = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
    den = sum((x - mx) ** 2 for x in lx)
    if den == 0:
        return 0.0
    return num / den


def add50_control() -> dict:
    small = measure_n(ADD50_BASE, policy=POLICY_TOPK)
    large = measure_n(ADD50_PLUS, policy=POLICY_TOPK)
    flood_small = measure_n(ADD50_BASE, policy=POLICY_FLOOD)
    flood_large = measure_n(ADD50_PLUS, policy=POLICY_FLOOD)
    topk_ratio = large["tokens"] / small["tokens"]
    flood_ratio = flood_large["tokens"] / flood_small["tokens"]
    proportional = ADD50_PLUS / ADD50_BASE
    return {
        "n": ADD50_BASE,
        "n_plus_50": ADD50_PLUS,
        "topk_tokens_n": small["tokens"],
        "topk_tokens_n_plus_50": large["tokens"],
        "topk_ratio": topk_ratio,
        "flood_tokens_n": flood_small["tokens"],
        "flood_tokens_n_plus_50": flood_large["tokens"],
        "flood_ratio": flood_ratio,
        "proportional_ratio": proportional,
        "topk_under_ceiling": (
            small["tokens"] <= CEILING_TOKENS
            and large["tokens"] <= CEILING_TOKENS
        ),
        "flood_exceeds_ceiling": flood_large["tokens"] > CEILING_TOKENS,
        "topk_not_proportional": topk_ratio < 0.5 * proportional,
        "flood_is_proportional": flood_ratio > 0.7 * proportional,
        "topk_selected_n": small["selected"],
        "topk_selected_n_plus_50": large["selected"],
        "ceiling": CEILING_TOKENS,
    }


def curve_verdict(rows: list[dict]) -> dict:
    ns = [r["n"] for r in rows]
    toks = [r["tokens"] for r in rows]
    ests = [r["chars_div_4"] for r in rows]
    slope = loglog_slope(ns, toks)
    under = all(t <= CEILING_TOKENS for t in toks)
    measured_differs = any(t != e for t, e in zip(toks, ests))
    return {
        "sizes": ns,
        "tokens": toks,
        "chars_div_4": ests,
        "loglog_slope": slope,
        "sublinear": slope < 0.35,
        "all_under_ceiling": under,
        "ceiling": CEILING_TOKENS,
        "measured_differs_from_chars_div_4": measured_differs,
        "max_tokens": max(toks),
        "min_tokens": min(toks),
        "flat_span": max(toks) - min(toks),
    }
