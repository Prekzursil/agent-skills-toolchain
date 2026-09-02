#!/usr/bin/env python3
"""Named probe 1: stale stored green is refused; two pulls get distinct snapshot ids.

Signal 1: promotion_log contains an explicit REFUSED/stale-green row (not mere
absence of consumption) and a forced re-scan of the same artifact hash.
Signal 2: pulls at T and T+7m record different snapshot ids; reusing T's id
fails freshness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import gate  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0014.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0014-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:REL-0014" not in blob:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "REL-0014":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    stale = controls.stale_stored_result()
    snaps = controls.distinct_snapshot_ids()
    print(json.dumps({"stale": {k: stale[k] for k in stale if k != "promotion_log" and k != "result"}, "snaps": snaps}, sort_keys=True, default=str))

    if not stale["pass"]:
        return fail("stale stored result was consumed or refusal was silent")
    if not stale["refused"] or not stale["forced_rescan"]:
        return fail("refusal or forced-rescan missing from live log")
    if stale["consumed_stored"]:
        return fail("gate consumed the stale stored green")
    if not gate.log_has_refusal(stale["promotion_log"], "stale-green"):
        return fail("live log missing REFUSED/stale-green")

    if not snaps["pass"]:
        return fail("snapshot freshness control failed")
    if snaps["snapshot_id_a"] == snaps["snapshot_id_b"]:
        return fail("two pulls reused the same snapshot id")
    if snaps["reuse_freshness_ok"]:
        return fail("reused snapshot id was accepted as fresh")

    scan = doc.get("scan") or {}
    db = doc.get("advisory_database") or {}
    if scan.get("window_length_seconds") != S.WINDOW_SECONDS:
        return fail(f"window {scan.get('window_length_seconds')}")
    if not isinstance(scan.get("artifact_sha256"), str) or len(scan["artifact_sha256"]) != 64:
        return fail("receipt scan.artifact_sha256 missing")
    if not isinstance(db.get("snapshot_id"), str) or len(db["snapshot_id"]) != 64:
        return fail("receipt snapshot_id missing")
    if not scan.get("timestamp"):
        return fail("receipt scan.timestamp missing")

    rec_stale = (doc.get("tests") or {}).get("stale_stored_result") or {}
    rec_snap = (doc.get("tests") or {}).get("distinct_snapshot_ids") or {}
    if rec_stale.get("pass") is not True:
        return fail("receipt stale control not pass")
    if rec_snap.get("pass") is not True:
        return fail("receipt snapshot control not pass")
    rec_log = rec_stale.get("promotion_log") or doc.get("promotion_log") or []
    if not gate.log_has_refusal(rec_log, "stale-green"):
        return fail("receipt log does not show stale-green refusal (must be visible, not absent)")

    if rec_snap.get("snapshot_id_a") != snaps["snapshot_id_a"]:
        return fail("receipt snapshot_id_a drifted from live pull")
    if rec_snap.get("snapshot_id_b") != snaps["snapshot_id_b"]:
        return fail("receipt snapshot_id_b drifted from live pull")

    print(
        f"stale_age={stale['age_seconds']} window={stale['window_length_seconds']} "
        f"snap_a={snaps['snapshot_id_a'][:12]} snap_b={snaps['snapshot_id_b'][:12]}"
    )
    print("SUCCESS:REL-0014-probe1 stale-window refusal and distinct snapshot ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
