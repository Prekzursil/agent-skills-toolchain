#!/usr/bin/env python3
"""Probe 2: independent schema-diff of the emitter vs the accepted field set.

Does not use the additionalProperties error path. It reads schema.properties
and the emitter's output keys, then asserts subset. Also proves the emitter
refuses a planted unknown field rather than writing it through.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from emitter import (
    PLANTED_UNKNOWN_FIELD,
    UnknownFieldEmitError,
    emit_plugin_manifest,
    schema_diff,
)


def run() -> dict:
    emitted = emit_plugin_manifest()
    diff = schema_diff(emitted)

    refused = False
    refused_fields: list[str] = []
    try:
        leak = dict(emitted)
        leak[PLANTED_UNKNOWN_FIELD] = "must-not-emit"
        emit_plugin_manifest(leak)
    except UnknownFieldEmitError as exc:
        refused = True
        refused_fields = list(exc.fields)

    # Distinct-keys control: a document whose keys are all in the allowlist
    # (already true of `emitted`) plus the planted field is NOT a subset.
    dirty_keys = sorted(set(emitted) | {PLANTED_UNKNOWN_FIELD})
    extra_if_leaked = sorted(k for k in dirty_keys if k not in set(diff["accepted_field_set"]))

    ok = (
        diff["emitter_subset_of_accepted"] is True
        and diff["extra_emitted_fields"] == []
        and diff["missing_required"] == []
        and refused
        and refused_fields == [PLANTED_UNKNOWN_FIELD]
        and extra_if_leaked == [PLANTED_UNKNOWN_FIELD]
        and PLANTED_UNKNOWN_FIELD not in emitted
        and diff["accepted_count"] >= 8
    )
    return {
        "probe": "probe2-schema-diff",
        "unit_id": "TST-0179",
        "pass": ok,
        "emitter_subset_of_accepted": diff["emitter_subset_of_accepted"],
        "accepted_count": diff["accepted_count"],
        "emitted_count": diff["emitted_count"],
        "emitted_field_set": diff["emitted_field_set"],
        "extra_emitted_fields": diff["extra_emitted_fields"],
        "emitter_refused_unknown": refused,
        "refused_fields": refused_fields,
        "leaked_would_extra": extra_if_leaked,
        "planted_field": PLANTED_UNKNOWN_FIELD,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, sort_keys=True))
    if result["pass"]:
        print(
            "SUCCESS:TST-0179-probe2 emitter field set is a subset of the "
            f"accepted set ({result['emitted_count']}/{result['accepted_count']}); "
            f"planted {result['planted_field']!r} refused"
        )
        return 0
    print("FAILED:TST-0179-probe2 schema-diff or emitter leak")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
