"""C2 re-probe: my first detector found 0 violation ids against a README claim of
28. A zero from an unproven matcher is a DETECTOR failure, not a finding.
Here I (a) show what the ids actually look like, (b) run three mechanically
different counters, (c) require them to agree before reporting a number.
"""

import re
import subprocess
from collections import Counter

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"


def blob(path):
    r = subprocess.run(
        ["git", "--git-dir", MIRROR, "cat-file", "-p", f"{REF}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or "") if r.returncode == 0 else None


v = blob("tools/agentspec/agentspec/validate.py") or ""
print(f"validate.py bytes={len(v)} lines={v.count(chr(10)) + 1}")

print("\n--- lines mentioning 'violation' (first 20) ---")
for i, ln in enumerate(v.splitlines(), 1):
    if "violation" in ln.lower():
        print(f"{i:>5}: {ln.strip()[:150]}")
        if i > 400:
            break

print("\n--- any quoted ALL-CAPS-ish tokens (sample) ---")
toks = re.findall(r"['\"]([A-Z][A-Z0-9_.\-]{2,30})['\"]", v)
print(Counter(toks).most_common(40))

# three independent counters
c1 = sorted(set(re.findall(r"['\"]([A-Z]{2,10}-\d{2,3})['\"]", v)))  # original
c2 = sorted(set(re.findall(r"['\"]([A-Z][A-Z0-9]*[_-]?\d{2,3})['\"]", v)))
c3 = sorted(set(re.findall(r"\b([A-Z]{2,12}\d{3})\b", v)))
print(f"\ncounter1 (X-NN)      n={len(c1)} {c1[:40]}")
print(f"counter2 (loose)     n={len(c2)} {c2[:40]}")
print(f"counter3 (bare CAPSNNN) n={len(c3)} {c3[:40]}")

# what does the README actually say, in context?
rd = blob("tools/agentspec/README.md") or ""
for ln in rd.splitlines():
    if "violation" in ln.lower():
        print("README:", ln.strip()[:220])
