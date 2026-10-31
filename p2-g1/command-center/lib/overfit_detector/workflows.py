"""Honest rule vs memorize-visible overfit workflows."""
from __future__ import annotations

from typing import Iterable

from overfit_detector.corpus import Case, true_label


class MemorizeVisibleWorkflow:
    def __init__(self, visible: Iterable[Case]) -> None:
        vis = list(visible)
        self.trained_ids = [c.id for c in vis]
        self._mem = {c.id: c.label for c in vis}

    def predict(self, case: Case) -> int | None:
        return self._mem.get(case.id)


class TrueRuleWorkflow:
    trained_ids: list[str] = []

    def predict(self, case: Case) -> int:
        return true_label(case.x)
