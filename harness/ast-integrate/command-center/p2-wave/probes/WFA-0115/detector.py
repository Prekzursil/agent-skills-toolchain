#!/usr/bin/env python3
"""WFA-0115: fused-worse-than-every-source gate (FC-11333).

Fails certification when a fused candidate scores below ALL of its sources
on the matched cases. Comparisons use the measured run-to-run variance floor,
not raw point scores. A fusion inside that floor of its best source is
INCONCLUSIVE, never a pass. The gate must run before any certification
record is emitted; attaching it afterwards is refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping, Sequence

COMPONENTS: tuple[str, ...] = ("correctness", "coverage", "recovery", "usability")
VERDICT = Literal["REJECT", "INCONCLUSIVE", "CLEAR", "REFUSE"]
ARM_ROLE = Literal["source", "fusion", "control"]

REJECT = "REJECT"
INCONCLUSIVE = "INCONCLUSIVE"
CLEAR = "CLEAR"
REFUSE = "REFUSE"

CASE_IDS: tuple[str, ...] = tuple(f"case-{i:02d}" for i in range(1, 9))


class OrderError(Exception):
    """Gate/certification sequencing violation."""


class CertificationRefused(Exception):
    """Certification blocked by this gate's verdict."""


def composite(components: Mapping[str, float]) -> float:
    missing = [k for k in COMPONENTS if k not in components]
    if missing:
        raise ValueError(f"missing rubric components: {missing}")
    return sum(float(components[k]) for k in COMPONENTS) / float(len(COMPONENTS))


def _mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean of empty")
    return float(sum(xs) / len(xs))


@dataclass(frozen=True)
class Arm:
    arm_id: str
    role: ARM_ROLE
    per_case: Mapping[str, Mapping[str, float]]

    def score(self, case_id: str) -> float:
        row = self.per_case.get(case_id)
        if row is None:
            raise KeyError(case_id)
        return composite(row)

    def scores(self, case_ids: Sequence[str]) -> dict[str, float]:
        return {cid: self.score(cid) for cid in case_ids}


@dataclass(frozen=True)
class MatchedComparison:
    """One matched-pair experiment: sources + fusion + control pair."""

    experiment_id: str
    case_ids: tuple[str, ...]
    sources: tuple[Arm, ...]
    fusion: Arm
    control_a: Arm
    control_b: Arm


def measure_variance_floor(
    control_a: Arm, control_b: Arm, case_ids: Sequence[str]
) -> float:
    """Null delta: same workflow twice. Max abs paired difference is the floor."""
    diffs: list[float] = []
    for cid in case_ids:
        try:
            a = control_a.score(cid)
            b = control_b.score(cid)
        except KeyError as exc:
            raise ValueError(f"control arm missing case {exc}") from exc
        diffs.append(abs(a - b))
    if not diffs:
        raise ValueError("variance floor requires at least one matched case")
    return max(diffs)


def _arm_mean(arm: Arm, case_ids: Sequence[str]) -> float:
    return _mean([arm.score(cid) for cid in case_ids])


