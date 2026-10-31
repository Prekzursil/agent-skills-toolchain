from wslrun import read_unc
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0044/'
for f in ['common.py', 'census.py']:
    print('='*100)
    print(base + f)
    print('='*100)
    print(read_unc(base + f))
