#!/usr/bin/env python3
"""Diagnose the 8 remaining ARC units on one OVH box (shared leftover + probe tree)."""
import base64
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
HOST = "root@176.31.201.117"
REMOTE = r"""
import json, os
from pathlib import Path

def slot(uid, n=18):
    return sum(ord(c) for c in uid) % n

WAVE = Path('/opt/p2/ast-integrate/command-center/p2-wave')
left = json.loads((WAVE/'P2-CLOUD-LEFTOVER_2026-08-24.json').read_text())
arc = [i for i in left.get('remaining_ids') or [] if str(i).startswith('ARC-')]
park = {}
pf = WAVE/'A-PLUS-D-PARK.json'
if pf.exists():
    try:
        park = json.loads(pf.read_text())
    except Exception as e:
        park = {'_err': str(e)}
park_ids = set()
if isinstance(park, dict):
    for rec in (park.get('units') or []) + (park.get('ids') or []):
        if isinstance(rec, dict) and rec.get('id'):
            park_ids.add(str(rec['id']))
        elif isinstance(rec, str):
            park_ids.add(rec)
blocked = {}
for name in ('P2-BLOCKED-UNITS.json','P2-BLOCKED-UNITS-R3.json'):
    p = WAVE/name
    if p.exists():
        try:
            blocked[name] = json.loads(p.read_text())
        except Exception:
            blocked[name] = 'bad'
done = set()
cp = Path('/opt/p2/completed.json')
if cp.exists():
    done = set(json.loads(cp.read_text()).get('ids') or [])
print('ARC_LEFTOVER', len(arc))
print('PARK_FILE', pf.exists(), 'park_ids_n', len(park_ids), 'park_arc', sorted(i for i in park_ids if i.startswith('ARC-')))
print('BOX_INDEX', os.environ.get('BOX_INDEX'), 'BOX_COUNT', os.environ.get('BOX_COUNT'))
# env from systemd may not be in this ssh
envp = Path('/opt/p2/cursor.env')
if envp.exists():
    keys = []
    for line in envp.read_text().splitlines():
        if line.startswith('BOX_') or line.startswith('PATH='):
            keys.append(line)
    print('ENVFILE', keys)
else:
    print('ENVFILE missing')
rows = []
for uid in arc:
    d = WAVE/'probes'/uid
    retp = d/'SUBAGENT-RETURN.json'
    rec = {
        'id': uid,
        'slot': slot(uid),
        'in_done_this_box': uid in done,
        'in_park': uid in park_ids,
        'dir': d.exists(),
        'return': retp.exists(),
        'manifest': (d/'UNIT-ARTIFACT-MANIFEST.json').exists(),
    }
    sp = Path('/opt/p2/strikes')/f'{uid}.json'
    if sp.exists():
        try:
            s = json.loads(sp.read_text())
            rec['strikes'] = s.get('count')
            rec['strike_parked'] = s.get('parked')
        except Exception:
            rec['strikes'] = 'bad'
    if retp.exists():
        try:
            r = json.loads(retp.read_text())
            rec['status'] = str(r.get('status') or r.get('state') or '')
            rec['registered'] = r.get('registered')
            rec['mline'] = str(r.get('measure_line') or '')[:80]
        except Exception as e:
            rec['status'] = 'BAD-JSON '+str(e)[:40]
    rows.append(rec)
# only print those not obviously done on this box AND (green-looking or no dir or parked)
interesting = [x for x in rows if not x.get('in_done_this_box')]
print('NOT_DONE_THIS_BOX', len(interesting))
# too many; summarize status counts
from collections import Counter
c = Counter((x.get('status') or 'NO-RETURN', bool(x.get('dir')), x.get('in_park')) for x in interesting)
print('STATUS_COUNTS', dict(c))
# print rows that look like skip-green or park or no-tree
for x in interesting:
    st = str(x.get('status') or '')
    if x.get('in_park') or x.get('strike_parked') or st in {'DELIVERED','SUCCESS'} or not x.get('dir'):
        print('SKIPCAND', json.dumps(x, separators=(',',':')))
"""


def main() -> None:
    payload = base64.b64encode(REMOTE.strip().encode("utf-8")).decode("ascii")
    p = run(
        SSH + [HOST, f"echo {payload} | base64 -d | python3"],
        capture_output=True,
        text=True,
        timeout=40,
    )
    print("rc", p.returncode)
    print((p.stdout or "")[-8000:])
    print((p.stderr or "")[-800:])


if __name__ == "__main__":
    main()
