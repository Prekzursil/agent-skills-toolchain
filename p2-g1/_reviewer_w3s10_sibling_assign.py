import json
import os
import re

base = r'C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/13dd0812-e887-4a76-9d0e-4c6e6d30a937/subagents/workflows/wf_a81de287-702'
w3 = {
 'w3s0':'ac602aaed4abbe958','w3s1':'a8dc405049603ed21','w3s2':'a994a975999d8cbc7',
 'w3s3':'ab2bd15c45b468439','w3s4':'acc21dd719de2cc76','w3s5':'a572f14f0a5bd0daa',
 'w3s6':'add60b03b5c36ac97','w3s7':'a4b39a6b1105cf4da','w3s8':'aedff67bc83905e54',
 'w3s9':'a3d463b1eeef20233','w3s11':'a464de04e65a88b9a','w3s12':'ab089b1bcf7f2a99a',
 'w3s13':'a01d20e19d4d7956f','w3s14':'aa0c1185f36ab3796','w3s15':'ae89345389848ccef',
 'w3s16':'a6182a6e140ca6ecf','w3s17':'ad19c568d6b9d2346',
}
id_re = re.compile(r'(?:ADV|ARC|AUD|BLD|CC|CNF|CNL|IMP|REL|RES|SYN|TST)-\d{3,4}')
assign = {}
for lab, aid in sorted(w3.items()):
    f = os.path.join(base, 'agent-%s.jsonl' % aid)
    found = None
    with open(f, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get('message') or {}
            content = msg.get('content')
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'tool_use':
                    s = json.dumps(c.get('input', {}))
                    m = re.search(r'UNITS\s*=\s*\[([^\]]+)\]', s)
                    if m:
                        ids = id_re.findall(m.group(1))
                        if len(ids) >= 8:
                            found = ids
                            break
                if found:
                    break
            if found:
                break
    assign[lab] = found
    print(lab, len(found) if found else 'NOT FOUND', found)

json.dump(assign, open(r'C:/Users/Prekzursil/p2-g1/_reviewer_w3_sibling_assignments.json', 'w'), indent=1)
