"""C11 lane probe: enumerate the receipt corpus that condition 11 sits on.

Answers, from disk (not from the owner-decision doc, which is re-verified here):
  (a) how many receipt-shaped JSON files under command-center/ carry a
      manifest_registration block, what their manifest_path values are, and how
      many point at the charter manifest command-center/ARTIFACT-MANIFEST.json;
  (b) for every receipt pointing at the OLD charter manifest, are ALL its
      declared artifacts[] present on disk today (the producer's fail-closed
      walk must be able to go green on this corpus, or the corpus is the
      finding);
  (c) how many carry registered=true and whether any of those live outside
      probe/fixture directories.
Writes the census to command-center/p2-next/C11-CENSUS.json.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
CC = ROOT / "command-center"
OLD = "command-center/ARTIFACT-MANIFEST.json"
NEW = "command-center/UNIT-ARTIFACT-MANIFEST.json"

rows = []
scanned = 0
for p in CC.rglob("*.json"):
    try:
        raw = p.read_bytes()
        if b"manifest_registration" not in raw:
            continue
        d = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        continue
    if not isinstance(d, dict) or "unit_id" not in d or "state" not in d:
        continue
    scanned += 1
    mr = d.get("manifest_registration")
    reg = mr.get("registered") if isinstance(mr, dict) else None
    mp = mr.get("manifest_path") if isinstance(mr, dict) else None
    arts = d.get("artifacts")
    declared = (
        [a.get("path") for a in arts if isinstance(a, dict)]
        if isinstance(arts, list)
        else []
    )
    missing = [a for a in declared if not (ROOT / str(a)).exists()]
    rows.append(
        {
            "receipt": str(p.relative_to(ROOT)).replace("\\", "/"),
            "unit_id": d.get("unit_id"),
            "state": d.get("state"),
            "registered": reg,
            "manifest_path": mp,
            "declared_artifacts": len(declared),
            "missing_artifacts": missing,
        }
    )

old = [r for r in rows if r["manifest_path"] == OLD]
new = [r for r in rows if r["manifest_path"] == NEW]
other = [r for r in rows if r["manifest_path"] not in (OLD, NEW)]
reg_true = [r for r in rows if r["registered"] is True]
incomplete = [r for r in old if r["missing_artifacts"]]

print(f"(a) receipt-shaped files with manifest_registration: {scanned}")
print(f"    -> old charter manifest {OLD}: {len(old)}")
print(f"    -> new unit manifest {NEW}: {len(new)}")
print(f"    -> other paths: {len(other)}")
for r in other:
    print(
        f"       other: {r['receipt']} -> {r['manifest_path']!r} registered={r['registered']}"
    )
print(
    f"(b) old-path receipts with ALL declared artifacts on disk: {len(old) - len(incomplete)}/{len(old)}"
)
for r in incomplete:
    print(f"       incomplete: {r['receipt']} missing={r['missing_artifacts'][:3]}")
print(f"(c) registered=true rows: {len(reg_true)}")
for r in reg_true:
    print(f"       true: {r['receipt']} ({r['unit_id']})")

# also: no declared-artifact receipts (the producer's empty-walk case)
no_arts = [r for r in old if r["declared_artifacts"] == 0]
print(
    f"(d) old-path receipts declaring ZERO artifacts (producer empty-walk case): {len(no_arts)}"
)
for r in no_arts:
    print(f"       zero-artifacts: {r['receipt']} ({r['unit_id']}) state={r['state']}")

census = {
    "scanned_with_block": scanned,
    "old_path_count": len(old),
    "new_path_count": len(new),
    "other_path": [
        {"receipt": r["receipt"], "manifest_path": r["manifest_path"]} for r in other
    ],
    "old_path_all_artifacts_present": len(old) - len(incomplete),
    "old_path_incomplete": [
        {"receipt": r["receipt"], "missing": r["missing_artifacts"]} for r in incomplete
    ],
    "registered_true": [r["receipt"] for r in reg_true],
    "old_path_zero_artifacts": [r["receipt"] for r in no_arts],
    "states": dict(Counter(r["state"] for r in old)),
    "rows": rows,
}
out = ROOT / "command-center/p2-next/C11-CENSUS.json"
out.write_text(json.dumps(census, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"SUCCESS:c11-enumerate census -> {out.relative_to(ROOT)}")
