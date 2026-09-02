#!/usr/bin/env python3
"""Measure-only G-1 for shard-17 IDs (no emit)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[2])
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"
IDS = [
    "ADV-0018", "ADV-0047", "ADV-0076", "ADV-0100", "ADV-0123",
    "ARC-0016", "ARC-0065", "ARC-0108",
    "AUD-0033", "AUD-0067",
    "BLD-0008", "BLD-0039",
    "CC-0014",
    "CNF-0031", "CNF-0081", "CNF-0127", "CNF-0167",
    "CNL-0036", "CNL-0095",
    "IMP-0005", "IMP-0031", "IMP-0053", "IMP-0078", "IMP-0104", "IMP-0124",
    "IMP-0150", "IMP-0189", "IMP-0217", "IMP-0245", "IMP-0270", "IMP-0296",
    "IMP-0322", "IMP-0344", "IMP-0367", "IMP-0402", "IMP-0428", "IMP-0464",
    "RES-0004", "RES-0058", "RES-0125", "RES-0161", "RES-0191",
    "SYN-0036",
    "TST-0011", "TST-0071", "TST-0114", "TST-0145", "TST-0173", "TST-0210",
    "TST-0241", "TST-0274", "TST-0301", "TST-0333",
    "WFA-0045", "WFA-0094", "WFA-0139",
]
LOG = Path(os.environ.get("SHARD17_MEASURE_LOG") or str(Path.home() / "p2-g1-shard17-final.jsonl"))


def main() -> int:
    only = sys.argv[1:] or IDS
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with LOG.open("w", encoding="utf-8") as fh:
        ok = fail = 0
        for uid in only:
            p = subprocess.run(
                [sys.executable, "-B", str(MEASURE), uid],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=200,
                env=env,
            )
            text = ((p.stdout or "") + (p.stderr or "")).strip()
            last = [ln for ln in text.splitlines() if ln.strip()][-1] if text else ""
            success = f"SUCCESS:delivered {uid}" in text.splitlines() or last.startswith("SUCCESS:delivered")
            rec = {"id": uid, "rc": p.returncode, "ok": success, "last": last, "tail": text[-1500:]}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if success:
                ok += 1
                print("OK", uid)
            else:
                fail += 1
                print("FAIL", uid, last[:160])
        print(f"attempted={len(only)} ok={ok} fail={fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
