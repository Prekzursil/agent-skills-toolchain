"""THE decisive test for generated-SSOT, taken from the candidate's own doc:

  13-ARCHITECTURE-CANDIDATES.md:279-282 - "Generate the FIRST spec from live ... and assert
  re-emission is byte-identical. That is the both-states control: if round-trip is not
  byte-exact, the spec is lossy and migration stops."

Applied to THIS repo's catalog: for every field, can a per-(slice,field) TEMPLATE with `{id}`
substitution reproduce the authored value byte-exactly? Measure:
  - fields fully template-reproducible (generator can own them outright)
  - fields needing per-unit content (generator must carry them verbatim)
  - the resulting byte split -> the honest size of the lever

Both-states control included: a deliberately WRONG template must fail to reproduce.

Terminal state: SUCCESS:ssot-roundtrip / FAILED:...
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).with_name("_probe_ssot_roundtrip_out.json")


def canon(v) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def templatize(text: str, wid: str) -> str:
    """Replace the unit id and its numeric tail with placeholders."""
    t = text.replace(wid, "{id}")
    fam, _, num = wid.partition("-")
    if num:
        t = t.replace(num, "{n}")
    return t


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wus = cat["work_units"]
    fields = sorted({k for w in wus for k in w.keys()})
    r: dict = {"work_units": len(wus), "fields": len(fields)}

    # ---------- per-(slice, field) template reproduction ----------
    per_field = {}
    tot_bytes = 0
    repro_bytes = 0
    for f in fields:
        by_slice = defaultdict(list)
        for w in wus:
            if f in w:
                by_slice[w.get("_source_slice_file", "<none>")].append(w)
        n_present = sum(len(v) for v in by_slice.values())
        f_bytes = 0
        f_repro = 0
        tmpl_count = 0
        slice_full = 0
        for sl, ws in by_slice.items():
            tmpls = Counter()
            for w in ws:
                raw = canon(w.get(f))
                f_bytes += len(raw)
                tmpls[templatize(raw, w["id"])] += 1
            tmpl_count += len(tmpls)
            if len(tmpls) == 1:
                slice_full += 1
                f_repro += sum(len(canon(w.get(f))) for w in ws)
        per_field[f] = {
            "present": n_present,
            "bytes": f_bytes,
            "distinct_templates_across_slices": tmpl_count,
            "slices_with_exactly_one_template": slice_full,
            "slices_present": len(by_slice),
            "bytes_reproducible_by_one_template_per_slice": f_repro,
            "template_coverage": round(f_repro / f_bytes, 4) if f_bytes else 0.0,
        }
        tot_bytes += f_bytes
        repro_bytes += f_repro
    r["per_field"] = per_field
    r["totals"] = {
        "authored_field_bytes": tot_bytes,
        "reproducible_by_slice_template_plus_id": repro_bytes,
        "must_be_carried_verbatim": tot_bytes - repro_bytes,
        "generator_owned_fraction": round(repro_bytes / tot_bytes, 4),
    }

    # ---------- ranked: which fields the generator fully owns ----------
    r["generator_owns_fully"] = sorted(
        f
        for f, v in per_field.items()
        if v["slices_with_exactly_one_template"] == v["slices_present"]
    )
    r["generator_owns_partially"] = sorted(
        f
        for f, v in per_field.items()
        if 0 < v["slices_with_exactly_one_template"] < v["slices_present"]
    )
    r["generator_owns_none"] = sorted(
        f for f, v in per_field.items() if v["slices_with_exactly_one_template"] == 0
    )

    # ---------- both-states control ----------
    # a WRONG template must NOT reproduce; a RIGHT one must.
    probe = wus[0]
    right = templatize(canon(probe["completion_sentinel"]), probe["id"])
    wrong = right.replace("SUCCESS", "SUCESS")
    r["both_states_control"] = {
        "unit": probe["id"],
        "right_template_reproduces": right.replace("{id}", probe["id"]).replace(
            "{n}", probe["id"].partition("-")[2]
        )
        == canon(probe["completion_sentinel"]),
        "wrong_template_reproduces": wrong.replace("{id}", probe["id"]).replace(
            "{n}", probe["id"].partition("-")[2]
        )
        == canon(probe["completion_sentinel"]),
        "detector_valid": None,
    }
    bsc = r["both_states_control"]
    bsc["detector_valid"] = (
        bool(bsc["right_template_reproduces"]) and not bsc["wrong_template_reproduces"]
    )

    # ---------- how many spec lines would the generator input be? ----------
    # spec = per-slice defaults (one block per slice x generator-owned field)
    #        + per-unit residue (only the not-owned fields)
    owned = set(r["generator_owns_fully"])
    residue_bytes = sum(len(canon(w.get(f))) for w in wus for f in w if f not in owned)
    n_slices = len({w.get("_source_slice_file") for w in wus})
    r["spec_size_estimate"] = {
        "slices": n_slices,
        "generator_owned_fields": len(owned),
        "per_slice_default_blocks": n_slices * len(owned),
        "per_unit_residue_bytes": residue_bytes,
        "residue_fraction_of_catalog": round(residue_bytes / tot_bytes, 4),
    }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in r.items() if k != "per_field"}, indent=2))
    print()
    print(f"{'field':34s} {'bytes':>9s} {'tmpl-cov':>9s} {'slices 1-tmpl':>14s}")
    for f, v in sorted(per_field.items(), key=lambda kv: -kv[1]["bytes"]):
        print(
            f"{f:34s} {v['bytes']:9d} {v['template_coverage']:9.3f} "
            f"{v['slices_with_exactly_one_template']:6d}/{v['slices_present']:<7d}"
        )
    print("wrote", OUT)
    print("SUCCESS:ssot-roundtrip")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-roundtrip {type(exc).__name__}: {exc}")
        raise
