import json, subprocess, os, sys
os.chdir(os.path.expanduser('~/p2-g1'))
CMD = {
 "ADV-0127": ["command-center/p2-wave/probes/ADV-0127/probe1_delivery_predicate.py","command-center/p2-wave/probes/ADV-0127/probe2_behavioral.py"],
 "ADV-0128": ["command-center/p2-wave/probes/ADV-0128/probe1_full_offline.py","command-center/p2-wave/probes/ADV-0128/probe2_mid_partition.py"],
 "ARC-0001": ["command-center/p2-wave/probes/ARC-0001/probe1_both_states.py","command-center/p2-wave/probes/ARC-0001/probe2_reviewer_anchor.py"],
 "ARC-0012": ["command-center/p2-wave/probes/ARC-0012/probe1_both_states.py","command-center/p2-wave/probes/ARC-0012/probe2_overclaim.py"],
 "ARC-0013": ["command-center/p2-wave/probes/ARC-0013/probe1_planted_edit.py","command-center/p2-wave/probes/ARC-0013/probe2_whitespace.py"],
 "ARC-0015": ["command-center/p2-wave/probes/ARC-0015/probe1_mutation.py","command-center/p2-wave/probes/ARC-0015/probe2_eol.py"],
 "ARC-0019": ["command-center/p2-wave/probes/ARC-0019/probe1_reconcile.py","command-center/p2-wave/probes/ARC-0019/probe2_overclaim.py"],
 "ARC-0020": ["command-center/p2-wave/probes/ARC-0020/probe1_path_coverage.py","command-center/p2-wave/probes/ARC-0020/probe2_negative_control.py"],
 "ARC-0021": ["command-center/p2-wave/probes/ARC-0021/probe1_adopt.py","command-center/p2-wave/probes/ARC-0021/probe2_uninstall.py"],
 "ARC-0047": ["command-center/p2-wave/probes/ARC-0047/probe1_both_states_audit.py","command-center/p2-wave/probes/ARC-0047/probe2_overclaim.py"],
 "ARC-0048": ["command-center/p2-wave/probes/ARC-0048/probe1_markers.py","command-center/p2-wave/probes/ARC-0048/probe2_classification.py"],
 "ARC-0054": ["command-center/p2-wave/probes/ARC-0054/probe1_both_states.py","command-center/p2-wave/probes/ARC-0054/probe2_overclaim.py"],
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
res = {}
for uid, scripts in CMD.items():
    res[uid] = []
    for s in scripts:
        p = subprocess.run([sys.executable, '-B', s], capture_output=True, text=True, timeout=600, env=env)
        res[uid].append({'script': s, 'exit': p.returncode, 'stdout_tail': (p.stdout or '').strip()[-400:], 'stderr_tail': (p.stderr or '').strip()[-200:]})
        print(f"{uid} {os.path.basename(s)} -> rc={p.returncode}")
        if p.returncode != 0:
            print('   OUT:', (p.stdout or '').strip()[-600:])
            print('   ERR:', (p.stderr or '').strip()[-400:])
json.dump(res, open('_reviewer-w4s2/probe_results.json','w', encoding='utf-8'), indent=1)
bad = {u:[r for r in rs if r['exit']!=0] for u,rs in res.items() if any(r['exit']!=0 for r in rs)}
print('ALL-EXIT-0' if not bad else f'FAILURES: {list(bad)}')
