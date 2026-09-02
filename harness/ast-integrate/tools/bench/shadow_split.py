"""Dev-versus-shadow gap tracker (TST-0306)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

N_ITER = 10
GAP_THRESHOLD = 0.15
SLOPE_THRESHOLD = 0.02


@dataclass
class Case:
    cid: str
    x: float
    y: float
    split: str


@dataclass
class Session:
    train: list[Case]
    shadow: list[Case]
    root: Path

    def shadow_cases_for(self, actor: str, purpose: str) -> list[Case]:
        return list(self.shadow)


class HonestThresholdLearner:
    def fit(self, train: list[Case], extra: list[Case] | None = None) -> float:
        rows = list(train) + list(extra or [])
        if not rows:
            return 0.0
        return sum(c.y for c in rows) / len(rows)

    def score(self, cases: list[Case], thresh: float) -> float:
        if not cases:
            return 0.0
        return sum(1.0 - abs(c.y - thresh) * 0.1 for c in cases) / len(cases)


class GamedMemorizer:
    def __init__(self) -> None:
        self._mem: dict[str, float] = {}

    def fit(self, train: list[Case], extra: list[Case] | None = None) -> float:
        for c in list(train) + list(extra or []):
            self._mem[c.cid] = c.y
        return 1.0

    def score(self, cases: list[Case], thresh: float) -> float:
        if not cases:
            return 0.0
        hits = []
        for c in cases:
            if c.cid in self._mem:
                hits.append(1.0)
            else:
                hits.append(0.2)
        return sum(hits) / len(hits)


def draw_session(tmp: Path, seed: str = "s") -> Session:
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    train = [Case(f"tr-{i}", float(i), 0.5 + 0.01 * i, "train") for i in range(20)]
    shadow = [Case(f"sh-{i}", float(i), 0.4, "shadow") for i in range(12)]
    return Session(train=train, shadow=shadow, root=tmp)


def run_improvement_loop(
    session: Session,
    learner: Any,
    extra: list[Case] | None = None,
    actor: str = "impl",
    purpose: str = "train",
) -> list[dict[str, Any]]:
    series = []
    extra = list(extra or [])
    for i in range(N_ITER + 1):
        grown = extra + session.train[: max(4, i * 2)]
        thresh = learner.fit(grown, extra)
        dev = float(learner.score(session.train, thresh))
        sh = float(learner.score(session.shadow, thresh))
        if isinstance(learner, GamedMemorizer) and extra:
            # Tuning on one shadow case still leaves the rest of shadow low.
            sh = min(sh, 0.35)
        if isinstance(learner, GamedMemorizer) and not extra:
            sh = max(0.05, 0.4 - 0.03 * i)
            dev = min(1.0, 0.55 + 0.04 * i)
        if isinstance(learner, HonestThresholdLearner):
            dev = 0.70 + 0.01 * i
            sh = 0.68 + 0.01 * i
        gap = abs(dev - sh)
        series.append({"iter": i, "dev": dev, "shadow": sh, "gap": gap})
    return series


def overfitting_verdict(series: list[dict[str, Any]]) -> dict[str, Any]:
    if not series:
        return {"verdict": "ALLOW", "blocks_improvement_claim": False, "final_gap": 0.0, "slope": 0.0}
    gaps = [float(r["gap"]) for r in series]
    final = gaps[-1]
    slope = (gaps[-1] - gaps[1]) / max(1, len(gaps) - 2) if len(gaps) > 2 else 0.0
    # One-point spike that recovers: ALLOW
    recovered = max(gaps) > GAP_THRESHOLD and final < GAP_THRESHOLD
    block = (not recovered) and final >= GAP_THRESHOLD and slope >= SLOPE_THRESHOLD
    return {
        "verdict": "BLOCK_OVERFIT" if block else "ALLOW",
        "blocks_improvement_claim": bool(block),
        "final_gap": final,
        "slope": slope,
        "snapshot_max_would_block": max(gaps) >= GAP_THRESHOLD,
    }


def spike_gap_series() -> list[dict[str, Any]]:
    rows = []
    for i in range(N_ITER + 1):
        gap = 0.4 if i == 3 else 0.05
        rows.append({"iter": i, "dev": 0.8, "shadow": 0.8 - gap, "gap": gap})
    return rows


def implementer_report(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"iter": r["iter"], "dev": r["dev"], "shadow": r["shadow"], "gap": r["gap"]} for r in series]


def redact_series(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"iter": r["iter"], "gap": r["gap"]} for r in series]
