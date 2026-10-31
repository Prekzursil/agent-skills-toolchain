from wslrun import read_unc
for p in [
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0044/common.py',
  '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0057/probe1_ramp.py',
]:
    print('='*100)
    print(p)
    print('='*100)
    print(read_unc(p))
