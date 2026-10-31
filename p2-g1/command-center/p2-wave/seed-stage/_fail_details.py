#!/usr/bin/env python3
"""Capture last 20 measure lines for each G-1 fail."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SUM = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull" / "g1-remeasure-summary.json"
OUT = Path(__file__).resolve().parent.parent / "ovh-monitor" / "error-pull" / "g1-fail-details.json"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]


def one(row: dict) -> dict:
    uid = row["id"]
    ip = row["ip"]
    cmd = (
        "cd /opt/p2/ast-integrate && "
        f"python3 command-center/p2-wave/_measure_one_delivered.py {uid}"
    )
    p = run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=90)
    text = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    last = text[-1] if text else f"rc={p.returncode}"
    return {
        "box": row["box"],
        "id": uid,
        "rc": p.returncode,
        "last": last[:300],
        "ok": last.startswith("SUCCESS:delivered"),
        "tail": text[-18:],
    }


def main() -> None:
    data = json.loads(SUM.read_text(encoding="utf-8"))
    rows = data.get("fails") or []
    out = []
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(one, r) for r in rows]
        for f in as_completed(futs):
            rec = f.result()
            out.append(rec)
            flag = "PASS" if rec["ok"] else "FAIL"
            print(f"{flag} {rec['box']:10s} {rec['id']:10s} {rec['last'][:120]}", flush=True)
    out.sort(key=lambda r: (r["box"], r["id"]))
    OUT.write_text(json.dumps({"n": len(out), "pass": sum(1 for r in out if r["ok"]), "rows": out}, indent=2) + "\n", encoding="utf-8")
    print("WROTE", OUT, "pass", sum(1 for r in out if r["ok"]), "fail", sum(1 for r in out if not r["ok"]))


if __name__ == "__main__":
    main()
