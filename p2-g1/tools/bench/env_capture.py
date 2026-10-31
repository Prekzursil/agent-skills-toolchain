"""Environment capture + drift alarm for TST-0297 (pin determinism).

Capture freezes everything that can vary a measured delta: seed, model id and
snapshot, temperature, tool versions, OS, locale, concurrency. The fingerprint
is the sha256 of the canonical JSON. compare() is the drift alarm: identical
captures are silent (status MATCH); any differing field flags DRIFT and the
comparison is REFUSED (a run under a different environment must never be
silently compared against a baseline).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import sysconfig
from typing import Any


def capture(
    *,
    seed: int = 20260824,
    model_id: str = "fixture-model",
    model_snapshot: str = "snap-0",
    temperature: float = 0.0,
    concurrency: int = 1,
    arrival_rate: float = 1.0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_versions = {}
    for name in ("python", "platform"):
        tool_versions[name] = "n/a"
    tool_versions["python_full"] = sys.version.split(" ")[0]
    tool_versions["platform_module"] = sys.implementation.name
    doc = {
        "sys_platform": sys.platform,
        "seed": seed,
        "model_id": model_id,
        "model_snapshot": model_snapshot,
        "temperature": temperature,
        "concurrency": concurrency,
        "arrival_rate": arrival_rate,
        "locale": {
            "LANG": os.environ.get("LANG", ""),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "LC_CTYPE": os.environ.get("LC_CTYPE", ""),
            "preferredencoding": "utf-8",
        },
        "os": {
            "system": os.name,
            "release": sysconfig.get_platform(),
            "machine": os.environ.get("PROCESSOR_ARCHITECTURE", "unknown"),
        },
        "tool_versions": tool_versions,
    }
    if extra:
        doc.update(extra)
    doc["fingerprint"] = fingerprint(doc)
    return doc


def fingerprint(doc: dict[str, Any]) -> str:
    payload = {k: v for k, v in doc.items() if k != "fingerprint"}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Drift alarm: identical = silent MATCH; any diff = DRIFT, refuse."""
    diffs = []
    for k in sorted(set(baseline) | set(candidate)):
        if k == "fingerprint":
            continue
        if baseline.get(k) != candidate.get(k):
            diffs.append(k)
    if not diffs:
        return {
            "status": "MATCH",
            "differing_fields": [],
            "comparison_allowed": True,
            "silently_compared": False,
        }
    return {
        "status": "DRIFT",
        "differing_fields": diffs,
        "comparison_allowed": False,
        "reason": "captured environment differs; comparison refused",
        "silently_compared": False,
    }
