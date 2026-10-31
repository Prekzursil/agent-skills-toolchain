from wslrun import read_unc
for p in [
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py',
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0044/probe2_cache_and_hermetic.py',
]:
    print('='*100)
    print(p)
    print('='*100)
    print(read_unc(p))
