import json
import os

H = r"C:/Users/Prekzursil/source/ast-integrate/command-center/harvest/harvest-wf_18aa91e4-3c1-wf_9cb1a66a-36f.json"
OUT = r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/harvest-split"
os.makedirs(OUT, exist_ok=True)

with open(H, "r", encoding="utf-8") as f:
    d = json.load(f)

total = 0
for run, items in d.items():
    for i, item in enumerate(items):
        res = item.get("result")
        if not isinstance(res, str):
            res = json.dumps(res, indent=2, ensure_ascii=False)
        total += len(res)
        p = os.path.join(OUT, f"{run}__{i:02d}__{item.get('agentId')}.md")
        with open(p, "w", encoding="utf-8", newline="\n") as g:
            g.write(res)
        # first non-empty 3 lines as a fingerprint
        head = [ln for ln in res.splitlines() if ln.strip()][:3]
        print(f"{run} [{i:02d}] {item.get('agentId')} len={len(res)}")
        for ln in head:
            print("      | " + ln[:200])
print("TOTAL CHARS:", total)
