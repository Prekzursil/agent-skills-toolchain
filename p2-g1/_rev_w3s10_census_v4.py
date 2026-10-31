"""Census v4 - CORRECT instruments.

For every catalog unit, at the CATALOG output_path:
  - exists / parses / state / reviewer-verdict fields
  - validate against the unit's OWN declared output_schema via the repo-blessed
    schema_resolver (NOT the receipt admission gate, which is receipt-class-only).
Cross-tab: green_closed = state==SUCCESS and reviewer PASS+independent.
           schema_ok    = resolver errors == []
           full_green   = green_closed AND schema_ok
"""
import json, sys, collections
from pathlib import Path

R = Path(r'C:\Users\Prekzursil\p2-g1')
sys.path.insert(0, str(R / 'platform' / 'lib'))
from schema_resolver import validate_artifact  # noqa: E402

catalog = json.load(open(R / 'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
units = catalog['work_units']
print('catalog total:', len(units), flush=True)

n_ok = n_missing = n_parse = 0
states = collections.Counter()
green_closed = []
schema_bad = []
not_green = []
reviewer_str = 0
full_green = []
for i, u in enumerate(units):
    uid = u['id']
    p = R / u['output_path']
    if not p.is_file() or p.stat().st_size == 0:
        n_missing += 1
        not_green.append((uid, 'artifact-missing'))
        continue
    n_ok += 1
    try:
        doc = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        n_parse += 1
        not_green.append((uid, 'unparseable'))
        continue
    st = str(doc.get('state', '')).upper()
    states[st] += 1
    rev = doc.get('reviewer')
    if isinstance(rev, str):
        reviewer_str += 1
        rev = {}
    rev = rev or {}
    closed = (st == 'SUCCESS' and rev.get('verdict') == 'PASS' and rev.get('independent') is True)
    try:
        errs = validate_artifact(doc, u.get('output_schema'))
    except Exception as e:
        errs = ['resolver-exception: ' + repr(e)]
    sok = not errs
    if not sok:
        schema_bad.append((uid, len(errs)))
    if closed:
        green_closed.append(uid)
        if not sok:
            pass
    else:
        not_green.append((uid, 'state=%s rev=%s/%s' % (st or '<empty>',
                         rev.get('verdict'), rev.get('independent'))))
    if closed and sok:
        full_green.append(uid)
    if (i + 1) % 250 == 0:
        print('  ...%d/%d scanned' % (i + 1, len(units)), flush=True)

print()
print('exists:', n_ok, '| missing/empty:', n_missing, '| parse-fail:', n_parse,
      '| reviewer-as-string:', reviewer_str)
print('state census:', dict(states))
print('closed-green (SUCCESS+PASS+independent):', len(green_closed))
print('schema-valid at output_path:', len(units) - len(schema_bad))
print('schema-INVALID:', len(schema_bad))
print('FULL GREEN (closed AND schema-valid):', len(full_green))
print()
print('schema-invalid list (first 40):', [u for u, _ in schema_bad[:40]])
json.dump({'full_green': full_green,
           'schema_bad': schema_bad,
           'not_green': not_green,
           'states': dict(states)},
          open(R / '_rev_w3s10_census_v4_results.json', 'w', encoding='utf-8'), indent=1)
print('WROTE _rev_w3s10_census_v4_results.json')
