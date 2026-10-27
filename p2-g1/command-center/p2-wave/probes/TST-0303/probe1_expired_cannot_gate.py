#!/usr/bin/env python3
"""TST-0303 probe 1: an expired result cannot satisfy a gate.

Both-states with an injected clock on the SAME advisory oracle: captured_at
past the class TTL is refused (cite-as NOT-CHECKED); captured_at within TTL
is accepted. The hermetic both-states complement: a TRUE hermetic PASS aged
3650 days still cites as current (the TTL must not force pointless re-runs),
while the misdeclared hermetic that actually hit NVD expires.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.expire import cite_as_current, gate_accepts  # noqa: E402


@dataclass
class Result:
    result_id: str
    case_id: str
    verdict: str
    observed_class: str
    captured_at: datetime


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def main() -> int:
    checks: dict[str, bool] = {}
    expired_adv = Result(
        "planted-expired-advisory", "advisory-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=86401),
    )
    fresh_adv = Result(
        "fresh-advisory", "advisory-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=3600),
    )
    g_exp = gate_accepts(expired_adv, NOW)
    g_fresh = gate_accepts(fresh_adv, NOW)
    checks["expired_advisory_gate_refused"] = g_exp["accepted"] is False
    checks["expired_cites_not_checked"] = (
        cite_as_current(expired_adv, NOW).status == "EXPIRED-NOT-CHECKED"
    )
    checks["fresh_advisory_gate_accepts"] = g_fresh["accepted"] is True
    checks["same_oracle_both_states"] = (
        expired_adv.observed_class == fresh_adv.observed_class
    )

    ancient_hermetic = Result(
        "ancient-hermetic", "hermetic-digest", "PASS", "hermetic",
        NOW - timedelta(days=3650),
    )
    g_herm = gate_accepts(ancient_hermetic, NOW)
    checks["hermetic_ancient_still_current"] = g_herm["accepted"] is True
    checks["hermetic_cite_current"] = (
        cite_as_current(ancient_hermetic, NOW).status == "CURRENT"
    )
    lie = Result(
        "planted-expired-lie", "lie-hermetic-hits-nvd", "PASS", "advisory-db",
        NOW - timedelta(seconds=86401),
    )
    checks["misdeclared_hermetic_expires"] = gate_accepts(lie, NOW)["accepted"] is False

    from bench.expire import dashboard  # noqa: E402

    dash = dashboard([expired_adv, fresh_adv, ancient_hermetic, lie], NOW)
    checks["expired_count_is_2"] = dash["expired_count"] == 2
    checks["greens_carry_age"] = all(
        "age_seconds" in g for g in dash["greens"]
    )
    checks["green_count_is_2"] = len(dash["greens"]) == 2

    out = {
        "probe": "probe1_expired_cannot_gate",
        "unit": "TST-0303",
        "expired_gate": g_exp,
        "fresh_gate": g_fresh,
        "hermetic_gate": g_herm,
        "dashboard": dash,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-expired.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, sort_keys=True, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
