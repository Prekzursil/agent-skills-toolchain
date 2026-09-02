#!/usr/bin/env python3
"""Probe 2: a per-character mask MUST fail the fixed-width assertion.

Negative control for TST-0212. The same five planted secrets, masked by
replacing each body character with '*', produce DISTINCT utf-8 lengths.
fixed_width_holds() on those renders is False. The live redactor on the
same secrets still holds, so the assertion is not vacuously false.

Secret bodies are never printed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    FIXED_MASK_BODY,
    length_secrets,
    mask_via_mjs,
    per_character_mask,
    public_row,
)

REPO_LIB = HERE.parents[3] / "tools" / "lib"
sys.path.insert(0, str(REPO_LIB))
from security import fixed_width_holds as fixed_width_holds  # noqa: E402
from security import utf8_len as utf8_len  # noqa: E402

UNIT = "TST-0212"
RAW = HERE / "probe2-per-char-mask-fails.raw.json"


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    secrets = length_secrets()
    raw_lens = [utf8_len(s) for s in secrets]
    if len(set(raw_lens)) != 5:
        return fail(f"fixture secrets are not five distinct lengths: {raw_lens}")

    mutant = [per_character_mask(s) for s in secrets]
    mutant_lens = [utf8_len(m) for m in mutant]
    mutant_rows = [public_row(s, m) for s, m in zip(secrets, mutant)]

    try:
        live = mask_via_mjs(secrets)
    except Exception as exc:  # noqa: BLE001
        return fail(f"live redactor failed: {exc}")
    live_lens = [utf8_len(m) for m in live]

    payload = {
        "probe": "probe2-per-char-mask-fails",
        "unit_id": UNIT,
        "pass": False,
        "raw_secret_byte_lengths": raw_lens,
        "mutant_renders": mutant,
        "mutant_byte_lengths": mutant_lens,
        "mutant_fixed_width_holds": fixed_width_holds(mutant),
        "mutant_unique_length_count": len(set(mutant_lens)),
        "live_renders": live,
        "live_byte_lengths": live_lens,
        "live_fixed_width_holds": fixed_width_holds(live),
        "mutant_rows": mutant_rows,
        "fixed_mask_body": FIXED_MASK_BODY,
        "negative_control": "per-character remainder mask leaks body length",
    }

    if fixed_width_holds(mutant):
        return fail("per-character mutant unexpectedly passed fixed-width", payload)
    if len(set(mutant_lens)) < 2:
        return fail("per-character mutant lengths were not distinct", payload)
    if mutant_lens == live_lens:
        return fail("mutant lengths matched live fixed-width lengths", payload)
    if not fixed_width_holds(live):
        return fail("live redactor failed fixed-width on the same secrets", payload)
    if any(m[3:] == FIXED_MASK_BODY for m in mutant):
        # sk- is 3 chars; a per-char mask of an 8-char body is 8 stars, not [REDACTED]
        pass
    if any(r["mask_body"] == FIXED_MASK_BODY for r in mutant_rows):
        return fail("per-character mutant used the production fixed body", payload)
    # Mutant still keeps the prefix (diagnosis), but leaks length.
    if not all(r["prefix_readable"] for r in mutant_rows):
        return fail("mutant dropped the diagnostic prefix; control is off-target", payload)

    payload["pass"] = True
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mutant_lens={mutant_lens} live_lens={live_lens} "
        f"mutant_holds=False live_holds=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 per-character mask fails fixed-width assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
