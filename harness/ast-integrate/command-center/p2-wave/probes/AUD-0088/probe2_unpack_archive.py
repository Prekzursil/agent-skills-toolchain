#!/usr/bin/env python3
"""Probe 2: unpack the built scratch archive and enumerate real contents.

The declared include list is not the receipt. This probe builds into a scratch
directory, reads ZipInfo + the extracted tree, and runs the planted-stray
control (.git, credential-shaped basename, extra member).
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
    live = M.probe2_unpack_archive(REPO)
    ctl = live["control"]
    report = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "archive_entry_count": live["archive_entry_count"],
        "archive_uncompressed_bytes": live["archive_uncompressed_bytes"],
        "archive_file_bytes": live["archive_file_bytes"],
        "declared_vs_archive_agree": live["declared_vs_archive_agree"],
        "zip_vs_extract_agree": live["zip_vs_extract_agree"],
        "declared_file_found_in_unpack": live["declared_file_found_in_unpack"],
        "prohibited_in_clean": live["prohibited_in_clean"],
        "control": {
            "declared_file_found": ctl["declared_file_found"],
            "dot_git_flagged": ctl["dot_git_flagged"],
            "credential_flagged": ctl["credential_flagged"],
            "stray_detected": ctl["stray_detected"],
            "clean_silent": ctl["clean_silent"],
            "ok": ctl["ok"],
        },
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"archive_entries={live['archive_entry_count']} "
        f"uncompressed={live['archive_uncompressed_bytes']} "
        f"zip_bytes={live['archive_file_bytes']} "
        f"agree={live['declared_vs_archive_agree']} "
        f"control_ok={ctl['ok']}"
    )
    if not ctl.get("ok"):
        print(f"FAILED:AUD-0088-probe2 control did not discriminate {ctl}")
        return 1
    if not live["declared_file_found_in_unpack"]:
        print("FAILED:AUD-0088-probe2 unpack missed a declared include-list file")
        return 1
    if not live["zip_vs_extract_agree"]:
        print("FAILED:AUD-0088-probe2 ZipInfo listing disagrees with extracted tree")
        return 1
    if live["prohibited_in_clean"]:
        print(f"FAILED:AUD-0088-probe2 clean archive carries prohibited paths {live['prohibited_in_clean']}")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0088-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:AUD-0088-probe2 artifact unparseable: {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0088-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0088-probe2 self-declared {st}")
        return 1
    rec = doc.get("unpacked_archive") or {}
    for key in (
        "archive_entry_count",
        "archive_uncompressed_bytes",
        "declared_vs_archive_agree",
        "declared_file_found_in_unpack",
    ):
        if rec.get(key) != live.get(key):
            print(f"FAILED:AUD-0088-probe2 artifact mismatch {key}: art={rec.get(key)} live={live.get(key)}")
            return 1
    art_ctl = rec.get("control") or {}
    for key in ("declared_file_found", "dot_git_flagged", "credential_flagged", "stray_detected", "clean_silent", "ok"):
        if art_ctl.get(key) != ctl.get(key):
            print(f"FAILED:AUD-0088-probe2 artifact control mismatch {key}")
            return 1
    # archive_file_bytes can depend on compressor; require it recorded and positive.
    if int(rec.get("archive_file_bytes") or 0) < 1:
        print("FAILED:AUD-0088-probe2 artifact missing archive_file_bytes")
        return 1
    print("SUCCESS:AUD-0088-probe2 unpack enumeration and stray-file control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
