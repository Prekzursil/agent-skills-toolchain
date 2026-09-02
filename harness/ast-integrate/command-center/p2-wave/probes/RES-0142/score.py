#!/usr/bin/env python3
"""Preregistered observable-field scorer. Title/body are not inputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "threshold_prereg.json"
FIELDS_PATH = HERE / "snapshots" / "fields.json"
LABELS_PATH = HERE / "estate_labels.json"


def load_prereg() -> dict[str, Any]:
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if doc.get("recorded_before_any_replay_or_control") is not True:
        raise RuntimeError("preregistration was not frozen before scoring")
    for key in ("window", "floor", "min_sources", "early_max_index", "holdout_ids"):
        if key not in doc:
            raise RuntimeError(f"prereg missing {key}")
    if len(doc["holdout_ids"]) != 8:
        raise RuntimeError("holdout_ids must contain exactly 8 ids")
    return doc


def load_fields() -> dict[str, dict[str, Any]]:
    doc = json.loads(FIELDS_PATH.read_text(encoding="utf-8"))
    rows = doc.get("issues") or []
    if len(rows) != 25:
        raise RuntimeError(f"expected 25 frozen issues, got {len(rows)}")
    return {row["id"]: row for row in rows}


def load_labels() -> dict[str, Any]:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def _labels(issue: dict[str, Any]) -> set[str]:
    return {str(x).lower() for x in (issue.get("labels") or [])}


def field_tuple(issue: dict[str, Any]) -> str:
    labs = tuple(sorted(_labels(issue)))
    reactions = int(issue.get("reaction_count") or 0)
    if reactions <= 0:
        rx = "0"
    elif reactions <= 2:
        rx = "1-2"
    else:
        rx = "3+"
    comments = int(issue.get("comment_count") or 0)
    if comments <= 0:
        cc = "0"
    elif comments <= 2:
        cc = "1-2"
    else:
        cc = "3+"
    parts = (
        str(issue.get("state") or "unknown"),
        labs,
        rx,
        cc,
        "ms" if issue.get("milestone") else "no-ms",
        "pr" if issue.get("is_pull_request") else "issue",
        "dup" if "duplicate" in _labels(issue) else "nodup",
        "maint" if issue.get("maintainer_response_hours") is not None else "no-maint",
    )
    return "|".join(str(p) for p in parts)


def score_issue(issue: dict[str, Any], prereg: dict[str, Any] | None = None) -> int:
    if prereg is None:
        prereg = load_prereg()
    w = prereg["weights"]
    labs = _labels(issue)
    s = 0
    if "bug" in labs:
        s += int(w["has_bug_label"])
    if int(issue.get("reaction_count") or 0) >= 1:
        s += int(w["reactions_ge_1"])
    if issue.get("maintainer_response_hours") is not None:
        s += int(w["maintainer_responded"])
    if issue.get("is_pull_request"):
        s += int(w["is_pull_request"])
    if issue.get("milestone"):
        s += int(w["has_milestone"])
    if "duplicate" in labs:
        s += int(w["has_duplicate_label"])
    if "stale" in labs:
        s += int(w["has_stale_label"])
    return s


def predict_blocked(issue: dict[str, Any], prereg: dict[str, Any] | None = None) -> bool:
    if prereg is None:
        prereg = load_prereg()
    return score_issue(issue, prereg) >= int(prereg["predict_blocked_if_score_gte"])


def fire_index_from_yields(
    yields: list[int],
    window: int,
    floor: float,
    min_sources: int,
) -> int | None:
    n = len(yields)
    start = max(int(min_sources), int(window))
    for t in range(start, n + 1):
        chunk = yields[t - window : t]
        if len(chunk) < window:
            continue
        mean = sum(chunk) / float(window)
        if mean <= float(floor) + 1e-12:
            return t
    return None


def score_run(
    sources: list[dict[str, Any]], prereg: dict[str, Any] | None = None
) -> dict[str, Any]:
    if prereg is None:
        prereg = load_prereg()
    seen: set[str] = set()
    yields: list[int] = []
    first_seen: dict[str, int] = {}
    for i, src in enumerate(sources, start=1):
        key = field_tuple(src)
        new = 0
        if key not in seen:
            seen.add(key)
            first_seen[key] = i
            new = 1
        yields.append(new)
    fire = fire_index_from_yields(
        yields,
        int(prereg["window"]),
        float(prereg["floor"]),
        int(prereg["min_sources"]),
    )
    miss_count = None
    miss_rate = None
    if fire is not None:
        miss_count = sum(1 for idx in first_seen.values() if idx > fire)
        miss_rate = (miss_count / len(seen)) if seen else 0.0
    return {
        "yields": yields,
        "fire_index": fire,
        "fired": fire is not None,
        "early": fire is not None and fire <= int(prereg["early_max_index"]),
        "total_distinct": len(seen),
        "n_sources": len(sources),
        "miss_count": miss_count,
        "miss_rate": miss_rate,
        "distinctness": prereg["distinctness"],
    }


def score_run_string_equality(
    sources: list[dict[str, Any]], prereg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Foil: identity is a dummy title string, not the field tuple."""
    if prereg is None:
        prereg = load_prereg()
    seen: set[str] = set()
    yields: list[int] = []
    for src in sources:
        key = str(src.get("dummy_title") or src.get("id") or "").strip()
        new = 0
        if key and key not in seen:
            seen.add(key)
            new = 1
        yields.append(new)
    fire = fire_index_from_yields(
        yields,
        int(prereg["window"]),
        float(prereg["floor"]),
        int(prereg["min_sources"]),
    )
    return {
        "yields": yields,
        "fire_index": fire,
        "fired": fire is not None,
        "total_distinct": len(seen),
        "distinctness": "string-equality",
    }


