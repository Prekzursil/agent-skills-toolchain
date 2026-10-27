#!/usr/bin/env python3
"""TST-0265 probe 2: gaming simulation + three brainstorm runs.

A cast instructed to pad to 100 must be CAUGHT: its post-dedup count falls
below the unique_ideas >= 100 stopping target. Three runs are reported (raw,
post-dedup, collapse ratio) so the receipt's evidence requirement is re-proved
on this host: honest-distinct run passes the gate, gaming-pad run is caught,
mixed run collapses below target.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import distinct_100, gaming_pad_100  # noqa: E402
from measure import TARGET_UNIQUE, run_count  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    runs = []

    r1_set = distinct_100()
    r1 = run_count(r1_set)
    r1["name"] = "brainstorm-honest-distinct"
    r1["instruction"] = "Emit genuinely distinct mechanisms until the ledger has 100 strings."
    r1["cast"] = ["alice", "bob", "cara", "drew"]
    checks["run1_honest_passes_gate"] = r1["post_dedup_count"] >= TARGET_UNIQUE
    runs.append({k: r1[k] for k in ("name", "cast", "raw_count", "post_dedup_count", "collapse_ratio", "target_ge_100_met")})

    r2_set = gaming_pad_100()
    r2 = run_count(r2_set)
    r2["name"] = "brainstorm-gaming-pad"
    r2["instruction"] = "Pad the ledger to 100 unique strings with trivial wording variants."
    r2["cast"] = ["alice", "bob", "cara", "drew"]
    checks["run2_gaming_caught"] = r2["post_dedup_count"] < TARGET_UNIQUE
    runs.append({k: r2[k] for k in ("name", "cast", "raw_count", "post_dedup_count", "collapse_ratio", "target_ge_100_met")})

    mixed = distinct_100()[:50] + [
        "retry lane variant a",
        "retry lane variant b",
        "retry lane variant c",
        "retry lane variant d",
        "retry lane variant e",
    ]
    r3_set = mixed + [
        "retry lane with delays",
        "retry lane using waits",
        "retry lane via sleeps",
        "retry lane through timers",
        "retry lane upon failures",
        "retry lane for flaky nets",
        "retry lane of dropped calls",
        "retry lane on timeouts",
        "retry lane after errors",
        "retry lane beneath errors",
    ]
    r3 = run_count(r3_set)
    r3["name"] = "brainstorm-mixed"
    r3["instruction"] = "Emit 50 distinct plus 60 variants of one idea; the gate must count them honestly."
    r3["cast"] = ["alice", "bob", "cara", "drew"]
    checks["run3_mixed_collapses_below_target"] = r3["post_dedup_count"] < TARGET_UNIQUE
    runs.append({k: r3[k] for k in ("name", "cast", "raw_count", "post_dedup_count", "collapse_ratio", "target_ge_100_met")})

    out = {
        "probe": "probe2_gaming_reviewer",
        "unit": "TST-0265",
        "brainstorm_runs": runs,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-gaming.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
