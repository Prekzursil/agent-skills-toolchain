#!/usr/bin/env python3
"""Run per-unit emit/write_receipts then refresh UNIT-ARTIFACT-MANIFEST sha."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}

EMIT = {
    "ADV-0038": "command-center/p2-wave/probes/ADV-0038/write_receipts.py",
    "ADV-0119": "command-center/p2-wave/probes/ADV-0119/write_receipts.py",
    "ARC-0101": "command-center/p2-wave/probes/ARC-0101/emit.py",
    "BLD-0001": "command-center/p2-wave/probes/BLD-0001/write_receipts.py",
    "BLD-0041": "command-center/p2-wave/probes/BLD-0041/write_receipts.py",
    "BLD-0037": "command-center/p2-wave/probes/BLD-0037/write_receipts.py",
    "CNF-0073": "command-center/p2-wave/probes/CNF-0073/emit_audit.py",
    "CNF-0161": "command-center/p2-wave/probes/CNF-0161/write_receipts.py",
    "CNL-0018": "command-center/p2-wave/probes/CNL-0018/write_receipts.py",
    "IMP-0030": "command-center/p2-wave/probes/IMP-0030/write_receipts.py",
    "IMP-0049": "command-center/p2-wave/probes/IMP-0049/emit_receipt.py",
    "IMP-0096": "command-center/p2-wave/probes/IMP-0096/write_receipts.py",
    "IMP-0126": "command-center/p2-wave/probes/IMP-0126/emit_receipt.py",
    "IMP-0211": "command-center/p2-wave/probes/IMP-0211/write_receipts.py",
    "IMP-0242": "command-center/p2-wave/probes/IMP-0242/write_receipts.py",
    "IMP-0289": "command-center/p2-wave/probes/IMP-0289/write_receipts.py",
    "IMP-0318": "command-center/p2-wave/probes/IMP-0318/write_receipts.py",
    "IMP-0341": "command-center/p2-wave/probes/IMP-0341/write_receipts.py",
    "IMP-0363": "command-center/p2-wave/probes/IMP-0363/emit_receipt.py",
    "IMP-0394": "command-center/p2-wave/probes/IMP-0394/emit_receipt.py",
    "IMP-0431": "command-center/p2-wave/probes/IMP-0431/emit_receipt.py",
    "IMP-0463": "command-center/p2-wave/probes/IMP-0463/write_receipts.py",
    "REL-0015": "command-center/p2-wave/probes/REL-0015/emit.py",
    "RES-0049": "command-center/p2-wave/probes/RES-0049/emit_research.py",
    "RES-0156": "command-center/p2-wave/probes/RES-0156/emit_spec.py",
    "SYN-0030": "command-center/p2-wave/probes/SYN-0030/emit.py",
    "TST-0063": "command-center/p2-wave/probes/TST-0063/emit_receipt.py",
    "TST-0109": "command-center/p2-wave/probes/TST-0109/write_receipts.py",
    "TST-0123": "command-center/p2-wave/probes/TST-0123/emit.py",
    "TST-0236": "command-center/p2-wave/probes/TST-0236/emit_receipt.py",
    "TST-0267": "command-center/p2-wave/probes/TST-0267/write_receipts.py",
    "TST-0298": "command-center/p2-wave/probes/TST-0298/write_receipts.py",
    "TST-0325": "command-center/p2-wave/probes/TST-0325/emit_receipt.py",
    "WFA-0035": "command-center/p2-wave/probes/WFA-0035/emit_report.py",
}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str) -> None:
    unit = BY[uid]
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    sha, size = digest(out)
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    found = False
    for a in rows:
        if isinstance(a, dict) and a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == out_rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
            found = True
    if not found:
        rows.append({"unit_id": uid, "path": out_rel, "sha256": sha, "bytes": size, "present": True})
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"refresh {uid} sha={sha[:16]} bytes={size}")


def main() -> None:
    ids = sys.argv[1:] or list(EMIT)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    for uid in ids:
        rel = EMIT.get(uid)
        if not rel:
            print("no-emit", uid)
            continue
        path = REPO / rel
        if not path.is_file():
            print("missing", rel)
            continue
        p = subprocess.run(
            [sys.executable, "-B", str(path)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        tail = ((p.stdout or "") + (p.stderr or "")).strip()[-800:]
        print(f"emit {uid} rc={p.returncode}")
        if tail:
            print(tail[-400:])
        if p.returncode == 0:
            try:
                refresh(uid)
            except Exception as exc:
                print("refresh-fail", uid, type(exc).__name__, exc)


if __name__ == "__main__":
    main()
