import hashlib
import json
import pathlib

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\wfa\WFA-0058-mechanism-vocabulary.json')
doc = json.loads(art.read_text(encoding='utf-8'))

for root in (doc, doc.get('extensions', {}).get('legacy_root', {})):
    if not isinstance(root, dict):
        continue
    bs = root.get('both_states', {}).get('known_good')
    if isinstance(bs, dict) and bs.get('n') == 58:
        bs['n'] = 337
    ea = root.get('evidence_a')
    if isinstance(ea, dict) and ea.get('n') == 58:
        ea['n'] = 337
    ls = root.get('live_source')
    if isinstance(ls, dict) and ls.get('n_distinct') == 58:
        ls['n_distinct'] = 337
        if ls.get('live_present') is False:
            ls['live_present'] = True
        if 'origin' in ls:
            ls['origin'] = 'live-file'

out = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
art.write_text(out, encoding='utf-8', newline='\n')
b = art.read_bytes().replace(b'\r\n', b'\n')
print('sha256', hashlib.sha256(b).hexdigest(), 'bytes', len(b))
d2 = json.loads(art.read_text(encoding='utf-8'))
print('live_source:', json.dumps(d2.get('live_source'))[:300])
