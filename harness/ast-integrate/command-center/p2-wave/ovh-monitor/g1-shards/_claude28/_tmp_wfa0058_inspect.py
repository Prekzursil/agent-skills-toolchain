import json
import pathlib
import sys

PROBE = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\WFA-0058')
sys.path.insert(0, str(PROBE))
import corpus as C  # noqa: E402
import mapper as M  # noqa: E402

data = C.load_corpus()
texts = C.distinct_texts(data)
print('origin:', data['origin'], 'live_present:', data['live_present'], 'n_distinct:', len(texts))
rows = M.map_all(texts)
print('map_all row sample:', json.dumps(rows[0], ensure_ascii=False))
print('leaks:', sorted(M.closed_ids(rows)), 'multi:', M.unique_mapping(rows))

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\wfa\WFA-0058-mechanism-vocabulary.json')
orig = art.read_text(encoding='utf-8')
doc = json.loads(orig)
fmt = None
for indent in (1, 2, 4):
    if json.dumps(doc, indent=indent, ensure_ascii=False) + '\n' == orig:
        fmt = indent
        break
print('roundtrip indent:', fmt)
tbl = doc.get('mapping_table') or []
print('stored mapping_table n:', len(tbl))
if tbl:
    print('stored row sample:', json.dumps(tbl[0], ensure_ascii=False))
    print('stored row keys:', sorted(tbl[0].keys()))
for k in ('corpus_n', 'n_distinct', 'corpus'):
    if k in doc:
        print('doc[%s] =' % k, json.dumps(doc[k])[:300])
