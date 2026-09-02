#!/usr/bin/env python3
"""Named probe 1: re-run every generated script by path; exit codes must match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mechanise as M  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0023-mechanised-repros.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0023-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0023":
        print("FAILED:CNF-0023-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0023" not in text:
        print("FAILED:CNF-0023-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0023-probe1 self-declared", doc.get("state"))
        return 1
    scripts = M.artifact_field(doc, "generated_scripts") or []
    if len(scripts) < 1:
        print("FAILED:CNF-0023-probe1 no generated_scripts")
        return 1

    M.write_generated_scripts()
    live = []
    for row in scripts:
        rel = row["script_path"]
        script = REPO / rel
        if not script.is_file():
            print("FAILED:CNF-0023-probe1 missing", rel)
            return 1
        if "-c" in (row.get("argv_unfixed") or []) or "-c" in (row.get("argv_fixed") or []):
            print("FAILED:CNF-0023-probe1 inlined argv", rel)
            return 1
        if row.get("invoked_by_path") is not True:
            print("FAILED:CNF-0023-probe1 invoked_by_path not true", rel)
            return 1
        red = M.invoke_by_path(script, M.UNFIXED)
        green = M.invoke_by_path(script, M.FIXED)
        if red.returncode != int(row["unfixed_exit_code"]):
            print(
                f"FAILED:CNF-0023-probe1 {rel} unfixed live={red.returncode} "
                f"recorded={row['unfixed_exit_code']}"
            )
            return 1
        if green.returncode != int(row["fixed_exit_code"]):
            print(
                f"FAILED:CNF-0023-probe1 {rel} fixed live={green.returncode} "
                f"recorded={row['fixed_exit_code']}"
            )
            return 1
        if red.returncode == 0 or green.returncode != 0:
            print(f"FAILED:CNF-0023-probe1 {rel} does not discriminate states")
            return 1
        live.append(
            {
                "script_path": rel,
                "unfixed": red.returncode,
                "fixed": green.returncode,
            }
        )

    payload = json.dumps(
        {
            "pass": True,
            "probe": "probe1-live-exit-codes",
            "unit_id": "CNF-0023",
            "scripts": live,
            "count": len(live),
        },
        sort_keys=True,
    )
    print(payload)
    print(f"scripts={len(live)} live exit codes match artifact; all invoked by path")
    print("SUCCESS:CNF-0023-probe1 live exit codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
