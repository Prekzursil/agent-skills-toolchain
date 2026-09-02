#!/usr/bin/env python3
"""Probe 1: live parser flags vs documented flags, both directions empty.

Re-imports each operator CLI, walks the live ArgumentParser option strings,
re-extracts backtick flag tokens from command-center/CLI-FLAGS.md, and diffs
the two sets per CLI. When the catalog receipt exists, checks it still matches
this live pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import parity as P  # noqa: E402

UNIT = "TST-0251"
ART = REPO / "command-center/receipts/TST-0251.json"
SENTINEL = "SUCCESS:TST-0251"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_receipt(report: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt-unparseable:{exc}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    live_rows = {r["path"]: r for r in report["clis"]}
    art_rows = {r["path"]: r for r in (doc.get("measurement") or {}).get("clis") or []}
    if not art_rows:
        # some receipts nest under answer / flag_parity
        art_rows = {
            r["path"]: r
            for r in (doc.get("flag_parity") or {}).get("clis") or []
            if isinstance(r, dict) and r.get("path")
        }
    if not art_rows:
        return "receipt-missing-per-cli-measurement"
    for path, live in live_rows.items():
        rec = art_rows.get(path)
        if rec is None:
            return f"receipt-missing-cli:{path}"
        if sorted(rec.get("parser") or []) != live["parser"]:
            return f"parser-drift:{path}"
        if sorted(rec.get("docs") or []) != live["docs"]:
            return f"docs-drift:{path}"
        if rec.get("empty_both_directions") is not True:
            return f"receipt-cli-not-empty:{path}"
    if doc.get("flag_parity", {}).get("bidirectional_empty") is not True and report["bidirectional_empty"]:
        # tolerate either nesting
        if not (doc.get("measurement") or {}).get("bidirectional_empty"):
            if "bidirectional_empty" in doc and doc.get("bidirectional_empty") is not True:
                return "receipt-bidirectional-not-empty"
    return None


def main() -> int:
    report = P.live_report(REPO)
    print(json.dumps({
        "probe": "probe1-live-parity",
        "unit_id": UNIT,
        "cli_count": report["cli_count"],
        "bidirectional_empty": report["bidirectional_empty"],
        "docs_present": report["docs_present"],
        "catalog_docs": report["catalog_docs"],
        "mismatches": [
            {
                "path": r["path"],
                "parser_not_docs": r["parser_not_docs"],
                "docs_not_parser": r["docs_not_parser"],
            }
            for r in report["clis"]
            if not r["empty_both_directions"]
        ],
    }, sort_keys=True))
    if not report["docs_present"]:
        return fail("CLI-FLAGS.md missing")
    if report["cli_count"] < 2:
        return fail(f"too-few-clis:{report['cli_count']}")
    if not report["bidirectional_empty"]:
        return fail("live-sets-not-empty")
    for row in report["catalog_docs"]:
        if row["present"]:
            continue
        # absence is recorded, not a fail: those files are not the inventory
    err = check_receipt(report)
    if err:
        return fail(err)
    print("SUCCESS:TST-0251-probe1 live parser and docs flag sets match both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
