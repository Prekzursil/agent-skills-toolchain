#!/usr/bin/env python3
"""Named probe 2: SBOM both-way differ + independent grep secret scan.

Mechanically different from probe 1 (no openssl). Known-broken: drop a
component from the SBOM copy and confirm present-but-unlisted fires; add a
phantom and confirm listed-but-absent fires. Secret scan must be clean on the
bundle and must fire on a planted documentation-example access-key *shape*.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from sbomdiff import (  # noqa: E402
    PHANTOM_PURL,
    VENDOR_HELPER_PURL,
    add_phantom,
    differ,
    load_sbom,
    remove_component,
    vendor_helper_arcname,
)
from secrets import grep_scan, plant_example, unpack_artifact, write_pattern_file  # noqa: E402
from tools import grep_version, python_version  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0179.json"
FIX = HERE / "fixtures" / "published"


def require_artifact() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0179-probe2 receipt missing")
        raise SystemExit(1)
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0179":
        print("FAILED:CNF-0179-probe2 unit_id", doc.get("unit_id"))
        raise SystemExit(1)
    if "SUCCESS:CNF-0179" not in text:
        print("FAILED:CNF-0179-probe2 sentinel absent")
        raise SystemExit(1)
    diff = doc.get("sbom_diff")
    if not isinstance(diff, dict):
        report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
        diff = report.get("sbom_diff") if isinstance(report, dict) else None
    if not isinstance(diff, dict):
        print("FAILED:CNF-0179-probe2 sbom_diff both directions missing")
        raise SystemExit(1)
    if "listed_but_absent" not in diff or "present_but_unlisted" not in diff:
        print("FAILED:CNF-0179-probe2 sbom_diff both directions missing")
        raise SystemExit(1)
    doc["_sbom_diff"] = diff
    return doc


def main() -> int:
    doc = require_artifact()
    artifact = FIX / "cnf-0179-published.tar.gz"
    sbom_path = FIX / "sbom.cdx.json"
    if not artifact.is_file() or not sbom_path.is_file():
        print("FAILED:CNF-0179-probe2 published fixture missing")
        return 1

    sbom = load_sbom(sbom_path)
    healthy = differ(artifact, sbom)
    print(
        "healthy listed_but_absent="
        f"{healthy['listed_but_absent']} present_but_unlisted="
        f"{healthy['present_but_unlisted']}"
    )
    if not healthy["healthy"]:
        print("FAILED:CNF-0179-probe2 unmodified SBOM differ not empty")
        print(json.dumps(healthy, indent=2)[:2000])
        return 1

    removed = differ(artifact, remove_component(sbom, VENDOR_HELPER_PURL))
    helper_path = vendor_helper_arcname()
    if helper_path not in removed["present_but_unlisted"]:
        print("FAILED:CNF-0179-probe2 removed-component differ silent")
        print(json.dumps(removed, indent=2)[:2000])
        return 1

    phantom = differ(artifact, add_phantom(sbom))
    if PHANTOM_PURL not in phantom["listed_but_absent"]:
        print("FAILED:CNF-0179-probe2 phantom-component differ silent")
        print(json.dumps(phantom, indent=2)[:2000])
        return 1

    recorded_listed = list(doc["_sbom_diff"]["listed_but_absent"])
    recorded_unlisted = list(doc["_sbom_diff"]["present_but_unlisted"])
    if recorded_listed != healthy["listed_but_absent"]:
        print("FAILED:CNF-0179-probe2 receipt listed_but_absent mismatch")
        return 1
    if recorded_unlisted != healthy["present_but_unlisted"]:
        print("FAILED:CNF-0179-probe2 receipt present_but_unlisted mismatch")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0179-p2-sec-") as tmp:
        root = Path(tmp)
        patterns = write_pattern_file(root / "secret-patterns.txt")
        unpacked = unpack_artifact(artifact, root / "unpack")
        found, rc, summary = grep_scan(unpacked, patterns)
        print(f"secret_scan_clean found={found} {summary}")
        if found or rc != 1:
            print("FAILED:CNF-0179-probe2 bundle secret scan not clean")
            return 1
        plant_example(unpacked)
        planted_found, planted_rc, planted_summary = grep_scan(unpacked, patterns)
        print(f"secret_scan_planted found={planted_found} {planted_summary}")
        if not planted_found or planted_rc != 0:
            print("FAILED:CNF-0179-probe2 planted example did not fire scanner")
            return 1

    out = {
        "probe": "probe2-sbom-secrets",
        "unit_id": "CNF-0179",
        "grep_version": grep_version(),
        "python_version": python_version(),
        "healthy_listed_but_absent": healthy["listed_but_absent"],
        "healthy_present_but_unlisted": healthy["present_but_unlisted"],
        "removed_component_fired": True,
        "phantom_component_fired": True,
        "secret_scan_clean": True,
        "secret_scan_planted_fired": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0179-probe2 SBOM both-way differ and grep secret scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
