"""compchem-validators · prefilters.py

CHEAP-TIER PREFILTER + funnel accounting for a structure-based / FEP campaign.

The economic core of E.4: the expensive tiers (Glide SP/XP, FEP+, QDX/EXESS
credits) are token/license-gated and serial. Spending them on candidates a cheap
GPU model would have rejected is the waste. This module is the pure-Python
DECISION-SUPPORT that sits in front of them — it ranks candidates by a cheap
score and selects which ones graduate to the expensive tier, and it accounts for
the credits saved. It does NOT itself run docking: the heavy compute rides the
EXISTING MCP bus (schrodinger / qdx-rush / cloud-hub GPU) — scientific compute is
NOT agent runtime.

Two prefilter stages this module encodes (both "cheap-model gates expensive-model"):

  Stage A — Uni-Dock GPU Vina  →  gates  →  Glide SP/XP  (token-gated docking)
  Stage B — Boltz-2 open weights (affinity) → gates → FEP+ / QDX EXESS (credits)

Both are recommenders, NOT blockers — they rank and propose a promotion set; the
orchestrator/owner confirms. Nothing here nags or blocks.

Evidence: MASTER-DECISION-QUEUE E.4 — "Uni-Dock (GPU Vina prefilter before
token-gated Glide, on cloud-hub) · Boltz-2 open weights (cheap FEP-prefilter tier
before FEP+/QDX credits)". All ride existing MCPs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Literal, Sequence

try:  # numpy is present; used only for percentile math, with a stdlib fallback.
    import numpy as _np
except Exception:  # pragma: no cover - stdlib fallback path
    _np = None

__all__ = [
    "Candidate",
    "PrefilterResult",
    "prefilter_rank",
    "prefilter_by_percentile",
    "estimate_savings",
    "STAGE_MCP_ROUTES",
    "recommend_route",
]

# Lower score = better for docking/affinity energies (more negative = tighter).
Direction = Literal["lower_is_better", "higher_is_better"]


@dataclass
class Candidate:
    """One molecule carrying its CHEAP-tier score (Vina / Boltz-2 affinity / xTB)."""

    cid: str
    score: float | None = None  # cheap-tier score; None = not yet scored
    smiles: str | None = None
    source: str = ""  # e.g. "uni-dock", "boltz2", "nn-xtb"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrefilterResult:
    """The promotion decision + funnel accounting."""

    promoted: list[Candidate]
    rejected: list[Candidate]
    unscored: list[Candidate]
    threshold: float | None
    direction: Direction
    stage: str
    savings: dict[str, Any] = field(default_factory=dict)

    @property
    def n_in(self) -> int:
        return len(self.promoted) + len(self.rejected) + len(self.unscored)

    @property
    def n_promoted(self) -> int:
        return len(self.promoted)

    def marker(self) -> str:
        """Terminal-state marker (AGENTS.md §4)."""
        return (
            f"PREFILTER:OK stage={self.stage} in={self.n_in} "
            f"promoted={self.n_promoted} rejected={len(self.rejected)} "
            f"unscored={len(self.unscored)}"
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["n_in"] = self.n_in
        d["n_promoted"] = self.n_promoted
        return d


def _norm(candidates: Iterable[Candidate | dict[str, Any]]) -> list[Candidate]:
    out: list[Candidate] = []
    for c in candidates:
        if isinstance(c, Candidate):
            out.append(c)
        elif isinstance(c, dict):
            out.append(
                Candidate(**{k: c[k] for k in c if k in Candidate.__annotations__})
            )
        else:
            raise TypeError(f"candidate must be Candidate or dict, got {type(c)!r}")
    return out


def _sorted_scored(scored: list[Candidate], direction: Direction) -> list[Candidate]:
    reverse = direction == "higher_is_better"
    return sorted(scored, key=lambda c: c.score, reverse=reverse)  # type: ignore[arg-type]


def prefilter_rank(
    candidates: Sequence[Candidate | dict[str, Any]],
    *,
    top_k: int | None = None,
    top_frac: float | None = None,
    threshold: float | None = None,
    direction: Direction = "lower_is_better",
    stage: str = "uni-dock->glide",
    cost_cheap: float = 0.0,
    cost_expensive: float = 1.0,
) -> PrefilterResult:
    """Rank cheap-scored candidates and select the promotion set.

    Exactly one selector should be given (precedence: ``threshold`` >
    ``top_k`` > ``top_frac``; default top_frac=0.25 if none given). Candidates
    with ``score is None`` are held out as ``unscored`` (never silently dropped —
    they must be cheap-scored first, honestly surfaced).

    ``direction`` — "lower_is_better" for docking/affinity ENERGIES (more negative
    is tighter), "higher_is_better" for a pIC50-style score.
    """
    cands = _norm(candidates)
    scored = [c for c in cands if c.score is not None and not _isnan(c.score)]
    unscored = [c for c in cands if c.score is None or _isnan(c.score)]

    promoted: list[Candidate]
    rejected: list[Candidate]
    used_threshold: float | None = None

    if threshold is not None:
        used_threshold = threshold
        if direction == "lower_is_better":
            promoted = [c for c in scored if c.score <= threshold]  # type: ignore[operator]
            rejected = [c for c in scored if c.score > threshold]  # type: ignore[operator]
        else:
            promoted = [c for c in scored if c.score >= threshold]  # type: ignore[operator]
            rejected = [c for c in scored if c.score < threshold]  # type: ignore[operator]
        ranked = _sorted_scored(promoted, direction)
        promoted = ranked
    else:
        ranked = _sorted_scored(scored, direction)
        if top_k is None and top_frac is None:
            top_frac = 0.25
        if top_k is not None:
            k = max(0, min(top_k, len(ranked)))
        else:
            k = max(1, math.ceil(len(ranked) * float(top_frac))) if ranked else 0  # type: ignore[arg-type]
        promoted = ranked[:k]
        rejected = ranked[k:]
        if promoted:
            used_threshold = promoted[-1].score

    savings = estimate_savings(
        n_total=len(scored),
        n_promoted=len(promoted),
        cost_cheap=cost_cheap,
        cost_expensive=cost_expensive,
    )
    return PrefilterResult(
        promoted=promoted,
        rejected=rejected,
        unscored=unscored,
        threshold=used_threshold,
        direction=direction,
        stage=stage,
        savings=savings,
    )


def prefilter_by_percentile(
    candidates: Sequence[Candidate | dict[str, Any]],
    *,
    percentile: float = 25.0,
    direction: Direction = "lower_is_better",
    stage: str = "boltz2->fep",
    **kwargs: Any,
) -> PrefilterResult:
    """Promote candidates past a data-driven percentile cut of the cheap score.

    For ``lower_is_better`` a percentile of 25 keeps the best (lowest-energy) 25%.
    """
    cands = _norm(candidates)
    scores = [c.score for c in cands if c.score is not None and not _isnan(c.score)]
    if not scores:
        return prefilter_rank(
            candidates,
            top_frac=percentile / 100.0,
            direction=direction,
            stage=stage,
            **kwargs,
        )
    if direction == "lower_is_better":
        cut = _percentile(scores, percentile)
    else:
        cut = _percentile(scores, 100.0 - percentile)
    return prefilter_rank(
        candidates, threshold=cut, direction=direction, stage=stage, **kwargs
    )


def estimate_savings(
    *, n_total: int, n_promoted: int, cost_cheap: float, cost_expensive: float
) -> dict[str, Any]:
    """Funnel economics: what the prefilter saved on the expensive tier.

    ``cost_expensive`` is the per-candidate cost of the gated tier (Glide token /
    FEP+ credit / QDX GPU-min). Naive baseline = run the expensive tier on ALL
    ``n_total``. Prefiltered = cheap-score all + expensive only on ``n_promoted``.
    """
    n_rejected = max(0, n_total - n_promoted)
    baseline = n_total * cost_expensive
    prefiltered = n_total * cost_cheap + n_promoted * cost_expensive
    saved = baseline - prefiltered
    return {
        "n_total": n_total,
        "n_promoted": n_promoted,
        "n_rejected": n_rejected,
        "reduction_frac": round(n_rejected / n_total, 4) if n_total else 0.0,
        "cost_baseline": round(baseline, 4),
        "cost_prefiltered": round(prefiltered, 4),
        "cost_saved": round(saved, 4),
        "saved_frac": round(saved / baseline, 4) if baseline else 0.0,
    }


# ---------------------------------------------------------------------------
# MCP routing map — WHICH existing MCP tool runs each tier's compute. This is
# documentation the orchestrator reads; this module never calls them (compute !=
# agent runtime). Names verified against the installed skill roster:
#   qdx-rush  : Boltz folding + affinity, NN-xTB screens, QM/MM (EXESS credits)
#   schrodinger: LigPrep / Glide grid / Glide dock / Prime MM-GBSA (license tokens)
#   cloud-hub : GPU sandboxes (Modal / RunPod) to run Uni-Dock / OpenFE / MACE-OFF
# ---------------------------------------------------------------------------
STAGE_MCP_ROUTES: dict[str, dict[str, Any]] = {
    "uni-dock": {
        "role": "cheap GPU-Vina prefilter (Stage A)",
        "runtime": "cloud-hub GPU sandbox",
        "mcp_tools": [
            "mcp__cloud-hub__modal_sandbox_create",
            "mcp__cloud-hub__modal_sandbox_exec",  # run unidock on the batch
            "mcp__cloud-hub__compute_provision / compute_exec",  # or a RunPod pod
        ],
        "gates": "schrodinger Glide SP/XP",
        "note": "MIT-licensed; batches thousands of ligands/GPU-hour. Score = Vina "
        "affinity (kcal/mol, lower is better).",
    },
    "boltz2": {
        "role": "cheap open-weights affinity prefilter (Stage B)",
        "runtime": "qdx-rush (Boltz fold+affinity) or cloud-hub GPU",
        "mcp_tools": ["qdx-rush Boltz fold+affinity", "mcp__cloud-hub__modal_run"],
        "gates": "FEP+ / QDX EXESS free-energy credits",
        "note": "Boltz-2 predicts binding affinity ~1000x cheaper than FEP; use as a "
        "pre-FEP triage tier, NOT a replacement for FEP on the shortlist.",
    },
    "openfe": {
        "role": "token-free FEP twin / cross-check of FEP+",
        "runtime": "cloud-hub GPU (OpenFE + OpenMM)",
        "mcp_tools": ["mcp__cloud-hub__modal_sandbox_exec"],
        "gates": "(cross-checks) FEP+ / QDX",
        "note": "MIT; run alongside FEP+ on the shortlist for a second-model check.",
    },
    "mace-off": {
        "role": "near-DFT MLIP for MD (via openmm-ml)",
        "runtime": "cloud-hub GPU",
        "mcp_tools": ["mcp__cloud-hub__modal_sandbox_exec"],
        "gates": "(quality tier for MD) classical FF MD",
        "note": "MACE-OFF23 weights — CHECK license before commercial embed.",
    },
}


def recommend_route(stage_key: str) -> dict[str, Any]:
    """Return the MCP routing recommendation for a prefilter stage (or a hint)."""
    if stage_key in STAGE_MCP_ROUTES:
        return STAGE_MCP_ROUTES[stage_key]
    return {
        "role": "unknown stage",
        "hint": f"no route registered for {stage_key!r}; "
        f"known: {sorted(STAGE_MCP_ROUTES)}",
    }


# ---------------------------------------------------------------------------
# small numeric helpers (stdlib fallback if numpy absent)
# ---------------------------------------------------------------------------
def _isnan(x: float) -> bool:
    try:
        return math.isnan(x)
    except (TypeError, ValueError):
        return False


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("empty values")
    if _np is not None:
        return float(_np.percentile(_np.asarray(values, dtype=float), q))
    # linear-interpolation percentile (numpy-compatible)
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    rank = (q / 100.0) * (len(xs) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(xs[int(rank)])
    frac = rank - lo
    return float(xs[lo] * (1 - frac) + xs[hi] * frac)


if __name__ == "__main__":  # tiny smoke when run directly
    demo = [
        Candidate(f"m{i}", score=s)
        for i, s in enumerate([-9.1, -6.2, -8.4, -5.0, -7.7])
    ]
    res = prefilter_rank(demo, top_k=2, cost_expensive=1.0)
    print(res.marker())
    print("promoted:", [(c.cid, c.score) for c in res.promoted])
    print("savings:", res.savings)
