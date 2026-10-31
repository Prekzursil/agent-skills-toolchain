from wslrun import read_unc
for p in [
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0044/probe1_ruleset_required.py',
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0095/probe1_freeze_anchors.py',
]:
    print('='*100)
    print(p)
    print('='*100)
    print(read_unc(p))