def evaluate(
    comparison: MatchedComparison, *, use_raw_points: bool = False
) -> dict:
    """Return the gate decision plus per-source deltas across all matched cases.

    use_raw_points is a mutation hook: it ignores the floor and treats any
    raw-mean deficit as a real difference. The live gate must keep this False.
    """
    cases = comparison.case_ids
    if not cases:
        return _refuse(comparison, "no matched cases")
    if not comparison.sources:
        return _refuse(comparison, "no source arms")
    if comparison.fusion.role != "fusion":
        return _refuse(comparison, "fusion arm role is not fusion")

    missing: list[str] = []
    for arm in (comparison.fusion, comparison.control_a, comparison.control_b, *comparison.sources):
        for cid in cases:
            if cid not in arm.per_case:
                missing.append(f"{arm.arm_id}:{cid}")
    if missing:
        return _refuse(comparison, "incomplete arms (never dropped): " + ",".join(missing))

    try:
        floor = measure_variance_floor(comparison.control_a, comparison.control_b, cases)
    except ValueError as exc:
        return _refuse(comparison, f"variance floor unmeasured: {exc}")

    source_means = {s.arm_id: _arm_mean(s, cases) for s in comparison.sources}
    fusion_mean = _arm_mean(comparison.fusion, cases)
    best_id = max(source_means, key=lambda k: source_means[k])
    best_mean = source_means[best_id]
    abs_vs_best = abs(fusion_mean - best_mean)

    per_case: list[dict] = []
    for cid in cases:
        fscore = comparison.fusion.score(cid)
        src_scores = {s.arm_id: s.score(cid) for s in comparison.sources}
        deltas = {sid: fscore - sc for sid, sc in src_scores.items()}
        per_case.append(
            {
                "case_id": cid,
                "fusion": fscore,
                "sources": src_scores,
                "delta_vs_source": deltas,
            }
        )

    mean_delta = {sid: fusion_mean - mean for sid, mean in source_means.items()}

    def below(source_mean: float) -> bool:
        deficit = source_mean - fusion_mean
        if use_raw_points:
            return deficit > 0.0
        return deficit > floor

    below_map = {sid: below(mean) for sid, mean in source_means.items()}
    below_all = all(below_map.values())
    within_best = abs_vs_best <= floor
    if use_raw_points:
        within_best = False

    if within_best:
        verdict: str = INCONCLUSIVE
        reason = (
            "fusion is inside the variance floor of its best source; "
            "INCONCLUSIVE, not a pass"
        )
    elif below_all:
        verdict = REJECT
        reason = (
            "fused candidate scores below ALL sources beyond the variance floor "
            "(FC-11333)"
        )
    else:
        verdict = CLEAR
        reason = (
            "named failure class did not fire: fusion is not below every source "
            "beyond the variance floor"
        )

    return {
        "experiment_id": comparison.experiment_id,
        "verdict": verdict,
        "reason": reason,
        "variance_floor": floor,
        "floor_measured_before_comparison": True,
        "used_raw_point_scores": use_raw_points,
        "case_ids": list(cases),
        "n_cases": len(cases),
        "fusion_arm_id": comparison.fusion.arm_id,
        "fusion_mean": fusion_mean,
        "source_means": source_means,
        "mean_delta_vs_source": mean_delta,
        "best_source_id": best_id,
        "best_source_mean": best_mean,
        "abs_delta_vs_best": abs_vs_best,
        "within_floor_of_best": (not use_raw_points) and abs_vs_best <= floor,
        "below_source_beyond_floor": below_map,
        "below_all_sources_beyond_floor": below_all,
        "per_case": per_case,
        "blocks_certification": verdict != CLEAR,
        "pass_claimed": False,
    }


def _refuse(comparison: MatchedComparison, reason: str) -> dict:
    return {
        "experiment_id": comparison.experiment_id,
        "verdict": REFUSE,
        "reason": reason,
        "variance_floor": None,
        "floor_measured_before_comparison": False,
        "used_raw_point_scores": False,
        "case_ids": list(comparison.case_ids),
        "n_cases": len(comparison.case_ids),
        "fusion_arm_id": comparison.fusion.arm_id,
        "fusion_mean": None,
        "source_means": {},
        "mean_delta_vs_source": {},
        "best_source_id": None,
        "best_source_mean": None,
        "abs_delta_vs_best": None,
        "within_floor_of_best": False,
        "below_source_beyond_floor": {},
        "below_all_sources_beyond_floor": False,
        "per_case": [],
        "blocks_certification": True,
        "pass_claimed": False,
    }


def _fill(
    value: float, case_ids: Iterable[str] | None = None
) -> dict[str, dict[str, float]]:
    ids = tuple(case_ids) if case_ids is not None else CASE_IDS
    return {cid: {k: float(value) for k in COMPONENTS} for cid in ids}


