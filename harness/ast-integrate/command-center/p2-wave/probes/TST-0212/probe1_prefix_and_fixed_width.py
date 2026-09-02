#!/usr/bin/env python3
"""Probe 1: prefix stays readable; five different-length secrets share one mask width.

Both-states: the five planted secrets have DISTINCT byte lengths before
masking; after the live redactor they share one byte length and each
diagnostic prefix remains at the start of the render.

Signal (a): the five rendered masks.
Signal (b): utf-8 byte-length equality across those renders.

The live SUT is tools/lib/security.mjs (node batch-mask). Python twin must
agree. Secret bodies are never printed.
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
    mask_via_python,
    prefix_samples,
    public_row,
)

REPO_LIB = HERE.parents[3] / "tools" / "lib"
sys.path.insert(0, str(REPO_LIB))
from security import fixed_width_holds as fixed_width_holds  # noqa: E402
from security import utf8_len as utf8_len  # noqa: E402

UNIT = "TST-0212"
RAW = HERE / "probe1-prefix-and-fixed-width.raw.json"


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    secrets = length_secrets()
    raw_lens = [utf8_len(s) for s in secrets]
    if len(set(raw_lens)) != 5:
        return fail(f"fixture secrets are not five distinct lengths: {raw_lens}")

    try:
        mjs_renders = mask_via_mjs(secrets)
        py_renders = mask_via_python(secrets)
    except Exception as exc:  # noqa: BLE001 — surface SUT/runtime failure
        return fail(f"redactor invocation failed: {exc}")

    if mjs_renders != py_renders:
        return fail("mjs and python twins disagree on masked forms")

    rows = [public_row(s, m) for s, m in zip(secrets, mjs_renders)]
    masked_lens = [r["masked_byte_len"] for r in rows]
    payload = {
        "probe": "probe1-prefix-and-fixed-width",
        "unit_id": UNIT,
        "pass": False,
        "signal_a_renders": [r["masked"] for r in rows],
        "signal_b_masked_byte_lengths": masked_lens,
        "raw_secret_byte_lengths": raw_lens,
        "raw_lengths_distinct": True,
        "rows": rows,
        "fixed_mask_body": FIXED_MASK_BODY,
        "mjs_python_agree": True,
        "fixed_width_holds": fixed_width_holds(mjs_renders),
        "prefixes_readable": all(r["prefix_readable"] for r in rows),
        "bodies_absent": all(r["body_absent_from_mask"] for r in rows),
        "prefix_family_samples": [],
    }

    if not all(r["prefix_readable"] for r in rows):
        return fail("diagnostic prefix not readable on an sk- render", payload)
    if not all(r["body_absent_from_mask"] for r in rows):
        return fail("secret body leaked into a mask", payload)
    if not all(r["mask_body"] == FIXED_MASK_BODY for r in rows):
        return fail("mask remainder is not the fixed body", payload)
    if not fixed_width_holds(mjs_renders):
        return fail(f"masked byte lengths are not equal: {masked_lens}", payload)
    if len(set(masked_lens)) != 1:
        return fail("independent length-set check failed", payload)

    family = []
    samples = prefix_samples()
    try:
        family_masked = mask_via_mjs([tok for _p, tok in samples])
        family_py = mask_via_python([tok for _p, tok in samples])
    except Exception as exc:  # noqa: BLE001
        return fail(f"prefix-family mask failed: {exc}", payload)
    if family_masked != family_py:
        return fail("prefix-family mjs/python disagree", payload)
    for (prefix, token), masked in zip(samples, family_masked):
        row = public_row(token, masked)
        family.append(
            {
                "prefix": prefix,
                "masked": masked,
                "prefix_readable": masked.startswith(prefix),
                "mask_body": masked[len(prefix) :],
            }
        )
        if not masked.startswith(prefix):
            payload["prefix_family_samples"] = family
            return fail(f"prefix {prefix!r} not readable after mask", payload)
        if masked[len(prefix) :] != FIXED_MASK_BODY:
            payload["prefix_family_samples"] = family
            return fail(f"prefix {prefix!r} remainder not fixed-width", payload)
        if token[len(prefix) :] in masked:
            payload["prefix_family_samples"] = family
            return fail(f"prefix {prefix!r} body leaked", payload)

    payload["prefix_family_samples"] = family
    payload["pass"] = True
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "renders="
        + ",".join(r["masked"] for r in rows)
        + f" raw_lens={raw_lens} masked_lens={masked_lens} prefixes_ok=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 prefix readable; five lengths share one mask width")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
