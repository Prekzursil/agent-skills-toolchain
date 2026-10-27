#!/bin/bash
cd /home/prekzursil/p2-g1
echo "===pack.py locations==="
find tools -name "pack.py" 2>/dev/null | head
find . -path ./node_modules -prune -o -name "pack.py" -print 2>/dev/null | grep -v node_modules | head
echo "===census sort sites==="
cd command-center/p2-wave/probes/BLD-0010 && python3 - <<'PYEOF' 2>&1 | tail -40
import json
import census as C
inv = C.census()
print('sorts_with_key n=', len(inv['sorts_with_key']))
for s in inv['sorts_with_key'][:40]:
    print('KEYED:', s['path'], s.get('lineno'), repr(s.get('key_repr'))[:80], 'nfc=', s.get('key_uses_nfc'))
print('plugin-ish sites:', [s['path'] for s in inv['sorts_with_key'] if 'pack' in s['path'].lower()])
PYEOF
