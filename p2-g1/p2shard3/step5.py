from wslrun import read_unc
src = read_unc('/home/prekzursil/p2-g1/command-center/p2-wave/_build_AUD0020.py')
lines = src.splitlines()
print(chr(10).join(lines[430:543]))
