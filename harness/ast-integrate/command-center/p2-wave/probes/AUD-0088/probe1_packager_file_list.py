#!/usr/bin/env python3
"""Probe 1: packaging tool's own file list (allowlist expansion).

Independent of the archive unpack. Expands tools/plugin/payload-allowlist.json
via the packager loader and via a directory listing of the same globs.
Disagreement is a detector failure, not a picked winner.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = REPO / "command-center/audit/AUD-0088-package-content-baseline.json"
SENTINEL = (
    "SUCCESS:AUD-0088 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def main() -> int:
    live = M.probe1_packager_file_list(REPO)
    report = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "allowlist_path": live["allowlist_path"],
        "deny_by_default": live["deny_by_default"],
        "declared_count": live["declared_count"],
        "declared_source_bytes": live["declared_source_bytes"],
        "independent_count": live["independent_count"],
        "lists_agree": live["lists_agree"],
        "listing_sha256": live["listing_sha256"],
        "plugin_manifest_in_allowlist": live["plugin_manifest_in_allowlist"],
        "pack_py_present": live["pack_py_present"],
        "missing_on_disk": live["missing_on_disk"],
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"declared={live['declared_count']} independent={live['independent_count']} "
        f"bytes={live['declared_source_bytes']} agree={live['lists_agree']} "
        f"deny_by_default={live['deny_by_default']} pack_py={live['pack_py_present']}"
    )
    if not live["deny_by_default"]:
        print("FAILED:AUD-0088-probe1 allowlist is not deny-by-default")
        return 1
    if not live["lists_agree"]:
        print(
            "FAILED:AUD-0088-probe1 packager list disagrees with independent glob "
            f"only_tool={set(live['declared_paths']) - set(live['independent_paths'])} "
            f"only_indep={set(live['independent_paths']) - set(live['declared_paths'])}"
        )
        return 1
    if live["declared_count"] < 1 or live["missing_on_disk"]:
        print(f"FAILED:AUD-0088-probe1 empty or missing payload {live['missing_on_disk']}")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0088-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:AUD-0088-probe1 artifact unparseable: {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0088-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0088-probe1 self-declared {st}")
        return 1
    rec = doc.get("packager_file_list") or {}
    for key in (
        "declared_count",
        "declared_source_bytes",
        "listing_sha256",
        "lists_agree",
        "pack_py_present",
        "plugin_manifest_in_allowlist",
    ):
        if rec.get(key) != live.get(key):
            print(f"FAILED:AUD-0088-probe1 artifact mismatch {key}: art={rec.get(key)} live={live.get(key)}")
            return 1
    if rec.get("declared_paths") != live["declared_paths"]:
        print("FAILED:AUD-0088-probe1 artifact declared_paths drifted")
        return 1
    print("SUCCESS:AUD-0088-probe1 packager file list recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
