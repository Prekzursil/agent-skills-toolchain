"""Strictly-proper betting ledger (IMP-0295)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

LOG_CLIP = 1e-15
GRID = tuple(round(i / 10, 10) for i in range(0, 11))
TOURNAMENT_N = 32
TOURNAMENT_SEED = 1


class BettingError(Exception):
    pass


class BrierPayoff:
    def payoff(self, p: float, y: int) -> float:
        return 1.0 - (float(p) - int(y)) ** 2


class LogPayoff:
    def payoff(self, p: float, y: int) -> float:
        q = min(1.0 - LOG_CLIP, max(LOG_CLIP, float(p)))
        if int(y) == 1:
            return math.log(q)
        return math.log(1.0 - q)


class HedgeRewardPayoff:
    def payoff(self, p: float, y: int) -> float:
        return 1.0 if abs(float(p) - 0.5) < 1e-12 else 0.0


class LinearHitPayoff:
    def payoff(self, p: float, y: int) -> float:
        return float(p) if int(y) == 1 else (1.0 - float(p))


@dataclass
class Proposition:
    proposition_id: str
    statement: str
    resolution_criterion: str


class _Store:
    def __init__(self) -> None:
        self.participants: dict[str, dict[str, Any]] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "council.calibration.store.v1",
            "participants": self.participants,
        }


class BettingLedger:
    def __init__(self) -> None:
        self._props: dict[str, Proposition] = {}
        self._stakes: dict[str, list[tuple[str, float]]] = {}
        self._resolved: dict[str, int] = {}
        self.store = _Store()
        self._payoff = BrierPayoff()

    def add_proposition(self, prop: Proposition) -> None:
        if not str(prop.resolution_criterion or "").strip():
            raise BettingError("unresolvable proposition")
        self._props[prop.proposition_id] = prop

    def stake(self, participant: str, proposition_id: str, p: float) -> None:
        if proposition_id not in self._props:
            raise BettingError("unknown proposition")
        self._stakes.setdefault(proposition_id, []).append((participant, float(p)))
        part = self.store.participants.setdefault(participant, {"forecasts": []})
        part["forecasts"].append(
            {"proposition_id": proposition_id, "p": float(p), "outcome": None}
        )

    def resolve(self, proposition_id: str, outcome: int) -> None:
        self._resolved[proposition_id] = int(outcome)
        for part in self.store.participants.values():
            for row in part["forecasts"]:
                if row["proposition_id"] == proposition_id:
                    row["outcome"] = int(outcome)

    def totals(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for pid, y in self._resolved.items():
            for participant, p in self._stakes.get(pid, []):
                out[participant] = out.get(participant, 0.0) + self._payoff.payoff(p, y)
        return out


def _expected(payoff: Any, q: float, pi: float) -> float:
    return float(pi) * payoff.payoff(q, 1) + (1.0 - float(pi)) * payoff.payoff(q, 0)


def strictly_proper_report(rule: Any = None) -> dict[str, Any]:
    payoff = rule or BrierPayoff()
    pi_grid = list(GRID)
    bad: list[float] = []
    hedge_ok = True
    for pi in pi_grid:
        scored = [(q, _expected(payoff, q, pi)) for q in pi_grid]
        best_q, best_s = max(scored, key=lambda t: t[1])
        ties = [q for q, s in scored if abs(s - best_s) <= 1e-12]
        if not (len(ties) == 1 and abs(best_q - pi) <= 1e-12):
            bad.append(pi)
        if abs(pi - 0.5) > 1e-12:
            truth = next(s for q, s in scored if abs(q - pi) <= 1e-12)
            hedge = next(s for q, s in scored if abs(q - 0.5) <= 1e-12)
            if not (truth > hedge + 1e-12):
                hedge_ok = False
    return {
        "strictly_proper": len(bad) == 0,
        "hedging_loses_when_pi_neq_half": hedge_ok,
        "n_pi": len(pi_grid),
        "brier": isinstance(payoff, BrierPayoff) or len(bad) == 0,
        "log": isinstance(payoff, LogPayoff) or type(payoff).__name__ == "LogPayoff",
        "bad_pi": bad,
    }


def self_check() -> dict[str, Any]:
    brier = strictly_proper_report(BrierPayoff())
    log = strictly_proper_report(LogPayoff())
    pathwise = pathwise_right_side_report()
    control = run_negative_control()
    return {
        "ok": bool(
            brier["strictly_proper"]
            and log["strictly_proper"]
            and pathwise["all_committer_ahead"]
            and control["discriminates"]
        ),
        "brier": brier,
        "log": log,
        "pathwise": pathwise,
        "negative_control": control["discriminates"],
    }


def pathwise_right_side_report() -> dict[str, Any]:
    brier = BrierPayoff()
    rows = []
    for p, y in ((0.9, 1), (0.8, 1), (0.3, 0), (0.1, 0)):
        committer = brier.payoff(p, y)
        hedger = brier.payoff(0.5, y)
        rows.append(
            {
                "p": p,
                "y": y,
                "committer": committer,
                "hedger": hedger,
                "ahead": committer > hedger,
            }
        )
    return {
        "ok": all(r["ahead"] for r in rows),
        "all_committer_ahead": all(r["ahead"] for r in rows),
        "rows": rows,
    }


def run_negative_control() -> dict[str, Any]:
    proper = run_tournament(seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=BrierPayoff())
    mutant = run_tournament(
        seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=HedgeRewardPayoff()
    )
    discriminates = (
        proper["winner"] == "committer"
        and (not proper["hedger_wins"])
        and mutant["winner"] == "hedger"
        and mutant["hedger_wins"]
        and proper["hedger_wins"] != mutant["hedger_wins"]
    )
    return {
        "ok": discriminates,
        "proper": proper,
        "nonproper": mutant,
        "discriminates": discriminates,
        "store_schema": proper["store"]["schema"],
        "n_store_forecasts": proper["n_store_forecasts"],
    }


def run_tournament(
    seed: int = TOURNAMENT_SEED,
    n: int = TOURNAMENT_N,
    rule: Any = None,
) -> dict[str, Any]:
    import random

    payoff = rule or BrierPayoff()
    rng = random.Random(int(seed))
    names = ("committer", "hedger", "random")
    store = {
        "schema": "council.calibration.store.v1",
        "participants": {name: {"forecasts": []} for name in names},
    }
    true_p = 0.8
    for _i in range(int(n)):
        y = 1 if rng.random() < true_p else 0
        preds = {
            "committer": true_p,
            "hedger": 0.5,
            "random": rng.random(),
        }
        for name, p in preds.items():
            store["participants"][name]["forecasts"].append({"p": float(p), "outcome": int(y)})
    totals = {}
    for name in names:
        totals[name] = sum(
            payoff.payoff(row["p"], row["outcome"])
            for row in store["participants"][name]["forecasts"]
        )
    ranking = sorted(names, key=lambda n_: (-totals[n_], n_))
    winner = ranking[0]
    n_store = sum(len(store["participants"][name]["forecasts"]) for name in names)
    if isinstance(payoff, HedgeRewardPayoff):
        rule_name = "hedge-reward-nonproper"
    elif isinstance(payoff, LogPayoff):
        rule_name = "log-payoff"
    else:
        rule_name = "brier-payoff"
    analytic = {
        name: int(n)
        * (
            true_p * payoff.payoff(p, 1)
            + (1.0 - true_p) * payoff.payoff(p, 0)
        )
        for name, p in (("committer", true_p), ("hedger", 0.5))
    }
    analytic["random"] = totals["random"]
    return {
        "n": int(n),
        "seed": int(seed),
        "store": store,
        "n_store_forecasts": n_store,
        "totals": totals,
        "ranking": ranking,
        "winner": winner,
        "hedger_wins": winner == "hedger",
        "committer_beats_hedger": totals["committer"] > totals["hedger"],
        "rule": rule_name,
        "true_p_palette": [true_p],
        "analytic_expected_totals": analytic,
    }
