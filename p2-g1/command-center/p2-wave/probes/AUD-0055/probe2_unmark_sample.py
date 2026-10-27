#!/usr/bin/env python3
"""AUD-0055 probe 2 - unmark-and-run over the four catalog control fixtures.

The only way to know whether a stated skip/xfail reason still holds is to
remove the marker and run the test. shard4-w2 reconstruction 2026-10-25:
recreates the catalog control cases from the delivered artifact (the original
probe ran on the prior worktree), strips each marker in a scratch copy, runs
pytest, and asserts the both-states classification:
  masquerade-temporary-skip  unmarked PASSES  (the skip hides a passing test)
  stale-xfail-bug-fixed      unmarked PASSES  (reason no longer holds)
  live-xfail-bug-present     unmarked FAILS   (reason still holds)
  skipif-true-unconditional  unmarked PASSES  (skip is unconditional)
Marked runs must stay silent (skipped / xfailed) - the census still sees them.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0055-skip-xfail-reason-audit.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
UNIT = "AUD-0055"

CASES = {
    "masquerade-temporary-skip": ("test_masquerade_skip.py", "PASS"),
    "stale-xfail-bug-fixed": ("test_stale_xfail_fixed.py", "PASS"),
    "live-xfail-bug-present": ("test_live_xfail_present.py", "FAIL"),
    "skipif-true-unconditional": ("test_skipif_unconditional.py", "PASS"),
}
MARKER_RE = re.compile(r"^\s*@pytest\.mark\.(skip|skipif|xfail)\(.*\)\s*$", re.MULTILINE)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def run_pytest(path: Path) -> tuple[int, str]:
    import os

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-I", "-m", "pytest", "-p", "no:cacheprovider",
         "-q", "--no-header", "-x", "--rootdir", str(path.parent), str(path)],
        capture_output=True, text=True, timeout=240,
        env=env, cwd=str(path.parent),
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    hl = doc.get("headline") or {}
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    results: dict[str, str] = {}
    stale_confirmed = 0
    still_justified = 0
    with tempfile.TemporaryDirectory() as td:
        for control_id, (fname, want) in CASES.items():
            src = FIXTURES / fname
            if not src.is_file():
                return fail(f"control fixture missing: {fname}")
            # marked run must stay silent: skipped or xfailed, never red
            rc_marked, tail_marked = run_pytest(src)
            if rc_marked != 0:
                return fail(f"{control_id}: MARKED run exited {rc_marked}: {tail_marked[-300:]}")
            # unmarked run in a scratch copy
            text = src.read_text(encoding="utf-8")
            stripped = MARKER_RE.sub("", text)
            if stripped == text:
                return fail(f"{control_id}: marker strip removed nothing")
            scratch = Path(td) / fname
            scratch.write_text(stripped, encoding="utf-8")
            rc, tail = run_pytest(scratch)
            outcome = "PASS" if rc == 0 else "FAIL" if rc == 1 else f"rc={rc}"
            results[control_id] = outcome
            if outcome != want:
                return fail(f"{control_id}: unmarked outcome={outcome} want={want} tail={tail[-300:]}")
            if control_id == "stale-xfail-bug-fixed" and outcome == "PASS":
                stale_confirmed += 1
            if control_id == "live-xfail-bug-present" and outcome == "FAIL":
                still_justified += 1
            print(f"  {control_id}: marked=silent unmarked={outcome}")

    want_stale = int(hl.get("stale_xfail_confirmed_by_unmark") or 0)
    want_still = int(hl.get("still_justified_confirmed_by_unmark") or 0)
    if stale_confirmed != want_stale:
        return fail(f"stale_xfail_confirmed_by_unmark: artifact={want_stale} live={stale_confirmed}")
    if still_justified != want_still:
        return fail(f"still_justified_confirmed_by_unmark: artifact={want_still} live={still_justified}")
    want_sample = int(hl.get("sample_executed") or 0)
    if want_sample and want_sample != len(CASES):
        return fail(f"headline sample_executed={want_sample} but control corpus has {len(CASES)} cases")
    print(
        f"unmark-and-run: {len(CASES)} cases classified, "
        f"stale_confirmed={stale_confirmed} still_justified={still_justified}"
    )
    print(f"SUCCESS:{UNIT}-probe2 unmark-and-run both-states control corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
