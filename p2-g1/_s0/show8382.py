from pathlib import Path
REPO = Path.home() / "p2-g1"
for uid, fn in [("IMP-0083", "probe1_repeat_shuffle.py"), ("IMP-0083", "probe2_unsat_conflict.py"),
                ("IMP-0082", "probe1_planted_cycles.py"), ("IMP-0082", "probe2_independent_library.py")]:
    p = REPO / "command-center/p2-wave/probes" / uid / fn
    print("=" * 25, uid, fn, "=" * 25)
    print(p.read_text(encoding="utf-8")[:4200])
