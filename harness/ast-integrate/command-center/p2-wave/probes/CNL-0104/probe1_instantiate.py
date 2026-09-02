#!/usr/bin/env python3
"""Probe 1: instantiate both family presets; schema; negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import family as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0104-probe1 {msg}")
    return 1


def main() -> int:
    art_path = REPO / F.OUT_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0104":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    raw = art_path.read_text(encoding="utf-8")
    if F.SENTINEL not in raw:
        return fail("sentinel absent")

    body = F.artifact_body(doc)
    presets = body.get("presets") or []
    if len(presets) != 2:
        return fail(f"preset count {len(presets)}")
    ids = {p.get("id") for p in presets if isinstance(p, dict)}
    want = {
        "council.preset.gated-review.design-plan-critique",
        "council.preset.gated-review.release-go-no-go",
    }
    if ids != want:
        return fail(f"preset ids {ids}")

    task = F.load_task()
    schema = F.load_schema()
    live_inst = []
    for p in presets:
        inst = F.instantiate(p, task)
        if not inst.get("ok"):
            return fail(f"instantiate {p.get('id')} {inst.get('reason')}")
        for key in ("roster", "protocol_schedule", "voting", "stopping"):
            if not inst.get(key):
                return fail(f"missing {key} for {p.get('id')}")
        live_inst.append(inst)

    recorded = body.get("instantiations") or []
    if len(recorded) != 2:
        return fail(f"recorded instantiations {len(recorded)}")
    for live, rec in zip(live_inst, recorded):
        if live.get("preset_id") != rec.get("preset_id"):
            return fail("instantiation preset_id mismatch")
        if json.dumps(live["roster"], sort_keys=True) != json.dumps(rec.get("roster"), sort_keys=True):
            return fail(f"roster drift {live.get('preset_id')}")
        if json.dumps(live["voting"], sort_keys=True) != json.dumps(rec.get("voting"), sort_keys=True):
            return fail(f"voting drift {live.get('preset_id')}")
        if json.dumps(live["stopping"], sort_keys=True) != json.dumps(rec.get("stopping"), sort_keys=True):
            return fail(f"stopping drift {live.get('preset_id')}")
        live_sched = sorted(
            [(s.get("order"), s.get("protocol_id")) for s in live["protocol_schedule"]],
        )
        rec_sched = sorted(
            [(s.get("order"), s.get("protocol_id")) for s in rec.get("protocol_schedule") or []],
        )
        if live_sched != rec_sched:
            return fail(f"schedule drift {live.get('preset_id')}")

    if live_inst[0]["mechanism_class"] == live_inst[1]["mechanism_class"]:
        return fail("both instantiations collapsed to one mechanism")

    err_total = 0
    for p in presets:
        n = F.schema_error_count(p, schema)
        err_total += n
        if n != 0:
            msgs = F.schema_error_messages(p, schema)[:8]
            return fail(f"schema errors {p.get('id')}={n} {msgs}")
    inv_n = F.schema_error_count(F.invalid_record(), schema)
    if inv_n < 1:
        return fail("validator vacuous")
    env_n = F.envelope_error_count(doc)
    if env_n != 0:
        return fail(f"envelope errors {env_n} {F.envelope_errors(doc)[:8]}")
    inv_env = F.envelope_error_count({"schema_version": 1, "unit_id": 0})
    if inv_env < 1:
        return fail("envelope validator vacuous")

    silent = F.instantiate(presets[1], task, dials={"delta.voting.rule": "majority"})
    if silent.get("ok"):
        return fail("non-editable dial accepted")
    mixed = F.mixed_gonogo_wearing_critique_evidence(presets[1])
    mixed_cls = F.classify_mechanism(mixed)
    if mixed_cls != "design-plan-critique":
        return fail(f"mixed name-only not classified as critique ({mixed_cls})")

    print(
        json.dumps(
            {
                "instantiations": [
                    {
                        "preset_id": i["preset_id"],
                        "mechanism_class": i["mechanism_class"],
                        "roster": [r["role"] for r in i["roster"]],
                        "protocols": [s["protocol_id"] for s in i["protocol_schedule"]],
                        "voting": i["voting"].get("rule"),
                        "stopping": i["stopping"].get("expression"),
                    }
                    for i in live_inst
                ],
                "schema_error_count": err_total,
                "invalid_record_error_count": inv_n,
                "envelope_error_count": env_n,
                "invalid_envelope_error_count": inv_env,
                "negative_control": {
                    "rejects": "name-only go-no-go (critique family vector) and non-editable dial override",
                    "mixed_class": mixed_cls,
                    "non_editable_rejected": True,
                    "reason": silent.get("reason"),
                },
            },
            indent=2,
        )
    )
    print(
        "schema_errors=0 invalid_errors="
        f"{inv_n} mixed={mixed_cls} non_editable_rejected=True"
    )
    print("SUCCESS:CNL-0104-probe1 instantiate schema negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
