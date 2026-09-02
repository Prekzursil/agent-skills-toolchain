#!/usr/bin/env python3
"""Assign candidates to task classes using cue-token overlap.

A candidate may serve several classes. Multi-class is recorded as a list, not
forced into one. The deciding sentence is quoted from the candidate's own
`does` field. Coverage holes are classes with zero assigned candidates.
"""
from __future__ import annotations

import re
from typing import Any

from taxonomy import cue_tokens

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENTENCE_RE.split(text) if p.strip()]
    return parts or [text.strip()]


def _id_mentioned(does: str, class_id: str) -> bool:
    low = does.lower()
    return class_id in low or class_id.replace("-", " ") in low


def score_class(does: str, cls: dict[str, Any]) -> int:
    have = cue_tokens(does)
    cues = set(cls["cues"])
    n = len(have & cues)
    if _id_mentioned(does, cls["id"]):
        n += 4
    return n


def deciding_sentence(does: str, cls: dict[str, Any]) -> str:
    cues = set(cls["cues"])
    best = ""
    best_n = -1
    for sent in _sentences(does):
        n = len(cue_tokens(sent) & cues)
        if n > best_n or (n == best_n and len(sent) > len(best)):
            best, best_n = sent, n
    if best_n <= 0:
        return _sentences(does)[0]
    return best


def assign_one(
    cand: dict[str, Any],
    classes: list[dict[str, Any]],
    *,
    min_score: int = 4,
    keep_ratio: float = 0.72,
) -> dict[str, Any]:
    ranked = []
    for cls in classes:
        s = score_class(cand["does"], cls)
        ranked.append((s, cls["id"], cls))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    top_s = ranked[0][0] if ranked else 0
    chosen: list[dict[str, Any]] = []
    if top_s >= min_score:
        floor = max(min_score, int(top_s * keep_ratio))
        for s, cid, cls in ranked:
            if s < floor:
                break
            quote = deciding_sentence(cand["does"], cls)
            if quote not in cand["does"]:
                raise RuntimeError(f"quote not in does for {cand['id']}")
            chosen.append(
                {
                    "class_id": cid,
                    "family": cls["family"],
                    "d_family": cls["d_family"],
                    "score": s,
                    "deciding_sentence": quote,
                }
            )
    status = "unclassified"
    if len(chosen) == 1:
        status = "single-class"
    elif len(chosen) > 1:
        status = "multi-class"
    return {
        "candidate_id": cand["id"],
        "name": cand.get("name") or cand["id"],
        "origin": cand.get("origin"),
        "planted": bool(cand.get("planted")),
        "status": status,
        "classes": chosen,
        "class_ids": [c["class_id"] for c in chosen],
        "top_score": top_s,
        "does": cand["does"],
    }


def assign_all(
    candidates: list[dict[str, Any]],
    classes: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [assign_one(c, classes) for c in candidates]
    by_class: dict[str, list[str]] = {cls["id"]: [] for cls in classes}
    for row in rows:
        for cid in row["class_ids"]:
            by_class[cid].append(row["candidate_id"])
    zero = []
    for cls in classes:
        if not by_class[cls["id"]]:
            zero.append(
                {
                    "class_id": cls["id"],
                    "family": cls["family"],
                    "d_family": cls["d_family"],
                    "source_unit": cls["source_unit"],
                    "spec_cite": cls["spec_cite"],
                    "generation_lane": {
                        "route": "WFA-generation",
                        "reason": "zero covering candidates on the measured set",
                        "typed_goal": (
                            f"Author at least one candidate whose own definition "
                            f"discriminates task class {cls['id']} "
                            f"({cls['family']}) from its siblings."
                        ),
                    },
                }
            )
    covered = [cid for cid, ids in by_class.items() if ids]
    multi = [r for r in rows if r["status"] == "multi-class"]
    return {
        "n_candidates": len(rows),
        "n_assigned": sum(1 for r in rows if r["class_ids"]),
        "n_unclassified": sum(1 for r in rows if r["status"] == "unclassified"),
        "n_multi_class": len(multi),
        "n_classes": len(classes),
        "n_covered_classes": len(covered),
        "n_zero_coverage_classes": len(zero),
        "assignments": rows,
        "coverage_by_class": {k: list(v) for k, v in by_class.items()},
        "zero_coverage_classes": zero,
        "multi_class_ids": [r["candidate_id"] for r in multi],
    }


def force_single_class(report: dict[str, Any]) -> dict[str, Any]:
    """Mutant: collapse every assignment to its first class. Detector must fire."""
    mutant = dict(report)
    rows = []
    for row in report["assignments"]:
        r = dict(row)
        if r["classes"]:
            r["classes"] = r["classes"][:1]
            r["class_ids"] = r["class_ids"][:1]
            r["status"] = "single-class" if r["class_ids"] else "unclassified"
        rows.append(r)
    mutant["assignments"] = rows
    mutant["n_multi_class"] = 0
    mutant["multi_class_ids"] = []
    return mutant
