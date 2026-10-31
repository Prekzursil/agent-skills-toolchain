#!/usr/bin/env python3
"""Watch g1-w3 home-box fix loops."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
OUT = WAVE / "ovh-monitor"
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
BOXES = [
    ("par-c", "57.130.46.182", 2),
    ("rbx-a", "164.132.87.22", 1),
    ("rbx-c", "152.228.192.99", 1),
    ("waw1-c", "54.38.138.226", 1),
    ("uk1-a", "54.37.3.247", 1),
    ("gra11-c", "176.31.201.215", 2),
    ("gra11-a", "176.31.201.117", 1),
    ("gra7-c", "51.210.248.225", 2),
    ("gra9-c", "141.94.186.60", 1),
]
CMD = r"""
import json
from pathlib import Path
st='RUN'
ok=n=None
fail=[]
last=''
if Path('/opt/p2/g1-w3.json').is_file():
    st='DONE'
    d=json.loads(Path('/opt/p2/g1-w3.json').read_text())
    ok=d.get('ok'); n=d.get('n'); fail=d.get('fail') or []
lp=Path('/opt/p2/g1-w3.log')
if lp.exists():
    lines=lp.read_text(errors='replace').splitlines()
    last=lines[-1] if lines else ''
print(json.dumps({'st':st,'ok':ok,'n':n,'fail':fail,'last':last[-180:]}))
"""


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe(name, ip, expect):
    payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    rec = {"name": name, "ip": ip, "expect": expect, "reachable": p.returncode == 0}
    if p.returncode != 0:
        rec["st"] = "DOWN"
        rec["err"] = ((p.stderr or "") + (p.stdout or ""))[-120:]
        return rec
    try:
        rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    except Exception as exc:
        rec["st"] = "DOWN"
        rec["err"] = str(exc)
    return rec


def tick():
    rows = []
    with ThreadPoolExecutor(9) as ex:
        futs = [ex.submit(probe, *b) for b in BOXES]
        for f in as_completed(futs):
            rows.append(f.result())
    rows.sort(key=lambda r: r["name"])
    done = sum(1 for r in rows if r.get("st") == "DONE")
    runn = sum(1 for r in rows if r.get("st") == "RUN")
    ok_sum = sum(int(r.get("ok") or 0) for r in rows if r.get("st") == "DONE")
    n_sum = sum(int(r.get("n") or 0) for r in rows if r.get("st") == "DONE")
    fails = []
    for r in rows:
        for uid in r.get("fail") or []:
            fails.append(f"{r['name']}:{uid}")
    payload = {
        "ts": utc(),
        "done_boxes": done,
        "run_boxes": runn,
        "ok_sum": ok_sum,
        "n_sum": n_sum,
        "fail_ids": fails,
        "expect_total": 12,
        "boxes": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "w3-latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# W3 home-box G-1 fix — {payload['ts']}",
        "",
        f"boxes DONE **{done}/9**  RUN {runn}",
        f"finished units **{ok_sum}/{n_sum}** PASS (of 12 expected)",
        "",
        "| box | st | ok/n | last |",
        "|---|---|---|---|",
    ]
    for r in rows:
        last = (r.get("last") or "").replace("|", "/")[:80]
        on = f"{r.get('ok')}/{r.get('n')}" if r.get("st") == "DONE" else "—"
        lines.append(f"| {r['name']} | {r.get('st')} | {on} | `{last}` |")
    (OUT / "w3-latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{payload['ts']} W3 {done}/9 ok={ok_sum}/{n_sum} run={runn} fail={fails}", flush=True)
    return done == 9


def main():
    while True:
        if tick():
            print("W3-ALL-DONE", flush=True)
            return
        time.sleep(45)


if __name__ == "__main__":
    main()
