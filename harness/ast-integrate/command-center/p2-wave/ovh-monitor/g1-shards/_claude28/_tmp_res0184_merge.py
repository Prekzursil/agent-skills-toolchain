import json
import sys

sys.path.insert(0, r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\RES-0184")
import engine as E  # noqa: E402

ART = r"C:\Users\Prekzursil\source\ast-integrate\command-center\research\evidence-quality\RES-0184-evidence-threshold-by-claim-severity.json"

doc = E.build_document()

with open(ART, encoding="utf-8") as f:
    art = json.load(f)

# Merge only the probe-asserted (and directly supporting) fields; keep the
# existing envelope (state, sentinel, tests, timestamps, manifest_registration).
for key in (
    "bars",
    "source_classes_used",
    "who_may_lower",
    "sample",
    "rescore",
    "negative_controls",
    "calibration",
    "calibration_reason",
    "answer",
):
    art[key] = doc[key]

with open(ART, "w", encoding="utf-8", newline="\r\n") as f:
    json.dump(art, f, indent=2, ensure_ascii=False)
    f.write("\n")

# Replicate probe assertions against the merged artifact (static checks only).
raw = open(ART, encoding="utf-8").read()
merged = json.loads(raw)
r = merged["rescore"]
gate = "CL-CC-0014-DEFAULT-FLOOR-ENFORCED"
checks = {
    "sentinel": E.SENTINEL in raw,
    "state": merged["state"] == "SUCCESS",
    "calibration": merged["calibration"] == "INFORMATIVE",
    "n20": r["n"] == 20,
    "below_nonzero": r["below_bar_count"] > 0,
    "gate_in_below": gate in r["below_bar_ids"],
    "gate_in_high": gate in r["high_severity_below_ids"],
    "who_p0": merged["who_may_lower"]["P0"] == "owner-only",
    "no_p0_waiver": not (merged["who_may_lower"].get("owner_waiver") or {}).get("p0_waiver_recorded"),
    "p0_rows": any(row["severity"] == "P0" for row in r["rows"]),
}
p0_below = [
    row["claim_id"]
    for row in r["rows"]
    if row["severity"] == "P0"
    and (
        int(row.get("independent_source_count") or 0) < 2
        or int(row.get("source_class_count") or 0) < 2
        or not row.get("executable")
        or not row.get("sherman_kent")
    )
]
checks["independent_p0_below"] = len(p0_below) > 0
rehash = None
import hashlib
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
for row in r["rows"]:
    for lin in row.get("lineage") or []:
        snap, expect = lin.get("snapshot_path"), lin.get("sha256")
        if not snap or not expect:
            continue
        path = REPO / snap
        if not path.is_file():
            continue
        b = path.read_bytes()
        got = {hashlib.sha256(b).hexdigest(), hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()}
        rehash = expect in got
        break
    if rehash is not None:
        break
checks["rehash"] = bool(rehash)
print(json.dumps(checks, indent=1))
print("p0_below:", p0_below)
print("below_bar_count:", r["below_bar_count"], "high:", r["high_severity_below_ids"])
bad = [k for k, ok in checks.items() if not ok]
print("BAD:" if bad else "ALL-OK", bad)
