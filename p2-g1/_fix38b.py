import json
from pathlib import Path
ART = Path('command-center/adversarial/ADV-0038-revocation-propagation-to-caches.json')
doc = json.loads(ART.read_text(encoding='utf-8'))
kinds = {'NC-NON-REVOKED-STILL-INSTALLS': 'known-broken-fixture',
         'NC-PLANTED-REVOCATION-FIELD': 'adversarial-payload',
         'NC-HONOURING-MUTANT': 'mutation'}
for nc in doc['negative_controls']:
    nc['kind'] = kinds.get(nc['id'], 'other')
if 'vendor' in doc.get('reviewer', {}):
    del doc['reviewer']['vendor']  # non-registry token; notes already disclose the mechanical-verifier nature
ART.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
print('patched NC kinds + reviewer.vendor, bytes:', ART.stat().st_size)
