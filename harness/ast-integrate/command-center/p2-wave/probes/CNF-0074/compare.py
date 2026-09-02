#!/usr/bin/env python3
"""Field-level artifact diff with cause attribution and timestamp normalisation."""
from __future__ import annotations

import json
import re
from typing import Any

TIMESTAMP_KEYS = {
    "created_at",
    "stamped_at",
    "timestamp",
    "generated_at",
    "wall_clock",
    "run_at",
}
PATH_KEYS = {"run_dir", "workdir", "abs_path", "path_leak"}
SAMPLE_KEYS = {
    "chosen",
    "chosen_sha256",
    "sample",
    "sample_nonce",
    "picked",
    "model_output",
    "token",
}
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
NS_RE = re.compile(r"^(ns:)?\d{15,}$")

CAUSES = ("timestamp", "ordering", "model-sampling", "path", "semantic")


def _is_timestamp_value(val: Any) -> bool:
    if isinstance(val, int) and val > 10**15:
        return True
    if isinstance(val, str) and (ISO_RE.match(val) or NS_RE.match(val)):
        return True
    return False


def classify_cause(key: str, va: Any, vb: Any) -> str:
    if key in SAMPLE_KEYS:
        return "model-sampling"
    if key in PATH_KEYS:
        return "path"
    if key in TIMESTAMP_KEYS or _is_timestamp_value(va) or _is_timestamp_value(vb):
        return "timestamp"
    if (
        isinstance(va, list)
        and isinstance(vb, list)
        and va != vb
        and sorted(map(repr, va)) == sorted(map(repr, vb))
    ):
        return "ordering"
    if (
        isinstance(va, dict)
        and isinstance(vb, dict)
        and va != vb
        and sorted(va.keys()) == sorted(vb.keys())
        and sorted(map(repr, va.values())) == sorted(map(repr, vb.values()))
    ):
        return "ordering"
    return "semantic"


def walk_diffs(a: Any, b: Any, prefix: str = "$") -> list[dict[str, str]]:
    diffs: list[dict[str, str]] = []
    if type(a) is not type(b):
        diffs.append(
            {
                "path": prefix,
                "cause": classify_cause(prefix.rsplit(".", 1)[-1], a, b),
                "run_a": _fmt(a),
                "run_b": _fmt(b),
            }
        )
        return diffs
    if isinstance(a, dict):
        keys = sorted(set(a) | set(b))
        for k in keys:
            p = f"{prefix}.{k}"
            if k not in a:
                diffs.append(
                    {
                        "path": p,
                        "cause": classify_cause(k, None, b[k]),
                        "run_a": "<ABSENT>",
                        "run_b": _fmt(b[k]),
                    }
                )
            elif k not in b:
                diffs.append(
                    {
                        "path": p,
                        "cause": classify_cause(k, a[k], None),
                        "run_a": _fmt(a[k]),
                        "run_b": "<ABSENT>",
                    }
                )
            else:
                diffs.extend(walk_diffs(a[k], b[k], p))
        return diffs
    if isinstance(a, list):
        if a != b and sorted(map(repr, a)) == sorted(map(repr, b)):
            diffs.append(
                {
                    "path": prefix,
                    "cause": "ordering",
                    "run_a": _fmt(a),
                    "run_b": _fmt(b),
                }
            )
            return diffs
        n = max(len(a), len(b))
        for i in range(n):
            p = f"{prefix}[{i}]"
            if i >= len(a):
                diffs.append(
                    {
                        "path": p,
                        "cause": "semantic",
                        "run_a": "<ABSENT>",
                        "run_b": _fmt(b[i]),
                    }
                )
            elif i >= len(b):
                diffs.append(
                    {
                        "path": p,
                        "cause": "semantic",
                        "run_a": _fmt(a[i]),
                        "run_b": "<ABSENT>",
                    }
                )
            else:
                diffs.extend(walk_diffs(a[i], b[i], p))
        return diffs
    if a != b:
        key = prefix.rsplit(".", 1)[-1].split("[", 1)[0]
        diffs.append(
            {
                "path": prefix,
                "cause": classify_cause(key, a, b),
                "run_a": _fmt(a),
                "run_b": _fmt(b),
            }
        )
    return diffs


def _fmt(val: Any) -> str:
    if val is None:
        return "null"
    text = json.dumps(val, sort_keys=True, ensure_ascii=True)
    if len(text) > 240:
        return text[:237] + "..."
    return text


def normalize_timestamps(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in TIMESTAMP_KEYS or _is_timestamp_value(v):
                out[k] = "<TIMESTAMP>"
            else:
                out[k] = normalize_timestamps(v)
        return out
    if isinstance(obj, list):
        return [normalize_timestamps(x) for x in obj]
    if _is_timestamp_value(obj):
        return "<TIMESTAMP>"
    return obj


def first_byte_diff(a: bytes, b: bytes) -> int | None:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    if len(a) != len(b):
        return n
    return None


def verdict_for(
    claims: bool,
    raw_identical: bool,
    norm_identical: bool,
    diffs: list[dict[str, str]],
) -> str:
    if raw_identical:
        return "DETERMINISTIC"
    causes = {d["cause"] for d in diffs}
    if norm_identical and causes <= {"timestamp"}:
        return "TIMESTAMP-ONLY"
    semanticish = causes - {"timestamp"}
    if claims and semanticish:
        return "OVERCLAIM"
    return "NONDETERMINISTIC"


# Names battery.py imports.
walk_diffs = walk_diffs
normalize_timestamps = normalize_timestamps
first_byte_diff = first_byte_diff
