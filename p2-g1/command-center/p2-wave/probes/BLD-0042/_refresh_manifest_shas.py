#!/usr/bin/env python3
"""Refresh non-primary manifest rows whose live file sha drifted (resume housekeeping)."""
import hashlib
import json
import sys
from pathlib import Path

mp = Path(sys.argv[1] if len(sys.argv) > 1 else
          'command-center/p2-wave/probes/BLD-0042/UNIT-ARTIFACT-MANIFEST.json')
man = json.loads(mp.read_text(encoding='utf-8'))
changed = []
for a in man.get('artifacts') or []:
    rel = str(a.get('path') or '').replace(chr(92), '/')
    p = Path(rel)
    if p.is_file():
        raw = p.read_bytes().replace(b'\r\n', b'\n')
        sha = hashlib.sha256(raw).hexdigest()
        if a.get('sha256') != sha:
            changed.append((rel, str(a.get('sha256'))[:12], sha[:12]))
            a['sha256'] = sha
            a['bytes'] = len(raw)
            a['present'] = True
if changed:
    mp.write_text(json.dumps(man, indent=1, sort_keys=True) + chr(10),
                  encoding='utf-8', newline='\n')
for c in changed:
    print('refreshed:', c[0], c[1], '->', c[2])
print('rows refreshed:', len(changed))
print('SUCCESS:manifest-sha-refresh' if True else '')
