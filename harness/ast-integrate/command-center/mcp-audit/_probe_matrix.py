"""Analyse the mcpctl matrix JSON: states, transports, conflicts, unmeasured fields."""

import json
import collections
import pathlib

P = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit/mcpctl-matrix.json"
)
d = json.loads(P.read_text(encoding="utf-8-sig"))
rows = d["rows"]

print("=== TOP-LEVEL ===")
print("counts       :", json.dumps(d.get("counts")))
print("precedence   :", d.get("precedence"))
print("project_key  :", d.get("project_key"), "found:", d.get("project_row_found"))
print("enable_all   :", d.get("enable_all_project_servers"))
print("approved     :", len(d.get("approved_mcpjson") or []))
print("problems     :", json.dumps(d.get("problems"))[:600])
print("envelope     :", json.dumps(d.get("envelope"))[:600])
print("terminal     :", d.get("terminal"))

print()
print("=== ROWS:", len(rows), "===")
for field in ("state", "transport", "inferred"):
    c = collections.Counter(r.get(field) for r in rows)
    print(f"{field:10}:", dict(c))

print()
print("=== SCOPE MEMBERSHIP ===")
sc = collections.Counter()
for r in rows:
    sc[tuple(sorted(r.get("scopes") or []))] += 1
for k, v in sc.most_common():
    print(f"  {v:4}  {k}")

print()
print("=== BASIS (which scope decided) ===")
bs = collections.Counter()
for r in rows:
    bs[tuple(r.get("basis") or [])] += 1
for k, v in bs.most_common():
    print(f"  {v:4}  {k}")

print()
print("=== UNMEASURED LIVENESS FIELDS (null == not measured) ===")
for field in ("tool_count", "pid", "rss_bytes", "last_error"):
    n_null = sum(1 for r in rows if r.get(field) is None)
    print(f"  {field:12} null in {n_null}/{len(rows)} rows")

print()
print("=== CONFLICTS ===")
conf = [r for r in rows if r.get("conflicts")]
print("rows with conflicts:", len(conf))
for r in conf[:20]:
    print("  ", r["name"], "->", r["conflicts"])

print()
print("=== ENABLED ROWS (the live candidate set) ===")
en = sorted(r["name"] for r in rows if r.get("state") == "enabled")
print(len(en), "enabled")
for n in en:
    row = next(r for r in rows if r["name"] == n)
    print(
        f"  {n:28} transport={row.get('transport')!s:8} scopes={','.join(row.get('scopes') or [])}"
    )

print()
print("=== ENV FIELDS (credential NAMES only) ===")
withenv = [r for r in rows if r.get("env_fields")]
print(len(withenv), "rows carry env fields")
for r in withenv:
    names = [(e.get("name"), e.get("status")) for e in r["env_fields"]]
    print(f"  {r['name']:28} state={r.get('state'):10} {names}")
