#!/usr/bin/env python3
"""Probe 1: current marketplace.json validates; six mutants fail distinctly.

Evidence signal (1): the CURRENT marketplace.json validates green under the
new schema without edits. Also enforces no second index file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.index_schema import (  # noqa: E402
    INDEX_REL,
    MUTATION_IDS,
    SCHEMA_REL,
    live_report,
    load_index,
    load_schema,
    mutation_verdicts,
    scan_second_indexes,
    validate_engine_a,
)

ART = REPO / "command-center/receipts/IMP-0067.json"
TEST = REPO / "tools/marketplace/tests/test_index_schema.py"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0067-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0067-probe1 unparseable:{exc}")
        return 1
    if doc.get("unit_id") != "IMP-0067" and doc.get("id") != "IMP-0067":
        print("FAILED:IMP-0067-probe1 unit_id", doc.get("unit_id") or doc.get("id"))
        return 1
    if "SUCCESS:IMP-0067" not in text:
        print("FAILED:IMP-0067-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0067-probe1 self-declared:{st}")
        return 1

    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        print(out[-2000:])
        print(f"FAILED:IMP-0067-probe1 tests rc={proc.returncode}")
        return 1

    index = load_index()
    schema = load_schema()
    current = validate_engine_a(index, schema)
    if not current.ok:
        print(json.dumps(current.as_dict(), indent=2)[:3000])
        print("FAILED:IMP-0067-probe1 current index rejected by engine A")
        return 1

    rows = mutation_verdicts(index, schema)
    codes = [rows[mid]["engine_a"]["primary_code"] for mid in MUTATION_IDS]
    if any(rows[mid]["engine_a"]["ok"] for mid in MUTATION_IDS):
        print("FAILED:IMP-0067-probe1 a mutant passed engine A")
        return 1
    if len(set(codes)) != 6 or set(codes) != set(MUTATION_IDS):
        print("FAILED:IMP-0067-probe1 mutant codes not distinct", codes)
        return 1

    seconds = scan_second_indexes()
    if seconds:
        print("FAILED:IMP-0067-probe1 second index files", seconds)
        return 1

    report = live_report()
    payload = {
        "probe": "probe1-current-and-mutations",
        "unit_id": "IMP-0067",
        "ok": True,
        "index": INDEX_REL,
        "schema": SCHEMA_REL,
        "engine": current.engine,
        "current_ok": current.ok,
        "mutation_codes": codes,
        "second_indexes": seconds,
        "tests_ok": True,
        "live_current_ok_a": report["current_ok_a"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"current_ok={current.ok} mutations={codes} second_indexes={seconds}")
    print("SUCCESS:IMP-0067-probe1 current index validates; six mutants fail distinctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
