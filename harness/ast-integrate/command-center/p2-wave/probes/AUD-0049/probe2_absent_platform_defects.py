#!/usr/bin/env python3
"""Named probe 2: already-measured defects on promised platforms absent from CI.

Mechanically different from probe 1: does not score the OS set difference as
the primary signal. For each promised platform missing from runs-on, require
at least one already-measured defect that only that platform exposes, and
require Windows to carry the three recorded CRLF failures at a different
severity from a no-defect underexercised platform. Independently greps the
AUD-0041 inventory for windows-latest / macos-latest; a hit would refute the
underexercised headline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from comparator import (  # noqa: E402
    INVENTORY,
    MACOS_DEFECTS,
    WINDOWS_CRLF_DEFECTS,
    compare,
    measure,
    windows_crlf_control,
)

ART = REPO / "command-center/audit/AUD-0049-runner-matrix-vs-support.json"
UNIT = "AUD-0049"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def inventory_mentions_os_runners() -> dict[str, bool]:
    blob = INVENTORY.read_text(encoding="utf-8").lower()
    return {
        "windows-latest": "windows-latest" in blob,
        "macos-latest": "macos-latest" in blob,
        "ubuntu-latest": "ubuntu-latest" in blob,
    }


def main() -> int:
    live = measure()
    mentions = inventory_mentions_os_runners()
    if not mentions["ubuntu-latest"]:
        return fail("inventory does not mention ubuntu-latest; grep is not reading the file")
    if mentions["windows-latest"] or mentions["macos-latest"]:
        return fail(
            "inventory names windows-latest or macos-latest; Windows/macOS underexercised headline is REFUTED",
            mentions,
        )

    missing = live["drift"]["promised_minus_exercised"]
    defects = live["absent_platform_defects"]
    by_platform: dict[str, list] = {}
    for row in defects:
        by_platform.setdefault(row["platform"], []).append(row)
    for platform in missing:
        if not by_platform.get(platform):
            return fail(f"promised platform {platform} absent from CI has no named defect")

    win = by_platform.get("windows") or []
    win_ids = {d["defect_id"] for d in win}
    expected = {d["defect_id"] for d in WINDOWS_CRLF_DEFECTS}
    if win_ids != expected or len(win) != 3:
        return fail("Windows CRLF defect set mismatch", {"got": sorted(win_ids), "want": sorted(expected)})
    if any(d.get("linux_ci_sees") for d in win):
        return fail("a Windows CRLF defect claims Linux CI sees it")

    mac = by_platform.get("macos") or []
    mac_ids = {d["defect_id"] for d in mac}
    if {d["defect_id"] for d in MACOS_DEFECTS} - mac_ids:
        return fail("macOS NFD defect missing", mac)

    ctl = windows_crlf_control()
    if not ctl["severity_discriminates"]:
        return fail("severity does not distinguish known-defect vs none", ctl)
    win_row = next(r for r in live["drift"]["rows"] if r["platform"] == "windows")
    if win_row["severity"] != "underexercised-with-known-defect":
        return fail("Windows severity is not underexercised-with-known-defect", win_row)
    empty = compare({"windows"}, set(), {"windows": []})
    empty_row = empty["rows"][0]
    if empty_row["severity"] == win_row["severity"]:
        return fail("severity collapsed known-defect and no-defect into one class")

    for rel in (
        "tools/command-center/validate.py",
        "tools/command-center/tests/test_seed.py",
        "command-center/p2-wave/_build_IMP0440.py",
    ):
        if not (REPO / rel).is_file():
            return fail(f"live-tree defect locus absent: {rel}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    art_defects = doc.get("absent_platform_defects") or []
    art_ids = {(d.get("platform"), d.get("defect_id")) for d in art_defects}
    live_ids = {(d["platform"], d["defect_id"]) for d in defects}
    if art_ids != live_ids:
        return fail("artifact defect set != live re-run", {"live": sorted(live_ids), "art": sorted(art_ids)})
    if doc.get("drift", {}).get("windows_underexercised") is not True:
        return fail("artifact dropped windows_underexercised")
    if doc.get("overall_verdict") != "DRIFT":
        return fail("overall_verdict is not DRIFT; reviewer would accept full coverage")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer gate not independent PASS", reviewer)

    out = {
        "probe": "probe2-absent-platform-defects",
        "unit_id": UNIT,
        "pass": True,
        "inventory_mentions": mentions,
        "windows_latest_in_inventory": False,
        "macos_latest_in_inventory": False,
        "missing_platforms": missing,
        "windows_crlf_defects": sorted(win_ids),
        "macos_defects": sorted(mac_ids),
        "windows_severity": win_row["severity"],
        "no_defect_severity": empty_row["severity"],
        "severity_discriminates": True,
        "headline_full_coverage_refuted": True,
        "artifact_matches_live": True,
    }
    (HERE / "probe2-absent-platform-defects.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0049-probe2 absent-platform defects and coverage falsification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
