#!/usr/bin/env python3
"""Point leftover dispatcher remaining_ids at the 281 prior log-success IDs.

Supervisors are QUEUE-EMPTY and rescan every 45s. Do not restart them
(G-1 fix loops are still running). Backup the 1726 leftover file first.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
SRC = WAVE / "CLOUD-DONE-FROM-LOGS-2026-08-21.json"
OUT = WAVE / "P2-PRIOR-281_2026-08-24.json"
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
SCP = [
    "scp",
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
FLEET = [
    "176.31.201.117",
    "176.31.201.215",
    "51.75.63.116",
    "54.38.138.226",
    "51.75.93.252",
    "162.19.209.251",
    "37.59.27.161",
    "141.94.186.60",
    "164.132.87.22",
    "152.228.192.99",
    "57.130.47.223",
    "57.130.46.182",
    "54.37.3.247",
    "54.37.7.164",
    "57.128.35.67",
    "57.128.111.33",
    "51.91.140.54",
    "51.210.248.225",
]


def main() -> None:
    ids = json.loads(SRC.read_text(encoding="utf-8"))["ids"]
    payload = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "CLOUD-DONE-FROM-LOGS-2026-08-21.json",
        "catalog": 2007,
        "remaining_if_log_success_skipped": len(ids),
        "remaining_ids": ids,
        "note": "G-1 remesure/dispatch of the 281 prior log-success claims. Not a skip.",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    remote = "/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
    bak = "/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_1726.bak.json"

    def one(ip: str) -> str:
        host = f"root@{ip}"
        run(SSH + [host, f"test -f {bak} || cp -n {remote} {bak}"], timeout=20)
        p = run(SCP + [str(OUT), f"{host}:{remote}"], capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return f"{ip} SCP-FAIL {(p.stderr or '')[-120:]}"
        q = run(
            SSH
            + [
                host,
                "python3 -c 'import json;d=json.load(open(\"/opt/p2/ast-integrate/command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json\"));print(len(d.get(\"remaining_ids\") or []))'",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return f"{ip} n={(q.stdout or '').strip()} rc={p.returncode}"

    with ThreadPoolExecutor(9) as ex:
        futs = [ex.submit(one, ip) for ip in FLEET]
        for f in as_completed(futs):
            print(f.result(), flush=True)
    print("SEEDED 281. Supervisors rescan QUEUE-EMPTY every 45s.")


if __name__ == "__main__":
    main()
