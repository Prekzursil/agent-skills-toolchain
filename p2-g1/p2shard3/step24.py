from wslrun import read_unc
src = read_unc('/home/prekzursil/p2-g1/tools/plugin/pack.py')
print('lines:', len(src.splitlines()))
print(src)
