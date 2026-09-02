#!/usr/bin/env python3
"""Probe 1: lossless round-trip. normalize(parse(x)) keeps every lossless key.

Mechanically different from probe 2 (lossy register / planted extras).
Also mutates one lossless key and requires the record to change, so a
normalizer that ignores source values cannot pass.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from tools.router import normalize as N  # noqa: E402

ART = S.REPO / S.ART_REL


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0386-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0386":
        return fail(f"unit_id {doc.get('unit_id')}")
    blob = json.dumps(doc)
    if S.SENTINEL not in blob:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.live_results()
    if len(live) != 4:
        return fail(f"expected 4 formats got {len(live)}")

    rec_by_fmt = {
        r.get("source_format"): r
        for r in (doc.get("records") or [])
        if isinstance(r, dict)
    }
    keymap = doc.get("lossless_keymap") or {}
    if keymap != N.lossless_keymap():
        return fail("artifact lossless_keymap drifted from normalizer")

    mutated = 0
    for result in live:
        parsed = result.parsed
        fmt = parsed.source_format
        errors = N.roundtrip_errors(parsed, result)
        if errors:
            return fail("; ".join(errors))
        src_view = N.source_lossless_projection(parsed.mapping, fmt)
        if "name" not in src_view or "description" not in src_view:
            return fail(f"{fmt} missing required lossless keys")
        art_rec = rec_by_fmt.get(fmt)
        if not art_rec:
            return fail(f"artifact missing record for {fmt}")
        if art_rec.get("name") != result.record.get("name"):
            return fail(f"artifact name drift {fmt}")
        if art_rec.get("description") != result.record.get("description"):
            return fail(f"artifact description drift {fmt}")
        if art_rec.get("capability_id") != result.record.get("capability_id"):
            return fail(f"artifact capability_id drift {fmt}")

        mutated_parsed = copy.deepcopy(parsed)
        mutated_parsed.mapping["name"] = str(parsed.mapping["name"]) + "-MUT"
        mutated_result = N.normalize_parsed(mutated_parsed)
        if mutated_result.record["name"] == result.record["name"]:
            return fail(f"{fmt} name mutation did not change record.name")
        if N.roundtrip_errors(mutated_parsed, mutated_result):
            return fail(f"{fmt} mutated lossless projection broken")
        mutated += 1

        print(
            f"roundtrip format={fmt} lossless_keys={sorted(src_view)} "
            f"capability_id={result.record['capability_id']} mutated_name=True"
        )

    if mutated != 4:
        return fail(f"mutation coverage {mutated}")

    schema_path = S.REPO / S.SCHEMA_REL
    if schema_path.is_file():
        try:
            import jsonschema
        except ImportError:
            print("jsonschema unavailable; skipping schema negative control")
        else:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            record_schema = schema["definitions"]["CapabilityRecord"]
            validator = jsonschema.Draft7Validator(record_schema)
            for result in live:
                bad = dict(result.record)
                bad["silently_kept_extra"] = "should-fail"
                if validator.is_valid(bad):
                    return fail("schema accepted extra field on CapabilityRecord")
                errs = list(validator.iter_errors(result.record))
                if errs:
                    return fail(f"live record failed schema {errs[0].message}")
            print("schema additionalProperties=false rejected planted extra field")

    payload = {
        "formats": 4,
        "mutated": mutated,
        "pass": True,
        "probe": "probe1-roundtrip",
        "unit_id": "IMP-0386",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0386-probe1 lossless round-trip and name-mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
