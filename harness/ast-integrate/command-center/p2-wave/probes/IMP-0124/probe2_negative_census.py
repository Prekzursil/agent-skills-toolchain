"""Named probe 2: missing-blob backup fails the functional probe; census + live gate.

NEGATIVE CONTROL: a backup with the blob store stripped must fail resolve/install/verify,
proving the functional probe discriminates. Independently, a scratch restore must not
write into the live registry (census + snapshot). Live restore without the owner token
is refused and does not retry.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.drill import live_restore_gate, missing_blob_negative, scratch_restore_drill  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0124-p2-") as raw:
        base = Path(raw)
        census_report = scratch_restore_drill(base / "census")
        neg = missing_blob_negative(base / "neg")
        gate = live_restore_gate(base / "gate")
    payload = {
        "pass": bool(neg["ok"] and gate["ok"] and census_report["live_snapshot_unchanged"] and not census_report["census_hits_live"]),
        "probe": "probe2-negative-census-live-gate",
        "unit_id": "IMP-0124",
        "missing_blobs_functional_failed": neg["functional_failed"],
        "missing_blobs_discriminates": neg["discriminates"],
        "dangling_blob_findings": neg["dangling_blob_findings"],
        "scratch_census_hits_live": census_report["census_hits_live"],
        "scratch_live_unchanged": census_report["live_snapshot_unchanged"],
        "live_restore_refused": gate["refused"],
        "live_restore_unchanged": gate["live_snapshot_unchanged"],
        "no_automatic_retry": gate["no_automatic_retry"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not neg["ok"]:
        print("FAILED:IMP-0124-probe2 missing-blob backup did not fail the functional probe")
        return 1
    if census_report["census_hits_live"] or not census_report["live_snapshot_unchanged"]:
        print("FAILED:IMP-0124-probe2 scratch restore wrote the live registry")
        return 1
    if not gate["ok"]:
        print("FAILED:IMP-0124-probe2 live restore was not owner-gated")
        return 1
    print(
        "neg_func_failed=True discriminates=True census_live_hits=0 "
        f"live_refused={gate['refused']} no_retry={gate['no_automatic_retry']}"
    )
    print("SUCCESS:IMP-0124-probe2 negative control, census, and live-restore gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