def _overlay(
    base: dict[str, dict[str, float]], updates: Mapping[str, float]
) -> dict[str, dict[str, float]]:
    out = {cid: dict(row) for cid, row in base.items()}
    for cid, val in updates.items():
        out[cid] = {k: float(val) for k in COMPONENTS}
    return out


def fixture_control_pair() -> tuple[Arm, Arm]:
    a = Arm("control-repeat-1", "control", _fill(0.80))
    b_scores = _overlay(_fill(0.80), {"case-01": 0.81})
    b = Arm("control-repeat-2", "control", b_scores)
    return a, b


def fixture_sources() -> tuple[Arm, Arm]:
    src_a = Arm("source-strong", "source", _fill(0.80))
    src_b = Arm("source-weak", "source", _fill(0.70))
    return src_a, src_b


def fixture_good_fusion() -> MatchedComparison:
    ca, cb = fixture_control_pair()
    s1, s2 = fixture_sources()
    fusion = Arm("fusion-good", "fusion", _fill(0.86))
    return MatchedComparison("good-fusion", CASE_IDS, (s1, s2), fusion, ca, cb)


def fixture_degraded_fusion() -> MatchedComparison:
    """Planted deliberately-degraded fusion: below every source beyond the floor."""
    ca, cb = fixture_control_pair()
    s1, s2 = fixture_sources()
    fusion = Arm("fusion-degraded", "fusion", _fill(0.40))
    return MatchedComparison("planted-degraded", CASE_IDS, (s1, s2), fusion, ca, cb)


def fixture_inconclusive_near_best() -> MatchedComparison:
    """Raw-worse-than-all, but inside the floor of the best source.

    source-strong mean 0.80, source-near mean 0.799, fusion 0.795.
    Raw points say worse than every source. The floor (0.01) says INCONCLUSIVE.
    """
    ca, cb = fixture_control_pair()
    src_a = Arm("source-strong", "source", _fill(0.80))
    src_b = Arm("source-near", "source", _fill(0.799))
    fusion = Arm("fusion-near-best", "fusion", _fill(0.795))
    return MatchedComparison(
        "inconclusive-inside-floor", CASE_IDS, (src_a, src_b), fusion, ca, cb
    )


def fixture_complementary_not_worse_than_all() -> MatchedComparison:
    """Worse than the best source, better than the weak source → not FC-11333."""
    ca, cb = fixture_control_pair()
    s1, s2 = fixture_sources()
    fusion = Arm("fusion-complement", "fusion", _fill(0.75))
    return MatchedComparison("complement-not-all", CASE_IDS, (s1, s2), fusion, ca, cb)


def fixture_incomplete_arm() -> MatchedComparison:
    ca, cb = fixture_control_pair()
    s1, s2 = fixture_sources()
    dropped = {cid: {k: 0.40 for k in COMPONENTS} for cid in CASE_IDS[:-1]}
    fusion = Arm("fusion-dropped-case", "fusion", dropped)
    return MatchedComparison("incomplete-arm", CASE_IDS, (s1, s2), fusion, ca, cb)


SCENARIOS = {
    "good": fixture_good_fusion,
    "degraded": fixture_degraded_fusion,
    "inconclusive": fixture_inconclusive_near_best,
    "complement": fixture_complementary_not_worse_than_all,
    "incomplete": fixture_incomplete_arm,
}


def run_all_scenarios(*, use_raw_points: bool = False) -> dict[str, dict]:
    return {name: evaluate(fn(), use_raw_points=use_raw_points) for name, fn in SCENARIOS.items()}


def both_states() -> dict:
    good = evaluate(fixture_good_fusion())
    broken = evaluate(fixture_degraded_fusion())
    fires = broken["verdict"] == REJECT
    silent = good["verdict"] == CLEAR
    return {
        "known_good": {
            "name": good["experiment_id"],
            "verdict": good["verdict"],
            "blocked": good["blocks_certification"],
            "exit_code": 0 if silent else 1,
        },
        "known_broken": {
            "name": broken["experiment_id"],
            "verdict": broken["verdict"],
            "blocked": broken["blocks_certification"],
            "exit_code": 0 if fires else 1,
        },
        "discriminates": fires and silent,
        "good": good,
        "broken": broken,
    }


