#!/usr/bin/env python3
"""Deterministic impacted-test selectors for TST-0337.

Coverage-map and dependency-graph selectors are in scope.
A predictive / ML selector is out of scope and must be rejected.
Tests absent from the coverage map default to SELECTED.
"""
from __future__ import annotations

import inspect
from pathlib import Path

BANNED_ML = (
    "sklearn",
    "predict_proba",
    "RandomForest",
    "GradientBoosting",
    "tensorflow",
    "torch.",
    "neural_net",
    "xgboost",
)

ALLOWED_KINDS = frozenset({"coverage-map", "dependency-graph"})


class SelectorRejected(ValueError):
    """Raised when a predictive or otherwise non-deterministic selector is offered."""


def _names(files: list[str] | tuple[str, ...]) -> set[str]:
    return {Path(str(f)).name for f in files}


class CoverageMapSelector:
    """Select tests whose mapped files intersect the changed set.

    Any test not present in the coverage map is SELECTED (new-file default).
    """

    kind = "coverage-map"

    def __init__(self, coverage_map: dict[str, list[str]], all_tests: list[str]):
        self.coverage_map = {k: list(v) for k, v in coverage_map.items()}
        self.all_tests = list(all_tests)

    def select(self, changed_files: list[str]) -> list[str]:
        changed = _names(changed_files)
        mapped = set(self.coverage_map)
        selected: list[str] = []
        for test_id in self.all_tests:
            if test_id not in mapped:
                selected.append(test_id)
                continue
            files = _names(self.coverage_map[test_id])
            if files & changed:
                selected.append(test_id)
        return selected


class DependencyGraphSelector:
    """Select tests whose import-graph closure includes a changed module.

    Tests with no declared entrypoint (not yet in the map) default to SELECTED.
    """

    kind = "dependency-graph"

    def __init__(
        self,
        entrypoints: dict[str, str],
        import_graph: dict[str, list[str]],
        all_tests: list[str],
    ):
        self.entrypoints = dict(entrypoints)
        self.import_graph = {k: list(v) for k, v in import_graph.items()}
        self.all_tests = list(all_tests)

    def _closure(self, module: str) -> set[str]:
        seen: set[str] = set()
        stack = [module]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.import_graph.get(cur) or [])
        return seen

    def select(self, changed_files: list[str]) -> list[str]:
        changed_modules = {Path(str(f)).stem for f in changed_files}
        selected: list[str] = []
        for test_id in self.all_tests:
            entry = self.entrypoints.get(test_id)
            if entry is None:
                selected.append(test_id)
                continue
            if self._closure(entry) & changed_modules:
                selected.append(test_id)
        return selected


class FilenameOnlySelector:
    """Unsound control: only the test named test_{stem}_public.

    Misses every helper()/mid/root failure that a file-level map would catch.
    """

    kind = "filename-only"

    def __init__(self, all_tests: list[str]):
        self.all_tests = list(all_tests)

    def select(self, changed_files: list[str]) -> list[str]:
        stems = {Path(str(f)).stem for f in changed_files}
        wanted = {f"test_{s}_public" for s in stems}
        return [t for t in self.all_tests if t in wanted]


class PredictiveSelector:
    """Out-of-scope control: hash-scored 'probability' ranking. Must be rejected."""

    kind = "predictive"

    def __init__(self, all_tests: list[str], top_k: int = 3):
        self.all_tests = list(all_tests)
        self.top_k = top_k

    def select(self, changed_files: list[str]) -> list[str]:
        key = "|".join(sorted(changed_files))
        ranked = sorted(
            self.all_tests,
            key=lambda t: hash((t, key)) & 0xFFFFFFFF,
        )
        return ranked[: self.top_k]


def reject_if_non_deterministic(selector: object) -> None:
    kind = str(getattr(selector, "kind", "") or "")
    if kind not in ALLOWED_KINDS:
        raise SelectorRejected(
            "predictive selector is out of scope and must be rejected; "
            "the selector must be deterministic (dependency graph or "
            f"coverage map); got kind={kind!r}"
        )
    try:
        src = inspect.getsource(type(selector))
    except (OSError, TypeError):
        src = ""
    lowered = src.lower()
    for token in BANNED_ML:
        if token.lower() in lowered:
            raise SelectorRejected(
                f"ML token {token!r} found in selector source; predictive "
                "selectors are out of scope"
            )
