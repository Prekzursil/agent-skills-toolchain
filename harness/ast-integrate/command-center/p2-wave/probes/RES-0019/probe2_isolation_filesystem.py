#!/usr/bin/env python3
"""Named probe 2: filesystem census + live-profile isolation + 222-fork control.

Mechanically different from probe 1: os.walk of SKILL.md files and a live
HOME census hash, plus a scan-all (no-replace) load that MUST report 222
so the detector is not silent on the refuting arm.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import (  # noqa: E402
    scenario_filesystem_and_scan_all,
    scenario_isolation,
)

ART = REPO / "command-center/research/RES-0019.json"
SENTINEL = (
    "SUCCESS:RES-0019 in the receipt AND an observed integer skill count "
    "from a throwaway profile with the fixture skill visible in the listing, "
    "and an explicit CONFIRMED or REFUTED against the 110/222 fork"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0019-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("completion sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        return fail("missing source_probe/verifier_probe")
    if src.get("fingerprint") == ver.get("fingerprint"):
        return fail("same-probe-rerun fingerprints")

    with tempfile.TemporaryDirectory(prefix="res0019-p2-") as tmp:
        root = Path(tmp)
        iso = scenario_isolation(root)
        fs = scenario_filesystem_and_scan_all(root)

    if not iso["unchanged"]:
        return fail("live profile changed")
    if fs["filesystem_plugin_body"] != 222:
        return fail(f"filesystem body {fs['filesystem_plugin_body']} != 222")
    if not fs["scan_all_matches_222_fork"]:
        return fail("scan-all control did not report 222")
    if not fs["replace_matches_110_fork"]:
        return fail("replace path did not report 110")
    if fs["filesystem_plugin_body"] == fs["replace_plugin_body"]:
        return fail("filesystem and client replace counts collapsed")
    if not fs["author_136_equals_inert_plus_commands"]:
        return fail("112 undeclared + 24 commands did not reconstruct 136")

    payload = {
        "probe": "probe2-isolation-filesystem-scan-all",
        "unit_id": "RES-0019",
        "pass": True,
        "isolation": iso,
        "filesystem_and_scan_all": fs,
        "live_unchanged": iso["unchanged"],
        "filesystem_plugin_body": fs["filesystem_plugin_body"],
        "scan_all_plugin_body": fs["scan_all_plugin_body"],
        "replace_plugin_body": fs["replace_plugin_body"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "live_unchanged="
        f"{iso['unchanged']} filesystem_body={fs['filesystem_plugin_body']} "
        f"scan_all={fs['scan_all_plugin_body']} replace={fs['replace_plugin_body']} "
        f"inert_plus_commands={fs['inert_plus_commands']}"
    )
    print("SUCCESS:RES-0019-probe2 isolation, filesystem count, 222-fork control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
