#!/usr/bin/env python3
"""Probe 1: planted synthetic present; happy-path diagnosis on all ten targets."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_case as P  # noqa: E402
import probe_common as C  # noqa: E402

UNIT = "ADV-0037"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = P.run_campaign("happy")
    det = live.get("detector") or {}
    rows = live.get("targets") or []
    hits = [r["id"] for r in rows if r.get("hit")]
    report = {
        "probe": "probe1-happy-path",
        "unit_id": UNIT,
        "planted": live.get("planted"),
        "detector": {
            "pass": det.get("pass"),
            "fired_on_bad_state": det.get("fired_on_bad_state"),
            "silent_on_good_state": det.get("silent_on_good_state"),
            "prefix_only_is_not_a_hit": det.get("prefix_only_is_not_a_hit"),
        },
        "targets": [
            {
                "id": r["id"],
                "hit": r["hit"],
                "stdout_hit": r.get("stdout_hit"),
                "stderr_hit": r.get("stderr_hit"),
                "file_hits": r.get("file_hits"),
                "source": r.get("source"),
                "source_exists": r.get("source_exists"),
                "stdout_sanitized": r.get("stdout_sanitized"),
            }
            for r in rows
        ],
        "hit_ids": hits,
        "target_count": len(rows),
        "egress_attempts": live.get("egress_attempts") or [],
        "hard_constraint": live.get("hard_constraint"),
        "parent_credential_values_read": live.get("parent_credential_values_read"),
    }
    print(C.dump_json(report))
    if len(rows) != 10:
        return fail(f"expected 10 targets got {len(rows)}")
    if not det.get("pass"):
        return fail("detector control did not discriminate")
    if report["egress_attempts"]:
        return fail(f"network egress {report['egress_attempts']}")
    if live.get("parent_credential_values_read"):
        return fail("parent credential value was read")
    blob = C.dump_json(report)
    if C.PLANTED in blob:
        return fail("probe JSON retained planted body")
    print(
        f"SUCCESS:{UNIT}-probe1 happy-path {len(hits)}/10 exact-body hits "
        f"detector=pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
