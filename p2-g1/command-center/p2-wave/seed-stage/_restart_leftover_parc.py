#!/usr/bin/env python3
"""If par-c G-1 is FIX-DONE, restart leftover supervisor."""
from __future__ import annotations

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
CMD = r"""
import json
from pathlib import Path
from subprocess import run
st='RUN'
if Path('/opt/p2/g1-fix.json').is_file():
    d=json.loads(Path('/opt/p2/g1-fix.json').read_text())
    print('G1', d.get('ok'), '/', d.get('n'), 'fail', d.get('fail'))
    st='DONE'
else:
    last=''
    p=Path('/opt/p2/g1-fix.log')
    if p.exists():
        last=p.read_text(errors='replace').splitlines()[-1]
    print('G1-RUN', last[-120:])
if st=='DONE':
    run(['systemctl','start','p2-supervisor'])
    svc=run(['systemctl','is-active','p2-supervisor'], capture_output=True, text=True).stdout.strip()
    print('RESTARTED', svc)
"""


def main() -> None:
    payload = __import__("base64").b64encode(CMD.strip().encode()).decode()
    p = run(
        SSH + ["root@57.130.46.182", f"echo {payload} | base64 -d | python3"],
        capture_output=True,
        text=True,
        timeout=25,
    )
    print((p.stdout or "") + (p.stderr or ""), flush=True)


if __name__ == "__main__":
    main()
