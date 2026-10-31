import json
import sys

s = json.load(open('platform/schema/artifact-class-profiles.schema.json', encoding='utf-8'))
defs = s.get('$defs') or {}
print('top keys:', list(s.keys()))
print('defs:', list(defs.keys())[:20])
d = defs.get('supply-chain-attestation') or {}
print('required:', d.get('required'))
print('props:', sorted((d.get('properties') or {}).keys()))
props = d.get('properties') or {}
for key in ('artifacts', 'evidence', 'schema_version', 'named_probes'):
    if key in props:
        print(f'--- {key}:', json.dumps(props[key], indent=1)[:900])
