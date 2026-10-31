"""Independently re-derive the catalog defect classes AND measure derivability.

Two questions:
  Q1 (defects) - re-measure the 4 defect classes the brief names, with MY OWN code
      (independent of platform/lib/wfdsl), so the numbers are a second signal.
  Q2 (derivability) - for each catalog field, could a generator have DERIVED it from
      (phase, id, artifact-class, output_path)? Measured as: does a simple deterministic
      rule reproduce the authored value for >=95% of units? A field that is derivable but
      authored is a field where drift is possible for free.

Read-only. Terminal state: SUCCESS:ssot-derivability / FAILED:...
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"
OUT = Path(__file__).with_name("_probe_ssot_derivability_out.json")


def main() -> int:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    wus = cat["work_units"]
    ids = {w["id"] for w in wus}
    r: dict = {"work_units": len(wus), "distinct_ids": len(ids)}

    # ---------- Q1a: output_schema paths that resolve on disk ----------
    def split_ref(ref: str):
        path, _, frag = ref.partition("#")
        return path, frag

    paths = Counter()
    for w in wus:
        p, _f = split_ref(w["output_schema"])
        paths[p] += 1
    resolving, missing = [], []
    for p in paths:
        cand = REPO / p
        (resolving if cand.is_file() else missing).append(p)
    r["output_schema"] = {
        "distinct_full_refs": len({w["output_schema"] for w in wus}),
        "distinct_paths": len(paths),
        "distinct_paths_resolving": len(resolving),
        "distinct_paths_missing": len(missing),
        "missing_sample": sorted(missing)[:10],
        "refs_resolving": sum(paths[p] for p in resolving),
        "refs_missing": sum(paths[p] for p in missing),
    }

    # ---------- Q1b: dependency refs that name no known unit ----------
    bad_dep = defaultdict(list)
    dep_total = 0
    for w in wus:
        deps = w.get("dependencies") or []
        if isinstance(deps, str):
            deps = [deps]
        for d in deps:
            if not isinstance(d, str):
                continue
            dep_total += 1
            # a dependency ref is a unit id if it matches the id shape
            if re.fullmatch(r"[A-Z]{2,5}-\d{3,4}", d.strip()) and d.strip() not in ids:
                bad_dep[w["id"]].append(d.strip())
    r["dependencies"] = {
        "total_dep_entries": dep_total,
        "units_with_unresolvable_id_ref": len(bad_dep),
        "unresolvable_refs": sum(len(v) for v in bad_dep.values()),
        "sample": dict(list(bad_dep.items())[:8]),
    }

    # ---------- Q1c: completion_sentinel that does not name its own unit ----------
    bad_sent = []
    for w in wus:
        s = w.get("completion_sentinel") or ""
        if w["id"] not in s:
            bad_sent.append({"id": w["id"], "sentinel": s[:110]})
    r["completion_sentinel"] = {
        "not_naming_own_id": len(bad_sent),
        "sample": bad_sent[:6],
    }

    # ---------- Q1d: assigned_model_vendor_role canonical shape ----------
    # canonical (as used by the majority): "<vendor>:<model>:<role>" style triples
    shapes = Counter()
    for w in wus:
        v = w.get("assigned_model_vendor_role")
        if isinstance(v, str):
            shapes[f"str/colons={v.count(':')}"] += 1
        elif isinstance(v, dict):
            shapes["dict/keys=" + ",".join(sorted(v.keys()))] += 1
        elif isinstance(v, list):
            shapes[f"list/len={len(v)}"] += 1
        else:
            shapes[f"other/{type(v).__name__}"] += 1
    r["assigned_model_vendor_role_shapes"] = dict(shapes.most_common())

    # ---------- Q2: derivability of every field ----------
    # Rule family: value is a pure function of a small key. Try keys in order of
    # increasing specificity; report the SMALLEST key that determines the field.
    keyfns = {
        "constant": lambda w: (),
        "phase": lambda w: (w.get("phase"),),
        "id_prefix": lambda w: (w["id"].split("-")[0],),
        "phase+id_prefix": lambda w: (w.get("phase"), w["id"].split("-")[0]),
        "phase+id_prefix+substrate": lambda w: (
            w.get("phase"),
            w["id"].split("-")[0],
            w.get("execution_substrate"),
        ),
    }
    fields = sorted({k for w in wus for k in w.keys()})
    deriv = {}
    for f in fields:
        present = [w for w in wus if f in w]
        if not present:
            continue
        entry = {"present": len(present), "determined_by": None, "purity": {}}
        for kname, kfn in keyfns.items():
            groups = defaultdict(Counter)
            for w in present:
                val = w.get(f)
                val = (
                    json.dumps(val, sort_keys=True)
                    if isinstance(val, (dict, list))
                    else str(val)
                )
                groups[kfn(w)][val] += 1
            # purity = fraction of units whose value equals the modal value for its key
            hits = sum(c.most_common(1)[0][1] for c in groups.values())
            entry["purity"][kname] = round(hits / len(present), 4)
            if entry["determined_by"] is None and hits == len(present):
                entry["determined_by"] = kname
        deriv[f] = entry
    r["derivability"] = deriv

    # summary buckets
    r["derivability_summary"] = {
        "fully_determined_by_small_key": sorted(
            f for f, e in deriv.items() if e["determined_by"] is not None
        ),
        "ge_95pct_determined_by_phase_prefix": sorted(
            f
            for f, e in deriv.items()
            if e["purity"].get("phase+id_prefix", 0) >= 0.95
            and e["determined_by"] is None
        ),
        "genuinely_per_unit_lt_50pct": sorted(
            f
            for f, e in deriv.items()
            if e["purity"].get("phase+id_prefix+substrate", 0) < 0.5
        ),
    }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(
        json.dumps({k: v for k, v in r.items() if k != "derivability"}, indent=2)[:6000]
    )
    print("wrote", OUT)
    print("SUCCESS:ssot-derivability")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-derivability {type(exc).__name__}: {exc}")
        raise
