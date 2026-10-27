#!/bin/bash
cd /home/prekzursil/p2-g1
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PYEOF'
from pathlib import Path
import py_compile
p = Path('/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0057/ramp.py')
t = p.read_text(encoding='utf-8')
old = "commit_ps.append(spawn(commit_run, mmap_bytes=48 * 1024 * 1024, fds=1))"
new = "commit_ps.append(spawn(commit_run, mmap_bytes=320 * 1024 * 1024, fds=1))"
n = t.count(old)
print('match count:', n)
assert n == 1
p.write_text(t.replace(old, new), encoding='utf-8')
py_compile.compile(str(p), doraise=True, cfile='/tmp/pyc3.pyc')
print('compile OK')
PYEOF
echo "===quick disagreement check==="
cd command-center/p2-wave/probes/BLD-0057 && timeout 300 python3 -B -c "
import json
import ramp as R
d = R.run_signal_disagreement()
print(json.dumps(d, indent=1, sort_keys=True))
" 2>&1 | tail -20
