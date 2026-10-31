"""CORRECTED derivability measurement + the contract-vs-content split.

Fixes a detector defect in _probe_ssot_derivability.py: its key
`phase+id_prefix+substrate` CONTAINS the target field for `phase`, `bucket` and
`execution_substrate`, so those three were trivially "fully determined by a small key".
Self-referencing keys are excluded here.

Questions:
  Q1 - split the 27 catalog fields into CONTRACT (machine-checkable shape/policy) vs
       CONTENT (irreducible per-unit prose), and measure the byte share of each.
  Q2 - for each CONTRACT field, how well is it determined by a NON-circular key
       (phase / family / phase+family / slice)? purity = fraction matching the modal
       value for its key group.
  Q3 - where do the measured defects live, contract or content?

Terminal state: SUCCESS:ssot-contract-layer / FAILED:...
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).with_name("_probe_ssot_contract_layer_out.json")

# A field is CONTRACT if a machine can check or choose it from a policy vocabulary;
# CONTENT if it is the irreducible statement of what this one unit must do.
CONTRACT = {
    "assigned_model_vendor_role",
    "completion_sentinel",
    "execution_substrate",
    "failure_classification",
    "output_path",
    "output_schema",
    "owner_approval_required",
    "retry_policy",
    "reviewer_requirement",
    "timeout_seconds",
    "tool_permissions",
}
CONTENT = {
    "evidence_requirement",
    "inputs",
    "mechanism",
    "not_a_duplicate_because",
    "question_or_target",
    "tests_required",
    "title",
}
IDENTITY = {
    "id",
    "phase",
    "slice",
    "bucket",
    "_source_slice_file",
    "notes",
    "spec_anchor",
    "dependencies",
    "dependency_anchors",
}


def canon(v) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wus = cat["work_units"]
    fields = sorted({k for w in wus for k in w.keys()})
    r: dict = {"work_units": len(wus)}

    r["field_classification"] = {
        "contract": sorted(CONTRACT & set(fields)),
        "content": sorted(CONTENT & set(fields)),
        "identity": sorted(IDENTITY & set(fields)),
        "unclassified": sorted(set(fields) - CONTRACT - CONTENT - IDENTITY),
    }

    # ---------- Q1 byte split ----------
    fb = Counter()
    for w in wus:
        for k, v in w.items():
            fb[k] += len(canon(v))
    total = sum(fb.values())

    def share(group):
        b = sum(fb[k] for k in group if k in fb)
        return {"bytes": b, "fraction": round(b / total, 4)}

    r["byte_split"] = {
        "total": total,
        "contract": share(CONTRACT),
        "content": share(CONTENT),
        "identity": share(IDENTITY),
    }

    # ---------- Q2 non-circular derivability ----------
    keyfns = {
        "constant": lambda w: (),
        "phase": lambda w: (w.get("phase"),),
        "family": lambda w: (w["id"].split("-")[0],),
        "phase+family": lambda w: (w.get("phase"), w["id"].split("-")[0]),
        "slice": lambda w: (w.get("_source_slice_file"),),
    }
    deriv = {}
    for f in sorted(CONTRACT & set(fields)):
        present = [w for w in wus if f in w]
        entry = {
            "present": len(present),
            "distinct": len({canon(w.get(f)) for w in present}),
            "bytes": fb[f],
            "purity": {},
            "exact_key": None,
        }
        for kname, kfn in keyfns.items():
            groups = defaultdict(Counter)
            for w in present:
                groups[kfn(w)][canon(w.get(f))] += 1
            hits = sum(c.most_common(1)[0][1] for c in groups.values())
            entry["purity"][kname] = round(hits / len(present), 4)
            if entry["exact_key"] is None and hits == len(present):
                entry["exact_key"] = kname
        best = max(entry["purity"].items(), key=lambda kv: kv[1])
        entry["best_key"] = best[0]
        entry["best_purity"] = best[1]
        entry["units_needing_an_override"] = len(present) - round(
            best[1] * len(present)
        )
        deriv[f] = entry
    r["contract_derivability"] = deriv

    wsum = sum(v["bytes"] for v in deriv.values())
    wavg = (
        sum(v["bytes"] * v["best_purity"] for v in deriv.values()) / wsum if wsum else 0
    )
    r["contract_layer_summary"] = {
        "contract_bytes": wsum,
        "byte_weighted_best_purity": round(wavg, 4),
        "total_overrides_needed": sum(
            v["units_needing_an_override"] for v in deriv.values()
        ),
        "total_contract_field_instances": sum(v["present"] for v in deriv.values()),
        "override_rate": round(
            sum(v["units_needing_an_override"] for v in deriv.values())
            / sum(v["present"] for v in deriv.values()),
            4,
        ),
    }

    # ---------- Q3 where the defects live ----------
    defects = {
        "output_schema_prose_compound": (
            "output_schema",
            lambda w: (
                isinstance(w.get("output_schema"), str)
                and (" + " in w["output_schema"] or "(" in w["output_schema"])
            ),
        ),
        "vendor_role_is_string": (
            "assigned_model_vendor_role",
            lambda w: isinstance(w.get("assigned_model_vendor_role"), str),
        ),
        "tests_required_is_string": (
            "tests_required",
            lambda w: isinstance(w.get("tests_required"), str),
        ),
        "failure_classification_is_string": (
            "failure_classification",
            lambda w: isinstance(w.get("failure_classification"), str),
        ),
        "dependency_bare_family": (
            "dependencies",
            lambda w: any(
                isinstance(x, str) and re.fullmatch(r"[A-Z]{2,6}", x)
                for x in (w.get("dependencies") or [])
            ),
        ),
        "sentinel_not_exact": (
            "completion_sentinel",
            lambda w: w.get("completion_sentinel") != f"SUCCESS:{w['id']}",
        ),
    }
    where = {}
    for name, (fld, fn) in defects.items():
        layer = (
            "contract"
            if fld in CONTRACT
            else ("content" if fld in CONTENT else "identity")
        )
        where[name] = {
            "field": fld,
            "layer": layer,
            "units_hit": sum(1 for w in wus if fn(w)),
        }
    r["defect_layer_map"] = where
    r["defect_layer_tally"] = dict(Counter(v["layer"] for v in where.values()))
    r["defect_units_by_layer"] = {
        lay: sum(v["units_hit"] for v in where.values() if v["layer"] == lay)
        for lay in ("contract", "content", "identity")
    }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in r.items() if k != "contract_derivability"}, indent=2
        )
    )
    print()
    print(
        f"{'CONTRACT field':30s} {'bytes':>8s} {'distinct':>8s} {'bestkey':>13s} "
        f"{'purity':>7s} {'overrides':>9s} {'exact':>7s}"
    )
    for f, v in sorted(deriv.items(), key=lambda kv: -kv[1]["bytes"]):
        print(
            f"{f:30s} {v['bytes']:8d} {v['distinct']:8d} {v['best_key']:>13s} "
            f"{v['best_purity']:7.3f} {v['units_needing_an_override']:9d} "
            f"{str(v['exact_key']):>7s}"
        )
    print("wrote", OUT)
    print("SUCCESS:ssot-contract-layer")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-contract-layer {type(exc).__name__}: {exc}")
        raise
