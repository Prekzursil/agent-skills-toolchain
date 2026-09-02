"""Anti-rebuild guard: consult the incumbent registry before building (IMP-0211).

``consult(goal, registry)`` searches every registered incumbent for one whose
capability vector covers the goal, then decides:

* ``ADOPT`` / ``incumbent-at-or-above-bar`` -- a covering incumbent has a
  comparable baseline (same corpus, corpus version and spec version) whose mean,
  recomputed from its per-case rows, meets the goal's quality bar. BUILD is
  blocked and the citation names the run.
* ``ADOPT`` / ``incomparable-baseline`` -- a covering incumbent exists but its
  baseline was measured on a different corpus/spec, so inferiority cannot be
  shown. The guard fails closed: BUILD stays blocked.
* ``BUILD`` / ``inferior-baseline`` -- every covering incumbent has a comparable
  baseline below the bar; the best one is cited with its recomputed mean.
* ``BUILD`` / ``absent-coverage`` -- nothing covers the goal; the citation lists
  the capabilities the nearest incumbent lacks.

Citations are STRUCTURAL: a closed ``kind`` vocabulary plus typed fields, and
:func:`assert_build_citation_structural` refuses prose or missing pieces.
Summary scores stored next to a baseline are never trusted; only per-case rows
are aggregated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ADOPT = "ADOPT"
BUILD = "BUILD"
KIND_INCUMBENT_AT_OR_ABOVE_BAR = "incumbent-at-or-above-bar"
KIND_ABSENT_COVERAGE = "absent-coverage"
KIND_INCOMPARABLE_BASELINE = "incomparable-baseline"
KIND_INFERIOR_BASELINE = "inferior-baseline"
# Older callers imported this name; an inferior comparable baseline IS the
# "below bar" case, so the two names denote one kind.
KIND_INCUMBENT_BELOW_BAR = KIND_INFERIOR_BASELINE

BUILD_KINDS: frozenset[str] = frozenset({KIND_ABSENT_COVERAGE, KIND_INFERIOR_BASELINE})
ADOPT_KINDS: frozenset[str] = frozenset({KIND_INCUMBENT_AT_OR_ABOVE_BAR, KIND_INCOMPARABLE_BASELINE})
CITATION_KINDS: frozenset[str] = BUILD_KINDS | ADOPT_KINDS

_COMPARABILITY_FIELDS: tuple[str, ...] = ("corpus_id", "corpus_version", "spec_version")


class GuardError(ValueError):
    """A citation (or registry record) is not structurally valid."""


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class CapabilityVector:
    taxonomy_id: str | None
    taxonomy_version: str | None
    capabilities: frozenset[str]

    @classmethod
    def from_doc(cls, doc: Any) -> "CapabilityVector":
        if not isinstance(doc, dict):
            return cls(taxonomy_id=None, taxonomy_version=None, capabilities=frozenset())
        raw = doc.get("capabilities") or []
        caps = frozenset(str(c) for c in raw if str(c).strip())
        tv = doc.get("taxonomy_version")
        return cls(
            taxonomy_id=None if doc.get("taxonomy_id") is None else str(doc["taxonomy_id"]),
            taxonomy_version=None if tv is None else str(tv),
            capabilities=caps,
        )

    def same_taxonomy(self, other: "CapabilityVector") -> bool:
        if self.taxonomy_id is None or other.taxonomy_id is None:
            return True
        return self.taxonomy_id == other.taxonomy_id


@dataclass(frozen=True)
class CaseRow:
    case_id: str
    score: float


@dataclass(frozen=True)
class Baseline:
    """A benchmark run; ``mean_score`` is always recomputed from ``per_case``."""

    run_id: str | None
    corpus_id: str | None
    corpus_version: str | None
    spec_version: str | None
    per_case: tuple[CaseRow, ...] = ()
    workflow_id: str | None = None

    @classmethod
    def from_doc(cls, doc: Any) -> "Baseline | None":
        if not isinstance(doc, dict):
            return None
        rows: list[CaseRow] = []
        for i, row in enumerate(doc.get("per_case") or []):
            if not isinstance(row, dict) or "score" not in row:
                raise GuardError(f"baseline {doc.get('run_id')!r} per_case[{i}] has no score")
            try:
                score = float(row["score"])
            except (TypeError, ValueError) as exc:
                raise GuardError(f"baseline {doc.get('run_id')!r} per_case[{i}] score not numeric") from exc
            rows.append(CaseRow(case_id=str(row.get("case_id") or f"case-{i}"), score=score))

        def _s(key: str) -> str | None:
            value = doc.get(key)
            return None if value is None else str(value)

        return cls(
            run_id=_s("run_id"),
            corpus_id=_s("corpus_id"),
            corpus_version=_s("corpus_version"),
            spec_version=_s("spec_version"),
            per_case=tuple(rows),
            workflow_id=_s("workflow_id"),
        )

    @property
    def n_cases(self) -> int:
        return len(self.per_case)

    def mean_score(self) -> float:
        """Arithmetic mean of the per-case scores. Any stored summary is ignored."""
        if not self.per_case:
            raise GuardError(f"baseline {self.run_id!r} has no per-case rows to aggregate")
        return sum(r.score for r in self.per_case) / len(self.per_case)

    def comparability_mismatch(self, goal: dict[str, Any]) -> list[str]:
        """Fields on which this baseline was not measured under the goal's conditions."""
        mismatch = [
            name
            for name in _COMPARABILITY_FIELDS
            if str(goal.get(name)) != str(getattr(self, name))
        ]
        if not self.per_case:
            mismatch.append("per_case")
        return mismatch

    def as_ref(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "spec_version": self.spec_version,
            "n_cases": self.n_cases,
        }


