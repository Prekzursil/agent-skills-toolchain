#!/usr/bin/env python3
"""Probe 1: every union script has a live result for all three interpreters."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runner as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0105-shell-interpreter-conformance.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0105 emitted only when"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        print("FAILED:CNF-0105-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0105":
        print("FAILED:CNF-0105-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0105-probe1 self-declared", doc.get("state"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL_PREFIX not in text:
        print("FAILED:CNF-0105-probe1 sentinel absent")
        return 1

    b = R.live_bundle()
    if not b["union_complete"]:
        print("FAILED:CNF-0105-probe1 union incomplete")
        return 1
    ids = set(R.INTERP_IDS)
    by: dict[str, set[str]] = {}
    for row in b["matrix"]:
        by.setdefault(row["script"], set()).add(row["interpreter"])
    for u in b["union"]:
        if by.get(u["path"], set()) != ids:
            print("FAILED:CNF-0105-probe1 missing cells", u["path"], sorted(by.get(u["path"], [])))
            return 1
    live_scripts = {r["script"] for r in b["matrix"]}
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    art_rows = list(doc.get("matrix") or []) or list(report.get("matrix") or [])
    art_scripts = {r["script"] for r in art_rows if isinstance(r, dict) and "script" in r}
    if not live_scripts:
        print("FAILED:CNF-0105-probe1 empty live matrix")
        return 1
    if not live_scripts <= art_scripts:
        print("FAILED:CNF-0105-probe1 artifact matrix missing live scripts")
        print(sorted(live_scripts - art_scripts)[:10])
        return 1
    if not R.protocol_ok(b):
        print("FAILED:CNF-0105-probe1 protocol_ok false")
        return 1
    print(json.dumps({
        "union_n": len(b["union"]),
        "matrix_n": len(b["matrix"]),
        "union_complete": True,
        "interpreters": [i["id"] for i in b["interpreters"]],
    }, sort_keys=True))
    print("SUCCESS:CNF-0105-probe1 union matrix complete for three interpreters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
