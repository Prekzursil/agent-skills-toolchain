import hashlib
import json
import pathlib
import sys

PROBE = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\WFA-0058')
sys.path.insert(0, str(PROBE))
import corpus as C  # noqa: E402
import mapper as M  # noqa: E402

data = C.load_corpus()
rows = data['rows']
assert len(rows) == 337, len(rows)

table = []
for row in rows:
    got = M.map_one(row['text'])
    table.append({
        "from": row["source"],
        "gap": bool(got["gap"]),
        "kind": row["kind"],
        "rule": got["rule"],
        "source_string": row["text"],
        "vocab_id": got["vocab_id"],
    })

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\wfa\WFA-0058-mechanism-vocabulary.json')
orig = art.read_text(encoding='utf-8')
doc = json.loads(orig)
assert json.dumps(doc, indent=1, ensure_ascii=False) + '\n' == orig

# find any stale references to the old count 58 near mapping summary fields
def walk(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, f'{path}.{k}')
    elif isinstance(node, list):
        pass
    elif node == 58 and isinstance(node, int) and not isinstance(node, bool):
        print('int58 at', path)

walk(doc)
old_n = len(doc.get('mapping_table') or [])
print('replacing mapping_table', old_n, '->', len(table))
doc['mapping_table'] = table

# refresh corpus provenance fields if present
for key in ('corpus_origin', 'corpus'):
    if key in doc:
        print('doc has', key, '=', json.dumps(doc[key])[:200])

out = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
art.write_text(out, encoding='utf-8', newline='\n')
d2 = json.loads(art.read_text(encoding='utf-8'))
assert len(d2['mapping_table']) == 337
assert 'SUCCESS:WFA-0058' in art.read_text(encoding='utf-8')
b = art.read_bytes().replace(b'\r\n', b'\n')
print('sha256', hashlib.sha256(b).hexdigest(), 'bytes', len(b))