@dataclass(frozen=True)
class Incumbent:
    workflow_id: str
    capability_vector: CapabilityVector
    baseline: Baseline | None = None

    @classmethod
    def from_doc(cls, doc: Any) -> "Incumbent":
        if not isinstance(doc, dict) or not str(doc.get("workflow_id") or "").strip():
            raise GuardError("incumbent record needs a workflow_id")
        return cls(
            workflow_id=str(doc["workflow_id"]),
            capability_vector=CapabilityVector.from_doc(doc.get("capability_vector")),
            baseline=Baseline.from_doc(doc.get("baseline")),
        )

    def covers(self, goal_vector: CapabilityVector) -> bool:
        return self.capability_vector.same_taxonomy(goal_vector) and (
            goal_vector.capabilities <= self.capability_vector.capabilities
        )

    def gap_for(self, goal_vector: CapabilityVector) -> frozenset[str]:
        return goal_vector.capabilities - self.capability_vector.capabilities


@dataclass
class Registry:
    incumbents: list[Incumbent] = field(default_factory=list)

    def ids(self) -> list[str]:
        return [i.workflow_id for i in self.incumbents]

    def get(self, workflow_id: str) -> Incumbent | None:
        for inc in self.incumbents:
            if inc.workflow_id == workflow_id:
                return inc
        return None


def registry_from_docs(docs: Iterable[Any]) -> Registry:
    return Registry(incumbents=[Incumbent.from_doc(d) for d in docs])


def load_registry(path: Path) -> Registry:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise GuardError(f"registry {path} is not a JSON object")
    return registry_from_docs(doc.get("incumbents") or [])


# --------------------------------------------------------------------------- verdict


@dataclass
class ConsultResult:
    action: str
    blocks_build: bool
    citation: dict[str, Any]
    searched_incumbent_ids: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "blocks_build": self.blocks_build,
            "citation": json.loads(json.dumps(self.citation)),
            "searched_incumbent_ids": list(self.searched_incumbent_ids),
        }


Verdict = ConsultResult


def _benchmark(baseline: Baseline, bar: float) -> dict[str, Any]:
    mean = baseline.mean_score()
    return {
        "run_id": baseline.run_id,
        "mean_score": mean,
        "quality_bar": bar,
        "at_or_above_bar": mean >= bar,
        "n_cases": baseline.n_cases,
        "corpus_id": baseline.corpus_id,
        "corpus_version": baseline.corpus_version,
        "spec_version": baseline.spec_version,
    }


def consult(goal: dict[str, Any], registry: Registry) -> ConsultResult:
    """Decide ADOPT or BUILD for ``goal`` against every incumbent in ``registry``."""
    if not isinstance(goal, dict):
        raise GuardError("goal must be a JSON object")
    goal_vector = CapabilityVector.from_doc(goal.get("capability_vector"))
    try:
        bar = float(goal.get("quality_bar"))
    except (TypeError, ValueError) as exc:
        raise GuardError("goal.quality_bar must be numeric") from exc
    searched = registry.ids()

    covering = [inc for inc in registry.incumbents if inc.covers(goal_vector)]
    if not covering:
        nearest: Incumbent | None = None
        if registry.incumbents:
            nearest = min(
                registry.incumbents,
                key=lambda inc: (len(inc.gap_for(goal_vector)), inc.workflow_id),
            )
        gap = sorted(nearest.gap_for(goal_vector) if nearest else goal_vector.capabilities)
        return ConsultResult(
            action=BUILD,
            blocks_build=False,
            citation={
                "kind": KIND_ABSENT_COVERAGE,
                "incumbent_id": None,
                "capability_gap": gap,
                "nearest_incumbent_id": nearest.workflow_id if nearest else None,
                "taxonomy_id": goal_vector.taxonomy_id,
            },
            searched_incumbent_ids=searched,
        )

    comparable: list[tuple[float, Incumbent, Baseline]] = []
    incomparable: list[tuple[Incumbent, list[str]]] = []
    for inc in covering:
        base = inc.baseline
        mismatch = base.comparability_mismatch(goal) if base is not None else ["baseline"]
        if base is None or mismatch:
            incomparable.append((inc, mismatch))
            continue
        comparable.append((base.mean_score(), inc, base))

    comparable.sort(key=lambda t: (-t[0], t[1].workflow_id))
    if comparable and comparable[0][0] >= bar:
        mean, inc, base = comparable[0]
        return ConsultResult(
            action=ADOPT,
            blocks_build=True,
            citation={
                "kind": KIND_INCUMBENT_AT_OR_ABOVE_BAR,
                "incumbent_id": inc.workflow_id,
                "benchmark": _benchmark(base, bar),
            },
            searched_incumbent_ids=searched,
        )

    if incomparable:
        # Fail closed: a covering incumbent exists and nothing proves it inferior.
        incomparable.sort(key=lambda t: t[0].workflow_id)
        inc, mismatch = incomparable[0]
        return ConsultResult(
            action=ADOPT,
            blocks_build=True,
            citation={
                "kind": KIND_INCOMPARABLE_BASELINE,
                "incumbent_id": inc.workflow_id,
                "baseline": inc.baseline.as_ref() if inc.baseline else None,
                "goal_conditions": {name: goal.get(name) for name in _COMPARABILITY_FIELDS},
                "mismatch": list(mismatch),
                "required_action": "re-benchmark the incumbent on the goal corpus before BUILD",
            },
            searched_incumbent_ids=searched,
        )

    mean, inc, base = comparable[0]
    return ConsultResult(
        action=BUILD,
        blocks_build=False,
        citation={
            "kind": KIND_INFERIOR_BASELINE,
            "incumbent_id": inc.workflow_id,
            "benchmark": _benchmark(base, bar),
        },
        searched_incumbent_ids=searched,
    )


