import json
from pathlib import Path
mine = ['ARC-0055','ARC-0056','ARC-0076','AUD-0003','AUD-0005','AUD-0008','AUD-0010','AUD-0026','AUD-0032','AUD-0033','AUD-0042','AUD-0043']
for uid in mine:
    p = Path('command-center/receipts')/(uid+'.json')
    r = json.loads(p.read_text(encoding='utf-8'))
    f = r.get('failure') if isinstance(r.get('failure'), dict) else {}
    rev = r.get('reviewer') if isinstance(r.get('reviewer'), dict) else {}
    print(uid, '| state=%s' % r.get('state'), '| cls=%s' % json.dumps(f.get('classification')), '| rev.verdict=%s' % rev.get('verdict'), '| rev.independent=%s' % rev.get('independent'), '| notes=%s' % json.dumps(r.get('notes'))[:160])
