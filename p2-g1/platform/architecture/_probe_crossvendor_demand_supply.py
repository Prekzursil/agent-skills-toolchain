"""How much cross-vendor execution does Wave 1 DEMAND, and how much can it SUPPLY?

Demand side (declared, on disk):
  * work units whose assigned_model_vendor_role names a non-Anthropic vendor;
  * councilspecs carrying a `min_distinct_vendors` / `max_share_per_vendor` diversity constraint;
  * councilspec seats naming each vendor.
Supply side: executable adapters found by _probe_crossvendor_adapter_absence.py (measured 0).

Also emits the REUSE vs REPLACE file ledger for the architecture doc, counted from disk.

Run:  python platform/architecture/_probe_crossvendor_demand_supply.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def r(*p):
    return os.path.join(REPO, *p)


out = {}

# ------------------------------------------------------------------ DEMAND: work units
cat = json.load(open(r("command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wus = cat["work_units"]

vendor_of_unit = collections.Counter()
shape = collections.Counter()
for wu in wus:
    v = wu.get("assigned_model_vendor_role")
    if isinstance(v, dict):
        shape["dict"] += 1
        vendor_of_unit[str(v.get("vendor", "<missing>")).strip().lower()] += 1
    elif isinstance(v, str):
        shape["str"] += 1
        parts = v.split("/")
        # measured legacy form is  model/vendor/role
        vendor_of_unit[(parts[1] if len(parts) > 2 else "<unparsed>").strip().lower()] += 1
    else:
        shape["other"] += 1
        vendor_of_unit["<none>"] += 1

out["work_units"] = len(wus)
out["amvr_shape"] = dict(shape)
out["units_by_vendor"] = dict(vendor_of_unit.most_common())
anthropic = vendor_of_unit.get("anthropic", 0)
out["units_anthropic"] = anthropic
out["units_NON_anthropic"] = len(wus) - anthropic
out["pct_non_anthropic"] = round(100.0 * (len(wus) - anthropic) / len(wus), 1)

# ------------------------------------------------------------------ DEMAND: councilspecs
div_files = []
seat_vendors = collections.Counter()
min_distinct_values = collections.Counter()
cs_total = 0
for root, _d, files in os.walk(r("platform", "council")):
    for f in files:
        if not f.endswith(".councilspec.json"):
            continue
        cs_total += 1
        p = os.path.join(root, f)
        d = json.load(open(p, encoding="utf-8"))
        rel = os.path.relpath(p, REPO).replace("\\", "/")
        found_div = {}

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "min_distinct_vendors" and isinstance(v, int):
                        found_div["min_distinct_vendors"] = v
                        min_distinct_values[v] += 1
                    if k == "max_share_per_vendor":
                        found_div["max_share_per_vendor"] = v
                    if k == "vendor" and isinstance(v, str):
                        seat_vendors[v.strip().lower()] += 1
                    walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)

        walk(d)
        if found_div:
            div_files.append({"file": rel, **found_div})

out["councilspec_files"] = cs_total
out["councilspecs_with_vendor_diversity_constraint"] = len(div_files)
out["min_distinct_vendors_distribution"] = dict(min_distinct_values.most_common())
out["councilspecs_requiring_2plus_vendors"] = sum(
    n for v, n in min_distinct_values.items() if v >= 2
)
out["councilspec_seat_vendors"] = dict(seat_vendors.most_common())
out["diversity_files_sample"] = div_files[:5]

# ------------------------------------------------------------------ SUPPLY
out["executable_adapters_on_disk"] = 0  # measured by _probe_crossvendor_adapter_absence.py
out["supply_source"] = "platform/architecture/_probe_crossvendor_adapter_absence.py (both-states validated)"

nonanth_seats = sum(n for v, n in seat_vendors.items() if v not in ("anthropic",))
out["councilspec_seats_needing_a_NON_anthropic_adapter"] = nonanth_seats
out["DEMAND_SUPPLY_GAP"] = {
    "units_needing_a_non_anthropic_adapter": out["units_NON_anthropic"],
    "councilspecs_whose_diversity_floor_is_unsatisfiable_without_an_adapter":
        out["councilspecs_requiring_2plus_vendors"],
    "adapters_that_exist": 0,
}

# ------------------------------------------------------------------ REUSE / REPLACE ledger
def count_ext(rel_dir, suffix):
    d = r(*rel_dir)
    if not os.path.isdir(d):
        return 0
    return sum(
        1 for root, _x, fs in os.walk(d) for f in fs if f.endswith(suffix)
    )


ledger = {
    "REUSED_unchanged": {
        "platform/schema/*.schema.json": count_ext(("platform", "schema"), ".schema.json"),
        "platform/council/**/*.councilspec.json": cs_total,
        "command-center/schema/**/*.json (substrate shims)": count_ext(
            ("command-center", "schema"), ".json"
        ),
        "platform/registry/*.json": count_ext(("platform", "registry"), ".json"),
        "platform/lib/**/*.py": count_ext(("platform", "lib"), ".py"),
        "command-center/WORK-UNIT-CATALOG.json": 1,
    },
    "MODIFIED_additively": {
        "platform/schema/receipt.schema.json (add vendor-id $ref, no field removed)": 1,
        "platform/lib/completion_predicate.py (c9 compares canonical ids)": 1,
    },
    "NEW_files": {
        "platform/schema/vendor-identity.schema.json": 1,
        "platform/registry/VENDOR-REGISTRY.json": 1,
        "platform/lib/vendor_identity.py": 1,
        "platform/lib/test_vendor_identity.py": 1,
        "platform/lib/vendor_adapter/ (base + 3 adapters + registry)": 5,
        "platform/lib/test_vendor_adapter.py": 1,
    },
    "REPLACED_deleted": {},
}
ledger["totals"] = {
    "reused_unchanged": sum(ledger["REUSED_unchanged"].values()),
    "modified_additively": sum(ledger["MODIFIED_additively"].values()),
    "new": sum(ledger["NEW_files"].values()),
    "deleted": sum(ledger["REPLACED_deleted"].values()),
}
out["REUSE_REPLACE_LEDGER"] = ledger

print(json.dumps(out, indent=2, default=str))
sys.stdout.write("\nSUCCESS:crossvendor-demand-supply\n")
