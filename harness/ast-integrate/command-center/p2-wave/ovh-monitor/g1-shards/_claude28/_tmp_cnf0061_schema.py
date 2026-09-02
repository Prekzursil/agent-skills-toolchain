import json
import pathlib
import sys

PROBE = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\CNF-0061')
sys.path.insert(0, str(PROBE))
import schema_local as S  # noqa: E402

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\confirmation\CNF-0061-coverage-line-delta.json')
doc = json.loads(art.read_text(encoding='utf-8'))
e_doc = S.errors(doc)
print('artifact errors:', e_doc[:3], 'n=', len(e_doc))
for i, garbage in enumerate(({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000})):
    e = S.errors(garbage)
    print(f'garbage[{i}] rejected:', bool(e), 'n_errors=', len(e))
print('sentinel:', 'SUCCESS:CNF-0061' in art.read_text(encoding='utf-8'), 'unit_id:', doc.get('unit_id'))
