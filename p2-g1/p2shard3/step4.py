from wslrun import read_unc
import json
base = '/home/prekzursil/p2-g1/command-center/p2-wave/probes/ADV-0001'
import os
UNC = r'\wsl.localhost' + chr(92) + 'Ubuntu'
for name in ['SUBAGENT-RETURN.json', 'UNIT-ARTIFACT-MANIFEST.json']:
    try:
        p = base + '/' + name
        txt = read_unc(p)
        print('=== %s ===' % name)
        print(txt[:4000])
        print()
    except Exception as e:
        print('=== %s === MISSING: %r' % (name, e))
# also list dir
d = UNC + base.replace('/', chr(92))
print('DIR LISTING:', sorted(os.listdir(d)) if os.path.isdir(d) else 'NODIR')
