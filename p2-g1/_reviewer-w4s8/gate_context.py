import json, os, subprocess, sys, random
os.chdir(os.path.expanduser('~/p2-g1'))
sib = ['ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','AUD-0003','AUD-0005','AUD-0008','AUD-0026','AUD-0032','AUD-0033','AUD-0042','AUD-0043','ADV-0127','ADV-0128','ARC-0047','ARC-0048','ARC-0054','ARC-0055','ARC-0056','ARC-0076']
others = ['ADV-0005','ADV-0010','ADV-0014','ADV-0018','IMP-0001','IMP-0004','TST-0018','TST-0028','RES-0004','REL-0001','BLD-0001','CNF-0077']
def run(uids):
    out = {}
    import collections
    for uid in uids:
        p = f'command-center/receipts/{uid}.json'
        if not os.path.exists(p):
            out[uid] = 'NO-RECEIPT'; continue
        r = subprocess.run([sys.executable, '-I', 'command-center/receipt_validate.py', p], capture_output=True, text=True)
        first = (r.stdout.strip().splitlines() or [''])[0]
        out[uid] = f"rc={r.returncode} {first[:60]}"
    return out
print('== sibling-closed (w4s2/w4s3) receipts:')
for uid, res in run(sib).items():
    print(' ', uid, res)
print('== random older sample:')
for uid, res in run(others).items():
    print(' ', uid, res)