# --------------------------------------------------------------------------- structural check


def _require_str(citation: dict[str, Any], key: str) -> str:
    value = citation.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GuardError(f"citation.{key} must be a non-empty string")
    return value


def _require_number(doc: dict[str, Any], key: str, where: str) -> float:
    value = doc.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardError(f"{where}.{key} must be numeric")
    return float(value)


def _check_benchmark(citation: dict[str, Any], *, expect_at_or_above: bool) -> None:
    bench = citation.get("benchmark")
    if not isinstance(bench, dict):
        raise GuardError("citation.benchmark must be an object")
    _require_str(bench, "run_id")
    mean = _require_number(bench, "mean_score", "benchmark")
    bar = _require_number(bench, "quality_bar", "benchmark")
    flag = bench.get("at_or_above_bar")
    if flag is not None and flag is not expect_at_or_above:
        raise GuardError(f"benchmark.at_or_above_bar={flag!r} contradicts kind")
    if expect_at_or_above and mean < bar:
        raise GuardError("at-or-above-bar citation carries a mean below the bar")
    if not expect_at_or_above and mean >= bar:
        raise GuardError("inferior-baseline citation carries a mean at or above the bar")


def assert_build_citation_structural(verdict: dict[str, Any]) -> dict[str, Any]:
    """Refuse any verdict whose citation is not a closed-vocabulary, typed record.

    Accepts a full verdict (``action``/``blocks_build``/``citation``) or a bare
    citation. Returns the validated citation so callers can chain on it.
    """
    if not isinstance(verdict, dict):
        raise GuardError("verdict must be a JSON object")
    if "citation" in verdict:
        citation = verdict["citation"]
        action = verdict.get("action")
    else:
        citation, action = verdict, None
    if not isinstance(citation, dict):
        raise GuardError("citation must be an object")
    if "kind" not in citation:
        raise GuardError("missing kind")
    kind = citation["kind"]
    if not isinstance(kind, str) or kind not in CITATION_KINDS:
        raise GuardError(f"non-structural kind {kind!r}")

    if action is not None:
        if action not in (ADOPT, BUILD):
            raise GuardError(f"unknown action {action!r}")
        if action == BUILD and kind not in BUILD_KINDS:
            raise GuardError(f"BUILD may cite only {sorted(BUILD_KINDS)}, got {kind!r}")
        if action == ADOPT and kind not in ADOPT_KINDS:
            raise GuardError(f"ADOPT may cite only {sorted(ADOPT_KINDS)}, got {kind!r}")
        blocks = verdict.get("blocks_build")
        if blocks is not None and blocks is not (action == ADOPT):
            raise GuardError(f"blocks_build={blocks!r} contradicts action {action}")

    if kind == KIND_ABSENT_COVERAGE:
        if citation.get("incumbent_id") is not None:
            raise GuardError("absent-coverage citation must not name an incumbent")
        gap = citation.get("capability_gap")
        if not isinstance(gap, list) or not gap:
            raise GuardError("absent-coverage citation needs a non-empty capability_gap list")
        if not all(isinstance(c, str) and c.strip() for c in gap):
            raise GuardError("capability_gap entries must be non-empty strings")
    elif kind == KIND_INFERIOR_BASELINE:
        _require_str(citation, "incumbent_id")
        _check_benchmark(citation, expect_at_or_above=False)
    elif kind == KIND_INCUMBENT_AT_OR_ABOVE_BAR:
        _require_str(citation, "incumbent_id")
        _check_benchmark(citation, expect_at_or_above=True)
    elif kind == KIND_INCOMPARABLE_BASELINE:
        _require_str(citation, "incumbent_id")
    return citation
