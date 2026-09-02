#!/usr/bin/env python3
"""Probe 2: fabrication fails freshness; positive VERIFIED appears; independent re-derive."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from project import (  # noqa: E402
    VERIFIED_HEADER,
    freshness_ok,
    load_registry,
    parse_claim_lines,
    project,
    render_changelog,
    render_release_notes,
    verified_ids_in_notes,
    version_line_for,
)

ART = REPO / "command-center/receipts/REL-0016.json"
CHANGELOG = REPO / "command-center/receipts/REL-0016.changelog.md"
NOTES = REPO / "command-center/receipts/REL-0016.release-notes.md"
REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"
EVIDENCE_REL = "command-center/p2-wave/probes/REL-0016/fixtures/ok-evidence.txt"
FABRICATED = "- [HAND-TYPED] This sentence was not projected from any claim."


def fixture_registry() -> dict:
    return {
        "claims": [
            {
                "id": "FIX-POS",
                "text": "Positive control: a genuinely VERIFIED claim with a resolving anchor appears.",
                "verification_status": "VERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:2",
            },
            {
                "id": "FIX-UNVER",
                "text": "Unverified filler.",
                "verification_status": "UNVERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
        ]
    }


def rederive_verified_ids(registry: dict, repo: Path) -> list[str]:
    """Re-derive verified membership from the registry and disk, not from the receipt."""
    projection = project(registry, repo)
    return [row["id"] for row in projection["verified"]]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0016-probe2 receipt missing")
        return 1
    receipt_text = ART.read_text(encoding="utf-8")
    if "SUCCESS:REL-0016" not in receipt_text:
        print("FAILED:REL-0016-probe2 sentinel absent")
        return 1

    registry = fixture_registry()
    version_line, _ = version_line_for(REPO)
    projection = project(registry, REPO)
    expected_c = render_changelog(projection, version_line=version_line)
    expected_n = render_release_notes(projection, version_line=version_line)

    if "FIX-POS" not in verified_ids_in_notes(expected_n):
        print("FAILED:REL-0016-probe2 positive control absent from regeneration")
        return 1
    if "FIX-UNVER" in verified_ids_in_notes(expected_n):
        print("FAILED:REL-0016-probe2 unverified in verified section")
        return 1
    if "Positive control: a genuinely VERIFIED claim" not in expected_n:
        print("FAILED:REL-0016-probe2 positive sentence missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="rel0016-p2-") as tmp:
        root = Path(tmp)
        changelog = root / "CHANGELOG.md"
        notes = root / "RELEASE-NOTES.md"
        changelog.write_text(expected_c, encoding="utf-8", newline="\n")
        notes.write_text(expected_n, encoding="utf-8", newline="\n")
        if not freshness_ok(changelog.read_text(encoding="utf-8"), expected_c):
            print("FAILED:REL-0016-probe2 clean changelog not fresh")
            return 1
        tampered = expected_n.rstrip() + "\n\n" + FABRICATED + "\n"
        notes.write_text(tampered, encoding="utf-8", newline="\n")
        if freshness_ok(notes.read_text(encoding="utf-8"), expected_n):
            print("FAILED:REL-0016-probe2 fabrication was not detected")
            return 1

    live = load_registry(REGISTRY)
    derived_ids = rederive_verified_ids(live, REPO)
    if not derived_ids:
        print("FAILED:REL-0016-probe2 live re-derive empty")
        return 1
    if not CHANGELOG.is_file() or not NOTES.is_file():
        print("FAILED:REL-0016-probe2 live notes missing")
        return 1
    live_notes = NOTES.read_text(encoding="utf-8")
    live_changelog = CHANGELOG.read_text(encoding="utf-8")
    live_proj = project(live, REPO)
    live_version_line, _ = version_line_for(REPO)
    regen_n = render_release_notes(live_proj, version_line=live_version_line)
    regen_c = render_changelog(live_proj, version_line=live_version_line)
    if not freshness_ok(live_notes, regen_n) or not freshness_ok(live_changelog, regen_c):
        print("FAILED:REL-0016-probe2 live notes differ from regeneration")
        return 1
    note_ids = verified_ids_in_notes(live_notes)
    if note_ids != derived_ids:
        print("FAILED:REL-0016-probe2 re-derived ids", derived_ids, "notes", note_ids)
        return 1
    for row in parse_claim_lines(live_notes, VERIFIED_HEADER):
        if row["status_tag"] != "VERIFIED":
            print("FAILED:REL-0016-probe2 tagged status in verified section", row)
            return 1
        if not row["id"]:
            print("FAILED:REL-0016-probe2 verified line missing claim id")
            return 1

    summary = {
        "fabrication_detected": True,
        "positive_control": True,
        "independent_rederive_ids": derived_ids,
        "live_fresh": True,
        "pass": True,
        "probe": "probe2-fabrication-and-positive",
        "unit_id": "REL-0016",
        "shown_conclusion_first": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "fabrication_detected=True positive_control=True "
        f"rederived={len(derived_ids)} live_fresh=True"
    )
    print("SUCCESS:REL-0016-probe2 fabrication freshness and positive control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
