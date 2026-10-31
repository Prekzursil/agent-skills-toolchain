from wslrun import read_unc
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/'
import os
for d in ['BLD-0037', 'BLD-0057']:
    UNC = r'\wsl.localhost' + chr(92) + 'Ubuntu'
    try:
        names = sorted(os.listdir(UNC + (base + d).replace('/', chr(92))))
    except Exception as e:
        names = ['LISTFAIL %r' % e]
    print(d, names)
for f in ['BLD-0037/write_receipts.py', 'BLD-0057/emit_model.py']:
    p = base + f
    try:
        src = read_unc(p)
        print('='*100)
        print(p, 'lines=', len(src.splitlines()))
        print('='*100)
        print(src)
    except Exception as e:
        print(p, 'READFAIL', repr(e))
