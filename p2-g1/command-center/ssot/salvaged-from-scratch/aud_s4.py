import json
import pathlib

BASE = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit")
rows = json.loads((BASE / "disposition.json").read_text(encoding="utf-8"))["rows"]

print("=== S4b: real in-session tool call evidence ===")
for r in rows:
    s4 = r.get("s4_executed")
    if s4:
        print(f"{r['name']:18} call_method={r.get('call_method')!r}")
        print(f"    s4_executed = {json.dumps(s4)[:260]}")
print()
print("=== source_file / config_basis / last_error / probe_note ===")
for r in rows:
    sf = r.get("source_file") or ""
    exists = pathlib.Path(sf).exists() if sf else False
    print(f"{r['name']:18} exists={exists} {sf}")
    print(f"    config_basis={str(r.get('config_basis'))[:70]!r}")
    print(f"    last_error  ={r.get('last_error')!r}")
    print(f"    probe_note  ={str(r.get('probe_note'))[:90]!r}")
print()
print("=== codex row in full ===")
codex = [r for r in rows if r["name"] == "codex"][0]
print(json.dumps(codex, indent=1))
