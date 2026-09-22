#!/usr/bin/env python3
"""IMP-0006 negative control: six mutated manifests each fail with a distinct code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    schema = M.load_schema(REPO)
    live = M.load_manifest(REPO / M.MANIFEST_RELPATH)
    raw = (REPO / M.MANIFEST_RELPATH).read_text(encoding="utf-8")

    results: list[dict] = []

    cases = [
        (M.ERR_MISSING_NAME, M.mutate_missing_name(live), None),
        (M.ERR_BAD_SEMVER, M.mutate_bad_semver(live), None),
        (M.ERR_UNKNOWN_TOP_LEVEL, M.mutate_unknown_top_level(live), None),
        (M.ERR_WRONG_TYPE, M.mutate_wrong_type(live), None),
        (M.ERR_EMPTY_KEYWORDS, M.mutate_empty_keywords(live), None),
    ]
    for expected, doc, _ in cases:
        v1, v2 = M.validate_manifest(doc, schema)
        results.append(
            {
                "expected": expected,
                "jsonschema_ok": v1.ok,
                "jsonschema_code": v1.error_code,
                "fastjsonschema_ok": v2.ok,
                "fastjsonschema_code": v2.error_code,
                "fired": (not v1.ok) and v1.error_code == expected,
            }
        )

    # duplicate key is parse-time
    dup_raw = M.mutate_duplicate_key_text(raw)
    try:
        M.parse_manifest_text(dup_raw)
        results.append(
            {
                "expected": M.ERR_DUPLICATE_KEY,
                "fired": False,
                "error": "parse unexpectedly succeeded",
            }
        )
    except M.ManifestSchemaError as exc:
        results.append(
            {
                "expected": M.ERR_DUPLICATE_KEY,
                "jsonschema_ok": None,
                "jsonschema_code": exc.code,
                "fired": exc.code == M.ERR_DUPLICATE_KEY,
            }
        )

    codes = [r["expected"] for r in results if r.get("fired")]
    distinct = len(set(codes)) == 6 and len(codes) == 6
    all_fired = all(r.get("fired") for r in results) and distinct

    # MUTATION proof: relax additionalProperties → unknown-key goes green
    unknown = M.mutate_unknown_top_level(live)
    relaxed = M.with_additional_properties(schema, allowed=True)
    vr1, vr2 = M.validate_manifest(unknown, relaxed)
    mutation_unknown_goes_green = bool(vr1.ok and vr2.ok)

    meas = {
        "negative_control_fired": all_fired,
        "mutation_unknown_goes_green": mutation_unknown_goes_green,
        "distinct_error_codes": sorted(set(codes)),
        "case_count": len(results),
        "results": results,
        "ok": all_fired and mutation_unknown_goes_green,
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NEGATIVE CONTROL: SIX MUTATED MANIFESTS + AP MUTATION",
        "NEG-BEGIN:IMP-0006",
        f"case_count={len(results)}",
        f"distinct_codes={','.join(sorted(set(codes)))}",
        f"all_fired={all_fired}",
        f"mutation_unknown_goes_green={mutation_unknown_goes_green}",
        f"negative_control_fired={all_fired}",
        "NEG-COMPLETE:IMP-0006",
        "SUCCESS:IMP-0006-neg" if meas["ok"] else "FAILED:IMP-0006-neg",
    ]
    for r in results:
        lines.append(
            f"case expected={r['expected']} fired={r.get('fired')} "
            f"code={r.get('jsonschema_code')}"
        )
    raw_out = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw_out, encoding="utf-8")
    print(raw_out, end="")
    return 0 if meas["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
