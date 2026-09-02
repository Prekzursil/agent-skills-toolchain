"""Read platform/registry/workflow-candidates-1.json BACK off disk and validate.

This is the acceptance gate for build/wfa-1. It re-resolves every provenance
anchor from scratch (it does NOT trust the builder's own 'resolved': true) and
includes both-states detector controls.
"""

import json
import os
import subprocess
import sys
from collections import Counter

REG = "platform/registry/workflow-candidates-1.json"
MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

VOCAB = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}
REQUIRED = [
    "id",
    "name",
    "classification",
    "provenance",
    "license",
    "license_source",
    "maintenance_state",
    "task_fit",
    "stages",
    "roles",
    "tools",
    "stop_rules",
    "failure_behaviour",
    "benchmark_evidence",
]

fail = []
with open(REG, encoding="utf-8") as fh:
    rows = json.load(fh)

print(f"file            : {os.path.abspath(REG)}")
print(f"bytes on disk   : {os.path.getsize(REG)}")
print(f"top-level type  : {type(rows).__name__}")
print(f"COUNT READ BACK : {len(rows)}")
if not isinstance(rows, list):
    fail.append("top-level is not a JSON array")
if len(rows) != 32:
    fail.append(f"expected 32 rows, got {len(rows)}")

# --- required fields, non-empty ---
missing = []
empty = []
for r in rows:
    for f in REQUIRED:
        if f not in r:
            missing.append((r.get("id"), f))
        elif r[f] in (None, "", [], {}):
            empty.append((r.get("id"), f))
print(f"missing fields  : {len(missing)} {missing[:8]}")
print(f"empty fields    : {len(empty)} {empty[:8]}")
if missing:
    fail.append(f"{len(missing)} missing required fields")
if empty:
    fail.append(f"{len(empty)} empty required fields")

# --- closed vocabulary ---
bad = [(r["id"], r["classification"]) for r in rows if r["classification"] not in VOCAB]
print(f"vocab violations: {len(bad)} {bad}")
if bad:
    fail.append("classification outside the 15-item closed set")

# --- unique ids ---
ids = [r["id"] for r in rows]
print(f"unique ids      : {len(set(ids))} of {len(ids)}")
if len(set(ids)) != len(ids):
    fail.append("duplicate ids")

# --- material distinctness: body hashes ---
hashes = [r["provenance"].get("body_sha256_16") for r in rows]
print(
    f"unique body hashes: {len(set(h for h in hashes if h))} of {sum(1 for h in hashes if h)}"
)
if len(set(h for h in hashes if h)) != sum(1 for h in hashes if h):
    fail.append("duplicate body hashes -> a trivial fork/renamed copy slipped in")

# --- RE-RESOLVE every provenance anchor independently ---
print("\n--- independent provenance re-resolution ---")
unresolved = []
for r in rows:
    p = r["provenance"]
    kind, anchor = p["kind"], p["anchor"]
    ok = False
    if kind == "file-live":
        ok = os.path.isfile(anchor)
    else:
        path = anchor.split(":", 1)[1].split("  (bare mirror")[0]
        rc = subprocess.run(
            ["git", "--git-dir", MIRROR, "cat-file", "-t", f"{REF}:{path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        ok = rc.returncode == 0
    if not ok:
        unresolved.append(r["id"])
print(
    f"re-resolved     : {len(rows) - len(unresolved)}/{len(rows)}   unresolved={unresolved}"
)
if unresolved:
    fail.append(f"{len(unresolved)} provenance anchors do not resolve")

# --- DETECTOR CONTROLS (both states) ---
print("\n--- detector controls ---")
c1 = os.path.isfile(r"C:\Users\Prekzursil\.claude\workflows\design-gate.mjs")
c2 = os.path.isfile(r"C:\Users\Prekzursil\.claude\workflows\THIS-DOES-NOT-EXIST.mjs")
print(
    f"[CTRL] fs probe: known-present={c1} (must be True)  known-absent={c2} (must be False)"
)
rc_p = subprocess.run(
    ["git", "--git-dir", MIRROR, "cat-file", "-t", f"{REF}:workflows/rtv-pdr.js"],
    capture_output=True,
    text=True,
).returncode
rc_a = subprocess.run(
    ["git", "--git-dir", MIRROR, "cat-file", "-t", f"{REF}:workflows/nope.js"],
    capture_output=True,
    text=True,
).returncode
print(
    f"[CTRL] mirror probe: known-present rc={rc_p} (must be 0)  known-absent rc={rc_a} (must be non-zero)"
)
if not (c1 and not c2 and rc_p == 0 and rc_a != 0):
    fail.append(
        "DETECTOR CONTROL FAILED -- the resolution probe above measures nothing"
    )

# --- classification distribution ---
print("\nclassification distribution:")
for k, v in sorted(
    Counter(r["classification"] for r in rows).items(), key=lambda kv: -kv[1]
):
    print(f"  {k:<24} {v}")
changed = [r for r in rows if r.get("classification_changed")]
print(f"\nre-classified vs prior pass: {len(changed)}")
for r in changed:
    print(
        f"  {r['id']:<44} {r['classification_prior_pass']:<22} -> {r['classification']}"
    )

# --- coverage of the required record fields per the spawn brief ---
print("\nspawn-brief record fields present on all 32:")
for f in (
    "provenance",
    "license",
    "license_source",
    "maintenance_state",
    "task_fit",
    "stages",
    "roles",
    "tools",
    "stop_rules",
    "failure_behaviour",
    "benchmark_evidence",
):
    n = sum(1 for r in rows if r.get(f) not in (None, "", [], {}))
    print(f"  {f:<22} {n}/32")

print()
if fail:
    print("FAILED:build/wfa-1 " + "; ".join(fail))
    sys.exit(1)
print(
    "SUCCESS:build/wfa-1 32 candidates, closed vocabulary, 32/32 anchors independently re-resolved, 0 duplicate bodies, detector controls pass"
)
