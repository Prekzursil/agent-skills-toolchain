import json, glob, os, re
base = r'C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\13dd0812-e887-4a76-9d0e-4c6e6d30a937\subagents\workflows\wf_a81de287-702'
mine = ['TST-0206','TST-0215','TST-0219','TST-0221','TST-0223','TST-0227','TST-0230','TST-0233']
# check every review:w3sN result summary for mentions of my units
meta = {}
for f in glob.glob(os.path.join(base, 'agent-*.meta.json')):
    aid = os.path.basename(f)[6:-10]
    meta[aid] = json.load(open(f, encoding='utf-8')).get('description', '')
recs = [json.loads(l) for l in open(os.path.join(base, 'journal.jsonl'), encoding='utf-8')]
results = {}
for r in recs:
    if r.get('type') == 'result':
        results[r['agentId']] = r.get('result')
nrev = 0
for aid, lab in sorted(meta.items()):
    if lab and lab.startswith('review:w3s'):
        nrev += 1
        res = results.get(aid)
        if res is None:
            print(lab, aid, '-> NULL RESULT (failed)')
            continue
        s = json.dumps(res)
        hits = [u for u in mine if u in s]
        summ = (res.get('summary') or '')[:260].replace('\n', ' ')
        print(lab, aid, '| mine-hit:', hits or '-')
        print('   ', summ)
print('reviewer agents total:', nrev)
