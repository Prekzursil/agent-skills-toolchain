#!/usr/bin/env python3
"""Named probe 1: three-fixture battery for completion condition 12.

Fixtures:
  readable                              -> READABLE (must PASS)
  exists-but-unparseable                -> UNPARSEABLE (must FAIL)
  parseable-but-missing-required-field  -> MISSING_REQUIRED_FIELD (must FAIL)

If the third fixture PASSES, the probe is measuring existence (or parseability)
rather than readability. A mutation reducing the probe to os.path.exists would
turn that third fixture green and thereby red this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(HERE))

from downstream_readability import consume, mutant_exists_only  # noqa: E402
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0455-probe1 {msg}")
    return 1


def main() -> int:
    rows = []
    for name, spec in F.EXPECTED.items():
        path = spec["path"]
        if not path.is_file():
            return fail(f"fixture missing: {name} {path}")
        result = consume(path)
        rows.append(
            {
                "fixture": name,
                "path": path.relative_to(REPO).as_posix(),
                "bytes": path.stat().st_size,
                "ok": result.ok,
                "code": result.code,
                "extracted": result.extracted,
                "detail": result.detail,
                "want_ok": spec["ok"],
                "want_code": spec["code"],
            }
        )
        print(
            f"fixture={name} ok={result.ok} code={result.code} "
            f"want_ok={spec['ok']} want_code={spec['code']}"
        )
        if result.ok != spec["ok"] or result.code != spec["code"]:
            return fail(
                f"{name}: got ok={result.ok} code={result.code} "
                f"want ok={spec['ok']} code={spec['code']}"
            )

    third = next(r for r in rows if r["fixture"] == "parseable-but-missing-required-field")
    if third["ok"]:
        return fail(
            "third fixture PASSED — probe measures existence/parseability, not readability"
        )
    exists_would_pass = mutant_exists_only(F.MISSING_FIELD)
    if not exists_would_pass:
        return fail("exists-only mutant cannot see the third fixture (vacuous control)")
    if exists_would_pass and third["ok"]:
        return fail("real probe agrees with exists-only on the third fixture")

    readable = next(r for r in rows if r["fixture"] == "readable")
    if readable["extracted"] != "SENTINEL:FIXT-0001:READABLE":
        return fail(f"consumer did not extract the required field: {readable['extracted']}")

    live = REPO / "command-center" / "receipts" / "IMP-0455.json"
    live_row = None
    if live.is_file():
        live_result = consume(live)
        live_row = live_result.as_dict()
        print(
            f"live_receipt ok={live_result.ok} code={live_result.code} "
            f"extracted={live_result.extracted}"
        )
        if not live_result.ok or live_result.code != "READABLE":
            return fail(f"live receipt not readable: {live_result}")
        if live_result.extracted != "SENTINEL:IMP-0455:DOWNSTREAM-READABLE-PROVEN":
            return fail(f"live sentinel mismatch: {live_result.extracted}")

    payload = {
        "probe": "probe1-three-fixtures",
        "unit_id": "IMP-0455",
        "required_field": F.REQUIRED_FIELD,
        "pass": True,
        "fixtures": rows,
        "mutation_control": {
            "mutant": "os.path.exists",
            "third_fixture_exists_only": exists_would_pass,
            "third_fixture_real_ok": third["ok"],
            "mutant_would_green_third": exists_would_pass and not third["ok"],
        },
        "live_receipt": live_row,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "readable=PASS unparseable=FAIL missing-field=FAIL "
        f"exists_only_would_green_third={exists_would_pass}"
    )
    print("SUCCESS:IMP-0455-probe1 three-fixture battery; third fixture FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
