#!/usr/bin/env python3
"""Probe 1: reserved-name walk delta and safe relpath for NUL.

Mechanically: build two fixture trees that differ only by a file named NUL,
walk both with windows_safe_path.walk_tree, require the file counts to differ
by exactly one, and require safe_relpath to return 'NUL' rather than a
\\\\.\\NUL device mount. The naive Windows relpath replica must raise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "lib"))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0467.json"
SENTINEL = "SENTINEL:IMP-0467:PATH-LIBRARY-WINDOWS-SAFE"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0467-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or doc.get("status") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if doc.get("unit_id") != "IMP-0467":
        return fail(f"unit_id {doc.get('unit_id')}")

    live = S.run_evidence()
    ans = S.answers(live)
    if not live["neither_walk_raised"]:
        return fail("walk raised")
    if ans["delta"] != 1:
        return fail(
            f"file-count delta {ans['delta']} "
            f"(without={ans['count_without_reserved_files']} "
            f"with={ans['count_with_reserved_files']})"
        )
    rec_delta = (doc.get("answer") or {}).get("delta")
    if rec_delta != 1:
        return fail(f"receipt delta {rec_delta}")
    if ans["relpath_for_NUL"] != "NUL":
        return fail(f"safe_relpath returned {ans['relpath_for_NUL']!r}")
    rec_rel = (doc.get("answer") or {}).get("relpath_for_NUL")
    if rec_rel != "NUL":
        return fail(f"receipt relpath {rec_rel!r}")
    if ans["relpath_is_device_mount"]:
        return fail("safe_relpath returned a device-mount form")
    if not ans["naive_windows_relpath_raises"]:
        return fail("naive Windows relpath replica did not raise on NUL")
    if "NUL" not in live["with_reserved"]["reserved_stems"]:
        return fail("library walk did not classify NUL as reserved")
    if os_name_posix_oracle_mismatch(live):
        return fail("library file count != os.walk oracle on POSIX")

    classifier = {r["component"]: r for r in live["reserved_classifier"]}
    for must in ("NUL", "CON", "AUX", "PRN"):
        if not classifier.get(must, {}).get("reserved"):
            return fail(f"classifier missed {must}")
    if classifier.get("readme.txt", {}).get("reserved"):
        return fail("classifier false-positive on readme.txt")
    if classifier.get("null", {}).get("reserved"):
        return fail("classifier false-positive on 'null'")

    out = {
        "probe": "probe1-reserved-enum",
        "unit_id": "IMP-0467",
        "count_without": ans["count_without_reserved_files"],
        "count_with": ans["count_with_reserved_files"],
        "delta": ans["delta"],
        "relpath_for_NUL": ans["relpath_for_NUL"],
        "naive_raised": ans["naive_windows_relpath_raises"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"without={out['count_without']} with={out['count_with']} "
        f"delta={out['delta']} relpath={out['relpath_for_NUL']}"
    )
    print("SUCCESS:IMP-0467-probe1 reserved-name enumeration and NUL relpath")
    return 0


def os_name_posix_oracle_mismatch(live: dict) -> bool:
    if live["host_os"] == "nt":
        return False
    w = live["without_reserved"]
    r = live["with_reserved"]
    return (
        w["file_count"] != w["oracle_os_walk_files"]
        or r["file_count"] != r["oracle_os_walk_files"]
        or live["delta"]["oracle_file_count"] != 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
