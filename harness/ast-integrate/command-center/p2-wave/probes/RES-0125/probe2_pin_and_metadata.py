#!/usr/bin/env python3
"""Probe 2: pin integrity, quote-in-capture, marketplace field gap.

Independent of probe 1's label-enum mutants. Starts from captures and the
lockfile schema, then checks the artifact. A pin-stripped mutant must go red.
A2 generator_version is not accepted as LLM generation_method.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from check import (  # noqa: E402
    A2_MARKET,
    ART,
    LOCKFILE,
    a2_generated_keys,
    check_artifact,
    load_indexes,
    lockfile_required_keys,
    mutant_strip_pins,
    quote_in_capture,
    sha256_bytes,
)
from labels import UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    indexes = load_indexes()

    lock_keys = lockfile_required_keys()
    want_lock = {"name", "version", "source_url", "digest"}
    if want_lock - lock_keys:
        return fail(f"lockfile required moved: {sorted(lock_keys)}")
    if "generation_method" in lock_keys:
        return fail("generation_method unexpectedly required by lockfile")

    a2_keys = a2_generated_keys()
    if "generator_id" not in a2_keys or "generator_version" not in a2_keys:
        return fail(f"A2 _generated keys {sorted(a2_keys)}")
    a2 = json.loads(A2_MARKET.read_text(encoding="utf-8"))
    if (a2.get("_generated") or {}).get("generator_id") == "model-generated":
        return fail("A2 header collides with LLM generation_method")

    live = check_artifact(doc, indexes)
    if not live["pass"]:
        return fail(f"live {live['errors']}")

    stripped = check_artifact(mutant_strip_pins(doc), indexes)
    if stripped["pass"]:
        return fail("pin-stripped mutant stayed green")
    if not any(e.startswith("unpinned:") for e in stripped["errors"]):
        return fail(f"pin mutant errors={stripped['errors']}")

    missing_quotes = []
    for row in doc.get("obligation_table") or []:
        if not quote_in_capture(row, indexes):
            missing_quotes.append(row.get("id"))
    if missing_quotes:
        return fail(f"quotes absent {missing_quotes}")

    fields = {f.get("field"): f for f in doc.get("marketplace_metadata") or []}
    gen = fields.get("generation_method") or {}
    if gen.get("required_versus_proposed") != "required-by-terms":
        return fail("generation_method not required-by-terms")
    if gen.get("present_in_lockfile_schema") is True:
        return fail("generation_method falsely claimed present in lockfile")
    c2pa = fields.get("c2pa_manifest") or {}
    if c2pa.get("required_versus_proposed") != "proposed-norm":
        return fail("c2pa_manifest not proposed-norm")

    lock_sha = sha256_bytes(LOCKFILE.read_bytes())
    art_lock = (doc.get("current_marketplace_surface") or {}).get("lockfile_sha256")
    if art_lock != lock_sha:
        return fail("lockfile sha drift vs artifact")

    if doc.get("not_legal_advice") is not True:
        return fail("not_legal_advice")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-pin-and-metadata",
                "unit_id": UNIT,
                "lockfile_required": sorted(lock_keys),
                "generation_method_in_lockfile": False,
                "a2_generator_id": (a2.get("_generated") or {}).get("generator_id"),
                "pin_stripped_mutant_red": True,
                "quotes_verified": True,
                "lockfile_sha256": lock_sha,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:RES-0125-probe2 pins and quotes hold, lockfile gap confirmed, "
        "pin mutant red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
