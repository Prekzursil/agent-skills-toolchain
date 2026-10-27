import json
import os
import collections

jpath = r'C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/13dd0812-e887-4a76-9d0e-4c6e6d30a937/subagents/workflows/wf_a81de287-702/journal.jsonl'
entries = [json.loads(l) for l in open(jpath, encoding='utf-8') if l.strip()]
started = {}
for e in entries:
    if e.get('type') == 'started':
        started[e['key']] = e.get('label')

# results in JOURNAL (completion) order, mapped to labels
res_order = []
seen = set()
for e in entries:
    if e.get('type') == 'result' and e.get('key'):
        lab = started.get(e['key'])
        if lab and lab not in seen:
            seen.add(lab)
            res_order.append((lab, e.get('result')))

S10 = ['IMP-0305','IMP-0306','IMP-0311','IMP-0323','IMP-0324','IMP-0329','IMP-0330','IMP-0332','IMP-0333','IMP-0338','IMP-0350','IMP-0355']

def built_ids_in_journal_order(wave):
    out = []
    for lab, r in res_order:
        if lab.startswith('build:w%d' % wave):
            for u in (r or {}).get('units', []):
                if u.get('state') == 'built-awaiting-review':
                    out.append(u['id'])
    return out

w1b = built_ids_in_journal_order(1)
w2b = built_ids_in_journal_order(2)
w3b = built_ids_in_journal_order(3)
print('w1 built (journal order):', len(w1b), w1b[:15])
print('w2 built (journal order):', len(w2b), w2b[:10])
print('w3 built (journal order):', len(w3b), w3b[:10])

pending = S10[:]
for uid in w1b + w2b + w3b:
    if uid not in pending:
        pending.append(uid)
print('pendingReview length:', len(pending), '-> shards:', (len(pending) + 11) // 12)

sib = json.load(open(r'C:/Users/Prekzursil/p2-g1/_reviewer_w3_sibling_assignments.json', encoding='utf-8'))
# also pin s14/s15 from the path-extraction (they had exact 12/9-clean lists)
sib['w3s14'] = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468','IMP-0470']
sib['w3s15'] = ['IMP-0478','REL-0001','REL-0006','REL-0014','REL-0017','REL-0020','REL-0021','REL-0022','RES-0004','RES-0009','RES-0011','RES-0020']

ok = True
for si in range(18):
    lo, hi = si * 12, si * 12 + 12
    got = pending[lo:hi]
    exp = sib.get('w3s%d' % si)
    if exp is None:
        print(f'w3s{si}: (unrecovered sibling) slice =', got)
        continue
    if sorted(got) == sorted(exp):
        print(f'w3s{si}: MATCH (order may differ)')
    else:
        ok = False
        print(f'w3s{si}: MISMATCH')
        print('   reconstructed:', got)
        print('   sibling actual:', exp)

json.dump(pending, open(r'C:/Users/Prekzursil/p2-g1/_reviewer_w3s10_pending_hypothesis.json', 'w'), indent=1)
print('ALL MATCH:', ok)
print('shard 10 slice:', pending[120:132])
