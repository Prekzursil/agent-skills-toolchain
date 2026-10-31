import json, glob, os

WF = r'C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\13dd0812-e887-4a76-9d0e-4c6e6d30a937\subagents\workflows\wf_a81de287-702'

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def structured_output(jsonl_path):
    result = None
    with open(jsonl_path, encoding='utf-8') as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            msg = rec.get('message') or {}
            content = msg.get('content')
            if rec.get('type') == 'assistant' and isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') == 'StructuredOutput':
                        result = c.get('input')
    return result

agents = {}
for m in glob.glob(os.path.join(WF, '*.meta.json')):
    j = jl(m)
    desc = j.get('description', '?')
    base = os.path.basename(m).replace('.meta.json', '')
    agents.setdefault(desc, []).append(os.path.join(WF, base + '.jsonl'))

for si in range(25):
    desc = 'review:w3s%d' % si
    for p in sorted(agents.get(desc, [])):
        so = structured_output(p)
        if so and si in (3, 4, 5):
            units = so.get('units', [])
            print(desc, 'n=%d' % len(units), 'ids:', ','.join(u.get('id', '?') for u in units))
            v = {}
            for u in units:
                v[u.get('verdict')] = v.get(u.get('verdict'), 0) + 1
            print('  verdicts:', v)
        elif not so:
            print(desc, 'NO OUTPUT')
