"""Cycle-3b fix: RES-0187 probe1 — not_in_coverage_fraction is a boolean flag."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\_p2shard20-w2\write_probes.py")
src = p.read_text(encoding="utf-8")

start = src.find('excluded = ctrl.get("not_in_coverage_fraction")')
end = src.find('ok("json walk"', start)
assert start > 0 and end > start, "R0187 probe1 block not found"
new_block = '''need(isinstance(ctrl.get("not_in_coverage_fraction"), bool)
     and ctrl.get("not_in_coverage_fraction") is True,
     "controls.not_in_coverage_fraction must be the boolean flag True (controls sit outside the measured fraction)")
labeled = (ctrl.get("labeled") or [])
need(len(labeled) >= 1, "no labeled control rows")
for row in labeled:
    if "however" in str(row.get("text", "")).lower():
        need(classify(row) == "UNCHALLENGED" and row.get("status") == "UNCHALLENGED",
             "however-only control not UNCHALLENGED under the strict rule")
'''
src = src[:start] + new_block + src[end:]

p.write_text(src, encoding="utf-8")
print("SUCCESS:R0187 probe1 rewritten around the boolean flag")
