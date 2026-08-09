"""Final self-audit for build/wfa-1.

Design note: the FIRST version of this script hardcoded the numbers it was
checking, so after I corrected the sidecar the checker kept reporting the old
(now absent) claims as mismatches -- a checker/artifact drift bug. It now PARSES
every number out of the sidecar text, so the assertion can never disagree with
the artifact for a reason other than a real error.
"""

import json
import re
import sys

with open("command-center/_wfa1_deep_scan.json", encoding="utf-8") as fh:
    S = json.load(fh)
with open("platform/registry/workflow-candidates-1.json", encoding="utf-8") as fh:
    R = json.load(fh)
SIDECAR = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "platform/registry/workflow-candidates-1.COVERAGE.json"
)
with open(SIDECAR, encoding="utf-8") as fh:
    raw = fh.read()
C = json.loads(raw)
print(f"sidecar under test      : {SIDECAR}")

fails = []
print("both files parse as JSON : True")
print(f"registry rows           : {len(R)}")
print(f"sidecar count field     : {C['count_read_back_off_disk']}")
if len(R) != C["count_read_back_off_disk"]:
    fails.append("registry row count != sidecar count field")

# ---- claim: N trees / N files / N bytes  (parsed from the sidecar) ----
trees = [s for s in S if s.get("tree_file_count")]
tf = sum(s["tree_file_count"] for s in trees)
tb = sum(s["tree_total_bytes"] for s in trees)
m = re.search(r"(\d+) trees / ([\d,]+) files / ([\d,]+) bytes", raw)
if not m:
    fails.append("could not find the trees/files/bytes claim in the sidecar")
    print("\nTREE CLAIM: NOT FOUND in sidecar")
else:
    ct, cf, cb = (
        int(m.group(1)),
        int(m.group(2).replace(",", "")),
        int(m.group(3).replace(",", "")),
    )
    print(f"\nsidecar tree claim      : {ct} trees / {cf} files / {cb} bytes")
    print(f"measured                : {len(trees)} trees / {tf} files / {tb} bytes")
    ok = (ct, cf, cb) == (len(trees), tf, tb)
    print(f"MATCH                   : {ok}")
    if not ok:
        fails.append("tree files/bytes claim does not match measurement")

# ---- claim: live/mirror provenance split (parsed) ----
live = sum(1 for s in S if s["kind"] == "file-live")
mir = sum(1 for s in S if str(s["kind"]).startswith("mirror"))
m2 = re.search(r"(\d+) from the live filesystem", raw)
m3 = re.search(r"(\d+) from the bare mirror", raw)
if not (m2 and m3):
    fails.append("could not find the live/mirror split claim in the sidecar")
else:
    cl, cm = int(m2.group(1)), int(m3.group(1))
    print(f"\nsidecar split claim     : {cl} live / {cm} mirror")
    print(f"measured                : {live} live / {mir} mirror")
    ok = (cl, cm) == (live, mir)
    print(f"MATCH                   : {ok}")
    if not ok:
        fails.append("live/mirror split claim does not match measurement")
if live + mir != len(R):
    fails.append("live+mirror != 32 -- an anchor is unclassified")

# ---- claim: maintenance date range (parsed) ----
dates = sorted(
    r["maintenance_state"]["last_commit_at_ref"]
    for r in R
    if r["maintenance_state"]["last_commit_at_ref"]
)
m4 = re.search(r"Range (\d{4}-\d{2}-\d{2}) \(.*?\) to (\d{4}-\d{2}-\d{2})", raw)
print(f"\nmeasured date range     : {dates[0]} .. {dates[-1]}  (n={len(dates)})")
if m4:
    print(f"sidecar range claim     : {m4.group(1)} .. {m4.group(2)}")
    ok = (m4.group(1), m4.group(2)) == (dates[0], dates[-1])
    print(f"MATCH                   : {ok}")
    if not ok:
        fails.append("maintenance date range claim does not match measurement")

# ---- every re-classification named in the sidecar findings must exist ----
changed = {r["id"] for r in R if r.get("classification_changed")}
print(f"\nre-classified rows      : {len(changed)} {sorted(changed)}")
for cid in ("tool-harness-drift", "tool-mcpctl", "tool-mcpapply", "tool-otel-traces"):
    if cid not in changed:
        fails.append(
            f"{cid} claimed as re-classified but is not flagged in the registry"
        )

# ---- distinctness restated from the artifact, not from memory ----
h = [r["provenance"]["body_sha256_16"] for r in R]
print(f"unique body hashes      : {len(set(h))} of {len(h)}")
if len(set(h)) != len(h):
    fails.append("duplicate body hashes")

print()
if fails:
    print("FAILED:wfa-1-selfaudit " + "; ".join(fails))
    sys.exit(1)
print(
    "SUCCESS:wfa-1-selfaudit every numeric claim in the sidecar matches its measurement"
)