def token_counter_fire(sources: list[dict[str, Any]], budget: int) -> int | None:
    """Foil: fires when cumulative dummy-token count exceeds budget."""
    total = 0
    for i, src in enumerate(sources, start=1):
        text = str(src.get("dummy_title") or src.get("id") or "x")
        total += max(1, len(text.split()))
        if total > budget:
            return i
    return None


def confusion(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if (not t) and (not p))
    fp = sum(1 for t, p in zip(y_true, y_pred) if (not t) and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and (not p))
    n = len(y_true)
    acc = (tp + tn) / n if n else None
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    pos = sum(1 for t in y_true if t)
    return {
        "n": n,
        "positives": pos,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": acc,
        "precision_blocked": prec,
        "recall_blocked": rec,
        "blocker_class_validated": pos > 0,
    }


def classify_set(
    ids: list[str],
    fields: dict[str, dict[str, Any]],
    labels: dict[str, Any],
    prereg: dict[str, Any],
) -> dict[str, Any]:
    labmap = labels.get("labels") or {}
    y_true: list[bool] = []
    y_pred: list[bool] = []
    rows = []
    for iid in ids:
        issue = fields[iid]
        truth = bool((labmap.get(iid) or {}).get("blocked_this_estate"))
        pred = predict_blocked(issue, prereg)
        sc = score_issue(issue, prereg)
        y_true.append(truth)
        y_pred.append(pred)
        rows.append(
            {
                "id": iid,
                "estate_blocked": truth,
                "predicted_blocked": pred,
                "score": sc,
                "field_tuple": field_tuple(issue),
                "state": issue.get("state"),
                "labels": issue.get("labels"),
                "reaction_count": issue.get("reaction_count"),
                "milestone": issue.get("milestone"),
                "is_pull_request": issue.get("is_pull_request"),
                "maintainer_response_hours": issue.get("maintainer_response_hours"),
            }
        )
    return {"metrics": confusion(y_true, y_pred), "rows": rows}


def split_and_score(
    fields: dict[str, dict[str, Any]] | None = None,
    labels: dict[str, Any] | None = None,
    prereg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if prereg is None:
        prereg = load_prereg()
    if fields is None:
        fields = load_fields()
    if labels is None:
        labels = load_labels()
    hold = list(prereg["holdout_ids"])
    all_ids = list(fields.keys())
    missing = [i for i in hold if i not in fields]
    if missing:
        raise RuntimeError(f"holdout ids not in frozen fields: {missing}")
    train = [i for i in all_ids if i not in set(hold)]
    if len(hold) != 8 or len(train) != 17:
        raise RuntimeError(f"split sizes hold={len(hold)} train={len(train)}")
    return {
        "train": classify_set(train, fields, labels, prereg),
        "holdout": classify_set(hold, fields, labels, prereg),
        "all_25": classify_set(all_ids, fields, labels, prereg),
        "in_sample_only_status": "NOT VALIDATED",
        "holdout_ids": hold,
        "train_ids": train,
    }
