"""Decision table: observed attempts per failure class match policy (IMP-0448)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import retry_engine as re  # noqa: E402


def main() -> int:
    policy = re.parse_retry_policy(
        "max 3 attempts, backoff 30s/120s; two strikes then pivot")
    assert policy.max_attempts == 3
    assert policy.backoff_seconds == (30, 120)
    assert policy.two_strikes_pivot is True

    # Catalog-shaped transients-only policy: limited classes are capped at one.
    tonly = re.parse_retry_policy(
        "max 3 attempts for provider transients only, backoff 30s/120s")
    assert tonly.transient_only is True
    assert re.observe_attempts(
        "partial-artifact", tonly, distinct_fingerprints=True
    ).observed_attempt_count == 1

    rows = re.decision_table(policy, distinct_fingerprints=True)
    errors = re.table_is_sound(rows)
    assert errors == [], errors

    by_class = {row["failure_class"]: row for row in rows}
    expect = {
        "severed-stream": 3,
        "adapter-exit-n": 3,
        "timeout": 3,
        "schema-invalid": 1,
        "win-arg-limit": 1,
        "partial-artifact": 2,
        "degraded": 1,
        "blocked": 1,
        "UNCLASSIFIED": 1,
    }
    mismatched = {}
    for cls, want in expect.items():
        got = by_class[cls]["observed_attempt_count"]
        if got != want:
            mismatched[cls] = {"observed": got, "policy": want}
    assert not mismatched, mismatched

    assert by_class["schema-invalid"]["terminal_reason"] == re.REASON_ZERO
    assert by_class["severed-stream"]["terminal_reason"] == re.REASON_CAP
    assert by_class["UNCLASSIFIED"]["kind"] == "never"

    print(json.dumps({
        "probe": "probe1-decision-table",
        "unit_id": "IMP-0448",
        "parse_ok": True,
        "table_match": True,
        "rows": [{k: r[k] for k in ("failure_class", "kind", "configured_policy",
                                    "observed_attempt_count", "terminal_reason")}
                 for r in rows],
        "sentinel": "SENTINEL:IMP-0448:RETRY-CLASS-DRIVEN",
    }, indent=2))
    print("SUCCESS:IMP-0448-probe1 decision table matches configured policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
