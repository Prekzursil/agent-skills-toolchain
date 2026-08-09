#!/usr/bin/env python3
"""Measure the ACTUAL shape of every field across all work_units in the catalog.

Read-only probe. Emits JSON to stdout. No mutation of any catalog file.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "WORK-UNIT-CATALOG.json"

MANDATED_19 = [
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
]


def jtype(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        inner = sorted({jtype(x) for x in v}) or ["<empty>"]
        return "array[" + "|".join(inner) + "]"
    if isinstance(v, dict):
        return "object{" + ",".join(sorted(v.keys())) + "}"
    return type(v).__name__


def main() -> int:
    d = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = d["work_units"]
    out: dict[str, object] = {
        "catalog": str(CATALOG),
        "n_work_units": len(wu),
        "schema_version": d.get("schema_version"),
        "field_types": {},
        "missing_mandated": {},
        "extra_fields": {},
        "value_domains": {},
        "numeric_ranges": {},
        "id_forms": {},
        "examples": {},
    }

    type_counts: dict[str, Counter] = defaultdict(Counter)
    examples: dict[str, dict[str, object]] = defaultdict(dict)
    missing = Counter()
    extra = Counter()
    for u in wu:
        for k in MANDATED_19:
            if k not in u:
                missing[k] += 1
        for k, v in u.items():
            t = jtype(v)
            type_counts[k][t] += 1
            if t not in examples[k]:
                examples[k][t] = {"unit": u.get("id"), "value": v}
            if k not in MANDATED_19:
                extra[k] += 1

    out["field_types"] = {k: dict(c) for k, c in sorted(type_counts.items())}
    out["missing_mandated"] = dict(missing)
    out["extra_fields"] = dict(extra)

    # value domains for likely-enum fields
    for k in ("phase", "execution_substrate", "owner_approval_required"):
        c = Counter()
        for u in wu:
            v = u.get(k)
            c[json.dumps(v, sort_keys=True) if not isinstance(v, str) else v] += 1
        out["value_domains"][k] = dict(c.most_common())

    # flattened token domains for arrays of strings
    for k in ("tool_permissions", "failure_classification"):
        c = Counter()
        for u in wu:
            v = u.get(k)
            if isinstance(v, list):
                for x in v:
                    c[x if isinstance(x, str) else json.dumps(x, sort_keys=True)] += 1
            elif isinstance(v, str):
                c["<STRING:" + v[:60] + ">"] += 1
        out["value_domains"][k] = dict(c.most_common(60))

    # assigned_model_vendor_role sub-shapes
    amvr = Counter()
    amvr_keys = Counter()
    models = Counter()
    vendors = Counter()
    roles = Counter()
    for u in wu:
        v = u.get("assigned_model_vendor_role")
        amvr[jtype(v)] += 1
        if isinstance(v, dict):
            amvr_keys[",".join(sorted(v))] += 1
            models[str(v.get("model"))] += 1
            vendors[str(v.get("vendor"))] += 1
            roles[str(v.get("role"))] += 1
        elif isinstance(v, str):
            parts = v.split("/")
            if len(parts) == 3:
                models[parts[0]] += 1
                vendors[parts[1]] += 1
                roles[parts[2]] += 1
    out["value_domains"]["assigned_model_vendor_role_shape"] = dict(amvr)
    out["value_domains"]["assigned_model_vendor_role_keysets"] = dict(amvr_keys)
    out["value_domains"]["models"] = dict(models.most_common(40))
    out["value_domains"]["vendors"] = dict(vendors.most_common(40))
    out["value_domains"]["roles_top"] = dict(roles.most_common(40))

    # numeric ranges
    ts = [
        u["timeout_seconds"]
        for u in wu
        if isinstance(u.get("timeout_seconds"), (int, float))
        and not isinstance(u.get("timeout_seconds"), bool)
    ]
    out["numeric_ranges"]["timeout_seconds"] = {
        "n": len(ts),
        "min": min(ts) if ts else None,
        "max": max(ts) if ts else None,
        "distinct": sorted(set(ts))[:40],
        "nonint": [u["id"] for u in wu if isinstance(u.get("timeout_seconds"), str)][
            :10
        ],
    }

    # id forms
    import re

    pat = re.compile(r"^([A-Z]{2,4})-(\d{4})$")
    forms = Counter()
    bad = []
    for u in wu:
        i = u.get("id")
        m = pat.match(i) if isinstance(i, str) else None
        if m:
            forms[m.group(1)] += 1
        else:
            bad.append(i)
    out["id_forms"] = {
        "prefix_counts": dict(forms.most_common()),
        "nonconforming": bad[:40],
        "n_nonconforming": len(bad),
    }

    # dependency token forms
    dep_forms = Counter()
    for u in wu:
        deps = u.get("dependencies")
        if isinstance(deps, list):
            for t in deps:
                if not isinstance(t, str):
                    dep_forms["<NONSTRING>"] += 1
                elif pat.match(t):
                    dep_forms["UNIT-ID"] += 1
                elif re.match(r"^B\d{2}$", t):
                    dep_forms["BUCKET-Bnn"] += 1
                elif t == "":
                    dep_forms["<EMPTY>"] += 1
                else:
                    dep_forms["OTHER:" + t] += 1
        elif isinstance(deps, str):
            dep_forms["<STRING FIELD>"] += 1
    out["value_domains"]["dependency_token_forms"] = dict(dep_forms.most_common(50))

    # output_schema referenced files
    oschemas = Counter()
    for u in wu:
        v = u.get("output_schema")
        if isinstance(v, str):
            oschemas[v.split("#")[0]] += 1
    out["value_domains"]["output_schema_files"] = dict(oschemas.most_common(40))

    out["examples"] = {
        k: {t: (str(x["value"])[:220], x["unit"]) for t, x in v.items()}
        for k, v in examples.items()
    }
    json.dump(out, sys.stdout, indent=1, sort_keys=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
