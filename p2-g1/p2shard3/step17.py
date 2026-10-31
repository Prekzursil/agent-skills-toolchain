from wslrun import read_unc
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/'
for f in ['AUD-0044/probe2_merged_pr_checks.py', 'AUD-0095/emit_artifact.py']:
    print('='*100)
    print(base + f)
    print('='*100)
    print(read_unc(base + f))
