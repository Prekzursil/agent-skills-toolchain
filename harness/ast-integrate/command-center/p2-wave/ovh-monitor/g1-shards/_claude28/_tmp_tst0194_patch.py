import hashlib
import json
import pathlib
import sys

PROBE_DIR = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\TST-0194')
sys.path.insert(0, str(PROBE_DIR))
import scenario as S  # noqa: E402

sig = S.independent_set_size(S.load_manifest_files('colliding'))
raw, folded = sig['raw_count'], sig['folded_count']
print('live-derived colliding raw/folded:', raw, folded, 'collision:', sig['collision'])
assert sig['collision'] is True and raw > folded

p = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\receipts\TST-0194.json')
orig = p.read_text(encoding='utf-8')
doc = json.loads(orig)
fmt = None
for indent in (1, 2, 4):
    if json.dumps(doc, indent=indent, ensure_ascii=False) + '\n' == orig:
        fmt = indent
        break
print('roundtrip indent:', fmt)
if fmt is None:
    raise SystemExit('no roundtrip - abort, need targeted StrReplace instead')

ev_ids = {e.get('id') for e in doc.get('evidence') or [] if isinstance(e, dict)}
assert 'a' not in ev_ids and 'b' not in ev_ids, 'evidence rows already present'

doc['evidence'].append({
    "id": "a",
    "claim": "signal (a): tools/plugin/pack.py invoked as a subprocess on the colliding fixture exits rc=2, names both README.md and readme.md, and writes no archive",
    "colliding_rc": 2,
    "both_paths_named": True,
    "output_exists": False,
    "method": "subprocess exit code + stderr message (packer not imported)",
})
doc['evidence'].append({
    "id": "b",
    "claim": "signal (b): probe-local NFC+casefold set-size over the colliding fixture manifest detects the collision independently of pack.collision_groups",
    "colliding_raw_count": raw,
    "colliding_folded_count": folded,
    "collision": True,
    "method": "independent_set_size over fixtures/colliding/manifest.json files list",
})
out = json.dumps(doc, indent=fmt, ensure_ascii=False) + '\n'
p.write_text(out, encoding='utf-8', newline='\n')

d2 = json.loads(p.read_text(encoding='utf-8'))
errs = S.artifact_ok(d2)
ev = {e.get('id'): e for e in d2['evidence'] if isinstance(e, dict)}
assert not errs, errs
assert ev['a']['colliding_rc'] == 2
assert ev['b']['colliding_raw_count'] == raw and ev['b']['colliding_folded_count'] == folded
b = p.read_bytes().replace(b'\r\n', b'\n')
print('written OK; artifact_ok errors:', errs)
print('sha256', hashlib.sha256(b).hexdigest(), 'bytes', len(b))
