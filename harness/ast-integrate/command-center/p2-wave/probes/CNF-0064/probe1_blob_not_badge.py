#!/usr/bin/env python3
"""Probe 1: SPDX and SHA come from the LICENSE blob, never badge/package.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402
import schema_ctl as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0064-license-provenance.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0064-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if A.SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0064-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0064" or doc.get("state") != "SUCCESS":
        print("FAILED:CNF-0064-probe1 unit/state", doc.get("unit_id"), doc.get("state"))
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "license-audit":
        print("FAILED:CNF-0064-probe1 report.kind", report.get("kind"))
        return 1
    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0064-probe1 schema", errs[0])
        return 1
    try:
        S.garbage_rejected()
    except AssertionError as exc:
        print("FAILED:CNF-0064-probe1", exc)
        return 1

    live = {r["id"]: r for r in A.audit_all()}
    payload = A.artifact_payload(doc)
    art_rows = {r["id"]: r for r in payload["candidates"]}
    if set(live) != set(art_rows):
        print("FAILED:CNF-0064-probe1 candidate id set drift")
        return 1

    for cid, live_row in live.items():
        art = art_rows[cid]
        rel = live_row["license_blob_path"]
        blob_path = REPO / rel
        if not blob_path.is_file():
            print(f"FAILED:CNF-0064-probe1 missing blob {cid} {rel}")
            return 1
        recomputed = A.sha256_file(blob_path)
        art_sha = art.get("license_blob_sha256") or art.get("license_blob_sha256")
        if art_sha != recomputed:
            print(f"FAILED:CNF-0064-probe1 sha mismatch {cid}")
            return 1
        text = blob_path.read_text(encoding="utf-8", errors="replace")
        parsed = A.parse_spdx(text)
        art_spdx = art.get("spdx_from_blob") or art.get("spdx_from_blob")
        if art_spdx != parsed:
            print(
                f"FAILED:CNF-0064-probe1 spdx not from blob {cid} "
                f"art={art_spdx} parsed={parsed}"
            )
            return 1
        if parsed != live_row["spdx_from_blob"]:
            print(f"FAILED:CNF-0064-probe1 live parse drift {cid}")
            return 1
        if not live_row["match_registry"]:
            if art_spdx == (art.get("registry_spdx") or art.get("registry_spdx")):
                print(f"FAILED:CNF-0064-probe1 copied registry SPDX onto blob {cid}")
                return 1
        print(
            f"blob id={cid} sha={recomputed[:12]} spdx={parsed} "
            f"match_registry={live_row['match_registry']}"
        )

    trap_pkg = HERE / "fixtures/planted/badge-trap/package.json"
    trap_readme = HERE / "fixtures/planted/badge-trap/README.md"
    pkg = json.loads(trap_pkg.read_text(encoding="utf-8"))
    readme = trap_readme.read_text(encoding="utf-8")
    if pkg.get("license") != "MIT" or "license-MIT" not in readme:
        print("FAILED:CNF-0064-probe1 badge-trap fixture broken")
        return 1
    trap = art_rows["planted-badge-trap"]
    trap_spdx = trap.get("spdx_from_blob") or trap.get("spdx_from_blob")
    trap_reg = trap.get("registry_spdx") or trap.get("registry_spdx")
    trap_sha = trap.get("license_blob_sha256") or trap.get("license_blob_sha256")
    if trap_spdx == "MIT" or trap_reg != "MIT":
        print("FAILED:CNF-0064-probe1 badge-trap did not prefer blob over badge")
        return 1
    if trap_spdx != "Apache-2.0":
        print("FAILED:CNF-0064-probe1 badge-trap blob SPDX", trap_spdx)
        return 1
    if A.sha256_file(trap_pkg) == trap_sha:
        print("FAILED:CNF-0064-probe1 hashed package.json instead of LICENSE")
        return 1
    if payload["summary"].get("blob_sha_missing_count") != 0:
        print("FAILED:CNF-0064-probe1 blob_sha_missing_count")
        return 1
    method = payload["method"]
    if method.get("reads_readme_badge") or method.get("reads_package_json_license"):
        print("FAILED:CNF-0064-probe1 method claims to read badges")
        return 1
    print("badge_trap package.json=MIT blob=Apache-2.0 sha_is_license_file=True")
    print("SUCCESS:CNF-0064-probe1 blob SHA and SPDX from LICENSE bytes not badges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
