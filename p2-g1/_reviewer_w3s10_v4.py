import glob
import json

jpath = glob.glob(r'C:/Users/Prekzursil/.claude/projects/*/*/subagents/workflows/wf_a81de287-702/journal.jsonl')[0]
entries = [json.loads(l) for l in open(jpath, encoding='utf-8') if l.strip()]
started = {}
last = {}
for e in entries:
    if e.get('type') == 'started':
        started.setdefault(e['key'], e.get('label'))
    elif e.get('type') == 'result' and e.get('key'):
        last[e['key']] = e.get('result')
by_label = {}
for k, r in last.items():
    lab = started.get(k)
    if lab:
        by_label[lab] = r

S10 = ['IMP-0305','IMP-0306','IMP-0311','IMP-0323','IMP-0324','IMP-0329','IMP-0330',
       'IMP-0332','IMP-0333','IMP-0338','IMP-0350','IMP-0355']

w3b = []
added = set(S10)
for si in range(24):
    r = by_label.get('build:w3s%d' % si)
    for u in (r or {}).get('units', []):
        uid = u['id']
        if u.get('state') == 'built-awaiting-review' and uid not in added:
            added.add(uid)
            w3b.append(uid)

pending = S10 + w3b
print('pending:', len(pending), '-> shards:', (len(pending) + 11) // 12)

sib = json.load(open(r'C:/Users/Prekzursil/p2-g1/_reviewer_w3_sibling_assignments.json', encoding='utf-8'))
sib['w3s14'] = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468','IMP-0470']
sib['w15'] = None
sib['w3s15'] = ['IMP-0478','REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021','REL-0022','RES-0004','RES-0009','RES-0011','RES-0020']

allmatch = True
for si in range(18):
    got = pending[si * 12:(si + 1) * 12]
    exp = sib.get('w3s%d' % si)
    if exp is None:
        print('w3s%d: unrecovered; slice = %s' % (si, got))
        continue
    match = sorted(got) == sorted(exp)
    allmatch = allmatch and match
    print('w3s%d: %s' % (si, 'MATCH' if match else 'MISMATCH'))
    if not match:
        print('   reconstructed:', got)
        print('   sibling actual:', exp)

print('ALL MATCH:', allmatch)
print()
print('w3s10 (MINE) =', pending[120:132])
