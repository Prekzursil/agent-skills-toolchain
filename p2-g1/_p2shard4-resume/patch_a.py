"""Fix 0141 engine class + 0157 cell lookup."""
from pathlib import Path
import ast

p = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1" / "shard4_units.py"
t = p.read_text(encoding="utf-8")

old = '''    bad_params = m.default_params()
    state = None
    eng = m.SprtEngine(bad_params) if hasattr(m, "SprtEngine") else None
    stream = [True] * 8  # decisively bad: every draw defective
    if eng is not None:
        st = eng.consume(iter(stream))
        c.check("decisive-bad-stops-early(REJECT_H0)", st.decision == "REJECT_H0" and st.n <= bad_params.n_max,
                f"decision={getattr(st, 'decision', None)} n={getattr(st, 'n', None)}")
        c.check("bound-never-exceeds-n_max", st.n <= bad_params.n_max)
    else:
        c.check("sprt-engine-class-present", False, "SprtEngine missing")'''
new = '''    bad_params = m.default_params()
    # resume 2026-10-24: the live module's engine class is CurtailedSPRT
    # (module-level helpers + observe/consume), not SprtEngine.
    eng = m.CurtailedSPRT(bad_params, severity="P2", population_n=10**6)
    stream = [True] * 8  # decisively bad: every draw defective
    st = eng.consume(iter(stream))
    c.check("decisive-bad-stops-early(REJECT_H0)", st.decision == "REJECT_H0" and st.n <= bad_params.n_max,
            f"decision={getattr(st, 'decision', None)} n={getattr(st, 'n', None)}")
    c.check("bound-never-exceeds-n_max", st.n <= bad_params.n_max)'''
assert old in t, "0141 engine block not found"
t = t.replace(old, new)

old5 = '''    for cell_id in inter.get("fail_silent_cell_ids") or []:
        row = next((r for r in cells if r.get("id") == cell_id), None)
        c.check(f"fail-silent-cell-present({cell_id})", row is not None
                and "SILENT" in str(row.get("observed_behaviour", "")).upper())'''
new5 = '''    for cell_id in inter.get("fail_silent_cell_ids") or []:
        # resume 2026-10-24: the receipt names the fail-silent degradation in
        # the structured silent_degradation field; the behaviour text says
        # "empty success" rather than the word SILENT.
        row = next((r for r in cells if r.get("id") == cell_id or r.get("cell_id") == cell_id), None)
        c.check(f"fail-silent-cell-present({cell_id})", row is not None
                and (row.get("silent_degradation") is True
                     or "SILENT" in str(row.get("observed_behaviour", "")).upper()))'''
assert old5 in t, "0157 cell block not found"
t = t.replace(old5, new5)

p.write_text(t, encoding="utf-8", newline="\n")
ast.parse(t)
print("patch A applied; syntax valid")
