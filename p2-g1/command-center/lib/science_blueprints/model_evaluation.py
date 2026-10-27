"""Model evaluation: refuse visible-slice-only verdicts."""
from __future__ import annotations

from dataclasses import dataclass

from overfit_detector.partition import HELD_OUT, VISIBLE, slice_of


class VisibleSliceOnlyVerdictError(ValueError):
    reason_id = "model-eval.visible-slice-only"

    def __init__(self, message: str = "visible-slice-only") -> None:
        super().__init__(message)
        self.reason_id = "model-eval.visible-slice-only"


class HonestRule:
    def predict(self, case: "Case") -> str:
        return case.label


@dataclass(frozen=True)
class Case:
    id: str
    label: str


def build_eval_corpus(n: int) -> list[Case]:
    return [Case(id=f"case-{i:03d}", label="pos" if i % 2 == 0 else "neg") for i in range(n)]


def try_evaluate(model: HonestRule, cases: list[Case], slice_name: str) -> dict:
    if slice_name in {VISIBLE, "all"}:
        return {
            "refused": True,
            "reason_id": "model-eval.visible-slice-only",
            "verdict": None,
            "accuracy": None,
        }
    selected = [c for c in cases if slice_of(c.id) == slice_name]
    if not selected:
        selected = [c for c in cases if slice_of(c.id) == HELD_OUT]
    correct = sum(1 for c in selected if model.predict(c) == c.label)
    acc = correct / len(selected)
    return {
        "refused": False,
        "verdict": "EVALUATED",
        "accuracy": acc,
        "heldout_n": len(selected),
        "slice": slice_name,
    }


def evaluate(model: HonestRule, cases: list[Case], slice_name: str) -> dict:
    result = try_evaluate(model, cases, slice_name)
    if result.get("refused"):
        raise VisibleSliceOnlyVerdictError()
    return result
