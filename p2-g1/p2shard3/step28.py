from wslrun import read_unc
src = read_unc('/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0057/ramp.py')
lines = src.splitlines()
print('total lines:', len(lines))
import re
start = None
for i, l in enumerate(lines):
    if 'def run_signal_disagreement' in l:
        start = i
        break
print(chr(10).join(lines[start:start+120]))
