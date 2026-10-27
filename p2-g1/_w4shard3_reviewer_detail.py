import json
from pathlib import Path
for uid in ['AUD-0033','AUD-0043']:
    ret = json.loads(Path(f'command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json').read_text(encoding='utf-8'))
    print(f'=== {uid} ts={ret.get("ts")}')
    print('reviewer:', json.dumps(ret.get('reviewer'), ensure_ascii=False))
    print('notes:', str(ret.get('notes'))[:400])
