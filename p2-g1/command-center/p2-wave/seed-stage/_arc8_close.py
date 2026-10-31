#!/usr/bin/env python3
"""Re-measure the stalled ARC-8, then record them in completed.json if SUCCESS."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

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
JOBS = [
    ("de1-a", "51.75.93.252", ["ARC-0003", "ARC-0012"]),
    ("gra9-b", "37.59.27.161", ["ARC-0005", "ARC-0014"]),
    ("rbx-a", "164.132.87.22", ["ARC-0007", "ARC-0016"]),
    ("par-a", "57.130.47.223", ["ARC-0009"]),
    ("waw1-b", "51.75.63.116", ["ARC-0010"]),
]


def ssh(ip: str, cmd: str, timeout: int = 90):
    return run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=timeout)


def measure(name: str, ip: str, uid: str) -> str:
    p = ssh(
        ip,
        f"cd /opt/p2/ast-integrate && python3 command-center/p2-wave/_measure_one_delivered.py {uid}",
        timeout=90,
    )
    lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    last = lines[-1] if lines else f"rc={p.returncode}"
    return f"{name} {uid} {last} rc={p.returncode}"


def record(ip: str, uids: list[str]) -> str:
    # merge into completed.json
    inner = (
        "import json,datetime\n"
        "from pathlib import Path\n"
        f"uids={uids!r}\n"
        "p=Path('/opt/p2/completed.json')\n"
        "data={'ids':[], 'ts': None}\n"
        "if p.exists():\n"
        "    try: data=json.loads(p.read_text())\n"
        "    except Exception: data={'ids':[]}\n"
        "ids=set(str(x) for x in (data.get('ids') or []))\n"
        "before=len(ids)\n"
        "ids.update(uids)\n"
        "data['ids']=sorted(ids)\n"
        "data['ts']=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "data['arc8_close']=True\n"
        "p.write_text(json.dumps(data, indent=2)+'\\n')\n"
        "print('merged', before, '->', len(ids), 'added', sorted(set(uids)-set(data.get('ids') and [])))\n"
    )
    # fix added print
    inner = (
        "import json, datetime\n"
        "from pathlib import Path\n"
        f"uids={uids!r}\n"
        "p=Path('/opt/p2/completed.json')\n"
        "data={'ids': []}\n"
        "if p.exists():\n"
        "    try:\n"
        "        data=json.loads(p.read_text()) or {'ids': []}\n"
        "    except Exception:\n"
        "        data={'ids': []}\n"
        "ids=set(str(x) for x in (data.get('ids') or []))\n"
        "before=len(ids)\n"
        "added=[u for u in uids if u not in ids]\n"
        "ids.update(uids)\n"
        "data['ids']=sorted(ids)\n"
        "data['ts']=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "data['arc8_close']=True\n"
        "p.write_text(json.dumps(data, indent=2)+'\\n')\n"
        "print('merged', before, '->', len(ids), 'added', added)\n"
    )
    b64 = __import__("base64").b64encode(inner.encode()).decode()
    p = ssh(ip, f"echo {b64} | base64 -d | python3", timeout=20)
    return ((p.stdout or "") + (p.stderr or "")).strip() + f" rc={p.returncode}"


def main() -> None:
    print("===== re-measure =====", flush=True)
    ok = True
    results = []
    with ThreadPoolExecutor(8) as ex:
        futs = []
        for name, ip, uids in JOBS:
            for uid in uids:
                futs.append(ex.submit(measure, name, ip, uid))
        for f in as_completed(futs):
            line = f.result()
            print(line, flush=True)
            results.append(line)
            if "SUCCESS:delivered" not in line:
                ok = False
    if not ok:
        print("FAILED:not all ARC-8 re-measured SUCCESS — not writing completed.json")
        return
    print("===== record completed.json =====", flush=True)
    for name, ip, uids in JOBS:
        print(name, record(ip, uids), flush=True)


if __name__ == "__main__":
    main()