@dataclass
class CertificationBoundGate:
    """Refuse certification until this gate has run; refuse post-hoc reports."""

    _result: dict | None = field(default=None, init=False)
    _certified: bool = field(default=False, init=False)
    _log: list[str] = field(default_factory=list, init=False)

    def run_gate(self, comparison: MatchedComparison) -> dict:
        if self._certified:
            raise OrderError(
                "WFA-0115 gate cannot run as a post-certification report"
            )
        result = evaluate(comparison)
        self._result = result
        self._log.append(f"gate:{result['experiment_id']}:{result['verdict']}")
        return result

    def emit_certification(self, *, extra_conditions_ok: bool = True) -> dict:
        if self._result is None:
            raise OrderError("WFA-0115 gate must run before certification")
        verdict = self._result["verdict"]
        if verdict != CLEAR:
            raise CertificationRefused(
                f"certification refused: gate verdict {verdict} is not CLEAR "
                f"({self._result.get('reason')})"
            )
        if not extra_conditions_ok:
            raise CertificationRefused("other certification conditions unmet")
        record = {
            "record_type": "CertificationRecord",
            "state": "CERTIFIED",
            "worse_than_source_gate": self._result["verdict"],
            "gate_ran_before_certification": True,
            "experiment_id": self._result["experiment_id"],
        }
        self._certified = True
        self._log.append("certification:emitted")
        return record

    @property
    def certified(self) -> bool:
        return self._certified

    @property
    def last_result(self) -> dict | None:
        return self._result

    @property
    def log(self) -> tuple[str, ...]:
        return tuple(self._log)


def ordering_controls() -> dict:
    """Live demonstration that the gate is pre-certification, not a report."""
    out: dict = {}

    missing = CertificationBoundGate()
    try:
        missing.emit_certification()
        out["certify_without_gate"] = {"raised": False}
    except OrderError as exc:
        out["certify_without_gate"] = {"raised": True, "type": "OrderError", "msg": str(exc)}

    degraded = CertificationBoundGate()
    degraded.run_gate(fixture_degraded_fusion())
    try:
        degraded.emit_certification()
        out["certify_after_reject"] = {"raised": False}
    except CertificationRefused as exc:
        out["certify_after_reject"] = {
            "raised": True,
            "type": "CertificationRefused",
            "msg": str(exc),
        }

    incon = CertificationBoundGate()
    incon.run_gate(fixture_inconclusive_near_best())
    try:
        incon.emit_certification()
        out["certify_after_inconclusive"] = {"raised": False, "verdict": incon.last_result}
    except CertificationRefused as exc:
        out["certify_after_inconclusive"] = {
            "raised": True,
            "type": "CertificationRefused",
            "msg": str(exc),
            "verdict": (incon.last_result or {}).get("verdict"),
        }

    good = CertificationBoundGate()
    good.run_gate(fixture_good_fusion())
    record = good.emit_certification()
    out["certify_after_clear"] = {"raised": False, "record": record}
    try:
        good.run_gate(fixture_degraded_fusion())
        out["gate_after_certification"] = {"raised": False}
    except OrderError as exc:
        out["gate_after_certification"] = {
            "raised": True,
            "type": "OrderError",
            "msg": str(exc),
        }

    out["pass"] = (
        out["certify_without_gate"].get("raised") is True
        and out["certify_after_reject"].get("raised") is True
        and out["certify_after_inconclusive"].get("raised") is True
        and out["certify_after_inconclusive"].get("verdict") == INCONCLUSIVE
        and out["certify_after_clear"].get("raised") is False
        and (out["certify_after_clear"].get("record") or {}).get("gate_ran_before_certification")
        is True
        and out["gate_after_certification"].get("raised") is True
    )
    return out
