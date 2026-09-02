#!/usr/bin/env python3
"""Probe 2: semantic claim survival (counterexample + FNR), plus artifact schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

OUT = "command-center/adversarial/ADV-0097-minority-report-survival-trace.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
VERDICTS = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def catalog_sentinel() -> str:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0097":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:ADV-0097-probe2 catalog unit missing")


def _refuse(uri: str):
    raise RefResolutionError(f"offline-refused {uri}")


def _validator():
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT).read_text(encoding="utf-8"))
    store = {
        str(shim.get("$id") or ""): shim,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
        "https://ast-integrate.invalid/" + SCHEMA: shim,
        "https://ast-integrate.invalid/" + PROFILES: profiles,
        "https://ast-integrate.invalid/" + RECEIPT: receipt,
        str((REPO / SCHEMA).as_posix()): shim,
        str((REPO / PROFILES).as_posix()): profiles,
        str((REPO / RECEIPT).as_posix()): receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse, "https": _refuse, "file": _refuse},
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def semantic_payload() -> dict:
    ev = M.evaluate()
    husk = ev["matrix"]["husk"]
    preserve = ev["matrix"]["preserve"]
    omit = ev["matrix"]["omit"]
    ok = (
        husk["first_dissent_claim_absent"] == "synthesis"
        and omit["first_dissent_claim_absent"] == "synthesis"
        and preserve["dissent_claim_survived_every_stage"]
        and husk["first_dissent_token_absent"] == "artifact_manifest"
        and ev["majority_control_pass"]
        and ev["preserve_both_survive"]
    )
    return {
        "probe": "probe2_semantic_survival",
        "ok": ok,
        "mechanism": (
            "claim presence requires counterexample id ADV97-COUNTER-XRAY-771 "
            "AND the 0.41 false-negative observation; token husk does not count"
        ),
        "husk_first_claim_absent": husk["first_dissent_claim_absent"],
        "husk_first_token_absent": husk["first_dissent_token_absent"],
        "split_token_vs_claim": (
            husk["first_dissent_token_absent"] != husk["first_dissent_claim_absent"]
        ),
        "preserve_claim_survived": preserve["dissent_claim_survived_every_stage"],
        "husk_rows": husk["rows"],
        "preserve_rows": preserve["rows"],
    }


def validate_artifact() -> dict:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        return {"present": False, "ok": False, "reason": "artifact-absent"}
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    sentinel = catalog_sentinel()
    validator = _validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    garbage_rejected = 0
    for g in GARBAGE:
        if list(validator.iter_errors(g)):
            garbage_rejected += 1
    targets = doc.get("targets") or []
    verdicts = [t.get("verdict") for t in targets if isinstance(t, dict)]
    named = doc.get("named_probes") or []
    raw_ok = sum(
        1
        for p in named
        if isinstance(p, dict) and len(str(p.get("raw_output") or "")) >= 8
    )
    controls = doc.get("negative_controls") or []
    ok = (
        not errs
        and garbage_rejected == 3
        and sentinel in text
        and str(doc.get("state") or "").upper() == "SUCCESS"
        and all(v in VERDICTS for v in verdicts)
        and len(verdicts) >= 1
        and raw_ok >= 2
        and len(controls) >= 1
        and str(doc.get("report_kind") or "") == "council-pathology-sim"
    )
    return {
        "present": True,
        "ok": ok,
        "schema_errors": [e.message for e in errs[:8]],
        "garbage_rejected": garbage_rejected,
        "sentinel_present": sentinel in text,
        "n_targets": len(verdicts),
        "named_probes_with_raw": raw_ok,
        "negative_controls": len(controls),
        "state": doc.get("state"),
    }


def run() -> dict:
    sem = semantic_payload()
    art = validate_artifact()
    ok = bool(sem["ok"] and art.get("ok"))
    return {"semantic": sem, "artifact": art, "ok": ok}


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["semantic"]["ok"]:
        print("FAILED:ADV-0097-probe2 semantic contract")
        return 1
    if not payload["artifact"].get("present"):
        print("FAILED:ADV-0097-probe2 artifact absent")
        return 1
    if not payload["artifact"].get("ok"):
        print("FAILED:ADV-0097-probe2 artifact/schema contract")
        print(payload["artifact"].get("schema_errors"))
        return 1
    print(
        "claim_drop_stage={c} token_drop_stage={t} split={s} schema_ok=True".format(
            c=payload["semantic"]["husk_first_claim_absent"],
            t=payload["semantic"]["husk_first_token_absent"],
            s=payload["semantic"]["split_token_vs_claim"],
        )
    )
    print("SUCCESS:ADV-0097-probe2 semantic survival plus schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
