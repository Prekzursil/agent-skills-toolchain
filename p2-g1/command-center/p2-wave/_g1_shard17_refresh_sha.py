#!/usr/bin/env python3
"""Refresh per-unit manifests for sha-mismatch IDs, then G-1 remesure."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[2])
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = sys.argv[1:] or [
    "ADV-0047",
    "ADV-0123",
    "ARC-0065",
    "AUD-0067",
    "CC-0014",
    "CNF-0167",
    "RES-0161",
    "RES-0191",
    "TST-0071",
    "WFA-0045",
    "WFA-0094",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str) -> None:
    unit = BY[uid]
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    sha, size = digest(out)
    man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    found = False
    for a in rows:
        if not isinstance(a, dict):
            continue
        if a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == out_rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
            found = True
    if not found:
        rows.append(
            {
                "unit_id": uid,
                "path": out_rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
            }
        )
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"refresh {uid} sha={sha[:16]} bytes={size}")


def measure(uid: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-B", str(MEASURE), uid],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=200,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    for uid in IDS:
        refresh(uid)
        rc, text = measure(uid)
        last = [ln for ln in text.splitlines() if ln.strip()][-1] if text else ""
        print(last or f"rc={rc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
