"""Lane SYNTH read-only probe 2 - precise register state. Writes NOTHING. Gitignored scratch."""
import json
import os

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
with open(os.path.join(ROOT, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8") as fh:
    cat = json.load(fh)

items = cat["items"]
print("type(items)=", type(items).__name__, "len=", len(items))
print("terminal_dispositions=", json.dumps(cat.get("terminal_dispositions"))[:600])

seq = items if isinstance(items, list) else list(items.values())
print("item0 keys=", sorted(seq[0].keys()))

hist = {}
rows = []
for d in seq:
    st = d.get("status", "NO-STATUS")
    hist[st] = hist.get(st, 0) + 1
    rows.append((d.get("id"), st, d.get("disposition"), bool(d.get("owner_gate"))))
print("STATUS histogram:", json.dumps(hist, sort_keys=True))

dispo = {}
for _, _, dp, _ in rows:
    dispo[str(dp)] = dispo.get(str(dp), 0) + 1
print("DISPOSITION histogram:", json.dumps(dispo, sort_keys=True))

print("--- non-OPEN rows ---")
for i, st, dp, g in sorted(rows):
    if st != "OPEN":
        print("  %-7s status=%-14s disposition=%s owner_gate=%s" % (i, st, dp, g))

# duplicate-id detector control
ids = [d.get("id") for d in seq]
print("distinct ids=", len(set(ids)), "total rows=", len(ids))

# validator candidate 2 for Q22
ch = os.environ.get("CODEX_HOME") or os.path.join(os.environ["USERPROFILE"], ".codex")
for c in (
    os.path.join(ch, ".agents/skills/.system/skill-creator/scripts/quick_validate.py"),
    os.path.join(ch, "skills/.system/skill-creator/scripts/quick_validate.py"),
):
    print("Q22 candidate exists=%-5s  %s" % (os.path.exists(c), c))
print("CODEX_HOME env set=", "CODEX_HOME" in os.environ, "->", ch)
