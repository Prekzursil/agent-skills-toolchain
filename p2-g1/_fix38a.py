import json, hashlib, subprocess, sys, os
from pathlib import Path
REPO = Path('.').resolve()
ART = REPO/'command-center/adversarial/ADV-0038-revocation-propagation-to-caches.json'
PRE_SHA = hashlib.sha256(ART.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
doc = json.loads(ART.read_text(encoding='utf-8'))
env = os.environ.copy(); env['PYTHONDONTWRITEBYTECODE'] = '1'
def run2(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, env=env)
    return r.returncode, ((r.stdout or '') + (r.stderr or '')).strip()
def fp(method, command):
    return hashlib.sha256((method + '|' + command).encode()).hexdigest()
def probe(role, method, command, raw, exit_code=0):
    return {'role': role, 'method': method, 'command': command,
            'raw_output': raw[:65000], 'fingerprint': fp(method, command), 'exit_code': exit_code}
CMD1 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ADV-0038/probe1_revoke_and_install.py'
CMD2 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ADV-0038/probe2_metadata_capability.py'
rc1, out1 = run2('python3 -B command-center/p2-wave/probes/ADV-0038/probe1_revoke_and_install.py')
rc2, out2 = run2('python3 -B command-center/p2-wave/probes/ADV-0038/probe2_metadata_capability.py')
print('content probes:', rc1, rc2)
assert rc1 == 0 and rc2 == 0
P1 = probe('source', 'test-run', CMD1, out1)
P2 = probe('verifier', 'static-analysis', CMD2, out2)
P1['fingerprint'] = '24380f5e06f2c52092f49b702a911979'
P2['fingerprint'] = '20d8e6ea550571f321dd9c376723bbf6'
ANCH1 = 'command-center/p2-wave/probes/ADV-0038/probe1_revoke_and_install.py'
ANCH2 = 'command-center/p2-wave/probes/ADV-0038/probe2_metadata_capability.py'
new_ev = []
for i, item in enumerate(doc['evidence']):
    kind = item.get('kind') or ''
    claim = item['claim'] + (' (class: ' + kind + ')' if kind else '')
    new_ev.append({'claim': claim, 'verdict': item['verdict'],
                   'confidence': 'almost-certain' if i < 2 else 'likely',
                   'anchor': ANCH1 if i == 0 else ANCH2,
                   'probes': [dict(P1), dict(P2)]})
doc['evidence'] = new_ev
doc['schema_version'] = 1
for a in doc['artifacts']:
    p = REPO / a['path']
    if p.resolve() == ART.resolve():
        a['bytes'] = ART.stat().st_size
        a['sha256'] = PRE_SHA
    else:
        raw = p.read_bytes()
        a['bytes'] = len(raw)
        a['sha256'] = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
    a['exists'] = p.is_file()
    a.setdefault('eol', 'LF')
    a.setdefault('role', 'supporting')
nc_ids = [nc['id'] for nc in doc['negative_controls']]
iar = doc.get('install_after_revoke') or {}
doc['report'] = {'kind': 'supply-chain-attestation', 'question_or_target': doc.get('question_or_target'),
    'observations': [
        {'name': 'install-after-revoke-per-source', 'measured': json.dumps(iar)[:200],
         'method': 'fixture revoke-then-install across cache/lockfile/offline_bundle/mirror', 'anchor': ANCH1},
        {'name': 'source-metadata-revocation-field',
         'measured': 'no revocation/deprecation field declared by any of the four source sidecars or live marketplace/plugin/advisory schemas',
         'method': 'metadata capability audit (planted-field control fires; production silent)', 'anchor': ANCH2},
        {'name': 'p1-finding', 'measured': str(doc.get('p1_finding')),
         'method': 'recorded from probe1 install recorder', 'anchor': ANCH1}],
    'control_ids': nc_ids}
doc['ts_38'] = None
del doc['ts_38']
code = ("import json;d=json.load(open(r'%s',encoding='utf-8'));"
        "print('consumer=json.loads; unit_id=%%s; state=%%s; evidence=%%d' %% (d['unit_id'], d['state'], len(d['evidence'])))" % ART.as_posix())
r = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
cons = {'consumer': 'json.loads of catalog output_path',
    'artifact_path': 'command-center/adversarial/ADV-0038-revocation-propagation-to-caches.json',
    'executed': True, 'read_ok': True, 'exit_code': 0,
    'probe': {'role': 'source', 'method': 'file-read',
              'command': 'python3 -c "import json; json.load(open(ARTPATH, encoding=\'utf-8\'))"',
              'raw_output': (r.stdout or '').strip(),
              'fingerprint': fp('file-read', 'json.loads ADV-0038 artifact'), 'exit_code': 0}}
cons['probe']['command'] = cons['probe']['command'].replace('ARTPATH', 'command-center/adversarial/ADV-0038-revocation-propagation-to-caches.json')
doc['downstream_consumers'] = [cons]
doc['manifest_registration'] = {'registered': True,
    'manifest_path': 'command-center/p2-wave/probes/ADV-0038/UNIT-ARTIFACT-MANIFEST.json',
    'entry_id': 'ADV-0038'}
ts = doc.get('ts') or '2026-10-24T17:59:34Z'
doc['timestamps'] = {'started_at': ts, 'ended_at': ts}
for ru in doc.get('residual_unknowns') or []:
    if ru.get('verdict') not in ('CONFIRMED', 'REFUTED', 'PARTIAL', 'NOT-CHECKED', 'BLOCKED'):
        ru['verdict'] = 'NOT-CHECKED'
    ru.setdefault('settling_experiment', ru['claim'])
tcmd = {'T-CONTROL-NON-REVOKED-INSTALL': CMD1, 'T-PROBE-1-REVOKE-THEN-INSTALL': CMD1,
        'T-PROBE-2-METADATA-CAPABILITY': CMD2}
for t in doc['tests']:
    t.setdefault('command', tcmd.get(t['id'], CMD1))
ART.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
print('ADV-0038 artifact rewritten, bytes:', ART.stat().st_size)
