import sys, json
sys.path.insert(0, 'C:/Users/Prekzursil/p2-g1/platform/lib')
from schema_resolver import validate_artifact
REPO = 'C:/Users/Prekzursil/p2-g1/'
doc = json.load(open(REPO + 'command-center/audit/AUD-0095-freeze-inventory.json', encoding='utf-8'))
stub = [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True,
         'read_ok': True, 'exit_code': 0,
         'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub',
                   'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]
errs = validate_artifact({**doc, 'downstream_consumers': stub},
                         'command-center/schema/audit-inventory.schema.json')
print('error count:', len(errs))
for e in errs:
    print(' -', e)
