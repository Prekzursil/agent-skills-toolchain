#!/usr/bin/env python3
"""Probe 1: token-bucket unit tests (never negative, never above capacity)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from arrival_scheduler import FakeClock, TokenBucket, token_bucket_checks  # noqa: E402


def main() -> int:
    checks = token_bucket_checks()
    clock = FakeClock()
    empty = TokenBucket(5.0, 0.0, clock, initial=0.0)
    negatives = 0
    for _ in range(100):
        empty.try_consume(1.0)
        if empty.tokens < 0:
            negatives += 1
    overflow_clock = FakeClock()
    full = TokenBucket(5.0, 1000.0, overflow_clock, initial=5.0)
    overflow_clock.sleep(100.0)
    overflow = full.tokens > 5.0 + 1e-9

    failed = [name for name, ok, _ in checks if not ok]
    payload = {
        "probe": "probe1-token-bucket",
        "unit_id": "IMP-0427",
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
        "n_checks": len(checks),
        "n_failed": len(failed),
        "drain_negatives": negatives,
        "overflow": overflow,
        "tokens_after_long_refill": full.tokens,
        "pass": not failed and negatives == 0 and not overflow,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failed or negatives or overflow:
        print(f"FAILED:IMP-0427-probe1 token-bucket invariants failed={failed}")
        return 1
    print(f"checks={len(checks)} drain_negatives=0 overflow=False")
    print("SUCCESS:IMP-0427-probe1 token-bucket never negative never above capacity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
