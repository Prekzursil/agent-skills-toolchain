#!/usr/bin/env python3
"""STEP 1c: what per-class CONTRACT does the catalog itself already declare?

Three questions the fix design depends on:
  Q1 how many of the demanded '#/$defs/<name>' fragments exist in the ONE physical
     receipt.schema.json today, and which do not?
  Q2 the 159 prose-annotated refs carry 'profile=X (required: a, b, c)' -- parse them.
     Those are the author's declared field contract per class, i.e. free ground truth.
  Q3 the wfa-schema-pack.json (127 refs) and the two meta-schema mirrors: what are they?

Also reuses receipt_schema_gate.parse_schema_ref rather than re-implementing the split
(the repo already owns that function -- dup-guard).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

REPO = "C:/Users/Prekzursil/source/ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))
from receipt_schema_gate import parse_schema_ref  # noqa: E402  (repo-owned splitter)

CATALOG = os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json")
RECEIPT = os.path.join(REPO, "platform", "schema", "receipt.schema.json")


def main():
    with open(CATALOG, "r", encoding="utf-8") as fh:
        wus = json.load(fh)["work_units"]
    receipt = json.loads(open(RECEIPT, "rb").read().decode("utf-8"))
    have_defs = set(receipt.get("$defs", {}))

    out = {"physical_receipt_defs_count": len(have_defs), "physical_receipt_defs": sorted(have_defs)}

    # ---- control: prove parse_schema_ref behaves on known shapes -------------
    ctl = {
        "bare": parse_schema_ref("command-center/schema/x.schema.json"),
        "pointer": parse_schema_ref("command-center/schema/receipt.schema.json#/$defs/security_report"),
        "annotated": parse_schema_ref("command-center/schema/receipt.schema.json profile=foo (required: a, b)"),
        "url": parse_schema_ref("https://json-schema.org/draft/2020-12/schema"),
    }
    out["parse_schema_ref_control"] = {k: list(v) for k, v in ctl.items()}

    demanded_frags = defaultdict(Counter)   # file -> Counter(fragment)
    annotations = {}                        # logical file -> list of raw annotations
    profiles = defaultdict(Counter)         # logical file -> Counter(profile name)
    required_sets = defaultdict(Counter)    # logical file -> Counter(field)
    per_file_refcount = Counter()

    ann_re = re.compile(r"profile=([^\s(]+)")
    req_re = re.compile(r"\(required:\s*([^)]*)\)")

    for wu in wus:
        raw = wu["output_schema"]
        f, frag = parse_schema_ref(raw)
        if f.startswith("http"):
            per_file_refcount["<META-SCHEMA-URL>"] += 1
            continue
        per_file_refcount[f] += 1
        if frag:
            demanded_frags[f][frag] += 1
        if " " in raw:
            tail = raw.split(" ", 1)[1]
            annotations.setdefault(f, []).append(tail)
            m = ann_re.search(raw)
            if m:
                profiles[f][m.group(1)] += 1
            m2 = req_re.search(raw)
            if m2:
                for fld in m2.group(1).split(","):
                    fld = fld.strip().rstrip("[]")
                    if fld:
                        required_sets[f][fld] += 1

    # Q1 fragment coverage
    all_frag_names = Counter()
    for f, c in demanded_frags.items():
        for frag, n in c.items():
            all_frag_names[frag.lstrip("#").lstrip("/").replace("$defs/", "")] += n
    present = sorted(n for n in all_frag_names if n in have_defs)
    absent = sorted(n for n in all_frag_names if n not in have_defs)
    out["Q1_distinct_fragments_demanded"] = len(all_frag_names)
    out["Q1_fragments_present_in_receipt_schema"] = present
    out["Q1_fragments_ABSENT_count"] = len(absent)
    out["Q1_fragments_ABSENT"] = absent
    out["Q1_refs_hitting_present_fragment"] = sum(all_frag_names[n] for n in present)
    out["Q1_refs_hitting_absent_fragment"] = sum(all_frag_names[n] for n in absent)

    # Q2 declared required-field contracts
    out["Q2_files_with_annotation"] = len(annotations)
    out["Q2_files_with_parsed_required_set"] = len(required_sets)
    out["Q2_distinct_profile_names"] = sum(len(v) for v in profiles.values())
    out["Q2_required_field_frequency_global"] = dict(
        Counter({k: sum(c[k] for c in required_sets.values()) for c in required_sets.values() for k in c}).most_common(40)
    )
    out["Q2_example_contracts"] = {
        f: {"profiles": dict(profiles.get(f, {})), "required": sorted(required_sets[f])}
        for f in list(required_sets)[:12]
    }
    out["Q2_all_required_sets"] = {f: sorted(v) for f, v in sorted(required_sets.items())}
    out["Q2_all_profiles"] = {f: dict(v) for f, v in sorted(profiles.items())}

    # Q3 special files
    out["Q3_per_file_refcount_top"] = per_file_refcount.most_common(6)
    out["Q3_wfa_fragments"] = dict(demanded_frags.get("command-center/wfa/schema/wfa-schema-pack.json", {}))
    out["Q3_meta_mirrors"] = [f for f in per_file_refcount if "/meta" in f or "/_meta" in f]
    out["Q3_meta_url_refs"] = per_file_refcount["<META-SCHEMA-URL>"]
    out["Q3_receipt_schema_refs_bare_vs_frag"] = {
        "total": per_file_refcount["command-center/schema/receipt.schema.json"],
        "with_fragment": sum(demanded_frags["command-center/schema/receipt.schema.json"].values()),
    }

    with open(os.path.join(REPO, "command-center", "_sub1_contract_probe_out.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    slim = {k: v for k, v in out.items() if not k.startswith(("Q2_all", "physical_receipt_defs"))}
    slim["Q1_fragments_ABSENT"] = absent[:70]
    print(json.dumps(slim, indent=2)[:9000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
