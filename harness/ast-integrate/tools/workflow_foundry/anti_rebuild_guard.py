"""Incumbent consult: ADOPT when a covering baseline meets the bar (IMP-0211)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ADOPT = "ADOPT"
BUILD = "BUILD"
KIND_INCUMBENT_AT_OR_ABOVE_BAR = "incumbent-at-or-above-bar"
KIND_ABSENT_COVERAGE = "absent-coverage"
KIND_INCUMBENT_BELOW_BAR = "incumbent-below-bar"
KIND_INCOMPARABLE_BASELINE = "incomparable-baseline"
KIND_INFERIOR_BASELINE = "inferior-baseline"


class GuardError(ValueError):
    pass


def assert_build_citation_structural(citation: dict[str, Any]) -> None:
    kind = citation.get("kind")
    if kind not in {KIND_ABSENT_COVERAGE, KIND_INFERIOR_BASELINE, KIND_INCOMPARABLE_BASELINE}:
        raise GuardError(f"non-structural kind {kind!r}")
    if "kind" not in citation:
        raise GuardError("missing kind")


@dataclass
class Registry:
    incumbents: list[dict[str, Any]] = field(default_factory=list)

    def ids(self) -> list[str]:
        return [str(i.get("workflow_id") or "") for i in self.incumbents]


def load_registry(path: Path) -> Registry:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return Registry(incumbents=list(doc.get("incumbents") or []))


def _caps(vec: dict[str, Any] | None) -> set[str]:
    if not isinstance(vec, dict):
        return set()
    return {str(c) for c in (vec.get("capabilities") or [])}


def _same_corpus(goal: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return (
        str(goal.get("corpus_id")) == str(baseline.get("corpus_id"))
        and str(goal.get("corpus_version")) == str(baseline.get("corpus_version"))
        and str(goal.get("spec_version")) == str(baseline.get("spec_version"))
    )


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
            "citation": self.citation,
            "searched_incumbent_ids": self.searched_incumbent_ids,
        }


def consult(goal: dict[str, Any], registry: Registry) -> ConsultResult:
    need = _caps(goal.get("capability_vector"))
    bar = float(goal.get("quality_bar") or 0.0)
    searched = registry.ids()
    covering: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    incomparable: list[dict[str, Any]] = []
    for inc in registry.incumbents:
        have = _caps(inc.get("capability_vector"))
        baseline = inc.get("baseline") or {}
        if not need <= have:
            continue
        if not _same_corpus(goal, baseline):
            incomparable.append(inc)
            continue
        rows = baseline.get("per_case") or []
        scores = [float(r.get("score") or 0.0) for r in rows if isinstance(r, dict)]
        mean = sum(scores) / len(scores) if scores else 0.0
        covering.append((mean, inc, baseline))
    if not covering:
        if incomparable and need <= _caps((incomparable[0] or {}).get("capability_vector")):
            inc = incomparable[0]
            return ConsultResult(
                action=BUILD,
                blocks_build=False,
                citation={
                    "kind": KIND_INCOMPARABLE_BASELINE,
                    "incumbent_id": inc.get("workflow_id"),
                    "capability_gap": [],
                },
                searched_incumbent_ids=searched,
            )
        missing = sorted(need)
        return ConsultResult(
            action=BUILD,
            blocks_build=False,
            citation={
                "kind": KIND_ABSENT_COVERAGE,
                "incumbent_id": None,
                "capability_gap": missing,
            },
            searched_incumbent_ids=searched,
        )
    covering.sort(key=lambda t: t[0], reverse=True)
    mean, inc, baseline = covering[0]
    if mean >= bar:
        return ConsultResult(
            action=ADOPT,
            blocks_build=True,
            citation={
                "kind": KIND_INCUMBENT_AT_OR_ABOVE_BAR,
                "incumbent_id": inc.get("workflow_id"),
                "benchmark": {
                    "run_id": baseline.get("run_id"),
                    "mean_score": mean,
                    "quality_bar": bar,
                },
            },
            searched_incumbent_ids=searched,
        )
    return ConsultResult(
        action=BUILD,
        blocks_build=False,
        citation={
            "kind": KIND_INCUMBENT_BELOW_BAR,
            "incumbent_id": inc.get("workflow_id"),
            "benchmark": {
                "run_id": baseline.get("run_id"),
                "mean_score": mean,
                "quality_bar": bar,
            },
        },
        searched_incumbent_ids=searched,
    )
