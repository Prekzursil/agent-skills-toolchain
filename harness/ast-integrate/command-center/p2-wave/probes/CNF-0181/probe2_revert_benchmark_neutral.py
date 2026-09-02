#!/usr/bin/env python3
"""Probe 2: revert, benchmark-removal, and neutral-change controls.

Mechanically different from probe 1: this probe writes trees to disk, restores
baseline bytes (revert), deletes the new case from the public suite, and applies
a comment-only patch. Scoring is done by a subprocess python -c oracle, not by
in-process exec of the measurement pack.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    BASELINE_SRC,
    CASE_ID,
    IMPROVED_SRC,
    NEUTRAL_SRC,
    NEW_CASE,
    ORIGINAL_CASES,
    PUBLIC_AFTER,
)

ART = Path(__file__).resolve().parents[3] / "receipts" / "CNF-0181.json"

ORACLE = r"""
import json, pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
ns = {}
exec(src, ns)
fn = ns["join_url"]
cases = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
rows = []
ok = 0
for c in cases:
    got = fn(c["base"], c["path"])
    passed = got == c["want"]
    ok += int(passed)
    rows.append({"id": c["id"], "got": got, "pass": passed})
print(json.dumps({"ok": ok, "n": len(cases), "rows": rows}))
"""


def _oracle(join_path: Path, cases_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", "-c", ORACLE, str(join_path), str(cases_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:])
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0181-p2-") as tmp:
        root = Path(tmp)
        join = root / "join.py"
        cases_path = root / "cases.json"

        # --- Revert control: restore baseline bytes; new case must fail. ---
        join.write_text(IMPROVED_SRC, encoding="utf-8")
        cases_path.write_text(json.dumps([NEW_CASE]), encoding="utf-8")
        kept = _oracle(join, cases_path)
        join.write_text(BASELINE_SRC, encoding="utf-8")
        reverted = _oracle(join, cases_path)
        revert_reproduces = kept["ok"] == 1 and reverted["ok"] == 0
        revert_got = reverted["rows"][0]["got"]

        # --- Benchmark control: drop the new case; baseline public suite all-pass. ---
        public_wo = [c for c in PUBLIC_AFTER if c["id"] != CASE_ID]
        if public_wo != ORIGINAL_CASES:
            print("FAILED:CNF-0181-probe2 public-without-new-case != original suite")
            return 1
        join.write_text(BASELINE_SRC, encoding="utf-8")
        cases_path.write_text(json.dumps(public_wo), encoding="utf-8")
        invisible = _oracle(join, cases_path)
        # Same baseline against the new case still fails (failure exists, just hidden).
        cases_path.write_text(json.dumps([NEW_CASE]), encoding="utf-8")
        still_fails = _oracle(join, cases_path)
        bench_hidden = invisible["ok"] == invisible["n"] and still_fails["ok"] == 0

        # --- Neutral-change control: comment-only patch must be rejected. ---
        # Independent of loop.decide: equal oracle scores => reject.
        join.write_text(IMPROVED_SRC, encoding="utf-8")
        cases_path.write_text(json.dumps(PUBLIC_AFTER), encoding="utf-8")
        before_n = _oracle(join, cases_path)
        join.write_text(NEUTRAL_SRC, encoding="utf-8")
        after_n = _oracle(join, cases_path)
        scores_equal = before_n["ok"] == after_n["ok"] and before_n["n"] == after_n["n"]
        # Retention rule re-derived here: KEEP requires after_ok > before_ok.
        neutral_rejected = scores_equal and not (after_n["ok"] > before_n["ok"])

    payload = {
        "probe": "probe2-revert-benchmark-neutral",
        "unit_id": "CNF-0181",
        "case_id": CASE_ID,
        "revert_reproduces_original_failure": revert_reproduces,
        "revert_got": revert_got,
        "benchmark_removal_hides_failure": bench_hidden,
        "public_without_new_case_ok": invisible["ok"],
        "public_without_new_case_n": invisible["n"],
        "neutral_scores_equal": scores_equal,
        "neutral_rejected": neutral_rejected,
        "pass": bool(revert_reproduces and bench_hidden and neutral_rejected),
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNF-0181" not in text:
            print("FAILED:CNF-0181-probe2 receipt missing sentinel")
            return 1
        if CASE_ID not in text:
            print("FAILED:CNF-0181-probe2 receipt missing case id")
            return 1

    if not payload["pass"]:
        print("FAILED:CNF-0181-probe2 a required control did not fire")
        return 1
    print(
        f"revert_fail={revert_reproduces} hidden={bench_hidden} "
        f"neutral_rejected={neutral_rejected}"
    )
    print("SUCCESS:CNF-0181-probe2 revert, benchmark-removal, neutral-reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
