#!/usr/bin/env python3
"""Probe 1: UNVERIFIED injection stays out of verified; missing VERIFIED anchor refuses."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from project import (  # noqa: E402
    ProjectionRefused,
    load_registry,
    project,
    project_files,
    verified_ids_in_notes,
)

ART = REPO / "command-center/receipts/REL-0016.json"
EVIDENCE_REL = "command-center/p2-wave/probes/REL-0016/fixtures/ok-evidence.txt"


def fixture_registry(unverified_text: str = "injected unverified claim must not appear verified") -> dict:
    return {
        "claims": [
            {
                "id": "FIX-VERIFIED-OK",
                "text": "A genuinely VERIFIED claim with a resolving anchor appears.",
                "verification_status": "VERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
            {
                "id": "FIX-UNVERIFIED",
                "text": unverified_text,
                "verification_status": "UNVERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
            {
                "id": "FIX-INFERRED",
                "text": "Inferred item is tagged, not verified.",
                "verification_status": "INFERRED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
            {
                "id": "FIX-REJECTED",
                "text": "Rejected item is tagged, not verified.",
                "verification_status": "REJECTED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
            {
                "id": "FIX-DEFERRED",
                "text": "Deferred item is tagged, not verified.",
                "verification_status": "DEFERRED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
        ]
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0016-probe1 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if receipt.get("unit_id") != "REL-0016":
        print("FAILED:REL-0016-probe1 unit_id", receipt.get("unit_id"))
        return 1
    if "SUCCESS:REL-0016" not in json.dumps(receipt):
        print("FAILED:REL-0016-probe1 sentinel absent")
        return 1

    injected = "INJECTED-UNVERIFIED-SENTENCE must never enter verified"
    registry = fixture_registry(injected)
    projection = project(registry, REPO)
    verified_ids = [row["id"] for row in projection["verified"]]
    verified_text = "\n".join(row["line"] for row in projection["verified"])
    tagged_text = "\n".join(row["line"] for row in projection["tagged"])

    if "FIX-UNVERIFIED" in verified_ids:
        print("FAILED:REL-0016-probe1 UNVERIFIED appeared in verified ids")
        return 1
    if injected in verified_text:
        print("FAILED:REL-0016-probe1 injected UNVERIFIED text in verified section")
        return 1
    if "FIX-VERIFIED-OK" not in verified_ids:
        print("FAILED:REL-0016-probe1 positive VERIFIED claim missing")
        return 1
    if "[UNVERIFIED] [FIX-UNVERIFIED]" not in tagged_text:
        print("FAILED:REL-0016-probe1 UNVERIFIED not tagged inline")
        return 1
    for status, cid in (
        ("INFERRED", "FIX-INFERRED"),
        ("REJECTED", "FIX-REJECTED"),
        ("DEFERRED", "FIX-DEFERRED"),
    ):
        if f"[{status}] [{cid}]" not in tagged_text:
            print(f"FAILED:REL-0016-probe1 {status} not tagged inline")
            return 1

    with tempfile.TemporaryDirectory(prefix="rel0016-p1-") as tmp:
        root = Path(tmp)
        changelog = root / "CHANGELOG.md"
        notes = root / "RELEASE-NOTES.md"
        project_files(registry, REPO, changelog, notes)
        live_ids = verified_ids_in_notes(notes.read_text(encoding="utf-8"))
        if "FIX-UNVERIFIED" in live_ids or "FIX-VERIFIED-OK" not in live_ids:
            print("FAILED:REL-0016-probe1 notes verified ids", live_ids)
            return 1

        missing_reg = {
            "claims": [
                {
                    "id": "FIX-VERIFIED-MISSING",
                    "text": "This VERIFIED claim points at a file that does not exist.",
                    "verification_status": "VERIFIED",
                    "evidence_anchor": "command-center/p2-wave/probes/REL-0016/fixtures/does-not-exist.txt:1",
                }
            ]
        }
        refuse_changelog = root / "refused" / "CHANGELOG.md"
        refuse_notes = root / "refused" / "RELEASE-NOTES.md"
        refused = False
        try:
            project_files(missing_reg, REPO, refuse_changelog, refuse_notes)
        except ProjectionRefused as exc:
            refused = True
            if exc.claim_id != "FIX-VERIFIED-MISSING":
                print("FAILED:REL-0016-probe1 refuse id", exc.claim_id)
                return 1
            if exc.reason != "missing-file":
                print("FAILED:REL-0016-probe1 refuse reason", exc.reason)
                return 1
        if not refused:
            print("FAILED:REL-0016-probe1 missing VERIFIED anchor emitted instead of refuse")
            return 1
        if refuse_changelog.is_file() or refuse_notes.is_file():
            print("FAILED:REL-0016-probe1 refuse still wrote notes")
            return 1

    live_registry = load_registry(REPO / "command-center/CLAIM-REGISTRY.json")
    live_proj = project(live_registry, REPO)
    if live_proj["emitted_verified"] < 1:
        print("FAILED:REL-0016-probe1 live registry emitted nothing")
        return 1

    summary = {
        "unverified_excluded": True,
        "missing_anchor_refused": True,
        "positive_verified_present": True,
        "live_emitted_verified": live_proj["emitted_verified"],
        "pass": True,
        "probe": "probe1-unverified-and-missing-anchor",
        "unit_id": "REL-0016",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "unverified_excluded=True missing_anchor_refused=True "
        f"positive={live_proj['emitted_verified']}"
    )
    print("SUCCESS:REL-0016-probe1 unverified exclusion and missing-anchor refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
