from wslrun import read_unc
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0057/'
w = read_unc(base + 'worker.py')
print('=== worker.py ===')
print(w[:3500])
p2 = read_unc(base + 'probe2_controls.py')
print('=== probe2_controls.py (first 120 lines) ===')
print(chr(10).join(p2.splitlines()[:120]))
g = read_unc(base + 'guard.py')
print('=== guard.py ABORT_COMMIT_RATIO ===')
for l in g.splitlines():
    if 'ABORT_COMMIT_RATIO' in l or 'RATIO' in l.upper() and '=' in l:
        print(l)
