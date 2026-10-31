#!/usr/bin/env python3
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

WAVE = Path(__file__).resolve().parent.parent
OUT = WAVE / "ovh-monitor"
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
BOXES = [
    ("de1-c", "162.19.209.251", "IMP-0051"),
    ("gra9-c", "141.94.186.60", "BLD-0055"),
]
CMD = r"""
import json
from pathlib import Path
st='RUN'
ok=n=None
fail=[]
last=''
if Path('/opt/p2/g1-w4.json').is_file():
    st='DONE'
    d=json.loads(Path('/opt/p2/g1-w4.json').read_text())
    ok=d.get('ok'); n=d.get('n'); fail=d.get('fail') or []
lp=Path('/opt/p2/g1-w4.log')
if lp.exists():
    lines=lp.read_text(errors='replace').splitlines()
    last=lines[-1] if lines else ''
sz=Path('/opt/p2/workers/g1fix-UID/worker.log').stat().st_size if Path('/opt/p2/workers/g1fix-UID/worker.log').exists() else -1
print(json.dumps({'st':st,'ok':ok,'n':n,'fail':fail,'last':last[-160:],'logsz':sz}))
"""


def probe(name, ip, uid):
    code = CMD.replace("UID", uid)
    payload = __import__("base64").b64encode(code.strip().encode()).decode()
    p = run(SSH + [f"root@{ip}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    rec = {"name": name, "uid": uid, "reachable": p.returncode == 0}
    if p.returncode != 0:
        rec["st"] = "DOWN"
        rec["err"] = ((p.stderr or "") + (p.stdout or ""))[-80:]
        return rec
    rec.update(json.loads((p.stdout or "").strip().splitlines()[-1]))
    return rec


def tick():
    rows = []
    with ThreadPoolExecutor(2) as ex:
        for f in as_completed([ex.submit(probe, *b) for b in BOXES]):
            rows.append(f.result())
    rows.sort(key=lambda r: r["name"])
    done = sum(1 for r in rows if r.get("st") == "DONE")
    (OUT / "w4-latest.json").write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")
    print(
        " ".join(
            f"{r['name']}:{r.get('st')} {r.get('ok')}/{r.get('n')} log={r.get('logsz')} {(r.get('last') or '')[:50]}"
            for r in rows
        ),
        flush=True,
    )
    return done == 2


def main():
    while True:
        if tick():
            print("W4-ALL-DONE", flush=True)
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
