#!/usr/bin/env python3
"""Named probe 2: independent reviewer — mutation + adversarial fourth fixture.

Reviewer obligation (catalog): construct a fourth fixture that passes a
decorative probe but breaks a real consumer.

Also re-proves the catalog mutation: reducing the probe to os.path.exists
greens the third fixture (parseable, missing field), which is exactly why
probe 1 requires that fixture to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(HERE))

from downstream_readability import (  # noqa: E402
    consume,
    decorative_parse_and_key,
    mutant_exists_only,
)
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0455-probe2 {msg}")
    return 1


def main() -> int:
    if not F.ADVERSARIAL.is_file():
        return fail(f"fourth fixture missing {F.ADVERSARIAL}")

    fourth_real = consume(F.ADVERSARIAL)
    fourth_deco = decorative_parse_and_key(F.ADVERSARIAL)
    fourth_exists = mutant_exists_only(F.ADVERSARIAL)

    print(
        f"fourth real ok={fourth_real.ok} code={fourth_real.code} "
        f"decorative_key={fourth_deco} exists_only={fourth_exists}"
    )
    if not fourth_exists:
        return fail("fourth fixture not on disk")
    if not fourth_deco:
        return fail("fourth fixture must pass parse+key-presence (attack is vacuous)")
    if fourth_real.ok:
        return fail(
            f"fourth fixture passed the real consumer ({fourth_real}) — "
            "the shipped probe is still decorative"
        )
    if fourth_real.code != "REQUIRED_FIELD_UNUSABLE":
        return fail(f"fourth fixture code {fourth_real.code}, want REQUIRED_FIELD_UNUSABLE")

    # Mutation control on the third fixture (independent of probe 1's run).
    third_real = consume(F.MISSING_FIELD)
    third_exists = mutant_exists_only(F.MISSING_FIELD)
    print(
        f"third real ok={third_real.ok} code={third_real.code} "
        f"exists_only={third_exists}"
    )
    if third_real.ok:
        return fail("reviewer: third fixture is green under the real probe")
    if not third_exists:
        return fail("reviewer: exists-only mutant cannot see third fixture")

    # Source check: consume() is not an exists wrapper.
    lib = REPO / "tools" / "command-center" / "downstream_readability.py"
    src = lib.read_text(encoding="utf-8")
    body = src[src.index("def consume(") : src.index("\ndef condition_12(")]
    # Strip the docstring so a mention of the forbidden mutation in comments
    # is not mistaken for an actual call.
    if '"""' in body:
        first = body.index('"""')
        second = body.index('"""', first + 3)
        body_no_doc = body[:first] + body[second + 3 :]
    else:
        body_no_doc = body
    if "os.path.exists" in body_no_doc or "path.exists(" in body_no_doc:
        return fail("consume() body calls exists() — probe reduced to existence")
    if "json.loads" not in body or "required_field" not in body:
        return fail("consume() does not parse-and-extract")

    payload = {
        "probe": "probe2-mutation-and-refuter",
        "unit_id": "IMP-0455",
        "reviewer_id": "IMP-0455-probe2-adversarial-fourth",
        "pass": True,
        "fourth_fixture": {
            "path": F.ADVERSARIAL.relative_to(REPO).as_posix(),
            "real_consumer": fourth_real.as_dict(),
            "decorative_parse_and_key": fourth_deco,
            "exists_only": fourth_exists,
            "passes_probe_but_breaks_consumer_if_probe_is_key_presence": True,
        },
        "mutation": {
            "name": "reduce probe to os.path.exists",
            "third_fixture_exists_only": third_exists,
            "third_fixture_real_ok": third_real.ok,
            "would_green_third_and_red_probe1": bool(third_exists and not third_real.ok),
        },
        "verdict": "PASS",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "fourth_breaks_real_consumer=True fourth_passes_decorative=True "
        "exists_only_would_green_third=True"
    )
    print("SUCCESS:IMP-0455-probe2 reviewer fourth fixture and exists-mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
