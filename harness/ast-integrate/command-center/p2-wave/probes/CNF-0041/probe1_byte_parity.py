#!/usr/bin/env python3
"""Named probe 1: pre vs post-rollback hash sets must be equal.

Reads sha256 fingerprints (not the planted-file detector). Residue, if any,
is listed by path. Re-runs the clean rehearsal in a fresh temp tree.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rehearse import report_payload, run_clean  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0041-rollback-byte-parity.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0041-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = report_payload(doc)
    if doc.get("unit_id") != "CNF-0041":
        print("FAILED:CNF-0041-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    if "SUCCESS:CNF-0041" not in text or "planted-file control was detected" not in text:
        print("FAILED:CNF-0041-probe1 sentinel absent")
        return 1
    if not sentinel.startswith("SUCCESS:CNF-0041"):
        print("FAILED:CNF-0041-probe1 sentinel field")
        return 1

    manifests = payload.get("hash_manifests") or {}
    for key in ("pre", "post", "post_rollback"):
        rows = manifests.get(key) or []
        if not isinstance(rows, list) or len(rows) < 1:
            print(f"FAILED:CNF-0041-probe1 hash manifest {key} missing")
            return 1

    with tempfile.TemporaryDirectory(prefix="cnf0041-p1-") as tmp:
        live = run_clean(Path(tmp) / "clean")

    if not live["symmetric_difference"]["empty"]:
        print("FAILED:CNF-0041-probe1 live residue")
        print(json.dumps(live["symmetric_difference"], indent=2))
        return 1
    if live["residue"]:
        print("FAILED:CNF-0041-probe1 residue listed on clean rollback")
        print(json.dumps(live["residue"], indent=2))
        return 1
    recorded = payload.get("symmetric_difference") or {}
    if recorded.get("empty") is not True:
        print("FAILED:CNF-0041-probe1 artifact residue not empty")
        return 1
    if payload.get("verdict") != "BYTE-IDENTICAL":
        print("FAILED:CNF-0041-probe1 verdict", payload.get("verdict"))
        return 1
    if payload.get("residue") not in ([], None):
        print("FAILED:CNF-0041-probe1 artifact residue", payload.get("residue"))
        return 1

    live_pre = {r["path"]: r["sha256"] for r in live["pre_rows"]}
    rec_pre = {r["path"]: r["sha256"] for r in manifests["pre"]}
    rec_rb = {r["path"]: r["sha256"] for r in manifests["post_rollback"]}
    if rec_pre != rec_rb:
        print("FAILED:CNF-0041-probe1 recorded pre != post_rollback")
        return 1
    if live_pre != rec_pre:
        print("FAILED:CNF-0041-probe1 live pre sha drift vs artifact")
        print(json.dumps({"live": live_pre, "recorded": rec_pre}, indent=2)[:3000])
        return 1
    post = {r["path"]: r["sha256"] for r in manifests["post"]}
    if post == rec_pre:
        print("FAILED:CNF-0041-probe1 post hash set equals pre; change was vacuous")
        return 1

    out = {
        "probe": "probe1-byte-parity",
        "unit_id": "CNF-0041",
        "pre_files": len(live_pre),
        "post_rollback_files": len(live["post_rollback_rows"]),
        "symmetric_difference_empty": True,
        "residue_paths": [],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"pre={len(live_pre)} post_rollback={len(live['post_rollback_rows'])} "
        "residue=[] direction=none"
    )
    print("SUCCESS:CNF-0041-probe1 byte-parity pre equals post-rollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
