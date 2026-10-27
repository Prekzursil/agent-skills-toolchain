import json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = {
 'CNF-0173': ['probe1_confirmer_unanimity.py','probe2_both_states_siblings.py'],
 'CNF-0177': ['probe1_heldout.py','probe2_overselect.py'],
 'CNF-0178': ['probe1_healthy_lifecycle.py','probe2_broken_control.py'],
 'CNF-0188': ['probe1_independent_extractors.py','probe2_detector_controls.py'],
 'CNL-0076': ['probe1_flapping.py','probe2_purity.py'],
 'IMP-0003': ['probe1.py','probe2.py'],
 'IMP-0013': ['probe1_cmd_shim_disagreement.py','probe2_missing_tool_and_no_gitbash.py'],
 'IMP-0014': ['probe1.py','probe2.py'],
 'IMP-0018': ['probe1_over_limit_roundtrip.py','probe2_inline_fail_and_cleanup.py'],
 'IMP-0020': ['probe1_both_directions.py','probe2_global_control.py'],
 'IMP-0022': ['probe1_set_collision.py','probe2_extract_shortfall.py'],
}
TIMEOUT = 600

def run_one(uid, fname):
    pdir = REPO/'command-center'/'p2-wave'/'probes'/uid
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, '-B', fname], cwd=str(pdir),
                           capture_output=True, text=True, timeout=TIMEOUT,
                           env=None)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = 'TIMEOUT', '', ''
    dt = time.time() - t0
    tail = (out or '').strip().splitlines()[-3:]
    etail = (err or '').strip().splitlines()[-3:]
    return {'unit': uid, 'probe': fname, 'rc': rc, 'secs': round(dt,1),
            'out_tail': tail, 'err_tail': etail}

results = []
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = []
    for uid, probes in PROBES.items():
        for f in probes:
            futs.append(ex.submit(run_one, uid, f))
    for fu in futs:
        results.append(fu.result())

results.sort(key=lambda r: (r['unit'], r['probe']))
for r in results:
    print(f"{r['unit']:9s} {r['probe']:42s} rc={r['rc']} {r['secs']}s")
    if r['rc'] != 0:
        for l in r['out_tail']: print('   OUT|', l[:200])
        for l in r['err_tail']: print('   ERR|', l[:200])
ok = sum(1 for r in results if r['rc']==0)
print(f"\nPROBE RUN RESULT: {ok}/{len(results)} exit 0")
Path('_shard5_probe_results.json').write_text(json.dumps(results, indent=1))
