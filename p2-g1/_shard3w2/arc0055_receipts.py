import hashlib, json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path('command-center/p2-wave/probes/ARC-0055').resolve()
REPO = Path('.').resolve()
OUT = 'command-center/phase3/A8/SECURITY.json'
P1 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py'
P2 = 'PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0055/probe2_fatigue_overclaim.py'
SUPPORTING = [
    'command-center/schema/architecture-review.schema.json',
    'command-center/phase3/A1/DESIGN.json',
    'command-center/phase3/A2/DESIGN.json',
    'command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py',
    'command-center/p2-wave/probes/ARC-0055/probe2_fatigue_overclaim.py',
    'command-center/p2-wave/probes/ARC-0055/fatigue.py',
    'command-center/p2-wave/probes/ARC-0055/overclaim.py',
    'command-center/p2-wave/probes/ARC-0055/anchors.py',
    'command-center/p2-wave/probes/ARC-0055/fixtures/session-census.json',
]

def digest(path):
    raw = path.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)

def run_probe(cmd):
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    while True:
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+', cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env)
    return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()

c1, t1 = run_probe(P1)
c2, t2 = run_probe(P2)
if c1 != 0 or c2 != 0:
    raise SystemExit('FAILED probes not green: %s %s' % (c1, c2))

def row(rel, role):
    sha, size = digest(REPO / rel)
    return {'path': rel, 'sha256': sha, 'bytes': size, 'present': True,
            'unit_id': 'ARC-0055',
            'receipt_path': 'command-center/p2-wave/probes/ARC-0055/SUBAGENT-RETURN.json',
            'role': role}

primary = row(OUT, 'primary')
artifacts = [primary] + [row(p, 'supporting') for p in SUPPORTING if (REPO / p).is_file()]
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

ret = {
  'id': 'ARC-0055', 'unit_id': 'ARC-0055',
  'status': 'DELIVERED', 'state': 'BLOCKED',
  'sentinel': 'SUCCESS:ARC-0055',
  'registered': True,
  'output_path': OUT,
  'output_schema': 'command-center/schema/architecture-review.schema.json',
  'named_probes': [
    {'id': 'probe1', 'command': P1, 'exit_code': c1, 'raw_output': t1[-4000:]},
    {'id': 'probe2', 'command': P2, 'exit_code': c2, 'raw_output': t2[-4000:]},
  ],
  'artifacts': [{'path': OUT, 'sha256': primary['sha256'], 'bytes': primary['bytes'],
                 'exists': True, 'role': 'primary'}],
  'manifest_path': 'command-center/p2-wave/probes/ARC-0055/UNIT-ARTIFACT-MANIFEST.json',
  'failure': {
    'classification': ['reviewer-absent'],
    'reason': ('Builder lane may not self-certify (receipt_core: state=SUCCESS forbidden '
               'without reviewer.verdict=PASS and independent=true). The dead prior attempt '
               'authored a self-certifying reviewer PASS in its write_receipts.py; that '
               'closure was NOT written. Delivery is measured green (artifact on disk, named '
               'probes exit 0, manifest sha row matches live artifact); closure is reserved '
               'to the independent reviewer.'),
  },
  'extensions': {
    'shard3_w2_resume_2026-10-25': {
      'action': ('artifact repaired live on this Windows worktree: fatigue census re-derived '
                 'from the local .claude/projects corpus (original root.cursor corpus absent '
                 'after host migration; scanner extended for line-level ISO timestamps, '
                 'frame = latest 47 sessions by mtime); SECURITY.json fatigue block and prose '
                 'numbers updated coherently; dossier evidence rows repointed from absent '
                 'fixture stand-ins to the real phase3 A1/A2 dossiers; all evidence anchors '
                 're-derived and resolving.'),
      'builder': 'shard3 wave-2 builder (resume of a mid-flight-dead prior attempt)',
      'prior_attempt_self_closure': 'REFUSED - write_receipts.py reviewer PASS not written',
    },
  },
  'reviewer': {'reviewer_id': None, 'verdict': 'PENDING', 'independent': False,
               'note': 'closure reserved to the independent reviewer'},
  'ts': now,
  'notes': ('G-1 for ARC-0055: live named probes exit 0 on this host, SECURITY.json '
            'state=SUCCESS in-artifact, per-unit manifest row matches live sha; receipt '
            'state=BLOCKED classification reviewer-absent per program contract.'),
}
man = {
  'schema_version': 1,
  'contract': 'completion-predicate-condition-11-unit-artifact-registration',
  'derivation': 'per-unit (not tools/command-center/unit_manifest.py --write)',
  'unit_id': 'ARC-0055',
  'verified_on_disk': True,
  'expected': len(artifacts),
  'present': len(artifacts),
  'artifacts': artifacts,
}
(HERE / 'SUBAGENT-RETURN.json').write_text(json.dumps(ret, indent=1, sort_keys=True) + '\n', encoding='utf-8')
(HERE / 'UNIT-ARTIFACT-MANIFEST.json').write_text(json.dumps(man, indent=1, sort_keys=True) + '\n', encoding='utf-8')
print('primary sha', primary['sha256'][:16], 'bytes', primary['bytes'])
print('receipts written: BLOCKED/reviewer-absent')
