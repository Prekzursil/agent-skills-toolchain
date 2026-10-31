import json, glob, os

WF = r'C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\13dd0812-e887-4a76-9d0e-4c6e6d30a937\subagents\workflows\wf_a81de287-702'
WFJSON = r'C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\13dd0812-e887-4a76-9d0e-4c6e6d30a937\workflows\wf_a81de287-702.json'

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

args = jl(WFJSON).get('args', {})
s10 = args.get('s10Units', [])

# map description -> list of (jsonl path, has_structured_output)
agents = {}
for m in glob.glob(os.path.join(WF, '*.meta.json')):
    j = jl(m)
    desc = j.get('description', '?')
    base = os.path.basename(m).replace('.meta.json', '')
    agents.setdefault(desc, []).append(os.path.join(WF, base + '.jsonl'))

def structured_units(jsonl_path):
    """Return the units array from the StructuredOutput tool_use, or None."""
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

# Wave-4 build shards in si order
pending = list(s10)  # allBuilt = S10_UNITS.slice()
per_shard = {}
missing = []
for si in range(24):
    desc = 'build:w4s%d' % si
    paths = agents.get(desc, [])
    got = None
    for p in paths:
        so = structured_units(p)
        if so and isinstance(so.get('units'), list):
            got = so  # latest one wins (parallel writes; only one in w4)
    if got is None:
        missing.append(si)
        continue
    units = got['units']
    per_shard[si] = [(u.get('id'), u.get('state')) for u in units]
    for u in units:
        uid = u.get('id')
        if u.get('state') == 'built-awaiting-review' and uid and uid not in pending:
            pending.append(uid)

print('s10 inherited:', len(s10))
print('build shards missing structured output:', missing)
for si in sorted(per_shard):
    ids = [i for i, s in per_shard[si]]
    states = {}
    for i, s in per_shard[si]:
        states[s] = states.get(s, 0) + 1
    print('build w4s%-2d: n=%2d states=%s' % (si, len(ids), states))
print('pendingReview total:', len(pending))
CAP = 12
nshards = (len(pending) + CAP - 1) // CAP
print('review shards:', nshards)
out = {}
for ri in range(nshards):
    out[ri] = pending[ri*CAP:(ri+1)*CAP]
    print('shard %2d (%d): %s' % (ri, len(out[ri]), ', '.join(out[ri])))

# sanity-check against sibling reviewer evidence
shard2_expect = ['ADV-0127','ADV-0128','ARC-0001','ARC-0012','ARC-0013','ARC-0015','ARC-0019','ARC-0020','ARC-0021','ARC-0047','ARC-0048','ARC-0054']
shard3_expect = ['ARC-0055','ARC-0056','ARC-0076','AUD-0003','AUD-0005','AUD-0008','AUD-0010','AUD-0026','AUD-0032','AUD-0033','AUD-0042','AUD-0043']
print('shard2 matches sibling survey:', out.get(2) == shard2_expect)
print('shard3 matches sibling verify:', out.get(3) == shard3_expect)
with open(os.path.dirname(os.path.abspath(__file__)) + r'\shard-plan.json', 'w', encoding='utf-8') as f:
    json.dump({'s10': s10, 'per_shard': per_shard, 'pendingReview': pending, 'revShards': out}, f, indent=1)
print('MINE (review w4s4):', json.dumps(out.get(4)))
