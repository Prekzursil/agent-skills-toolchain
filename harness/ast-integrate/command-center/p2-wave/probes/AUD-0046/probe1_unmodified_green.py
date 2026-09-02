#!/usr/bin/env python3
"""Probe 1: every runnable gate exits 0 on the unmodified isolated scratch.

Does not plant mutations (that is probe 2). Re-runs the live good-state arm
and checks the artifact table matches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

ART = REPO / "command-center" / "audit" / "AUD-0046-gate-detector-control-sweep.json"
OUT = HERE / "probe1-unmodified-green.raw.json"
SENTINEL = "SUCCESS:AUD-0046"
COMPLETION = (
    "SUCCESS:AUD-0046 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0046-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text or COMPLETION not in text:
        return fail("sentinel absent")
    if doc.get("kind") != "detector-control":
        return fail("kind is not detector-control")

    report = S.run_report()
    if not report["baseline_green"]:
        return fail("live unmodified scratch is not green")
    if report["n_fired"] < 2:
        return fail(f"too few FIRED rows: {report['n_fired']}")

    art_rows = {
        r.get("id"): r
        for r in (doc.get("detectors") or [])
        if isinstance(r, dict)
    }
    live = {m["id"]: m for m in report["measured"]}
    if set(art_rows) != set(live):
        return fail(f"detector ids artifact={sorted(art_rows)} live={sorted(live)}")
    for mid, row in live.items():
        art = art_rows[mid]
        if art.get("status") != row["status"]:
            return fail(f"{mid} status artifact={art.get('status')} live={row['status']}")
        if art.get("good_exit") != row.get("good_exit"):
            return fail(f"{mid} good_exit artifact={art.get('good_exit')} live={row.get('good_exit')}")
        if not row.get("silent_on_good_state"):
            return fail(f"{mid} not silent on unmodified scratch")

    raw = {
        "probe": "probe1-unmodified-green",
        "unit_id": "AUD-0046",
        "n_fired": report["n_fired"],
        "n_disarmed": report["n_disarmed"],
        "baseline_green": True,
        "inventory_jobs": report["inventory_jobs"],
        "inventory_on_disk": report["inventory_on_disk"],
        "pass": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired={report['n_fired']} disarmed={report['n_disarmed']} "
        f"silent={report['n_silent']} baseline_green=True "
        f"inventory_on_disk={report['inventory_on_disk']}/{report['inventory_jobs']}"
    )
    print("SUCCESS:AUD-0046-probe1 unmodified scratch exits 0 for every runnable gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
