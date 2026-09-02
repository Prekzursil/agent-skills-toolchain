#!/usr/bin/env python3
"""Probe 1: declared-versus-measured loss sets, with a planted undeclared leak.

Known-good: projector, recount, and declared ledger agree (no undeclared leaks).
Planted-bad: a native field not in the ledger is dropped; compare FIRES.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import ledger as L  # noqa: E402
import projector as P  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0055-adapter-lossy-field-ledger.json"
SENTINEL = "SUCCESS:WFA-0055"
PLANT_ADAPTER = "WFA-0045"
PLANT_FIELD = "planted_secret_gate"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0055-probe1 {msg}")
    return 1


def natives() -> dict[str, dict]:
    return {uid: C.native_doc(uid) for uid in C.ADAPTER_IDS}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "WFA-0055":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("record_type") != "AuditReport":
        return fail("record_type")
    leaks = (doc.get("declared_vs_measured") or {}).get("undeclared_leaks") or []
    if leaks:
        return fail(f"artifact undeclared_leaks={leaks}")

    schema = json.loads((HERE / "schema.json").read_text(encoding="utf-8"))
    try:
        import jsonschema

        validator = jsonschema.Draft7Validator(schema)
        errs = list(validator.iter_errors(doc))
        if errs:
            return fail(f"schema {errs[0].message}")
        if not list(validator.iter_errors({})):
            return fail("schema accepted empty object")
    except ImportError:
        for key in ("ledger", "declared_vs_measured", "disposition_gate"):
            if key not in doc:
                return fail(f"missing {key}")

    declared_by = L.declared_fields_by_adapter()
    good_native = natives()
    proj = P.measure_all({u: d["fields"] for u, d in good_native.items()})
    rec = R.measured_by_adapter(good_native)
    measured = {uid: set(proj[uid]) for uid in C.ADAPTER_IDS}
    for uid in C.ADAPTER_IDS:
        if set(proj[uid]) != rec[uid]:
            return fail(f"projector/recount {uid}")
    good = L.compare(declared_by, measured)
    if not good["aligned"] or good["n_undeclared"] != 0:
        return fail(f"known-good not aligned {good['undeclared_leaks']}")

    planted_native = copy.deepcopy(good_native)
    planted_native[PLANT_ADAPTER]["fields"][PLANT_FIELD] = {
        "kind": "gate",
        "blocking": True,
        "planted": True,
    }
    p_proj = P.roundtrip(PLANT_ADAPTER, planted_native[PLANT_ADAPTER]["fields"])
    p_rec = R.dropped_fields(
        PLANT_ADAPTER, planted_native[PLANT_ADAPTER]["fields"]
    )
    if PLANT_FIELD not in p_proj["differing_fields"]:
        return fail("plant not in projector differing_fields")
    if PLANT_FIELD not in p_rec:
        return fail("plant not in recount dropped_fields")
    measured_bad = {uid: set(proj[uid]) for uid in C.ADAPTER_IDS}
    measured_bad[PLANT_ADAPTER] = set(p_proj["differing_fields"])
    bad = L.compare(declared_by, measured_bad)
    fired = (
        bad["aligned"] is False
        and bad["n_undeclared"] >= 1
        and any(
            x.get("native_field") == PLANT_FIELD
            for x in bad["undeclared_leaks"]
        )
    )
    if not fired:
        return fail(f"planted leak not caught {bad['undeclared_leaks']}")

    losses = (doc.get("ledger") or {}).get("losses") or []
    adapters_hit = {r.get("adapter_id") for r in losses}
    if adapters_hit != set(C.ADAPTER_IDS):
        return fail(f"ledger adapters {sorted(adapters_hit)}")
    for row in losses:
        ex = row.get("worked_example") or {}
        if not ex.get("snippet") or not row.get("source_construct"):
            return fail(f"{row.get('loss_id')} missing worked example")

    out = {
        "pass": True,
        "probe": "probe1-declared-vs-measured",
        "unit_id": "WFA-0055",
        "silent_on_good": True,
        "fired_on_plant": True,
        "plant_field": PLANT_FIELD,
        "n_declared": sum(len(v) for v in declared_by.values()),
        "n_measured_good": sum(len(v) for v in measured.values()),
        "n_undeclared_good": good["n_undeclared"],
        "n_undeclared_plant": bad["n_undeclared"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "known-good aligned=True undeclared=0; "
        f"planted {PLANT_FIELD} fired=True leaks={bad['undeclared_leaks']}"
    )
    print("SUCCESS:WFA-0055-probe1 declared-versus-measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
