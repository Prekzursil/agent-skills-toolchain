import json, re
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
for uid in ['TST-0129','TST-0130']:
    p = REPO/'command-center'/'receipts'/(uid+'.json')
    text = p.read_text(encoding='utf-8')
    print('='*15, uid)
    for m in re.finditer('SUCCESS:' + uid, text):
        s = max(0, m.start()-160)
        print('...', text[s:m.end()+120].replace(chr(10),' | '), '...')
