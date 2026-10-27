import json
from pathlib import Path
mine = ['TST-0283','TST-0284','TST-0288','TST-0297','TST-0303','TST-0309','TST-0313','TST-0315','TST-0319','TST-0322','TST-0328','TST-0330']
out = {}
for uid in mine:
    r = json.loads(Path('command-center/receipts/%s.json' % uid).read_text(encoding='utf-8'))
    def shape(v, depth=0):
        if isinstance(v, dict):
            return {k: shape(x, depth+1) for k, x in list(v.items())[:6]} if depth < 2 else 'dict[%d]' % len(v)
        if isinstance(v, list):
            return [shape(v[0], depth+1)] if v else []
        s = str(v)
        return s[:60]
    out[uid] = {
        'evidence_type': type(r.get('evidence')).__name__,
        'evidence': shape(r.get('evidence')),
        'tests_type': type(r.get('tests')).__name__,
        'tests': shape(r.get('tests')),
        'nc_type': type(r.get('negative_controls')).__name__,
        'nc': shape(r.get('negative_controls')),
    }
json.dump(out, open('_builder_shard19_w4_shapes.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('written')
