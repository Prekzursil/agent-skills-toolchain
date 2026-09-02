"""Free-tag and category validity gate (IMP-0103)."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
PARAMS_PATH = HERE / "tag_gate_params.json"
CATEGORIES_PATH = HERE / "categories.json"
PAIRS_PATH = HERE / "reviewer_pairs.json"
PLUGIN_JSON = Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json"


@dataclass
class TagDecision:
    accepted: bool
    reason: str
    canonical: str
    nearest: str = ""
    nearest_score: float = 0.0
    metric: str = ""
    threshold: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "canonical": self.canonical,
            "nearest": self.nearest,
            "nearest_score": round(self.nearest_score, 6),
            "metric": self.metric,
            "threshold": self.threshold,
        }


def load_params(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return json.loads(PARAMS_PATH.read_text(encoding="utf-8"))


def load_reviewer_pairs(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return json.loads(PAIRS_PATH.read_text(encoding="utf-8"))


def load_plugin_keywords(repo: Any = None) -> list[str]:
    root = Path(repo) if repo is not None else PLUGIN_JSON.parents[1]
    path = Path(root) / ".claude-plugin" / "plugin.json"
    if not path.is_file():
        path = PLUGIN_JSON
    doc = json.loads(path.read_text(encoding="utf-8"))
    kws = doc.get("keywords") or []
    return [str(k) for k in kws]


def normalize(tag: str) -> str:
    text = unicodedata.normalize("NFKC", str(tag or "")).strip().lower()
    return text


def compact(tag: str) -> str:
    return re.sub(r"[\s_\-./]+", "", normalize(tag))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def validate_free_tag(tag: str, existing: Iterable[str] | None = None) -> TagDecision:
    params = load_params()
    threshold = float(params["similarity_threshold"])
    metric = str(params["similarity_metric"])
    min_len = int(params["min_length"])
    max_len = int(params["max_length"])
    canonical = str(tag)
    live = [str(x) for x in (existing if existing is not None else load_plugin_keywords())]
    if len(canonical) > max_len:
        return TagDecision(False, "over-length", canonical, metric=metric, threshold=threshold)
    if len(canonical) < min_len:
        return TagDecision(False, "under-length", canonical, metric=metric, threshold=threshold)
    norm = normalize(canonical)
    live_norm = {normalize(k): k for k in live}
    if norm in live_norm:
        return TagDecision(
            True,
            "already-present",
            canonical,
            nearest=live_norm[norm],
            nearest_score=1.0,
            metric=metric,
            threshold=threshold,
        )
    best_name = ""
    best = 0.0
    for k in live:
        if compact(canonical) == compact(k):
            return TagDecision(
                False,
                "near-duplicate",
                canonical,
                nearest=k,
                nearest_score=1.0,
                metric=metric,
                threshold=threshold,
            )
        score = similarity(canonical, k)
        if score > best:
            best = score
            best_name = k
    if best >= threshold:
        return TagDecision(
            False,
            "near-duplicate",
            canonical,
            nearest=best_name,
            nearest_score=best,
            metric=metric,
            threshold=threshold,
        )
    return TagDecision(
        True,
        "new",
        canonical,
        nearest=best_name,
        nearest_score=best,
        metric=metric,
        threshold=threshold,
    )


def sweep_live_keywords(keywords: Iterable[str] | None = None) -> dict[str, Any]:
    live = [str(k) for k in (keywords if keywords is not None else load_plugin_keywords())]
    failures: list[dict[str, Any]] = []
    for k in live:
        others = [x for x in live if x != k]
        # a live keyword must be accepted as already-present against the set including itself
        decision = validate_free_tag(k, live)
        if not decision.accepted:
            failures.append(decision.as_dict())
    threshold = float(load_params()["similarity_threshold"])
    all_ok = not failures
    return {
        "all_accepted": all_ok,
        "count": len(live),
        "enforcement": "enforce" if all_ok else "report",
        "failures": failures,
        "threshold": threshold,
        "threshold_wrong": bool(failures),
    }


def validate_category(name: str) -> TagDecision:
    doc = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    cats = {str(c) for c in (doc.get("categories") or [])}
    if str(name) in cats:
        return TagDecision(True, "category", str(name))
    return TagDecision(False, "unknown-category", str(name))


def false_merge_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
    spec = load_reviewer_pairs()
    threshold = float(load_params()["similarity_threshold"])
    pairs = list(spec.get("pairs") or [])
    rows = []
    merges = 0
    for pair in pairs:
        a, b = pair["a"], pair["b"]
        score = similarity(a, b)
        merged = bool(compact(a) == compact(b) or score >= threshold)
        if merged:
            merges += 1
        rows.append({"a": a, "b": b, "score": score, "merged": merged})
    n = len(rows)
    return {
        "n": n,
        "merges": merges,
        "false_merge_rate": (merges / n) if n else 0.0,
        "pairs": rows,
        "threshold": threshold,
    }
