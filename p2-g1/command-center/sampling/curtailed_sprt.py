"""Curtailed Wald SPRT. Early stopping cannot shrink the P0/P1 census."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

IMPLEMENTATION_REL = "command-center/sampling/curtailed_sprt.py"
CENSUS_SEVERITIES = frozenset({"P0", "P1"})
CALIBRATION_SEED = 20260824
PROBE_MC_SEED = 20260824
MC_TOLERANCE_ABS = 0.04
_ALLOWED_SEV = frozenset({"P0", "P1", "P2", "P3"})


class CensusGuardError(ValueError):
    """Early stop attempted on a P0/P1 census stratum."""


class SequentialClosedError(RuntimeError):
    """observe() after the sequential rule closed."""


@dataclass(frozen=True)
class Params:
    p0: float
    p1: float
    alpha: float
    beta: float
    n_max: int
    A: float
    B: float
    incr0: float
    incr1: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "p0": self.p0,
            "p1": self.p1,
            "alpha": self.alpha,
            "beta": self.beta,
            "n_max": self.n_max,
            "A": self.A,
            "B": self.B,
            "incr0": self.incr0,
            "incr1": self.incr1,
        }


@dataclass
class SprtState:
    n: int
    llr: float
    decision: str
    truncated: bool


def default_params() -> Params:
    p0, p1, alpha, beta, n_max = 0.02, 0.10, 0.05, 0.10, 80
    a = math.log((1.0 - beta) / alpha)
    b = math.log(beta / (1.0 - alpha))
    incr1 = math.log(p1 / p0)
    incr0 = math.log((1.0 - p1) / (1.0 - p0))
    return Params(
        p0=p0,
        p1=p1,
        alpha=alpha,
        beta=beta,
        n_max=n_max,
        A=a,
        B=b,
        incr0=incr0,
        incr1=incr1,
    )


def normalize_severity(sev: str) -> str:
    token = str(sev or "").strip().upper()
    if not token:
        raise ValueError("empty severity")
    if token not in _ALLOWED_SEV:
        raise ValueError(f"unknown severity {sev!r}")
    return token


def llr_of(obs: Sequence[bool], params: Params) -> float:
    total = 0.0
    for x in obs:
        total += params.incr1 if x else params.incr0
    return total


def refuse_census_early_stop(severity: str, *, allow_early_stop: bool = False) -> None:
    sev = normalize_severity(severity)
    if sev in CENSUS_SEVERITIES and allow_early_stop:
        raise CensusGuardError(f"{sev} census cannot early-stop")


def guard_path_line() -> str:
    path = Path(__file__).resolve()
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if "def refuse_census_early_stop" in ln]
    line = hits[0] if hits else 1
    return f"{IMPLEMENTATION_REL}:{line}"


def make_continuation_path(params: Params) -> list[bool]:
    path: list[bool] = []
    llr = 0.0
    margin = 0.08
    for _ in range(params.n_max):
        if llr + params.incr0 > params.B + margin and llr + params.incr0 < params.A - margin:
            obs = False
        elif llr + params.incr1 < params.A - margin:
            obs = True
        else:
            obs = False
        nxt = llr + (params.incr1 if obs else params.incr0)
        if nxt >= params.A or nxt <= params.B:
            obs = not obs
            nxt = llr + (params.incr1 if obs else params.incr0)
            if nxt >= params.A or nxt <= params.B:
                obs = False
                nxt = llr + params.incr0
        path.append(obs)
        llr = nxt
    return path


def apply_plan(frame: dict[str, Any], params: Params) -> dict[str, Any]:
    strata = []
    census_n = 0
    for row in frame.get("strata") or []:
        sev = normalize_severity(str(row.get("severity") or "P3"))
        n = int(row.get("N") or 0)
        census = sev in CENSUS_SEVERITIES
        if census:
            census_n += n
        strata.append(
            {
                "stratum_id": row.get("stratum_id"),
                "severity": sev,
                "mode": "CENSUS" if census else "SEQUENTIAL",
                "N": n,
                "n_required": n if census else min(n, params.n_max),
                "early_stop_allowed": False if census else True,
                "n_max": n if census else params.n_max,
            }
        )
    return {
        "census_n_before": census_n,
        "census_n_required": census_n,
        "census_shrunk": False,
        "strata": strata,
        "params": params.as_dict(),
    }


class CurtailedSPRT:
    def __init__(
        self,
        params: Params,
        *,
        severity: str,
        population_n: int,
        n_max: int | None = None,
        allow_early_stop: bool = False,
        stratum_id: str = "",
    ) -> None:
        self.params = params
        self.severity = normalize_severity(severity)
        self.population_n = int(population_n)
        self.stratum_id = stratum_id
        self.census = self.severity in CENSUS_SEVERITIES
        refuse_census_early_stop(self.severity, allow_early_stop=allow_early_stop)
        if self.census and allow_early_stop:
            raise CensusGuardError("census allow_early_stop")
        cap = int(n_max) if n_max is not None else (self.population_n if self.census else params.n_max)
        if self.census:
            if n_max is not None and cap < self.population_n:
                raise CensusGuardError("P0/P1 n_max < N")
            self.n_max = self.population_n
        else:
            self.n_max = cap
        self._obs: list[bool] = []
        self._closed = False
        self._decision = "CONTINUE"
        self._truncated = False

    def try_declare_stop(self, decision: str | None = None) -> None:
        del decision
        if self.census:
            raise CensusGuardError("P0/P1 try_declare_stop refused")
        raise CensusGuardError("try_declare_stop refused before bound")

    def _close(self, decision: str, truncated: bool) -> SprtState:
        self._closed = True
        self._decision = decision
        self._truncated = truncated
        return SprtState(n=len(self._obs), llr=llr_of(self._obs, self.params), decision=decision, truncated=truncated)

    def observe(self, defect: bool) -> SprtState:
        if self._closed:
            raise SequentialClosedError("observe after close")
        self._obs.append(bool(defect))
        n = len(self._obs)
        llr = llr_of(self._obs, self.params)
        if self.census:
            if n >= self.population_n:
                decision = "REJECT_H0" if llr >= 0 else "ACCEPT_H0"
                if llr >= self.params.A:
                    decision = "REJECT_H0"
                elif llr <= self.params.B:
                    decision = "ACCEPT_H0"
                return self._close(decision, truncated=False)
            return SprtState(n=n, llr=llr, decision="CONTINUE", truncated=False)
        if llr >= self.params.A:
            return self._close("REJECT_H0", truncated=False)
        if llr <= self.params.B:
            return self._close("ACCEPT_H0", truncated=False)
        if n >= self.n_max:
            decision = "REJECT_H0" if llr >= 0 else "ACCEPT_H0"
            return self._close(decision, truncated=True)
        return SprtState(n=n, llr=llr, decision="CONTINUE", truncated=False)

    def consume(self, stream: Iterable[bool]) -> SprtState:
        last = SprtState(n=0, llr=0.0, decision="CONTINUE", truncated=False)
        for x in stream:
            last = self.observe(bool(x))
            if self._closed:
                return last
        if self.census and not self._closed:
            decision = "REJECT_H0" if last.llr >= 0 else "ACCEPT_H0"
            return self._close(decision, truncated=False)
        return last


def _simulate_one(p_true: float, params: Params, rng: random.Random) -> SprtState:
    seq = CurtailedSPRT(params, severity="P2", population_n=10**6)
    while True:
        st = seq.observe(rng.random() < p_true)
        if seq._closed:
            return st


def monte_carlo(
    p_true: float,
    n_sims: int,
    seed: int,
    params: Params | None = None,
) -> dict[str, Any]:
    params = params or default_params()
    rng = random.Random(int(seed))
    accept = reject = trunc = 0
    ns = 0
    for _ in range(int(n_sims)):
        st = _simulate_one(p_true, params, rng)
        ns += st.n
        if st.truncated:
            trunc += 1
        if st.decision == "ACCEPT_H0":
            accept += 1
        elif st.decision == "REJECT_H0":
            reject += 1
    n = float(n_sims)
    asn = ns / n
    return {
        "p_true": p_true,
        "n_sims": n_sims,
        "seed": seed,
        "p_accept_h0": accept / n,
        "p_reject_h0": reject / n,
        "p_truncate": trunc / n,
        "asn": asn,
        "saving_frac": max(0.0, 1.0 - asn / params.n_max),
    }


def operating_characteristic(
    ps: Sequence[float],
    n_sims: int,
    seed: int,
    params: Params | None = None,
) -> list[dict[str, Any]]:
    params = params or default_params()
    rows = []
    for i, p in enumerate(ps):
        rec = monte_carlo(p_true=float(p), n_sims=n_sims, seed=int(seed) + i, params=params)
        rec["p"] = float(p)
        rows.append(rec)
    return rows
