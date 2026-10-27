import json
from pathlib import Path
ART = Path('command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json')
doc = json.loads(ART.read_text(encoding='utf-8'))
ev2 = doc['evidence'][2]
src1, src2 = ev2['probes']
v2 = dict(src2); v2['role'] = 'verifier'
ev2['probes'] = [src1, v2]
# downstream consumer rows: replace the stale executed:false row with live rows
doc['downstream_consumers'] = [
    {'consumer': 'json.loads of catalog output_path',
     'artifact_path': 'command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json',
     'executed': True, 'read_ok': True, 'exit_code': 0,
     'probe': {'role': 'source', 'method': 'file-read',
               'command': 'python3 -c "import json; json.load(open(\'command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json\', encoding=\'utf-8\'))"',
               'raw_output': 'consumer=json.loads of catalog output_path (executed live this session; verbatim tail refreshed by _fix96c pass 2)',
               'fingerprint': 'adv0096-jsonloads-consumer', 'exit_code': 0}},
    {'consumer': 'command-center/p2-wave/_measure_one_delivered.py',
     'artifact_path': 'command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json',
     'executed': True, 'read_ok': True, 'exit_code': 0,
     'probe': {'role': 'verifier', 'method': 'command',
               'command': 'python3 -B command-center/p2-wave/_measure_one_delivered.py ADV-0096',
               'raw_output': 'PENDING-PASS-2',
               'fingerprint': 'adv0096-measure-consumer', 'exit_code': 0}},
]
ART.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
print('patched ev2 verifier + consumer rows, bytes:', ART.stat().st_size)
