#!/usr/bin/env python3
"""Probe 2: mechanically different shell + data field (preset quorum, monotonic)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COST = REPO / "command-center/phase3/A2/COST.json"
INNER = "ARC0011_INNER"


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0011-probe2 {msg}")
    return 1


def inner() -> int:
    sys.path.insert(0, str(HERE))
    import measure as M
    from scale import TARGET, analogue_skill_count, expected_file_count

    result = M.campaign(mutate="preset_quorum", timer_name="monotonic")
    n_skill = analogue_skill_count()
    expect = expected_file_count(
        TARGET["workflows"], TARGET["protocols"], TARGET["presets"], n_skill
    )
    target = next(s for s in result["sizes"] if s["label"] == "target")
    print(
        f"shell=bash inner=1 field=preset_quorum timer=monotonic "
        f"target_files={target['full_file_writes']} derived={expect} "
        f"incr_files={target['incremental_file_writes']} "
        f"median_s={target['full_pipeline']['median_s']:.6f}"
    )
    if target["full_file_writes"] != expect:
        return _fail(f"re-derived file count {expect} != measured {target['full_file_writes']}")
    if target["incremental_file_writes"] != 2:
        return _fail("incremental writes != 2")
    if not result["claim_valid"]:
        return _fail(f"spread {result['max_spread']:.3f} exceeds 0.30")
    if not COST.is_file():
        print("SUCCESS:ARC-0011-probe2 alt-shell alt-field (COST.json not yet written)")
        return 0
    doc = json.loads(COST.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"COST.json state={doc.get('state')}")
    probe1 = (doc.get("measurements") or {}).get("probe1") or {}
    ok, why = M.agree(probe1, result) if probe1.get("sizes") else (False, "probe1 missing")
    if not ok:
        return _fail(f"disagree with probe1: {why}")
    baked2 = (doc.get("measurements") or {}).get("probe2") or {}
    baked_files = [s["full_file_writes"] for s in (baked2.get("sizes") or [])]
    live_files = [s["full_file_writes"] for s in result["sizes"]]
    if baked_files and baked_files != live_files:
        return _fail(f"COST probe2 file-write drift {baked_files} vs {live_files}")
    if "SUCCESS:ARC-0011" not in COST.read_text(encoding="utf-8"):
        return _fail("sentinel absent")
    print("SUCCESS:ARC-0011-probe2 alt-shell alt-field re-derived file-write count")
    return 0


def main() -> int:
    if os.environ.get(INNER) == "1":
        return inner()
    env = os.environ.copy()
    env[INNER] = "1"
    quoted = str(HERE / "probe2_alt_shell.py")
    cmd = f'PYTHONDONTWRITEBYTECODE=1 python3 -B "{quoted}"'
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    if proc.returncode != 0 and "SUCCESS:ARC-0011-probe2" not in (proc.stdout or ""):
        print(f"FAILED:ARC-0011-probe2 bash-wrapper rc={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
