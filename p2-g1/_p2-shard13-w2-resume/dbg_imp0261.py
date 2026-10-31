import importlib.util, io, sys, json, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
REPO = Path(r'C:/Users/Prekzursil/p2-g1')
spec = importlib.util.spec_from_file_location('m1d', REPO/'command-center'/'p2-wave'/'_measure_one_delivered.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# Replicate probe2's inner CLI call under run_cmd's env construction
code, tail = m.run_cmd('PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0261/probe2_jsonschema.py')
print('probe2 rc=', code)
for line in tail.splitlines():
    print('   ', line[:220])
