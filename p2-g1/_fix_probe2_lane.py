#!/usr/bin/env python3
"""Fix (1) bash-cmp lane in ARC-0021 probe2: validate the comparator with a
both-states control before its verdict counts (a lane that cannot tell
identical from different measures nothing); (2) receipt method enum in the
finisher: 'live-probe' -> 'command' (schema enum)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --- patch 1: probe2_uninstall.py ------------------------------------------ #
p2 = ROOT / "command-center" / "p2-wave" / "probes" / "ARC-0021" / "probe2_uninstall.py"
t = p2.read_text(encoding="utf-8")
old = """        bash_ok = None
        try:
            r = subprocess.run(
                ["bash", "-c", "true"],
                capture_output=True,
                timeout=15,
            )
            if r.returncode == 0:
                bad_cmp = []
                for rel in UNCLAIMED:
                    a = str((work / rel).resolve()).replace("\\\\", "/")
                    b = str((snapshot / rel).resolve()).replace("\\\\", "/")
                    p = subprocess.run(
                        ["bash", "-c", f'cmp -s "{a}" "{b}"'],
                        capture_output=True,
                        timeout=15,
                    )
                    if p.returncode != 0:
                        bad_cmp.append(rel)
                bash_ok = not bad_cmp
                signals.append(("bash-cmp", bash_ok))
        except (OSError, subprocess.TimeoutExpired):
            print("  bash lane unavailable; falling back to byte-compare + size")
"""
new = """        bash_ok = None
        try:
            r = subprocess.run(["bash", "-c", "true"], capture_output=True, timeout=15)
            if r.returncode == 0:
                # Validate the comparator itself before trusting its verdict:
                # identical pair must PASS, different pair must FAIL.
                ctl_a = work / sorted(UNCLAIMED)[0]
                ctl_b = snapshot / sorted(UNCLAIMED)[0]
                ctl_diff = snapshot / sorted(UNCLAIMED)[-1]
                pa = str(ctl_a.resolve()).replace("\\\\", "/")
                pb = str(ctl_b.resolve()).replace("\\\\", "/")
                pd = str(ctl_diff.resolve()).replace("\\\\", "/")
                same = subprocess.run(
                    ["bash", "-c", f'cmp -s "{pa}" "{pb}"'], capture_output=True, timeout=15
                )
                diff = subprocess.run(
                    ["bash", "-c", f'cmp -s "{pa}" "{pd}"'], capture_output=True, timeout=15
                )
                lane_ok = same.returncode == 0 and diff.returncode != 0
                print(f"  bash-cmp lane control: same_rc={same.returncode} diff_rc={diff.returncode} lane_ok={lane_ok}")
                if lane_ok:
                    bad_cmp = []
                    for rel in UNCLAIMED:
                        a = str((work / rel).resolve()).replace("\\\\", "/")
                        b = str((snapshot / rel).resolve()).replace("\\\\", "/")
                        p = subprocess.run(
                            ["bash", "-c", f'cmp -s "{a}" "{b}"'], capture_output=True, timeout=15
                        )
                        if p.returncode != 0:
                            bad_cmp.append(rel)
                    bash_ok = not bad_cmp
                    signals.append(("bash-cmp", bash_ok))
        except (OSError, subprocess.TimeoutExpired):
            print("  bash lane unavailable; falling back to byte-compare + size")
"""
if old in t:
    t = t.replace(old, new, 1)
    print("probe2: bash lane control patched")
else:
    print("probe2: PATTERN-NOT-FOUND")
p2.write_text(t, encoding="utf-8", newline="\n")

# --- patch 2: finisher method enum ------------------------------------------ #
fin = ROOT / "_shard2w2_finish.py"
t = fin.read_text(encoding="utf-8")
if '"method": "live-probe"' in t:
    t = t.replace('"method": "live-probe"', '"method": "command"')
    fin.write_text(t, encoding="utf-8", newline="\n")
    print("finisher: method enum patched")
else:
    print("finisher: method literal not found (already patched?)")
