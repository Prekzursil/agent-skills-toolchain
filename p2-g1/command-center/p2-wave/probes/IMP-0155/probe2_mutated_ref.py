"""IMP-0155 probe 2 (verifier, both-states control): a record with a mutated ref
FAILS the re-fetch (the detector fires on the broken state) while the clean twin
passes (silent on the good state).

Re-run: python command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "workflow-foundry"))
import wf_provenance as PR  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "probe2-mutated-ref.raw.txt"

records = json.loads((HERE / "provenance-records.json").read_text(encoding="utf-8"))
clean = records[0]

# Good state: the untouched record re-fetches clean.
good = PR.refetch(clean)
lines = ["clean record {} -> ok={}".format(clean["path"], good["ok"])]
assert good["ok"], "clean twin failed to re-fetch: " + good.get("detail", "")
silent_on_good = good["ok"]

# Bad state: mutate the recorded hash (simulates a corrupted provenance ref);
# the re-fetch MUST fail against the real bytes on disk.
bad = copy.deepcopy(clean)
bad["sha256"] = "0" * 64
badres = PR.refetch(bad)
lines.append("mutated record {} -> ok={} detail={!r}".format(
    bad["path"], badres["ok"], badres.get("detail", "")))
fired_on_bad = not badres["ok"]
assert fired_on_bad, "mutated ref re-fetched ok; detector is inert"

# A second broken state: a record pointing at a nonexistent path must fail too.
gone = copy.deepcopy(clean)
gone["path"] = gone["path"] + ".does-not-exist"
goneres = PR.refetch(gone)
lines.append("absent path -> ok={} detail={!r}".format(goneres["ok"], goneres.get("detail", "")))
assert not goneres["ok"], "absent-path record re-fetched ok; detector is inert"

lines.append("PASS: detector fires on mutated ref and absent path, silent on clean twin")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "clean_ok": silent_on_good,
    "mutated_ref_failed": fired_on_bad,
    "absent_path_failed": not goneres["ok"],
}))
print("PASS")
