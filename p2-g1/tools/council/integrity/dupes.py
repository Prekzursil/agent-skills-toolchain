#!/usr/bin/env python3
"""Effective-voice / duplicate-roster audit (IMP-0279)."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import sys
from typing import Any


FINGERPRINT_FIELDS = ("vendor", "model", "system_prompt", "tools", "context")
IDENTITY_EXCLUDED = ("seat_id", "name", "label")
LOW_SIMILARITY = 0.35


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _canon_tools(tools: Any) -> Any:
    if isinstance(tools, list):
        rows = []
        for item in tools:
            if isinstance(item, dict):
                rows.append(_canon(item))
            else:
                rows.append(str(item))
        return sorted(rows)
    return tools


def fingerprint(seat: dict[str, Any]) -> str:
    payload = {k: seat.get(k) for k in FINGERPRINT_FIELDS}
    payload["tools"] = _canon_tools(payload.get("tools"))
    payload["vendor"] = str(payload.get("vendor") or "").casefold()
    payload["model"] = str(payload.get("model") or "").casefold()
    return hashlib.sha256(_canon(payload).encode("utf-8")).hexdigest()


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def audit_roster(seats: list[dict[str, Any]], outputs: list[str] | dict[str, str] | None = None) -> dict[str, Any]:
    if isinstance(outputs, dict):
        outputs = [outputs.get(s.get("seat_id") or s.get("id") or "", "") for s in seats]
    else:
        outputs = list(outputs or [])
    fps = [fingerprint(s) for s in seats]
    clusters: dict[str, list[int]] = defaultdict(list)
    for i, fp in enumerate(fps):
        clusters[fp].append(i)
    flagged = [{"fingerprint": k, "size": len(v), "seats": v} for k, v in clusters.items() if len(v) > 1]
    effective = len(clusters)
    pairs = []
    within = []
    across = []
    for i in range(len(outputs)):
        for j in range(i + 1, len(outputs)):
            sim = _jaccard(outputs[i], outputs[j])
            pairs.append(sim)
            if fps[i] == fps[j]:
                within.append(sim)
            else:
                across.append(sim)
    mean_j = sum(pairs) / len(pairs) if pairs else 1.0
    within_mean = sum(within) / len(within) if within else 1.0
    across_mean = sum(across) / len(across) if across else 0.0
    config_dup = effective == 1 and len(seats) > 1
    output_ident = mean_j >= 0.99 if outputs else config_dup
    all_unique = effective == len(seats) and mean_j < LOW_SIMILARITY
    cluster_sizes = sorted(len(v) for v in clusters.values() if len(v) > 1)
    mixed_ok = effective > 1 and effective < len(seats) and bool(cluster_sizes)
    if config_dup and output_ident:
        corroboration = {"agrees": True, "verdict": "CORROBORATED"}
    elif all_unique:
        corroboration = {"agrees": True, "verdict": "CORROBORATED"}
    elif mixed_ok:
        corroboration = {"agrees": True, "verdict": "CORROBORATED"}
    else:
        corroboration = {"agrees": False, "verdict": "SPLIT"}
    return {
        "seat_count": len(seats),
        "effective_independence_count": effective,
        "duplicate_cluster_count": len(flagged),
        "flagged": flagged,
        "fingerprint_fields": list(FINGERPRINT_FIELDS),
        "identity_fields_excluded": list(IDENTITY_EXCLUDED),
        "similarity": {
            "mean_pairwise_jaccard": mean_j,
            "n_pairs": len(pairs),
            "within_cluster_mean": within_mean,
            "across_cluster_mean": across_mean,
        },
        "corroboration": corroboration,
    }


def main() -> int:
    args = sys.argv[1:]
    roster_path = None
    if "--roster" in args:
        roster_path = args[args.index("--roster") + 1]
    if not roster_path:
        print("{}", file=sys.stderr)
        return 2
    doc = json.loads(open(roster_path, encoding="utf-8").read())
    seats = doc.get("seats") or doc.get("roster") or doc
    outputs = doc.get("outputs") or [s.get("output", "") for s in seats]
    print(json.dumps(audit_roster(seats, outputs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
