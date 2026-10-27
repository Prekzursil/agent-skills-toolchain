"""Probe: does the substrate's ref splitter silently DROP co-declared schemas?

parse_schema_ref (platform/lib/receipt_schema_gate.py:208-220) keeps only the text
before the first " + " / " (" / " profile=". Anything after is discarded, so a unit
that declares TWO schemas is only ever checked against the first.

This probe counts the dropped tails, tests whether they name real repo paths, and
carries BOTH detector controls:
  control-A (known-present): a hand-picked compound ref must be split into 2 parts.
  control-B (known-absent):  a plain single-path ref must yield 0 dropped tails.
"""
import json
import os
import re
import sys

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))
from receipt_schema_gate import parse_schema_ref  # noqa: E402

cat = json.load(open(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wus = cat["work_units"]

PATHISH = re.compile(r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+\.(?:json|schema\.json)")

out = {}

# ---- controls ------------------------------------------------------------
ctrlA_in = "command-center/schema/receipt.schema.json + tools/marketplace/schema/advisory.schema.json"
a_head, a_frag = parse_schema_ref(ctrlA_in)
ctrlA = {
    "input": ctrlA_in,
    "head": a_head,
    "tail_dropped": ctrlA_in[len(a_head):].strip(),
    "fires": a_head != ctrlA_in and bool(ctrlA_in[len(a_head):].strip()),
}
ctrlB_in = "command-center/schema/receipt.schema.json"
b_head, _ = parse_schema_ref(ctrlB_in)
ctrlB = {"input": ctrlB_in, "head": b_head, "tail_dropped": ctrlB_in[len(b_head):].strip(),
         "silent_as_expected": b_head == ctrlB_in}
out["detector_control_known_present_compound"] = ctrlA
out["detector_control_known_absent_plain"] = ctrlB
out["detector_valid"] = bool(ctrlA["fires"] and ctrlB["silent_as_expected"])

# ---- the measurement ----------------------------------------------------
# CORRECTION (self-caught detector flaw): parse_schema_ref RETURNS the "#..." fragment
# as its 2nd element, so a fragment is NOT dropped. The dropped text is
# raw minus head minus fragment. An earlier version of this probe counted
# fragments as drops and reported 446 units -- an overclaim, now fixed.
def dropped_text(raw: str) -> str:
    head, frag = parse_schema_ref(raw)
    kept = head + (frag or "")
    return raw[len(kept):].strip() if raw.startswith(kept) else ""


units_with_tail = []
tail_paths = {}
for u in wus:
    raw = u.get("output_schema")
    if not isinstance(raw, str):
        continue
    tail = dropped_text(raw)
    if not tail:
        continue
    units_with_tail.append(u["id"])
    for m in PATHISH.findall(tail):
        tail_paths.setdefault(m, []).append(u["id"])

out["units_declaring_more_than_the_checked_schema"] = len(units_with_tail)
out["pct_of_catalog"] = round(100.0 * len(units_with_tail) / len(wus), 2)
out["distinct_dropped_pathish_tokens"] = len(tail_paths)

exists = {}
for p in sorted(tail_paths):
    fp = os.path.join(REPO, p.replace("/", os.sep))
    exists[p] = {"units": len(tail_paths[p]), "on_disk": os.path.isfile(fp)}
out["dropped_paths"] = exists
out["dropped_paths_on_disk"] = sum(1 for v in exists.values() if v["on_disk"])
out["dropped_paths_MISSING"] = sum(1 for v in exists.values() if not v["on_disk"])
out["units_affected_by_a_MISSING_dropped_path"] = len(
    {uid for p, ids in tail_paths.items() if not exists[p]["on_disk"] for uid in ids}
)

# tail taxonomy: which decoration caused the drop
tax = {"plus": 0, "paren": 0, "profile": 0, "other": 0}
other_samples = []
for u in wus:
    raw = u.get("output_schema")
    if not isinstance(raw, str):
        continue
    tail = dropped_text(raw)
    if not tail:
        continue
    if tail.startswith("+"):
        tax["plus"] += 1
    elif tail.startswith("("):
        tax["paren"] += 1
    elif tail.startswith("profile="):
        tax["profile"] += 1
    else:
        tax["other"] += 1
        if len(other_samples) < 8:
            other_samples.append({"id": u["id"], "raw": raw, "dropped": tail})
out["drop_cause_taxonomy"] = tax
out["drop_cause_other_samples"] = other_samples

# is output_schema free text? count values that are not a bare path[#frag]
BARE = re.compile(r"^[A-Za-z0-9_.\-/]+\.json(#\S*)?$")
nonbare = [u["output_schema"] for u in wus
           if isinstance(u.get("output_schema"), str) and not BARE.match(u["output_schema"].strip())]
out["output_schema_values_that_are_NOT_a_bare_path"] = len(nonbare)
out["nonbare_sample"] = sorted(set(nonbare))[:6]

print(json.dumps(out, indent=1))
marker = "SUCCESS" if out["detector_valid"] else "FAILED"
print(f"{marker}:cf-compound-ref-probe detector_valid={out['detector_valid']}")
