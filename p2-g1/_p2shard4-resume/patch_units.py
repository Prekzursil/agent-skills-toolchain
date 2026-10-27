"""Resume patch 3/3: shard4_units.py (PLAN flip + preserved-closure probe check)."""
from pathlib import Path

W1 = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1"
un = W1 / "shard4_units.py"
src = un.read_text(encoding="utf-8")

for uid, note in [
    ("BLD-0052", "resume 2026-10-24: SUCCESS no longer verifies live (open P1 defect + FAILED sentinel); C5 closure preserved in extensions.prev_closure"),
    ("BLD-0057", "resume 2026-10-24: SUCCESS no longer verifies live (open P1 defect + envelope gaps); C5 closure preserved in extensions.prev_closure"),
    ("CC-0011", "resume 2026-10-24: SUCCESS no longer verifies live (open P0 defect + FAILED sentinel); C5 closure preserved in extensions.prev_closure"),
]:
    old = '    "%s": "KEEP",' % uid
    assert old in src, "units: PLAN line for %s not found" % uid
    src = src.replace(old, '    "%s": "BLOCKED",  # %s' % (uid, note))

old_c5 = '''    rev = doc.get("reviewer") or {}
    c.check("c5-closure-cross-vendor-fresh-context",
            rev.get("vendor") == "openai" and rev.get("fresh_context") is True
            and rev.get("independent") is True and rev.get("verdict") == "PASS")'''
new_c5 = '''    _pc = (((doc.get("extensions") or {}).get("prev_closure") or {}).get("reviewer")) or doc.get("reviewer") or {}
    c.check("c5-closure-preserved-cross-vendor-fresh-context",
            _pc.get("vendor") == "openai" and _pc.get("fresh_context") is True
            and _pc.get("independent") is True and _pc.get("verdict") == "PASS")'''
assert src.count(old_c5) == 3, "units: c5 block count=%d" % src.count(old_c5)
src = src.replace(old_c5, new_c5)
un.write_text(src, encoding="utf-8", newline="\n")
print("patched shard4_units.py OK")
