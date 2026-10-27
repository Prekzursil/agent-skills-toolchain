import json, os
ids = ['AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075','AUD-0080']
for i in ids:
    rp = f'command-center/receipts/{i}.json'
    if not os.path.isfile(rp):
        print(i, 'RECEIPT-MISSING'); continue
    r = json.load(open(rp, encoding='utf-8'))
    out = {
        'state': r.get('state'),
        'failure': r.get('failure'),
        'reviewer': r.get('reviewer'),
        'notes': str(r.get('notes') or '')[:150],
        'keys': sorted(r.keys()),
    }
    print(i, json.dumps(out)[:600])
