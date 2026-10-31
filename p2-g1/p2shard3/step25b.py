from wslrun import read_unc
src = read_unc('/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0037/audit.py')
lines = src.splitlines()
print(chr(10).join(lines[465:560]))
print('...')
print(chr(10).join(lines[700:862]))
