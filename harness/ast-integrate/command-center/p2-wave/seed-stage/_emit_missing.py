#!/usr/bin/env python3
"""Re-emit catalog output_path artifacts from harvested probe emit scripts.

Harvest packed probes/ only; primaries lived at receipts/research/adversarial
on OVH and were not in the tarball. This rebuilds them from emit.py /
emit_receipt.py. Run under WSL.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PROBES = REPO / "command-center" / "p2-wave" / "probes"
LOG = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "emit-missing.jsonl"
SUM = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "emit-missing.json"
SCRIPTS = ("emit_receipt.py", "emit.py", "write_receipts.py")


def picker(probe: Path) -> Path | None:
    for name in SCRIPTS:
        p = probe / name
        if p.is_file():
            return p
    return None


def main() -> int:
    ids = []
    for u in CATALOG.get("work_units") or []:
        uid = u["id"]
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if (REPO / rel).is_file():
            continue
        script = picker(PROBES / uid)
        if script is None:
            continue
        ids.append((uid, rel, script))
    done = set()
    if LOG.is_file():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line).get("id"))
            except Exception:
                continue
    ids = [row for row in ids if row[0] not in done]
    print(f"to_emit={len(ids)} already={len(done)}", flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.is_file():
        LOG.write_text("", encoding="utf-8")
    ok = fail = skip = 0
    fails = []
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO), str(REPO / "tools"), str(REPO / "tools" / "command-center")]
    )
    for i, (uid, rel, script) in enumerate(ids, 1):
        if (REPO / rel).is_file():
            skip += 1
            continue
        try:
            p = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=25,
                env=env,
            )
            last = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
            line = last[-1] if last else f"exit={p.returncode}"
        except subprocess.TimeoutExpired:
            p = None
            line = "TIMEOUT"
        present = (REPO / rel).is_file()
        rec = {"id": uid, "ok": present, "line": line[:240]}
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        if present:
            ok += 1
            mark = "OK"
        else:
            fail += 1
            if len(fails) < 40:
                fails.append(uid)
            mark = "NO"
        print(f"{i}/{len(ids)} {mark} {uid} {line[:100]}", flush=True)
    SUM.write_text(
        json.dumps({"n": len(ids), "ok": ok, "fail": fail, "skip": skip, "fail_sample": fails}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"EMIT ok={ok} fail={fail} skip={skip} n={len(ids)}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
