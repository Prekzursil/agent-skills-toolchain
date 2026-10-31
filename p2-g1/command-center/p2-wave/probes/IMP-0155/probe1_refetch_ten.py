"""IMP-0155 probe 1 (source): a fresh re-fetch from the records ALONE reproduces
the recorded hash for 10/10 sampled candidates.

The probe receives only provenance-records.json (plus the workspace root on
disk); it is the "second agent" of the acceptance clause. It never reads the
original sampling code path.

Re-run: python command-center/p2-wave/probes/IMP-0155/probe1_refetch_ten.py
Exit 0 iff 10/10 records re-fetch to identical bytes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "workflow-foundry"))
import wf_provenance as PR  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "probe1-refetch-ten.raw.txt"

records = json.loads((HERE / "provenance-records.json").read_text(encoding="utf-8"))
lines = ["loaded {} provenance records".format(len(records))]
result = PR.refetch_many(records)
for r in result["results"]:
    lines.append("{} -> ok={} sha256={}".format(
        r.get("path"), r["ok"], r.get("sha256", "-")[:16]))
lines.append("reproduced {}/{}".format(result["reproduced"], result["sampled"]))

assert records, "no records to verify"
assert result["all_reproduced"], "re-fetch reproduced only {}/{}".format(
    result["reproduced"], result["sampled"])
lines.append("PASS: 10/10 provenance records re-fetched to identical bytes")

RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "sampled": result["sampled"],
    "reproduced": result["reproduced"],
    "all_reproduced": result["all_reproduced"],
}))
print("PASS")
