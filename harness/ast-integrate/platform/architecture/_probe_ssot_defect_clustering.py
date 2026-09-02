"""THE load-bearing measurement for generated-SSOT: do catalog defects cluster by the
authoring provenance (_source_slice_file) rather than by unit semantics?

If YES, the defect cause is "N humans/agents authored the same field N ways" and a generator
removes the cause by construction. If NO (defects spread evenly), generation buys much less
and this architecture's central claim is weak.

Also derives the brief's 41 exactly, and pins what the 96 sentinel failures REALLY are.

Terminal state: SUCCESS:ssot-clustering / FAILED:...
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).with_name("_probe_ssot_defect_clustering_out.json")


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wus = cat["work_units"]
    r: dict = {}

    slices = Counter(w.get("_source_slice_file", "<none>") for w in wus)
    r["slice_files"] = {
        "count": len(slices),
        "units_per_slice": dict(slices.most_common()),
    }

    # ---- defect predicates, each independent of platform/lib ----
    def d_vendor_role_str(w):
        return isinstance(w.get("assigned_model_vendor_role"), str)

    def d_tests_required_str(w):
        return isinstance(w.get("tests_required"), str)

    def d_failure_class_str(w):
        return isinstance(w.get("failure_classification"), str)

    def d_output_schema_prose(w):
        v = w.get("output_schema")
        return isinstance(v, str) and (" + " in v or "(" in v)

    def d_dep_bare_prefix(w):
        return any(
            isinstance(x, str) and re.fullmatch(r"[A-Z]{2,6}", x)
            for x in (w.get("dependencies") or [])
        )

    def d_sentinel_not_exact(w):
        return w.get("completion_sentinel") != f"SUCCESS:{w['id']}"

    preds = {
        "vendor_role_is_string": d_vendor_role_str,
        "tests_required_is_string": d_tests_required_str,
        "failure_classification_is_string": d_failure_class_str,
        "output_schema_is_prose_compound": d_output_schema_prose,
        "dependency_is_bare_family_prefix": d_dep_bare_prefix,
        "sentinel_not_exact_SUCCESS_id": d_sentinel_not_exact,
    }

    r["defects"] = {}
    for name, fn in preds.items():
        hit = [w for w in wus if fn(w)]
        by_slice = Counter(w.get("_source_slice_file", "<none>") for w in hit)
        # concentration: what fraction of hits live in the single worst slice,
        # and how many slices contain ANY hit
        top = by_slice.most_common(1)[0] if by_slice else ("<none>", 0)
        r["defects"][name] = {
            "units_hit": len(hit),
            "slices_containing_a_hit": len(by_slice),
            "of_total_slices": len(slices),
            "worst_slice": top[0],
            "worst_slice_hits": top[1],
            "worst_slice_total_units": slices.get(top[0], 0),
            "worst_slice_hit_rate": round(top[1] / slices[top[0]], 4)
            if top[1]
            else 0.0,
            "share_of_hits_in_worst_slice": round(top[1] / len(hit), 4) if hit else 0.0,
            "by_slice": dict(by_slice.most_common()),
            "sample_ids": [w["id"] for w in hit[:6]],
        }

    # ---- do the 3 "type" defects hit the SAME units? (one convention, one author) ----
    s_vr = {w["id"] for w in wus if d_vendor_role_str(w)}
    s_tr = {w["id"] for w in wus if d_tests_required_str(w)}
    s_fc = {w["id"] for w in wus if d_failure_class_str(w)}
    r["type_defect_overlap"] = {
        "vendor_role_str": len(s_vr),
        "tests_required_str": len(s_tr),
        "failure_classification_str": len(s_fc),
        "tests_AND_failure": len(s_tr & s_fc),
        "tests_AND_failure_AND_vendor": len(s_tr & s_fc & s_vr),
        "union": len(s_vr | s_tr | s_fc),
        "tr_equals_fc": s_tr == s_fc,
    }

    # ---- derive the brief's 41 exactly ----
    bare = Counter()
    for w in wus:
        for x in w.get("dependencies") or []:
            if isinstance(x, str) and re.fullmatch(r"[A-Z]{2,6}", x):
                bare[x] += 1
    r["bare_family_dependency_occurrences"] = {
        "per_token": dict(bare.most_common()),
        "total": sum(bare.values()),
    }

    # ---- what fraction of catalog BYTES is low-cardinality repetition? ----
    field_bytes = Counter()
    for w in wus:
        for k, v in w.items():
            field_bytes[k] += len(json.dumps({k: v}, ensure_ascii=False)) - 2
    distinct = {}
    for k in field_bytes:
        vals = {
            json.dumps(w.get(k), sort_keys=True, ensure_ascii=False)
            for w in wus
            if k in w
        }
        distinct[k] = len(vals)
    total = sum(field_bytes.values())
    # "repetition bytes" = bytes spent on fields whose distinct-value count is <= 5% of units
    rep = sum(b for k, b in field_bytes.items() if distinct[k] <= 0.05 * len(wus))
    r["byte_economics"] = {
        "total_work_unit_field_bytes": total,
        "bytes_in_fields_with_le_5pct_distinct_values": rep,
        "fraction": round(rep / total, 4),
        "per_field": {
            k: {"bytes": field_bytes[k], "distinct": distinct[k]}
            for k in sorted(field_bytes, key=lambda x: -field_bytes[x])
        },
    }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(
        json.dumps({k: v for k, v in r.items() if k != "byte_economics"}, indent=2)[
            :7000
        ]
    )
    print("--- byte economics ---")
    be = r["byte_economics"]
    print("total field bytes", be["total_work_unit_field_bytes"])
    print(
        "low-cardinality bytes",
        be["bytes_in_fields_with_le_5pct_distinct_values"],
        "=",
        be["fraction"],
    )
    print("wrote", OUT)
    print("SUCCESS:ssot-clustering")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-clustering {type(exc).__name__}: {exc}")
        raise
