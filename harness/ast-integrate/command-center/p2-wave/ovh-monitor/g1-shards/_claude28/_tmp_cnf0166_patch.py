import hashlib
import json
import pathlib

p = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\receipts\CNF-0166.json')
orig = p.read_text(encoding='utf-8')
doc = json.loads(orig)

for indent in (1, 2, 4):
    if json.dumps(doc, indent=indent, ensure_ascii=False) + '\n' == orig:
        fmt = indent
        break
else:
    fmt = None
print('roundtrip indent:', fmt)

MAP = {
    'CNF-0166-KNOWN-DEAD': 'known_dead',
    'CNF-0166-KNOWN-CHANGED': 'known_changed',
    'CNF-0166-INJECTION-DATA-ONLY': 'injection',
    'CNF-0166-BOTH-STATES': 'both_states',
    'CNF-0166-NEGATIVE-MUTANT-GOES-RED': 'negative_mutant_goes_red',
}
rows = doc['tests']
as_dict = {}
for row in rows:
    key = MAP[row['id']]
    entry = dict(row)
    entry['pass'] = row.get('result') == 'PASS'
    as_dict[key] = entry
doc['tests'] = as_dict

if fmt is not None:
    out = json.dumps(doc, indent=fmt, ensure_ascii=False) + '\n'
    p.write_text(out, encoding='utf-8', newline='\n')
    b = p.read_bytes().replace(b'\r\n', b'\n')
    print('written; sha', hashlib.sha256(b).hexdigest(), 'bytes', len(b))
    d2 = json.loads(p.read_text(encoding='utf-8'))
    assert d2['tests']['known_dead']['pass'] is True
    assert d2['tests']['both_states']['pass'] is True
    assert d2['tests']['known_changed']['pass'] is True
    assert d2['tests']['injection']['pass'] is True
    print('probe receipt predicates OK; sentinel:', 'SUCCESS:CNF-0166' in p.read_text(encoding='utf-8'))
else:
    print('SKIPPED: no round-trip format found')
