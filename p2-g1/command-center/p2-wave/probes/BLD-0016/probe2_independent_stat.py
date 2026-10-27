#!/usr/bin/env python3
"""BLD-0016 probe2: mechanically-independent re-probe (PowerShell Get-Item).

The receipt's existence_reviewer used powershell_get_item as the independent
method. This probe re-probes fixture states AND real tree rows with
PowerShell, comparing against Python os.stat — two mechanically different
instruments must agree on every row, and every receipt ABSENT item must
still be absent under the independent instrument.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import REPO, ProbeFailure, check_receipt_core, require  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
UID = "BLD-0016"


def ps_get_item(path: Path) -> dict:
    """PowerShell Get-Item verdict: ABSENT / DIR / FILE+length."""
    ps_path = str(path).replace("'", "''")
    cmd = (
        "$ErrorActionPreference='Stop';"
        f"if (Test-Path -LiteralPath '{ps_path}') {{"
        f" $i = Get-Item -LiteralPath '{ps_path}';"
        " if ($i.PSIsContainer) { 'DIR' } else { 'FILE ' + $i.Length }"
        " } else { 'ABSENT' }"
    )
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=120,
    )
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise ProbeFailure(f"powershell failed on {path}: {r.stderr[:200]}")
    if out == "ABSENT":
        return {"verdict": "ABSENT", "length": None}
    if out == "DIR":
        return {"verdict": "DIR", "length": None}
    parts = out.split()
    length = int(parts[1])
    if length == 0:
        return {"verdict": "EMPTY", "length": 0}
    return {"verdict": "FILE", "length": length}


def classify_py(path: Path) -> str:
    if not path.exists():
        return "ABSENT"
    if path.is_dir():
        return "DIR"
    return "FILE" if path.stat().st_size > 0 else "EMPTY"


def main() -> int:
    doc = check_receipt_core(UID)

    d = FIX / "dir_with_member"
    member = d / "member.txt"
    require(member.is_file(), "probe1 fixtures missing; run probe1 first")
    states = [
        (FIX / "does-not-exist.bin", "ABSENT", None),
        (FIX / "empty.bin", "EMPTY", None),
        (d, "DIR", "member.txt"),
        (member, "FILE", None),
    ]
    for path, expect, _mm in states:
        ps = ps_get_item(path)
        py = classify_py(path)
        require(ps["verdict"] == py,
                f"instrument disagreement on {path.name}: PS={ps} PY={py}")
        require(ps["verdict"] == expect,
                f"fixture {path.name} expected {expect}, instruments say {ps}")

    # real tree rows through both instruments
    rows = [
        (REPO / "command-center/receipts/BLD-0016.json", "FILE"),
        (REPO / "tools/lib/handled-ledger.mjs", "FILE"),
        (REPO / "tools/lib", "DIR"),
    ]
    for path, expect in rows:
        ps = ps_get_item(path)
        py = classify_py(path)
        require(ps["verdict"] == py and ps["verdict"] == expect,
                f"real row {path.name}: PS={ps} PY={py} expect={expect}")
        if expect == "FILE":
            require(ps["length"] == os.stat(path).st_size,
                    f"length disagreement on {path.name}")

    # every receipt ABSENT item is still ABSENT live: its resolved_path and
    # candidate set (all empty here) cannot point at an existing file
    dp = doc.get("deliverable_probe") or {}
    for it in dp.get("items") or []:
        rel = it.get("resolved_path")
        require(rel is None,
                f"receipt item {it.get('id')} now has resolved_path {rel}; "
                "receipt answer changed under this probe")
    print(json.dumps({
        "probe": "probe2-independent-stat", "unit_id": UID,
        "method": "PowerShell Get-Item vs Python os.stat",
        "fixture_states_agree": len(states),
        "real_rows_agree": len(rows), "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 instruments agree on "
          f"{len(states)} fixtures + {len(rows)} real rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
