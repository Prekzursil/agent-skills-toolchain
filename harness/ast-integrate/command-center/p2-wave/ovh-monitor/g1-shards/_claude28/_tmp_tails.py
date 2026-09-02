import json
import pathlib

spec = json.loads(pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_claude28\shard-10.spec.json').read_text(encoding='utf-8'))
want = {"WFA-0058", "CNF-0061", "CNF-0110", "BLD-0047", "IMP-0023", "IMP-0078", "IMP-0116", "IMP-0224", "TST-0068", "TST-0155", "TST-0273"}
rows = spec.get('failing') or spec.get('units') or spec
if isinstance(rows, dict):
    rows = rows.get('failing') or rows.get('units') or []
for r in rows:
    if r.get('id') in want:
        print('====', r['id'], '| cls:', r.get('cls'))
        print((r.get('tail') or '')[-700:])
        print()
