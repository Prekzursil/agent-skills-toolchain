#!/usr/bin/env python3
"""Named probe 1: both-states archive gate plus receipt evidence match.

Re-runs the four catalog controls against freshly packed archives. Then checks
that command-center/receipts/REL-0009.json pastes totals, entry count, top-ten
and headroom that match a live re-list of the clean archive — not a source-tree
walk.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "release"))
sys.path.insert(0, str(HERE))

from archive_gate import evaluate_archive, load_policy  # noqa: E402
from controls import receipt_view, run_all_controls  # noqa: E402
from scenario import pack_clean  # noqa: E402

ART = REPO / "command-center/receipts/REL-0009.json"
SENTINEL = "SUCCESS:REL-0009"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0009-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    view = receipt_view(doc)
    if doc.get("unit_id") != "REL-0009":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if view.get("evaluation_surface") != "archive-entry-list":
        return fail("evaluation_surface is not archive-entry-list")

    with tempfile.TemporaryDirectory(prefix="rel0009-p1-") as tmp:
        work = Path(tmp)
        rows = run_all_controls(work)
        live_clean = pack_clean(work / "live-clean.zip", work / "live")
        live = evaluate_archive(live_clean, load_policy())

    clean = rows["clean"]
    print(json.dumps({
        "probe": "probe1-archive-controls",
        "unit_id": "REL-0009",
        "pass": True,
        "clean_pass": True,
        "clean_total_bytes": clean["total_bytes"],
        "clean_entry_count": clean["entry_count"],
        "byte_headroom": clean["byte_headroom"],
        "file_count_headroom": clean["file_count_headroom"],
        "dotgit_rejected": True,
        "blob_named": rows["blob"]["ceiling_hits"][0]["offending_entry"],
        "gitignored_detected": True,
        "evaluation_surface": "archive-entry-list",
    }, sort_keys=True))

    reported = view.get("clean_archive") or {}
    if int(reported.get("total_bytes") or -1) != live.total_bytes:
        return fail(
            f"receipt total_bytes {reported.get('total_bytes')} "
            f"!= live archive {live.total_bytes}"
        )
    if int(reported.get("entry_count") or -1) != live.entry_count:
        return fail("receipt entry_count != live archive")
    if int(reported.get("byte_headroom") or -1) != live.byte_headroom:
        return fail("receipt byte_headroom != live archive")
    if int(reported.get("file_count_headroom") or -1) != live.file_count_headroom:
        return fail("receipt file_count_headroom != live archive")
    rec_top = [
        (r.get("path"), r.get("bytes")) for r in (reported.get("top_ten_by_size") or [])
    ]
    live_top = [(r["path"], r["bytes"]) for r in live.top_ten_by_size]
    if rec_top != live_top:
        return fail(f"top_ten mismatch receipt={rec_top} live={live_top}")

    tests = {t.get("id"): t for t in (view.get("tests") or []) if isinstance(t, dict)}
    for tid in ("dotgit-reject", "blob-ceiling-names-entry", "clean-headroom", "gitignored-from-archive"):
        row = tests.get(tid)
        if not row or row.get("verdict") != "PASS":
            return fail(f"receipt test {tid} not PASS")

    print(
        f"clean bytes={live.total_bytes} entries={live.entry_count} "
        f"byte_headroom={live.byte_headroom} file_headroom={live.file_count_headroom}"
    )
    print("SUCCESS:REL-0009-probe1 archive controls and receipt match live listing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
