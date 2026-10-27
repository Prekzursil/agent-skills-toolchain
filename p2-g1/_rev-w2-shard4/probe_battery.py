"""Independent reviewer probe battery - wave2 shard4.
Runs each unit's named probe scripts from repo root, records rc + output.
Gate: exit 0 required per probe. Also records SUCCESS:/FAILED: marker state.
"""
import json, subprocess, sys, time, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ~/p2-g1
OUT  = os.path.join(ROOT, '_rev-w2-shard4', 'probe_results.json')
LOG  = os.path.join(ROOT, '_rev-w2-shard4', 'probe_battery.log')

with open(os.path.join(ROOT, '_rev-w2-shard4', 'named_probes.json'), encoding='utf-8') as f:
    NAMED = json.load(f)

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

results = {}
for unit, probes in NAMED.items():
    for p in probes:
        t0 = time.time()
        try:
            cp = subprocess.run(
                [sys.executable, '-B', p],
                cwd=ROOT, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=900)
            rc, out, err = cp.returncode, cp.stdout, cp.stderr
        except subprocess.TimeoutExpired as e:
            rc, out, err = 'TIMEOUT', (e.stdout or b'').decode('utf-8','replace') if isinstance(e.stdout, bytes) else str(e.stdout or ''), 'timeout after 900s'
        dt = round(time.time() - t0, 1)
        tail = (out or '')[-2000:]
        etail = (err or '')[-800:]
        results[f'{unit}::{os.path.basename(p)}'] = {
            'unit': unit, 'probe': p, 'rc': rc, 'seconds': dt,
            'stdout_tail': tail, 'stderr_tail': etail,
            'has_SUCCESS_marker': 'SUCCESS:' in (out or ''),
            'has_FAILED_marker': 'FAILED:' in (out or ''),
        }
        log(f'{unit} {os.path.basename(p)} rc={rc} {dt}s SUCCESS_marker={results[f"{unit}::{os.path.basename(p)}"]["has_SUCCESS_marker"]} FAILED_marker={results[f"{unit}::{os.path.basename(p)}"]["has_FAILED_marker"]}')
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=1)

log('DONE:probe-battery')
print('DONE:probe-battery')
