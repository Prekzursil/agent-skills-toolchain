import json
from pathlib import Path
OLD = "3b2aee2f27a443b0"  # 16-hex prefix, enough to locate rows
def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(node, str) and OLD in node:
        yield path, node[:180]
r = json.loads(Path("command-center/p2-wave/probes/ADV-0038/SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
print("--- SUBAGENT-RETURN occurrences:")
for p, s in walk(r): print(" ", p, "=>", s)
print("artifacts rows:", json.dumps(r.get("artifacts"), indent=1)[:600])
print("measure_line:", r.get("measure_line"))
print("notes:", json.dumps(r.get("notes"))[:300])
