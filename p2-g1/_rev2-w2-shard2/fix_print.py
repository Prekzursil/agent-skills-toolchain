"""Fix the ConditionOutcome attr names in close_shard2_w2.py printing."""
import io

P = r"C:\Users\Prekzursil\p2-g1\_rev2-w2-shard2\close_shard2_w2.py"
src = io.open(P, encoding="utf-8").read()
src = src.replace(
    'unsat = [c for c in ga.conditions if getattr(c, "outcome", "") == "UNSATISFIED"]',
    "unsat = [c for c in ga.conditions if c.blocking]",
).replace(
    'print("   gate:", getattr(c, "condition_number", "?"), str(getattr(c, "basis", ""))[:160])',
    'print("   gate: c%s=%s %s" % (c.n, c.outcome, str(c.basis)[:160]))',
)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched")
