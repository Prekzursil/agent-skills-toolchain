#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PYEOF'
from pathlib import Path
p = Path('/home/prekzursil/p2-g1/tools/plugin/pack.py')
t = p.read_text(encoding='utf-8')
old = "        extras.sort()\n        members.sort()\n"
new = "        extras.sort()\n        members = sorted(\n            members, key=lambda rel: unicodedata.normalize(\"NFC\", rel)\n        )\n"
n = t.count(old)
print('match count:', n)
assert n == 1, 'unexpected match count'
p.write_text(t.replace(old, new), encoding='utf-8')
import py_compile
py_compile.compile(str(p), doraise=True, cfile='/tmp/pyc2.pyc')
print('compile OK')
PYEOF
cd command-center/p2-wave/probes/BLD-0010 && python3 -c "
import runtime as R
loc = R.locale_sort()
print('locale_sort pass:', loc['pass'], 'declared:', loc['pack_nfc_key_present'], 'site:', loc['pack_site'])
" 2>&1 | tail -2
