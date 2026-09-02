#!/usr/bin/env python3
"""Probe 2: rehearse the highest-risk rollback entry in a scratch tree.

Catalog control: rehearse one entry known to be irreversible and confirm
the rehearsal reports failure rather than a false success. The reversible
copy fixture is the other state so the detector is not always-red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0093-rollback-manifest-reality.json"
SENTINEL = (
    "SUCCESS:AUD-0093 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0093-probe2 {msg}")
    return 1


def main() -> int:
    measured = E.measure()
    fx = measured["fixture_rehearsal"]
    live = measured["live_rehearsal"]
    highest = measured["highest_risk"]
    payload = {
        "probe": "probe2-highest-risk-rehearsal",
        "highest_risk": {
            "source": highest["source"],
            "id": highest["id"],
            "title": highest["title"],
            "risk": highest["risk"],
        },
        "live_byte_recovered": live["byte_recovered"],
        "live_mode": live.get("mode"),
        "irreversible_reported_failure": fx["irreversible_reported_failure"],
        "reversible_reported_success": fx["reversible_reported_success"],
        "false_success_on_irreversible": fx["false_success_on_irreversible"],
        "control_pass": fx["control_pass"],
        "restore_possible": measured["restore_possible"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if fx["false_success_on_irreversible"]:
        return fail("irreversible-control-false-success")
    if not fx["irreversible_reported_failure"]:
        return fail("irreversible-control-did-not-report-failure")
    if not fx["reversible_reported_success"]:
        return fail("reversible-control-did-not-report-success")
    if not fx["control_pass"]:
        return fail("rehearsal-detector-does-not-discriminate")
    if live.get("mode") == "uncovered-destructive-no-procedure" and live["byte_recovered"]:
        return fail("empty-restore-after-delete-reported-success")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact-unparseable:{exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    ext = doc.get("extensions") or {}
    if bool(ext.get("live_byte_recovered")) != bool(live["byte_recovered"]):
        return fail("artifact-live-byte-recovered-mismatch")
    if bool(ext.get("irreversible_reported_failure")) is not True:
        return fail("artifact-missing-irreversible-failure")

    print(
        "NEGATIVE CONTROL verbatim: irreversible-delete-no-backup deletes "
        "gone.txt with restore_map pointing at absent backup/gone.txt; "
        f"byte_recovered={fx['irreversible']['byte_recovered']} "
        "(must be false). reversible-copy restores keep.txt from backup "
        f"and byte_recovered={fx['reversible']['byte_recovered']}."
    )
    print(
        "BOTH-STATES: FIRED failure on known-irreversible; SILENT success "
        f"on reversible copy; live highest={highest['id']} "
        f"mode={live.get('mode')} byte_recovered={live['byte_recovered']}"
    )
    print("SUCCESS:AUD-0093-probe2 scratch-rehearsal irreversible-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
