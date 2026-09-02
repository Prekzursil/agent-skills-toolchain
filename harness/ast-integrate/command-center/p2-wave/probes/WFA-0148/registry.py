#!/usr/bin/env python3
"""Load the 284-candidate registry and recount classifications two ways.

Signal A walks candidates[].classification.
Signal B reads the document counts block and never inspects the array.
Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is preferred when present.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from classifier import USED_DECLARED, VOCABULARY

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PUBLISHED_HISTOGRAM: dict[str, int] = {
    "ADOPT-AS-IS": 122,
    "UNKNOWN-NEEDS-PROBE": 44,
    "DISTILL": 43,
    "RETIRE": 24,
    "ADOPT-WITH-WRAPPER": 20,
    "REPAIR": 15,
    "EXTEND": 6,
    "MERGE": 6,
    "SPECIALIZE": 4,
}

SEARCH_PATHS = (
    Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    HERE / "fixtures/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)


def _features_for(label: str, index: int) -> dict[str, Any]:
    plane = "ast-integrate"
    rec: dict[str, Any] = {
        "id": f"wf-fixture-{index:03d}",
        "does": f"fixture candidate {index} labelled {label}",
        "license": "MIT",
        "runtime": plane,
        "control_plane": plane,
        "classification": label,
    }
    if label == "UNKNOWN-NEEDS-PROBE":
        rec.pop("does")
    elif label == "RETIRE":
        rec["archived"] = True
    elif label == "DISTILL":
        rec["distill_mechanisms"] = True
    elif label == "ADOPT-WITH-WRAPPER":
        rec["needs_wrapper"] = True
    elif label == "REPAIR":
        rec["repairable_defects"] = True
    elif label == "EXTEND":
        rec["extend_with"] = "extra-stage"
    elif label == "MERGE":
        rec["merge_with"] = "wf-fixture-001"
    elif label == "SPECIALIZE":
        rec["specialize_of"] = "wf-generic-parent"
    return rec


def build_standin() -> dict[str, Any]:
    if sum(PUBLISHED_HISTOGRAM.values()) != 284:
        raise AssertionError("published histogram does not sum to 284")
    if set(PUBLISHED_HISTOGRAM) != set(USED_DECLARED):
        raise AssertionError("published histogram keys != used vocabulary")
    candidates: list[dict[str, Any]] = []
    n = 0
    for label, count in PUBLISHED_HISTOGRAM.items():
        for _ in range(count):
            n += 1
            candidates.append(_features_for(label, n))
    hist = dict(Counter(c["classification"] for c in candidates))
    counts_block = {
        "n": len(candidates),
        "by_classification": {k: int(hist.get(k, 0)) for k in VOCABULARY},
        "note": (
            "counts block is a stored field; recount must not trust it "
            "without walking candidates[]"
        ),
    }
    return {
        "artifact": "08-WORKFLOW-CANDIDATE-REGISTRY stand-in",
        "classification_vocabulary": list(VOCABULARY),
        "counts": counts_block,
        "candidates": candidates,
        "generated_by": "WFA-0148-registry-standin",
        "source_of_truth_ref": (
            "WORK-UNIT-CATALOG.json WFA-0005 evidence_requirement histogram"
        ),
    }


def find_live() -> Path | None:
    for path in SEARCH_PATHS:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def _normalize_live(raw: dict[str, Any]) -> dict[str, Any]:
    candidates = raw.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("live registry missing candidates[]")
    counts = raw.get("counts")
    if not isinstance(counts, dict) or not isinstance(
        counts.get("by_classification"), dict
    ):
        hist = histogram_from_candidates({"candidates": candidates})
        raw = dict(raw)
        raw["counts"] = {
            "n": sum(hist.values()),
            "by_classification": hist,
            "note": "counts block synthesised because live file lacked by_classification",
        }
    return raw


def load_registry() -> tuple[dict[str, Any], dict[str, Any]]:
    live = find_live()
    if live is not None:
        doc = _normalize_live(json.loads(live.read_text(encoding="utf-8")))
        meta = {
            "origin": "live-file",
            "live_present": True,
            "path": str(live),
            "n_candidates": len(doc.get("candidates") or []),
        }
        return doc, meta
    doc = build_standin()
    meta = {
        "origin": "reconstructed-from-published-histogram",
        "live_present": False,
        "path": "command-center/p2-wave/probes/WFA-0148/registry.py",
        "n_candidates": len(doc["candidates"]),
        "absent_reason": (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux "
            "worktree. Stand-in matches the WFA-0005 published 284-row "
            "histogram; both readings are still printed from independent "
            "code paths."
        ),
    }
    return doc, meta


def histogram_from_candidates(doc: dict[str, Any]) -> dict[str, int]:
    hist: dict[str, int] = {k: 0 for k in VOCABULARY}
    extra: dict[str, int] = {}
    for row in doc.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("classification") or "")
        if label in hist:
            hist[label] += 1
        else:
            extra[label] = extra.get(label, 0) + 1
    if extra:
        hist.update({f"OTHER:{k}": v for k, v in extra.items()})
    return hist


def histogram_from_counts_block(doc: dict[str, Any]) -> dict[str, int]:
    counts = doc.get("counts")
    if not isinstance(counts, dict):
        return {}
    by_c = counts.get("by_classification")
    if not isinstance(by_c, dict):
        return {str(k): int(v) for k, v in counts.items() if isinstance(v, int)}
    return {str(k): int(v) for k, v in by_c.items() if isinstance(v, int)}


def n_from_array(hist: dict[str, int]) -> int:
    return sum(int(v) for v in hist.values())


def unused_zero(hist: dict[str, int], unused: tuple[str, ...]) -> bool:
    return all(int(hist.get(v, 0)) == 0 for v in unused)


def histograms_equal(a: dict[str, int], b: dict[str, int]) -> bool:
    keys = set(a) | set(b)
    return all(int(a.get(k, 0)) == int(b.get(k, 0)) for k in keys)


def mismatch_copy(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(doc))
    counts = clone.setdefault("counts", {})
    if not isinstance(counts, dict):
        clone["counts"] = {"by_classification": {"REJECT": 99}}
        return clone
    by_c = counts.get("by_classification")
    if isinstance(by_c, dict):
        by_c["REJECT"] = 99
    else:
        counts["REJECT"] = 99
    return clone


# Call-site aliases used by emit/probes.
load_registry = load_registry
histogram_from_candidates = histogram_from_candidates
histogram_from_counts_block = histogram_from_counts_block
n_from_array = n_from_array
unused_zero = unused_zero
histograms_equal = histograms_equal
mismatch_copy = mismatch_copy
