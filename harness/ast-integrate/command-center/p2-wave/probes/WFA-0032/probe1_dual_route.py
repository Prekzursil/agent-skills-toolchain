#!/usr/bin/env python3
"""Probe 1: dual-route census, UNRESOLVED names failing route, hashes stored."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import extract as X  # noqa: E402
from corpus import N_EXPECTED, PLANT_FS_ONLY, PLANT_GIT_ONLY  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0032-extract-provenance.json"


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0032-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return _fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0032" not in json.dumps(doc):
        return _fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return _fail(f"self-declared {doc.get('state')}")
    live = X.run_extract()
    recs = doc.get("records") or []
    if len(recs) != N_EXPECTED:
        return _fail(f"artifact n={len(recs)} want={N_EXPECTED}")
    if live["n"] != N_EXPECTED:
        return _fail(f"live n={live['n']} want={N_EXPECTED}")
    by_id = {r["candidate_id"]: r for r in recs}
    live_by = {r["candidate_id"]: r for r in live["records"]}
    if set(by_id) != set(live_by):
        return _fail("id set drift between artifact and live extract")
    missing_hash = 0
    silent = 0
    status_drift = 0
    hash_drift = 0
    for cid, rec in by_id.items():
        live_rec = live_by[cid]
        if rec.get("status") != live_rec.get("status"):
            status_drift += 1
        if rec.get("status") == "UNRESOLVED":
            if not rec.get("failing_route"):
                silent += 1
        else:
            if rec.get("status") != "RESOLVED":
                return _fail(f"{cid} status={rec.get('status')}")
            ch = rec.get("content_sha256") or ""
            lh = rec.get("line_sha256") or ""
            if len(ch) != 64 or len(lh) != 64:
                missing_hash += 1
            if ch != live_rec.get("content_sha256") or lh != live_rec.get("line_sha256"):
                hash_drift += 1
    if silent:
        return _fail(f"{silent} UNRESOLVED rows lack failing_route")
    if missing_hash:
        return _fail(f"{missing_hash} RESOLVED rows missing stored hashes")
    if status_drift:
        return _fail(f"{status_drift} status drift vs live re-extract")
    if hash_drift:
        return _fail(f"{hash_drift} hash drift vs live re-extract")
    fs_only = by_id.get(PLANT_FS_ONLY) or {}
    git_only = by_id.get(PLANT_GIT_ONLY) or {}
    if fs_only.get("status") != "UNRESOLVED" or "git-blob" not in (
        fs_only.get("failing_route") or ""
    ):
        return _fail(f"fs-only plant not named git-blob: {fs_only}")
    if git_only.get("status") != "UNRESOLVED" or "filesystem" not in (
        git_only.get("failing_route") or ""
    ):
        return _fail(f"git-only plant not named filesystem: {git_only}")
    if int(doc.get("n_resolved") or 0) != live["n_resolved"]:
        return _fail("n_resolved mismatch")
    out = {
        "probe": "probe1-dual-route",
        "n": len(recs),
        "n_resolved": doc.get("n_resolved"),
        "n_unresolved": doc.get("n_unresolved"),
        "silent_unresolved": silent,
        "plants": {
            PLANT_FS_ONLY: fs_only.get("failing_route"),
            PLANT_GIT_ONLY: git_only.get("failing_route"),
        },
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0032-probe1 dual-route census, UNRESOLVED names failing route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
