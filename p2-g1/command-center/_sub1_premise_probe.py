#!/usr/bin/env python3
"""substrate/output-schema  --  STEP 1: re-verify the briefed premise from disk.

Counts distinct output_schema values in WORK-UNIT-CATALOG.json work_units[] and
tests each for existence on disk. Also inventories what DOES exist so the fix can
be designed against real names, not the brief's summary.

DETECTOR CONTROL: the existence checker is proven against a KNOWN-PRESENT path
(platform/schema/receipt.schema.json) and a KNOWN-ABSENT path before any
"0 resolve" claim is emitted.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"
CATALOG = os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json")


def load_catalog():
    with open(CATALOG, "r", encoding="utf-8") as fh:
        return json.load(fh)


def exists_on_disk(rel_or_abs: str) -> bool:
    """Resolve a catalog output_schema string against the repo root."""
    s = rel_or_abs.strip()
    if not s:
        return False
    cand = s if os.path.isabs(s) else os.path.join(REPO, s)
    return os.path.isfile(cand)


def detector_control():
    known_present = "platform/schema/receipt.schema.json"
    known_absent = "platform/schema/__definitely_not_here__.schema.json"
    p = exists_on_disk(known_present)
    a = exists_on_disk(known_absent)
    return {
        "known_present_path": known_present,
        "known_present_result": p,
        "known_absent_path": known_absent,
        "known_absent_result": a,
        "detector_valid": (p is True and a is False),
    }


def main():
    ctl = detector_control()
    d = load_catalog()

    out = {"detector_control": ctl}
    if not ctl["detector_valid"]:
        out["FATAL"] = "detector failed its own control; no absence claim emitted"
        print(json.dumps(out, indent=2))
        return 1

    out["catalog_top_level_keys"] = sorted(d.keys()) if isinstance(d, dict) else "NOT-A-DICT"
    wus = d.get("work_units", [])
    items = d.get("items", [])
    out["work_units_len"] = len(wus)
    out["items_len"] = len(items)

    # --- output_schema census over work_units[] ---
    refs = []
    missing_field = 0
    non_string = 0
    per_unit = {}
    for wu in wus:
        uid = wu.get("id") or wu.get("unit_id") or wu.get("wu_id")
        v = wu.get("output_schema")
        if v is None:
            missing_field += 1
            continue
        if not isinstance(v, str):
            non_string += 1
            continue
        refs.append(v)
        per_unit[uid] = v

    cnt = Counter(refs)
    distinct = sorted(cnt)
    out["output_schema_total_references"] = len(refs)
    out["output_schema_distinct_count"] = len(distinct)
    out["output_schema_missing_field_units"] = missing_field
    out["output_schema_non_string_units"] = non_string

    resolving = [p for p in distinct if exists_on_disk(p)]
    dangling = [p for p in distinct if not exists_on_disk(p)]
    out["distinct_resolving_on_disk"] = len(resolving)
    out["distinct_dangling"] = len(dangling)
    out["resolving_examples"] = resolving[:20]
    dangling_refcount = sum(cnt[p] for p in dangling)
    out["dangling_reference_count"] = dangling_refcount
    out["resolving_reference_count"] = len(refs) - dangling_refcount

    # prefix profile of dangling paths -- tells us which dir tree they name
    prefixes = Counter()
    for p in distinct:
        parts = p.replace("\\", "/").split("/")
        prefixes["/".join(parts[:2]) if len(parts) > 1 else parts[0]] += 1
    out["distinct_prefix_profile"] = dict(prefixes.most_common())

    # basename profile -- the actual schema NAMES being demanded
    basenames = Counter(os.path.basename(p) for p in distinct)
    out["distinct_basename_count"] = len(basenames)
    out["distinct_basenames_all"] = sorted(basenames)

    # top-referenced distinct paths
    out["top_20_by_reference"] = cnt.most_common(20)

    # --- what physically exists today ---
    phys = []
    for root, _dirs, files in os.walk(os.path.join(REPO, "platform", "schema")):
        for f in files:
            if f.endswith(".json"):
                phys.append(os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/"))
    out["physical_platform_schema_files"] = sorted(phys)
    out["command_center_schema_dir_exists"] = os.path.isdir(os.path.join(REPO, "command-center", "schema"))

    # --- structure of one representative work unit (for receipt construction) ---
    if wus:
        sample = wus[0]
        out["sample_work_unit_keys"] = sorted(sample.keys())
        out["sample_work_unit"] = sample

    # bucket / class fields that might drive per-class schemas
    for field in ("bucket", "phase", "wave", "class", "category", "track", "lane", "kind", "type"):
        vals = Counter(str(wu.get(field)) for wu in wus if wu.get(field) is not None)
        if vals:
            out.setdefault("class_like_fields", {})[field] = dict(vals.most_common(30))

    with open(os.path.join(REPO, "command-center", "_sub1_premise_probe_out.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    # console summary
    slim = {k: v for k, v in out.items() if k not in ("sample_work_unit", "distinct_basenames_all", "physical_platform_schema_files")}
    print(json.dumps(slim, indent=2)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
