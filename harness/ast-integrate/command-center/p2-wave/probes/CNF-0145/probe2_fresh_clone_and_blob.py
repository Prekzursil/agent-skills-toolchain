#!/usr/bin/env python3
"""Probe 2: fresh-clone ctime plus independent cat-file member audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402
from scenario import assert_scenario, run_scenario  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0145.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:CNF-0145-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if L.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0145-probe2 sentinel absent")
        return 1
    if doc.get("byte_source") != L.BYTE_SOURCE:
        print("FAILED:CNF-0145-probe2 byte_source", doc.get("byte_source"))
        return 1
    if doc.get("forbidden_byte_source") != L.FORBIDDEN_BYTE_SOURCE:
        print("FAILED:CNF-0145-probe2 forbidden source missing")
        return 1
    errs = L.validate_report(doc)
    if errs:
        print("FAILED:CNF-0145-probe2 schema", errs[:8])
        return 1

    live = run_scenario()
    live_errs = assert_scenario(live)
    if live_errs:
        print("FAILED:CNF-0145-probe2 live", live_errs)
        return 1

    proof = live["fresh_clone_proof"]
    if not proof["created_during_this_run"]:
        print("FAILED:CNF-0145-probe2 clone not created this run")
        return 1
    if proof["clone_ctime"] < proof["run_started_unix"] - 1.0:
        print(
            "FAILED:CNF-0145-probe2 clone_ctime precedes run",
            proof["clone_ctime"],
            proof["run_started_unix"],
        )
        return 1
    art_proof = doc.get("fresh_clone_proof") or {}
    if not art_proof.get("created_during_this_run") or not art_proof.get("used"):
        print("FAILED:CNF-0145-probe2 artifact fresh-clone proof missing")
        return 1

    trap = live["archive_trap"]
    print(
        f"archive bytes={trap['archive_bytes']} crlf={trap['archive_crlf']} "
        f"cat-file bytes={trap['cat_file_bytes']} crlf={trap['cat_file_crlf']}"
    )
    if trap["archive_crlf"] <= 0 or trap["cat_file_crlf"] != 0:
        print("FAILED:CNF-0145-probe2 archive trap not discriminating")
        return 1
    art_trap = doc.get("archive_trap") or {}
    for key in ("archive_sha256", "cat_file_sha256", "archive_crlf", "cat_file_crlf"):
        if art_trap.get(key) != trap.get(key):
            print(f"FAILED:CNF-0145-probe2 archive_trap drift on {key}")
            return 1

    if not live["blob_audit_all_match"]:
        print("FAILED:CNF-0145-probe2 packed members != cat-file blobs")
        return 1
    art_audit = {row["path"]: row for row in doc.get("member_blob_audit") or []}
    live_audit = {row["path"]: row for row in live["member_blob_audit"]}
    if set(art_audit) != set(live_audit):
        print("FAILED:CNF-0145-probe2 member path set drift")
        return 1
    for path, row in live_audit.items():
        art = art_audit[path]
        if art.get("cat_file_sha256") != row["cat_file_sha256"]:
            print(f"FAILED:CNF-0145-probe2 cat-file sha drift {path}")
            return 1
        if art.get("packed_sha256") != row["packed_sha256"]:
            print(f"FAILED:CNF-0145-probe2 packed sha drift {path}")
            return 1
        if not row["match"]:
            print(f"FAILED:CNF-0145-probe2 mismatch {path}")
            return 1

    if not live["reviewer"]["matches_released"]:
        print("FAILED:CNF-0145-probe2 second clone pack mismatch")
        return 1
    if live["reviewer"]["second_scratch_pack_sha256"] != live["sha256_sets"]["released"][
        "archive_sha256"
    ]:
        print("FAILED:CNF-0145-probe2 reviewer sha != released")
        return 1

    checklist = (REPO / "command-center/RELEASE-CHECKLIST.md").read_text(encoding="utf-8")
    if "git cat-file -p" not in checklist:
        print("FAILED:CNF-0145-probe2 checklist lost cat-file recipe")
        return 1
    if "Do not verify against `git archive`" not in checklist:
        print("FAILED:CNF-0145-probe2 checklist lost archive forbid")
        return 1

    print(
        f"clone_ctime={proof['clone_ctime']} run_started={proof['run_started_unix']} "
        f"members={len(live_audit)} second_clone=identical"
    )
    print("SUCCESS:CNF-0145-probe2 fresh-clone ctime and cat-file audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
