from wslrun import read_unc
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/BLD-0037/'
src = read_unc(base + 'audit.py')
print('audit.py lines=', len(src.splitlines()))
# print reviewer-related parts
lines = src.splitlines()
import re
for i, l in enumerate(lines):
    if re.search(r'reviewer_queries|def run_audit|REVIEWER_PIN|queries', l):
        print(i, l)
