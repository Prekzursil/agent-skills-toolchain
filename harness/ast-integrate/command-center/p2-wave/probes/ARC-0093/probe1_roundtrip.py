#!/usr/bin/env python3
"""Named probe 1: round-trip three REAL schema_version=1 artifacts.

Apply the declared forward transform, then its reverse. Assert canonical-json-v1
byte recovery. Assert N does not still validate under strict N+1 so the
transformation obligation is the branch that was actually taken. Both-states:
the contract schema accepts the executed record and rejects garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from transform import (  # noqa: E402
    REAL_ARTIFACTS,
    apply_bytes,
    process_many,
    round_trip,
    still_validates_n_plus_1,
)

ART = REPO / "command-center/phase4/contracts/ARC-0093.json"
SENTINEL = "SUCCESS:ARC-0093"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:ARC-0093-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:3000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("contract artifact missing or thin")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ARC-0093":
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        return fail("$schema", doc.get("$schema"))

    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(garbage)):
            return fail("schema-document-vacuous")

    executed = (doc.get("x-arc-0093") or {}).get("executed_record")
    if not isinstance(executed, dict):
        return fail("executed_record-absent")
    inst_errs = list(validator.iter_errors(executed))
    if inst_errs:
        return fail("executed_record-invalid", [e.message for e in inst_errs[:8]])
    if executed.get("reversibility", {}).get("status") != "REVERSIBLE":
        return fail("expected REVERSIBLE migration; irreversible path not taken")
    if executed.get("dry_run", {}).get("executed") is not True:
        return fail("dry_run never executed; would be NOT-CHECKED")
    if executed.get("dry_run", {}).get("would_drop") != 0:
        return fail("dry_run.would_drop must be 0")

    recorded = {row["path"]: row for row in (executed.get("evidence") or [])}
    if len(recorded) < 3:
        return fail(f"evidence rows {len(recorded)} want>=3")

    live_rows: list[tuple[str, bytes, dict]] = []
    for rel in REAL_ARTIFACTS:
        path = REPO / rel
        if not path.is_file():
            return fail(f"real artifact absent {rel}")
        raw = path.read_bytes()
        obj = json.loads(raw.decode("utf-8"))
        live_rows.append((rel, raw, obj))

    dry = process_many([(rel, raw) for rel, raw, _ in live_rows], dry_run=True)
    if not dry["accounting_holds"] or dry["would_drop"] != 0:
        return fail("dry-run accounting", dry)
    if dry["would_transform"] != executed["dry_run"]["would_transform"]:
        return fail("dry_run.would_transform drifted vs live re-run", dry)
    if dry["records_in"] != executed["dry_run"]["records_in"]:
        return fail("dry_run.records_in drifted vs live re-run", dry)

    recovered = 0
    for rel, raw, obj in live_rows:
        if still_validates_n_plus_1(obj):
            return fail(f"{rel} already N+1; obligation untested")
        rec = recorded.get(rel)
        if rec is None:
            return fail(f"artifact missing evidence row {rel}")
        rt = round_trip(obj, path=rel)
        if not rt["byte_recovered"]:
            return fail(f"not byte-recovered {rel}", rt)
        if rt["n_plus_1_valid_before"] or not rt["n_plus_1_valid_after"]:
            return fail(f"n+1 validity {rel}", rt)
        fwd = apply_bytes(raw, path=rel)
        if rec.get("original_canonical_sha256") != rt["original_canonical_sha256"]:
            return fail(f"original sha drift {rel}")
        if rec.get("forward_canonical_sha256") != fwd.output_canonical_sha256:
            return fail(f"forward sha drift {rel}")
        if rec.get("recovered_canonical_sha256") != rt["recovered_canonical_sha256"]:
            return fail(f"recovered sha drift {rel}")
        recovered += 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "ARC-0093",
        "real_artifacts": list(REAL_ARTIFACTS),
        "records_in": dry["records_in"],
        "transformed": dry["would_transform"],
        "byte_recovered": recovered,
        "schema_rejects_garbage": True,
        "schema_accepts_executed_record": True,
        "dry_run_executed": True,
        "pass": recovered >= 3,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"round-trip recovered={recovered}/3 dry_run_transform={dry['would_transform']}")
    print("SUCCESS:ARC-0093-probe1 round-trip three real artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
