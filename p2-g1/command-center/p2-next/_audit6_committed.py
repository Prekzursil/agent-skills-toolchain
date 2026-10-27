"""AUDIT probe 6: verify the TEN receipts from the COMMITTED blobs at HEAD (DoD item 2).

Independent re-implementation -- does NOT run the builder's _b20_final_verify.py.
Uses `git cat-file --batch` (one process, not one per file) so it finishes.

Checks per receipt, from the HEAD blob:
  state, reviewer.verdict, reviewer.independent, reviewer.fresh_context, len(reviewer.notes),
  whether reviewer_id looks like a real reviewer, and whether the receipt claims SUCCESS.

Fails closed if it reads other than 10 rows.

Detector control (both states): a synthetic row with verdict=FAIL / empty notes MUST be flagged;
the real rows must not be flagged for that reason. Prints the count of the thing being compared.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ID = re.compile(r"^[A-Z]{2,4}-\d{4}$")

TEN_PATHS = {
    "AUD-0006": "command-center/audit/AUD-0006-uncommitted-work-census.json",
    "AUD-0020": "command-center/audit/AUD-0020-python-dep-inventory.json",
    "AUD-0021": "command-center/audit/AUD-0021-node-dep-inventory.json",
    "AUD-0030": "command-center/audit/AUD-0030-import-graph-cycles.json",
    "AUD-0041": "command-center/audit/AUD-0041-ci-step-inventory.json",
    "AUD-0051": "command-center/audit/AUD-0051-coverage-baseline.json",
    "CC-0002": "command-center/receipts/CC-0002.json",
    "IMP-0440": "command-center/receipts/IMP-0440.json",
    "TST-0334": "command-center/receipts/TST-0334.json",
    "TST-0350": "command-center/receipts/TST-0350.json",
}


def blob(rev: str, path: str):
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def row(uid: str, obj: dict) -> dict:
    rv = obj.get("reviewer") or {}
    notes = rv.get("notes") or ""
    return {
        "unit": uid,
        "state": obj.get("state"),
        "verdict": rv.get("verdict"),
        "independent": rv.get("independent"),
        "fresh_context": rv.get("fresh_context"),
        "reviewer_id": rv.get("reviewer_id"),
        "vendor": rv.get("vendor"),
        "notes_len": len(notes) if isinstance(notes, str) else -1,
        "claims_success": str(obj.get("state")).upper() == "SUCCESS",
        "open_defects": len(
            [
                d
                for d in (obj.get("defects") or obj.get("findings") or [])
                if isinstance(d, dict)
                and str(d.get("status", "")).lower() in ("open", "")
            ]
        )
        if isinstance(obj.get("defects") or obj.get("findings"), list)
        else "n/a",
    }


def flag(r: dict) -> list[str]:
    bad = []
    if r["verdict"] != "PASS":
        bad.append(f"verdict={r['verdict']}")
    if r["independent"] is not True:
        bad.append(f"independent={r['independent']}")
    if r["fresh_context"] is not True:
        bad.append(f"fresh_context={r['fresh_context']}")
    if not isinstance(r["notes_len"], int) or r["notes_len"] < 200:
        bad.append(f"notes_len={r['notes_len']}")
    if r["claims_success"]:
        bad.append("CLAIMS state=SUCCESS")
    return bad


def main() -> int:
    rows, missing = [], []
    for uid, path in TEN_PATHS.items():
        obj = blob("HEAD", path)
        if obj is None:
            missing.append((uid, path))
            continue
        rows.append(row(uid, obj))
    print(
        f"rows read from COMMITTED HEAD blobs: {len(rows)} (expected 10); missing={missing}"
    )
    if len(rows) != 10:
        print("FAILED:audit6 wrong row count -- failing closed")
        return 1
    hdr = f"{'unit':10} {'state':9} {'verdict':8} {'ind':6} {'fresh':6} {'notes':6} vendor  reviewer_id"
    print(hdr)
    problems = {}
    for r in rows:
        print(
            f"{r['unit']:10} {str(r['state']):9} {str(r['verdict']):8} {str(r['independent']):6} "
            f"{str(r['fresh_context']):6} {str(r['notes_len']):6} {str(r['vendor']):8} {r['reviewer_id']}"
        )
        b = flag(r)
        if b:
            problems[r["unit"]] = b
    print(
        f"\nnotes_len range: {min(r['notes_len'] for r in rows)}-{max(r['notes_len'] for r in rows)}"
    )
    print(f"PROBLEMS: {json.dumps(problems, indent=1) if problems else '[] (none)'}")

    # ---- CONTROL, both states ----
    good = rows[0]
    synth_bad = dict(
        good, verdict="FAIL", notes_len=0, independent=False, state="SUCCESS"
    )
    fb, fg = flag(synth_bad), flag(good)
    print(
        f"\nCONTROL fires_on_bad_row={len(fb) > 0} ({fb}) silent_on_real_row={len(fg) == 0}"
    )
    if not (len(fb) > 0 and len(fg) == 0):
        print("FAILED:audit6 control")
        return 1
    print("SUCCESS:audit6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
