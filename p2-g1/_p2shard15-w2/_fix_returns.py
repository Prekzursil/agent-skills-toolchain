import json
from pathlib import Path
BS = chr(92)
REPO = Path(r'C:' + BS + 'Users' + BS + 'Prekzursil' + BS + 'p2-g1')
MINE = ['IMP-0423','IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442',
        'IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468']
for uid in MINE:
    pdir = REPO / 'command-center' / 'p2-wave' / 'probes' / uid
    # normalize the return filename
    src = pdir / 'SUBAGENT-RETURN.json'
    if not src.is_file():
        alt = pdir / 'SUBAGENT-RETURN.json'
        if alt.is_file():
            alt.rename(src)
        else:
            cands = [x for x in pdir.glob('SUB*R*TURN.json')]
            assert cands, 'no return file in %s: %s' % (uid, [x.name for x in pdir.iterdir()])
            cands[0].rename(src)
    ret = json.loads(src.read_text(encoding='utf-8'))
    for item in ret.get('named_probes', []):
        cmd = item.get('command', '')
        item['command'] = cmd.replace('PYTHONDONTWRITEBYTECODE', 'PYTHONDONTWRITEBYTECODE')
    src.write_text(json.dumps(ret, indent=2) + chr(10), encoding='utf-8', newline=chr(10))
    print(uid, 'fixed ->', src.name)
print('FIXED')
