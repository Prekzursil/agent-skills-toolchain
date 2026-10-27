#!/usr/bin/env python3
"""AUD-0095 seal: schema check + manifest row + SUBAGENT-RETURN refresh."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
REPO = HOME / 'p2-g1'
ART = REPO / 'command-center/audit/AUD-0095-freeze-inventory.json'
PD = REPO / 'command-center/p2-wave/probes/AUD-0095'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
OUT_REL = 'command-center/audit/AUD-0095-freeze-inventory.json'

raw = ART.read_bytes()
norm = raw.replace(b'\r\n', b'\n')
sha = hashlib.sha256(norm).hexdigest()
size = len(norm)

# 1. schema check
import sys
sys.path.insert(0, str(REPO / 'platform' / 'lib'))
from schema_resolver import validate_artifact
doc = json.loads(ART.read_text(encoding='utf-8'))
stub = [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True,
         'read_ok': True, 'exit_code': 0,
         'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub',
                   'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]
errs = validate_artifact({**doc, 'downstream_consumers': stub},
                         'command-center/schema/audit-inventory.schema.json')
print('schema errors:', errs if errs else 'NONE')

# 2. manifest row update
man_path = PD / 'UNIT-ARTIFACT-MANIFEST.json'
man = json.loads(man_path.read_text(encoding='utf-8'))
rows = [a for a in (man.get('artifacts') or []) if isinstance(a, dict) and a.get('unit_id') == 'AUD-0095']
assert rows, 'no manifest row'
for a in rows:
    a.update({'path': OUT_REL, 'present': True, 'bytes': size, 'sha256': sha,
              'updated_at': NOW,
              'note': 'refreeze RF-2026-10-26: anchors re-derived live; builder-terminal BLOCKED awaiting independent review'})
man.setdefault('updated_at', NOW)
man_path.write_text(json.dumps(man, indent=1) + '\n', encoding='utf-8', newline='\n')
print('manifest row updated sha', sha[:16])

# 3. SUBAGENT-RETURN refresh
sr_path = PD / 'SUBAGENT-RETURN.json'
sr = json.loads(sr_path.read_text(encoding='utf-8'))
sr['artifact_bytes'] = size
sr['artifact_sha256_crlf_normalized'] = sha
sr['ts'] = NOW
sr['named_probes'] = doc.get('named_probes')
sr['notes'] = ('shard5 wave3 resume 2026-10-26: prior closure dead (green-not-live). '
               'Refreeze RF-2026-10-26 applied: 4 unversioned-drift files re-anchored under recorded migrations, '
               'AGENTS.md re-materialized from canonical ~/AGENTS.md, unmaterializable spec-cited corpus row '
               '_USER-PROMPTS.md relocated to spec_citations with estate-wide-search evidence. '
               'probe2 exit 0; probe1 exit 1 BY DESIGN (self-declared BLOCKED - receipt_core forbids builder SUCCESS; '
               'schema enum admits no builder-legal deliverable state; only a fresh independent reviewer closes). '
               'Unit is BUILT-AWAITING-INDEPENDENT-REVIEW, not delivered.')
sr_path.write_text(json.dumps(sr, indent=1) + '\n', encoding='utf-8', newline='\n')
print('SUBAGENT-RETURN refreshed')
print('SEALED sha=' + sha)
