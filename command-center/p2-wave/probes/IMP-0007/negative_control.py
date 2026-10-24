#!/usr/bin/env python3
"""IMP-0007 negative control: known-bad bare unknown must be rejected (not warn-as-green)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402
import strict_parser_policy as P  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    schema = M.load_schema(REPO)
    base = P.fixture_base_manifest()
    known_bad = dict(base)
    known_bad["totally_not_in_schema"] = {"planted": True}

    policy_v = P.lint_unknown_fields(known_bad)
    policy_fired = (not policy_v.ok) and (
        "totally_not_in_schema" in policy_v.unknown_keys
    )

    v1, v2 = M.validate_manifest(known_bad, schema)
    schema_fired = (
        (not v1.ok) and (not v2.ok) and v1.error_code == M.ERR_UNKNOWN_TOP_LEVEL
    )

    # Good state remains silent.
    good_policy = P.lint_unknown_fields(base).ok
    g1, g2 = M.validate_manifest(base, schema)
    good_silent = good_policy and g1.ok and g2.ok

    # MUTATION: relax additionalProperties → schema goes green; policy still fires.
    relaxed = M.with_additional_properties(schema, allowed=True)
    r1, r2 = M.validate_manifest(known_bad, relaxed)
    mutation_schema_goes_green = bool(r1.ok and r2.ok)
    mutation_policy_still_blocks = not P.lint_unknown_fields(known_bad).ok

    fired = policy_fired and schema_fired and good_silent
    ok = fired and mutation_schema_goes_green and mutation_policy_still_blocks

    meas = {
        "negative_control_fired": fired,
        "policy_fired": policy_fired,
        "schema_fired": schema_fired,
        "silent_on_good": good_silent,
        "mutation_schema_goes_green": mutation_schema_goes_green,
        "mutation_policy_still_blocks": mutation_policy_still_blocks,
        "ok": ok,
        "policy_code": policy_v.error_code,
        "schema_code": v1.error_code,
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NEGATIVE CONTROL: KNOWN-BAD BARE UNKNOWN + AP MUTATION",
        "NEG-BEGIN:IMP-0007",
        f"policy_fired={policy_fired}",
        f"schema_fired={schema_fired}",
        f"silent_on_good={good_silent}",
        f"mutation_schema_goes_green={mutation_schema_goes_green}",
        f"mutation_policy_still_blocks={mutation_policy_still_blocks}",
        f"negative_control_fired={fired}",
        "NEG-COMPLETE:IMP-0007",
        "SUCCESS:IMP-0007-neg" if ok else "FAILED:IMP-0007-neg",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
