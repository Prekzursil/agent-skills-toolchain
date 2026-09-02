#!/usr/bin/env python3
"""Named probe 1: packaging include-list control, then secret/PII scan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scan import scan_included  # noqa: E402

ART = REPO / "command-center/audit/AUD-0078-corpus-bundle-privacy-scan.json"
SENTINEL = (
    "SUCCESS:AUD-0078 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def _check_artifact() -> None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "AUD-0078":
        raise SystemExit(f"FAILED:AUD-0078-probe1 unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:AUD-0078-probe1 self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        raise SystemExit("FAILED:AUD-0078-probe1 sentinel absent")


def main() -> int:
    _check_artifact()
    result = scan_included()
    control = result["control"]
    if not control.get("ok"):
        print(json.dumps({"control": control}, sort_keys=True))
        print("FAILED:AUD-0078-probe1 include-list resolver control")
        return 1
    scanner_control = result.get("scanner_control") or {}
    if not scanner_control.get("ok"):
        print(json.dumps({"scanner_control": scanner_control}, sort_keys=True))
        print("FAILED:AUD-0078-probe1 scanner both-states control")
        return 1
    public = {
        "probe": "probe1-include-scan",
        "control_ok": True,
        "scanner_control_ok": True,
        "included_sample": control.get("included_sample"),
        "excluded_reasons": {
            k: v.get("reason") for k, v in (control.get("excluded") or {}).items()
        },
        "include_file_count": result["include"]["file_count"],
        "include_byte_count": result["include"]["byte_count"],
        "by_tree": result["include"]["by_tree"],
        "corpus_present": result["include"]["corpus_present"],
        "plugin_scanners_present": result.get("plugin_scanners_present"),
        "scanned_files": result["scanned_files"],
        "finding_count": result["finding_count"],
        "by_class": result["by_class"],
        "hottest_paths": result["hottest_paths"][:8],
        "never_prints_values": True,
    }
    print(json.dumps(public, sort_keys=True))
    print(
        "include={0} findings={1} control_ok=True".format(
            result["include"]["file_count"], result["finding_count"]
        )
    )
    print("SUCCESS:AUD-0078-probe1 include-list control and secret/PII scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
