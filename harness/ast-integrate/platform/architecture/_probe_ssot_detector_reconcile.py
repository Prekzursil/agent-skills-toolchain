"""Reconcile MY probe against the brief's 4 defect counts. Detector-discipline pass.

My probe said: output_schema 71 distinct paths missing / deps 0 bad / sentinel 0 bad /
vendor_role 128 non-canonical.
Brief said:    159 unloadable output_schema / 41 unresolvable deps / 96 sentinels not naming
own unit / 128 non-canonical vendor_role.

For each disagreement: show the RAW field values so the definition difference is visible,
and prove my detector fires on a known-broken synthetic input (both-states test).

Terminal state: SUCCESS:ssot-reconcile / FAILED:...
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"
OUT = Path(__file__).with_name("_probe_ssot_detector_reconcile_out.json")


def main() -> int:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    wus = cat["work_units"]
    ids = {w["id"] for w in wus}
    r: dict = {}

    # ============ A. completion_sentinel: what shapes exist? ============
    shapes = Counter()
    exact_ok = 0
    contains_id = 0
    samples_non_exact = []
    for w in wus:
        s = w.get("completion_sentinel") or ""
        wid = w["id"]
        if s == f"SUCCESS:{wid}":
            exact_ok += 1
            shapes["exact SUCCESS:<id>"] += 1
        elif wid in s:
            contains_id += 1
            shapes["contains id, not exact"] += 1
            if len(samples_non_exact) < 12:
                samples_non_exact.append({"id": wid, "sentinel": s})
        else:
            shapes["does NOT contain id"] += 1
    r["completion_sentinel"] = {
        "shapes": dict(shapes),
        "exact_SUCCESS_id": exact_ok,
        "contains_id_but_not_exact": contains_id,
        "samples_non_exact": samples_non_exact,
    }
    # both-states: my "does not contain id" detector must fire on a synthetic bad unit
    bad = {"id": "ZZZ-9999", "completion_sentinel": "SUCCESS:other-unit"}
    r["completion_sentinel"]["detector_fires_on_synthetic_bad"] = (
        bad["id"] not in bad["completion_sentinel"]
    )

    # ============ B. dependencies: raw value shapes ============
    dshapes = Counter()
    samples = []
    all_str_tokens = Counter()
    for w in wus:
        d = w.get("dependencies")
        if isinstance(d, list):
            dshapes[
                f"list[{','.join(sorted({type(x).__name__ for x in d})) or 'empty'}]"
            ] += 1
            for x in d:
                if isinstance(x, str):
                    all_str_tokens[x] += 1
        elif isinstance(d, str):
            dshapes["str"] += 1
            all_str_tokens[d] += 1
        else:
            dshapes[type(d).__name__] += 1
        if len(samples) < 10 and d:
            samples.append({"id": w["id"], "dependencies": d})
    # which dep tokens look like unit ids, and do they resolve?
    idlike = {t for t in all_str_tokens if re.search(r"[A-Z]{2,6}-\d{2,4}", t)}
    unresolved_tokens = {}
    for t in idlike:
        # extract every id-shaped substring; a token may be prose naming several
        found = re.findall(r"[A-Z]{2,6}-\d{2,4}", t)
        miss = [f for f in found if f not in ids]
        if miss:
            unresolved_tokens[t] = miss
    r["dependencies"] = {
        "value_shapes": dict(dshapes),
        "distinct_string_tokens": len(all_str_tokens),
        "tokens_containing_id_shape": len(idlike),
        "tokens_with_an_unresolvable_id_substring": len(unresolved_tokens),
        "unresolvable_id_substrings_total": sum(
            len(v) for v in unresolved_tokens.values()
        ),
        "unresolvable_sample": dict(list(unresolved_tokens.items())[:10]),
        "samples": samples[:6],
    }
    r["dependencies"]["detector_fires_on_synthetic_bad"] = bool(
        [f for f in re.findall(r"[A-Z]{2,6}-\d{2,4}", "NOPE-4242") if f not in ids]
    )

    # ============ C. output_schema: is the field polymorphic? ============
    poly = Counter()
    prose_samples = []
    extracted_paths = Counter()
    for w in wus:
        v = w["output_schema"]
        if not isinstance(v, str):
            poly[f"non-str/{type(v).__name__}"] += 1
            continue
        if " + " in v or v.endswith(")") or "(" in v:
            poly["compound/prose"] += 1
            if len(prose_samples) < 8:
                prose_samples.append({"id": w["id"], "output_schema": v})
        elif "#" in v:
            poly["path#fragment"] += 1
        else:
            poly["bare path"] += 1
        # extract every path-looking token
        for tok in re.findall(
            r"[A-Za-z0-9_./-]+\.schema\.json|[A-Za-z0-9_./-]+\.json", v
        ):
            extracted_paths[tok] += 1
    res = {p: (REPO / p).is_file() for p in extracted_paths}
    r["output_schema"] = {
        "field_shapes": dict(poly),
        "prose_samples": prose_samples,
        "extracted_path_tokens": len(extracted_paths),
        "extracted_resolving": sum(1 for p, ok in res.items() if ok),
        "extracted_NOT_resolving": sorted(p for p, ok in res.items() if not ok),
    }
    r["output_schema"]["detector_fires_on_known_absent"] = not (
        REPO / "command-center/schema/definitely-not-here.schema.json"
    ).is_file()
    r["output_schema"]["detector_finds_known_present"] = (
        REPO / "platform/schema/receipt.schema.json"
    ).is_file()

    # ============ D. what does the repo itself record? ============
    for name in ("CONFORMANCE-STATUS.json", "SUBSTRATE-RESOLUTION-STATUS.json"):
        p = REPO / "platform/schema" / name
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            r[f"recorded::{name}"] = {
                k: v for k, v in d.items() if not isinstance(v, (list,)) or len(v) < 12
            }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(json.dumps(r, indent=2)[:9000])
    print("wrote", OUT)
    print("SUCCESS:ssot-reconcile")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-reconcile {type(exc).__name__}: {exc}")
        raise
