import sys, tempfile, json, hashlib
sys.path.insert(0, '.')
from pathlib import Path
from tools.marketplace.index_linter import lint_index, reference_graph

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    (base / 'blobs').mkdir()
    good = b'good blob'
    (base / 'blobs' / 'a.bin').write_bytes(good)
    (base / 'blobs' / 'orphan.bin').write_bytes(b'nobody references me')
    dig = hashlib.sha256(good.replace(b'\r\n', b'\n')).hexdigest()
    idx = {
        'packages': [
            {'id': 'p@1', 'blob': 'blobs/a.bin', 'digest': 'f' * 64, 'dependencies': ['q@1']},
            {'id': 'p@1', 'blob': 'blobs/missing.bin', 'digest': '0' * 64, 'dependencies': ['ghost@1']},
        ]
    }
    (base / 'index.json').write_text(json.dumps(idx))
    f = lint_index(base, idx)
    codes = sorted(x['code'] for x in f)
    print('codes:', codes)
    expect = ['DANGLING_BLOB', 'DUPLICATE_ID', 'DIGEST_MISMATCH', 'ORPHAN_BLOB', 'UNRESOLVED_DEPENDENCY']
    assert sorted(set(codes)) == expect, codes
    g = reference_graph(index=idx, root=base)
    print('graph dangling:', sorted(g['dangling']), '| orphan:', sorted(g['orphan']), '| unresolved:', sorted(g['unresolved_deps']))
    assert g['dangling'] == {'blobs/missing.bin'} and g['orphan'] == {'blobs/orphan.bin'}
    idx2 = {'packages': [{'id': 'p@1', 'blob': 'blobs/a.bin', 'digest': dig}]}
    (base / 'index.json').write_text(json.dumps(idx2))
    f2 = lint_index(base, idx2)
    print('clean-control:', [x['code'] for x in f2])
    assert f2 == []
print('SMOKE-LINTER OK')
