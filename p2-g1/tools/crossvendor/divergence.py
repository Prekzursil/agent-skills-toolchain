"""Byte-level four-class path classifier (identical / ahead / behind / diverged)."""
from __future__ import annotations

from typing import Any

from .fixtures import labelled_cases

CLASSES = ("IDENTICAL", "AHEAD", "BEHIND", "DIVERGED")


def unique_spans(ours: bytes | str, theirs: bytes | str) -> dict[str, bool]:
    o = ours if isinstance(ours, bytes) else str(ours).encode("utf-8")
    t = theirs if isinstance(theirs, bytes) else str(theirs).encode("utf-8")
    return _unique(o, t)


def _unique(ours: bytes, theirs: bytes) -> dict[str, bool]:
    if ours == theirs:
        return {"ours_unique": False, "theirs_unique": False}
    o_tok = set(ours.split())
    t_tok = set(theirs.split())
    ours_u = bool(o_tok - t_tok)
    theirs_u = bool(t_tok - o_tok)
    if not ours_u and not theirs_u:
        # Equal token sets but unequal bytes (order/whitespace): treat as both unique.
        ours_u = True
        theirs_u = True
    return {"ours_unique": ours_u, "theirs_unique": theirs_u}


def classify_bytes(ours: bytes | str, theirs: bytes | str) -> str:
    o = ours if isinstance(ours, bytes) else str(ours).encode("utf-8")
    t = theirs if isinstance(theirs, bytes) else str(theirs).encode("utf-8")
    u = _unique(o, t)
    if not u["ours_unique"] and not u["theirs_unique"]:
        return "IDENTICAL"
    if u["ours_unique"] and not u["theirs_unique"]:
        return "AHEAD"
    if u["theirs_unique"] and not u["ours_unique"]:
        return "BEHIND"
    return "DIVERGED"


def one_directional_check(ours: bytes | str, theirs: bytes | str) -> str:
    """One-directional check cannot emit DIVERGED; it treats both-unique as AHEAD."""
    two = classify_bytes(ours, theirs)
    if two == "DIVERGED":
        return "AHEAD"
    return two


def error_points_at_data_loss(truth: str, predicted: str) -> bool:
    """A DIVERGED case predicted AHEAD is a data-loss miss (overwrite unique theirs)."""
    return truth == "DIVERGED" and predicted == "AHEAD"


def _score(one_directional: bool) -> dict[str, Any]:
    cases = labelled_cases()
    per_class: dict[str, dict[str, Any]] = {
        c: {"n": 0, "correct": 0, "accuracy": 0.0, "errors": []} for c in CLASSES
    }
    emitted_diverged = 0
    data_loss = 0
    total_errors = 0
    non_data_loss = 0
    for case in cases:
        label = case["label"]
        pred = (
            one_directional_check(case["ours"], case["theirs"])
            if one_directional
            else classify_bytes(case["ours"], case["theirs"])
        )
        bucket = per_class[label]
        bucket["n"] += 1
        if pred == "DIVERGED":
            emitted_diverged += 1
        if pred == label:
            bucket["correct"] += 1
        else:
            bucket["errors"].append({"id": case["id"], "pred": pred})
            total_errors += 1
            if error_points_at_data_loss(label, pred):
                data_loss += 1
            else:
                non_data_loss += 1
    for bucket in per_class.values():
        n = bucket["n"]
        bucket["accuracy"] = (bucket["correct"] / n) if n else 0.0
    return {
        "instrument": "one-directional" if one_directional else "two-directional",
        "n_cases": len(cases),
        "per_class": per_class,
        "emitted_diverged_count": emitted_diverged,
        "error_direction": {
            "total_errors": total_errors,
            "data_loss_count": data_loss,
            "non_data_loss_count": non_data_loss,
            "data_loss_fraction_of_errors": (data_loss / total_errors) if total_errors else 0.0,
            "definition": "DIVERGED predicted as AHEAD is data-loss (unique theirs overwritten)",
        },
        "pooled_accuracy_is_not_the_figure": True,
    }


def score_labelled(*, one_directional: bool = False) -> dict[str, Any]:
    return _score(one_directional)


def fixture_public_catalogue() -> list[str]:
    return [c["id"] for c in labelled_cases()]
