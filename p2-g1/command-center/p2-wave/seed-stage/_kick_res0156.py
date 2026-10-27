#!/usr/bin/env python3
"""Kill hung 0-byte RES-0156 agent on gra7-c and restart W3 for that id only."""
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
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
IP = "51.210.248.225"
KILL = r"""
import os, signal, subprocess, time
from pathlib import Path
killed=[]
p=subprocess.run(['ps','-eo','pid,args'], capture_output=True, text=True)
for line in p.stdout.splitlines():
    if 'RES-0156' in line and 'python3 -c' not in line and 'ps -eo' not in line:
        pid=int(line.split(None,1)[0])
        if pid != os.getpid():
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except Exception as e:
                killed.append(f'{pid}:{e}')
time.sleep(1)
print('KILLED', killed)
print('LOGSZ', Path('/opt/p2/workers/g1fix-RES-0156/worker.log').stat().st_size if Path('/opt/p2/workers/g1fix-RES-0156/worker.log').exists() else 'missing')
"""


def main():
    payload = __import__("base64").b64encode(KILL.strip().encode()).decode()
    p = run(SSH + [f"root@{IP}", f"echo {payload} | base64 -d | python3"], capture_output=True, text=True, timeout=20)
    print("kill", (p.stdout or "") + (p.stderr or "")[-200:], flush=True)
    tmp = STAGE / "g1-w3-fails.gra7-c.json"
    tmp.write_text('[{"id":"RES-0156","hint":"hung 0-byte worker.log; retry"}]\n', encoding="utf-8")
    host = f"root@{IP}"
    p = run(SCP + [str(tmp), f"{host}:/opt/p2/g1-w3-fails.json"], capture_output=True, text=True, timeout=20)
    print("scp fails", p.returncode, flush=True)
    start = (
        "set -a; . /opt/p2/cursor.env; set +a; "
        "rm -f /opt/p2/g1-w3.json; "
        "nohup python3 -u /opt/p2/fix_g1_w3.py >/opt/p2/g1-w3.out 2>&1 & echo W3-RESTARTED $!"
    )
    p = run(SSH + [host, start], capture_output=True, text=True, timeout=20)
    print("start", (p.stdout or "") + (p.stderr or ""), flush=True)
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
