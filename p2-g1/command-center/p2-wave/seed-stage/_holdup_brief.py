#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

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
    ("par-c", "57.130.46.182"),
    ("rbx-c", "152.228.192.99"),
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
]
CMD = r"""
python3 - <<'PY'
import json, os, time
from pathlib import Path
hb={}
p=Path('/opt/p2/supervisor-heartbeat.json')
if p.exists():
    hb=json.loads(p.read_text())
log=Path('/opt/p2/g1-fix.log')
lines=log.read_text(errors='replace').splitlines() if log.exists() else []
done=Path('/opt/p2/g1-fix.json').exists()
workers=list(Path('/opt/p2/workers').glob('g1fix-*'))
loop=list(Path('/opt/p2/workers').glob('loop-*'))
# live agent procs
import subprocess
pr=subprocess.run(['bash','-lc','pgrep -c -f "/root/.local/bin/agent " || true'],capture_output=True,text=True)
nagent=(pr.stdout or '0').strip()
cur=None
for line in reversed(lines):
    if line.startswith('FIX '):
        cur=line[4:].strip(); break
print(json.dumps({
  'fix_done_json': done,
  'fix_log_n': len(lines),
  'last3': lines[-3:],
  'current': cur,
  'g1fix_dirs': [w.name for w in workers],
  'hb_in_flight': hb.get('in_flight_n'),
  'hb_queued': hb.get('queued_n'),
  'agent_procs': nagent,
  'svc': subprocess.run(['systemctl','is-active','p2-supervisor'],capture_output=True,text=True).stdout.strip(),
}, separators=(',',':')))
PY
"""


def one(name, ip):
    p = run(SSH + [f"root@{ip}", CMD], capture_output=True, text=True, timeout=25)
    return name, (p.stdout or "").strip(), (p.stderr or "")[-200:], p.returncode


def main():
    with ThreadPoolExecutor(4) as ex:
        for f in as_completed([ex.submit(one, *b) for b in BOXES]):
            name, out, err, rc = f.result()
            print("====", name, "rc", rc)
            print(out or err)


if __name__ == "__main__":
    main()
