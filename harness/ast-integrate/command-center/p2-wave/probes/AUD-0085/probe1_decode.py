"""Named probe 1: strict UTF-8 decode + BOM census vs the live artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_census  # noqa: E402
from common import COMPLETION_SENTINEL, FX_BOM, FX_INVALID, OUT, UNIT  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = OUT.read_text(encoding="utf-8")
    if "SUCCESS:AUD-0085" not in text:
        return fail("short sentinel absent")
    if COMPLETION_SENTINEL not in text:
        return fail("completion_sentinel absent")

    live = run_census()
    s = live["summary"]
    art = doc.get("census") or {}
    checks = [
        ("files_scanned", s["files_scanned"]),
        ("invalid_utf8_text_count", s["invalid_utf8_text_count"]),
        ("invalid_utf8_text_paths", s["invalid_utf8_text_paths"]),
        ("bom_count", s["bom_count"]),
        ("bom_paths", s["bom_paths"]),
    ]
    for key, live_val in checks:
        if art.get(key) != live_val:
            return fail(f"artifact/live mismatch {key}", {"art": art.get(key), "live": live_val})
    if not s["planted_invalid_seen"] or FX_INVALID not in s["invalid_utf8_text_paths"]:
        return fail("planted invalid UTF-8 not seen", s["invalid_utf8_text_paths"])
    if not s["planted_bom_seen"] or FX_BOM not in s["bom_paths"]:
        return fail("planted BOM not seen", s["bom_paths"])
    rec = (doc.get("named_probe_records") or {}).get("probe1") or {}
    if rec.get("files_scanned") != s["files_scanned"]:
        return fail("named_probe_records.probe1 files_scanned mismatch", rec)

    out = {
        "probe": "probe1-decode",
        "unit_id": UNIT,
        "pass": True,
        "files_scanned": s["files_scanned"],
        "invalid_utf8_all_count": s["invalid_utf8_all_count"],
        "invalid_utf8_text_count": s["invalid_utf8_text_count"],
        "invalid_utf8_text_paths": s["invalid_utf8_text_paths"],
        "bom_count": s["bom_count"],
        "bom_paths": s["bom_paths"],
        "planted_invalid_seen": True,
        "planted_bom_seen": True,
        "artifact_matches_live": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0085-probe1 decode census and planted BOM/invalid UTF-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
