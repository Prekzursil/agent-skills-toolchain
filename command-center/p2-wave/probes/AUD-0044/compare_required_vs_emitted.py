#!/usr/bin/env python3
"""AUD-0044 live comparator: required (probe1) vs emitted (probe2).

Writes compare-required-vs-emitted.json (+ .raw.txt).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE))
from compare_contexts import compare  # noqa: E402

P1 = PROBE / "probe1-required-status-checks.json"
P2 = PROBE / "probe2-recent-pr-check-runs.json"
OUT_JSON = PROBE / "compare-required-vs-emitted.json"
OUT_RAW = PROBE / "compare-required-vs-emitted.raw.txt"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not P1.is_file() or not P2.is_file():
        print("FAILED: missing probe1 and/or probe2 JSON")
        return 1
    p1 = json.loads(P1.read_text(encoding="utf-8"))
    p2 = json.loads(P2.read_text(encoding="utf-8"))
    required = list(p1.get("required_status_checks") or [])
    emitted = list(p2.get("emitted_contexts") or [])
    result = compare(required, emitted)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "probe": "AUD-0044-compare-required-vs-emitted",
        "started_at": started,
        "ended_at": ended,
        "required_source": {
            "api_used": p1.get("api_used"),
            "required_count": p1.get("required_count"),
            "ok": p1.get("ok"),
        },
        "emitted_source": {
            "pr": (p2.get("selection") or {}).get("chosen"),
            "emitted_count": p2.get("emitted_count"),
            "ok": p2.get("ok"),
        },
        "required_status_checks": required,
        "emitted_contexts": emitted,
        **result,
        "ok": bool(p1.get("ok")) and bool(p2.get("ok")),
        "interpretation": {
            "required_but_never_emitted": (
                "A required context whose name no workflow emits stays "
                "permanently pending on protected merges."
            ),
            "emitted_but_not_required": (
                "A produced context that is not required gates nothing — "
                "merge may proceed even if it fails."
            ),
        },
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text(
        json.dumps(
            {
                "required_count": result["required_count"],
                "emitted_count": result["emitted_count"],
                "intersection_count": result["intersection_count"],
                "required_but_never_emitted_count": result[
                    "required_but_never_emitted_count"
                ],
                "emitted_but_not_required_count": result[
                    "emitted_but_not_required_count"
                ],
                "symmetric_difference_count": result["symmetric_difference_count"],
                "required_but_never_emitted": result["required_but_never_emitted"],
                "emitted_but_not_required": result["emitted_but_not_required"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"compare ok={doc['ok']} required={result['required_count']} "
        f"emitted={result['emitted_count']} "
        f"required_but_never_emitted={result['required_but_never_emitted_count']} "
        f"emitted_but_not_required={result['emitted_but_not_required_count']} "
        f"intersection={result['intersection_count']} "
        f"symdiff={result['symmetric_difference_count']}"
    )
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
