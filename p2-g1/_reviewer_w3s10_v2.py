import json

jpath = r'C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/13dd0812-e887-4a76-9d0e-4c6e6d30a937/subagents/workflows/wf_a81de287-702/journal.jsonl'
entries = [json.loads(l) for l in open(jpath, encoding='utf-8') if l.strip()]
started = {}
last_result = {}
for e in entries:
    if e.get('type') == 'started':
        started[e['key']] = e.get('label')
    elif e.get('type') == 'result' and e.get('key'):
        last_result[e['key']] = e.get('result')

res_by_label = {}
for k, r in last_result.items():
    lab = started.get(k)
    if lab:
        res_by_label[lab] = r

w2_review = {}
for si in range(26):
    r = res_by_label.get('review:w2s%d' % si)
    if r:
        for u in r.get('units', []):
            w2_review[u['id']] = u

w1_review = {}
for si in range(8):
    r = res_by_label.get('review:w1s%d' % si)
    if r:
        for u in r.get('units', []):
            w1_review[u['id']] = u

w3_built = {}
for si in range(24):
    r = res_by_label.get('build:w3s%d' % si)
    if r:
        for u in r.get('units', []):
            if u.get('state') == 'built-awaiting-review':
                w3_built[u['id']] = u

print('w1 reviewed:', len(w1_review), '| w2 reviewed:', len(w2_review), '| w3 built:', len(w3_built))

pending3 = set(w2_review) - set(w1_review)
print('pending3 (w2 minus w1-reviewed):', len(pending3))
pending3 |= set(w3_built)
print('pending3 final:', len(pending3), '-> shards:', (len(pending3) + 11) // 12)

s3 = sorted(pending3)
sib = json.load(open(r'C:/Users/Prekzursil/p2-g1/_reviewer_w3_sibling_assignments.json', encoding='utf-8'))
sib['w3s14'] = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468','IMP-0470']
sib['w3s15'] = ['IMP-0478','REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021','REL-0022','RES-0004','RES-0009','RES-0011','RES-0020']

allmatch = True
for si in range(18):
    exp = sib.get('w3s%d' % si)
    got = s3[si * 12:(si + 1) * 12]
    if exp is None:
        print('w3s%d: unrecovered; slice = %s' % (si, got))
        continue
    match = sorted(got) == sorted(exp)
    allmatch = allmatch and match
    print('w3s%d: %s' % (si, 'MATCH' if match else 'MISMATCH'))
    if not match:
        print('   slice :', got)
        print('   actual:', exp)

print('ALL MATCH:', allmatch)
print()
print('w3s10 (MINE) =', s3[120:132])
