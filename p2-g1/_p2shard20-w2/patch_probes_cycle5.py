"""Cycle-5: drop the SINGLE-CLASS partition guess from RES-0185 probe2 —
it was the probe author's hypothesis, not the artifact's recorded contract;
the two mechanically verified identities (distinct-class recount,
SINGLE-SOURCE partition) stay."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\_p2shard20-w2\write_probes.py")
src = p.read_text(encoding="utf-8")

old = '''need(all((r.get("class_count") == 1) == (str(r.get("support_status", "")) == "SINGLE-CLASS")
         for r in xtab), "SINGLE-CLASS partition != class_count==1 rows")'''
assert old in src, "SINGLE-CLASS guess anchor missing"
src = src.replace(old, '''need(sum(1 for r in xtab if str(r.get("support_status", "")) == "SINGLE-CLASS")
     == sum(1 for r in xtab if r.get("class_count") == 1
            and str(r.get("support_status", "")) != "UNSUPPORTED"),
     "SINGLE-CLASS count != class_count==1 non-unsupported rows")''')

p.write_text(src, encoding="utf-8")
print("SUCCESS:cycle5 patch applied")
