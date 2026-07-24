"""Program E Steps 3-4: coverage fan-out for a repo. One unit per uncovered file (up to 48
concurrent on the node), 5-clause gated; each green unit pushes to agent/E-<repo>-<file>.
Usage: python e2e/run_fanout.py <repo> <gaps_json_basename>   (real Databricks spend)"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.lanes import run_E

repo = sys.argv[1] if len(sys.argv) > 1 else "env-inspector"
gaps_file = sys.argv[2] if len(sys.argv) > 2 else "_runnability_gaps.json"
gaps = json.loads(Path(__file__).parent.joinpath(gaps_file).read_text(encoding="utf-8"))
print(f"FANOUT {repo}: {len(gaps)} gap(s)")

verdicts = run_E.run_coverage_fanout(repo, gaps)
done = [(uid, p) for uid, (v, p) in verdicts.items() if v == "DONE"]
print(f"RESULT: {len(done)}/{len(verdicts)} DONE")
for uid, (v, p) in sorted(verdicts.items()):
    print(f"  {v}: {uid}")
for uid, p in done:
    if p and Path(p).exists():
        t = Path(p).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*branch_pushed:\s*(.+)$", t, re.M)
        print(f"  branch[{uid}]: {m.group(1).strip() if m else '?'}")
