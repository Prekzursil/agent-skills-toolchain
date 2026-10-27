#!/usr/bin/env python3
"""Heartbeat loop: sum completed/live across leftover fleet. No teardown."""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

KEY = Path.home() / ".ssh" / "id_ed25519"
OUT = Path(__file__).resolve().parent.parent / "ovh-monitor" / "fleet-progress.jsonl"
FLEET = json.loads((Path(__file__).resolve().parent.parent / "ovh-monitor" / "fleet-now.json").read_text())["items"]
REMOTE = r"""
sudo python3 - << 'PY'
import json
from pathlib import Path
h=Path("/opt/p2/supervisor-heartbeat.json")
c=Path("/opt/p2/completed.json")
d=json.loads(h.read_text()) if h.is_file() else {}
n=len((json.loads(c.read_text()) or {}).get("ids") or []) if c.is_file() else 0
print(json.dumps({
  "live": d.get("live_grok") or 0,
  "flight": d.get("in_flight_n") or 0,
  "queued": d.get("queued_n") or 0,
  "ok": d.get("ok") or n,
  "parked": d.get("parked") or 0,
  "launched": d.get("launched") or 0,
  "active": True,
}))
PY
sudo systemctl is-active p2-supervisor 2>/dev/null || true
"""


def one(item):
    ip = item["ip"]
    name = item["name"]
    p = subprocess.run(
        ["ssh", "-i", str(KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new", f"ubuntu@{ip}", REMOTE],
        capture_output=True,
        text=True,
        timeout=25,
    )
    js = {}
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                js = json.loads(line)
            except json.JSONDecodeError:
                pass
    js["name"] = name
    js["ip"] = ip
    js["svc"] = "active" in (p.stdout or "")
    return js


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 70 * 60
    while time.time() < deadline:
        rows = []
        with ThreadPoolExecutor(max_workers=18) as pool:
            futs = [pool.submit(one, it) for it in FLEET]
            for f in as_completed(futs):
                try:
                    rows.append(f.result())
                except Exception as exc:
                    rows.append({"name": "?", "error": str(exc)})
        rec = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "boxes": len(rows),
            "live": sum(int(r.get("live") or 0) for r in rows),
            "flight": sum(int(r.get("flight") or 0) for r in rows),
            "queued": sum(int(r.get("queued") or 0) for r in rows),
            "ok": sum(int(r.get("ok") or 0) for r in rows),
            "parked": sum(int(r.get("parked") or 0) for r in rows),
            "active_svcs": sum(1 for r in rows if r.get("svc")),
            "rows": rows,
        }
        line = json.dumps({k: rec[k] for k in rec if k != "rows"})
        print(line, flush=True)
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        (OUT.parent / "fleet-progress-latest.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        if rec["ok"] >= 1685 and rec["flight"] == 0 and rec["queued"] == 0:
            print("SUCCESS:fleet-queue-empty", rec["ok"], flush=True)
            return
        time.sleep(90)
    print("TIMEOUT fleet watch", flush=True)


if __name__ == "__main__":
    main()
