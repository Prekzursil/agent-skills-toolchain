import json
import pathlib
import re

BASE = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit")
d = json.loads((BASE / "disposition.json").read_text(encoding="utf-8"))
rows = d["rows"]
print("TOP-LEVEL KEYS:", sorted(d.keys()))
print("ROWS:", len(rows))
print("ROW KEYS:", sorted(rows[0].keys()))
print()
hdr = f"{'name':22} {'disp':12} {'scope':16} {'tx':6} hs s4 cv  tools basis"
print(hdr)
for r in rows:
    print(
        f"{r['name']:22} {r['disposition']:12} {str(r.get('definition_scope')):16} "
        f"{str(r.get('transport')):6} "
        f"{str(r.get('handshake_verified'))[0]}  {str(r.get('s4_executed'))[0]}  "
        f"{str(r.get('call_verified'))[0]}  {str(r.get('tool_count')):5} "
        f"{str(r.get('liveness_basis'))[:44]}"
    )

print()
# Parse the captured claude mcp list
txt = (BASE / "claude-mcp-list.txt").read_text(encoding="utf-8", errors="replace")
entries = re.findall(r"^([A-Za-z0-9_.\-]+):\s+(.*?)\s+-\s+[^\S\n]*(.)", txt, re.M)
names = [e[0] for e in entries]
print("PARSED ENTRIES FROM claude-mcp-list.txt:", len(names))
print("names:", sorted(names))
print()
rownames = {r["name"] for r in rows}
print("ROW NAMES:", len(rownames))
print("IN LIST NOT IN ROWS:", sorted(set(names) - rownames))
print("IN ROWS NOT IN LIST:", sorted(rownames - set(names)))
