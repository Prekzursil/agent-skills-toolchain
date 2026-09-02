#!/usr/bin/env python3
"""Probe 2: timed git clone --no-hardlinks; disk bytes are not packed size."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = REPO / "command-center/audit/AUD-0010-repo-weight-baseline.json"
SENTINEL = (
    "SUCCESS:AUD-0010 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0010-probe2 {msg}")
    return 1


def main() -> int:
    fixture = M.measure_fixture()
    clone1 = fixture["clone_run1"]
    clone2 = fixture["clone_run2"]
    if not fixture["clone_repeat_ok"]:
        return fail(
            f"clone runs disagree a={clone1['clone_disk_bytes']} "
            f"b={clone2['clone_disk_bytes']}"
        )
    if fixture["packed_equals_clone"]:
        return fail("clone disk equals packed bytes; instruments did not diverge")
    if not fixture["clone_exceeds_packed"]:
        return fail(
            f"clone_disk={fixture['clone_disk_bytes']} "
            f"packed={fixture['packed_bytes']} expected clone > packed"
        )
    if fixture["dominant_path"] != M.DOMINATE_REL:
        return fail(f"dominant path {fixture['dominant_path']!r} != {M.DOMINATE_REL}")
    if int(fixture["dominant_blob_bytes"]) != M.DOMINATE_LEN:
        return fail("dominant blob size is not the planted dominate.bin")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    blob = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(blob)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    headline = doc.get("headline") or {}
    if headline.get("packed_equals_clone") is not False:
        return fail("artifact did not record packed_equals_clone=false")
    if not M.within_2pct(
        int(headline.get("clone_disk_bytes") or 0), int(fixture["clone_disk_bytes"])
    ):
        return fail("artifact clone_disk_bytes drifted from live clone")
    if int(headline.get("clone_disk_bytes") or 0) <= int(headline.get("packed_bytes") or 0):
        return fail("artifact headline does not show clone disk exceeding packed size")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer did not PASS after clone falsified packed-as-clone")
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")

    payload = {
        "pass": True,
        "probe": "probe2-timed-clone",
        "unit_id": "AUD-0010",
        "clone_disk_bytes": fixture["clone_disk_bytes"],
        "clone_run2_bytes": clone2["clone_disk_bytes"],
        "clone_wall_ms": fixture["clone_wall_ms"],
        "packed_bytes": fixture["packed_bytes"],
        "packed_equals_clone": False,
        "clone_exceeds_packed": True,
        "within_2pct": True,
        "dominant_path": fixture["dominant_path"],
        "dominant_blob_bytes": fixture["dominant_blob_bytes"],
        "falsified": "packed-size-as-clone-cost",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"clone_disk={fixture['clone_disk_bytes']} packed={fixture['packed_bytes']} "
        f"exceeds_packed=True dominant={fixture['dominant_path']}"
    )
    print("SUCCESS:AUD-0010-probe2 timed clone disk exceeds packed size")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
