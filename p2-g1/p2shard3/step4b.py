from wslrun import read_unc
p = '/home/prekzursil/p2-g1/command-center/p2-wave/_build_AUD0020.py'
src = read_unc(p)
# print the receipt-writing parts
lines = src.splitlines()
print('TOTAL LINES:', len(lines))
# find receipt_core import/def
for i, l in enumerate(lines):
    if 'receipt_core' in l or 'reviewer-absent' in l:
        print(i, l)
