#!/usr/bin/env python3
"""Probe 1: tokenize each turn-0 injected file/item and sum.

Tokenizer is tools/router/tokenizer.py (GPT-2 regex split), not len//4.
Always-on control fixture must be injected; lazy paths: fixture must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from injection import (  # noqa: E402
    UNIT,
    TOKENIZER_ID,
    char_quarter_estimate,
    control_paths,
    injected_only,
    injection_set,
    payloads_for,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    items = injection_set()
    inj = injected_only(items)
    ctr = control_paths()
    always = ctr["always_on"]
    lazy = ctr["lazy"]

    always_rows = [r for r in items if r["path"] == always]
    lazy_rows = [r for r in items if r["path"] == lazy]
    if not always_rows:
        return fail(f"always-on control missing from enumeration: {always}")
    if always_rows[0]["injected"] is not True:
        return fail("always-on control classified as not injected")
    if always_rows[0]["tokens"] < 80:
        return fail(f"always-on control too small: {always_rows[0]['tokens']}")
    if not lazy_rows:
        return fail(f"lazy control missing from enumeration: {lazy}")
    if lazy_rows[0]["injected"] is not False:
        return fail("lazy paths: control was injected — enumerator is broken")

    if not inj:
        return fail("injected set empty")

    file_sum = sum(int(r["tokens"]) for r in inj)
    if file_sum <= 0:
        return fail("file token sum is 0")

    payloads = payloads_for(inj)
    discriminated = False
    for row, payload in zip(inj, payloads):
        counted = row["tokens"]
        est = char_quarter_estimate(payload)
        if counted > 32 and counted != est:
            discriminated = True
            break
    if not discriminated:
        return fail("tokenizer matched len//4 on every substantial payload")

    dominant = max(inj, key=lambda r: int(r["tokens"]))
    report = {
        "probe": "probe1-tokenize-injected-files",
        "unit_id": UNIT,
        "tokenizer_id": TOKENIZER_ID,
        "injected_count": len(inj),
        "enumerated_count": len(items),
        "file_token_sum": file_sum,
        "dominant": {
            "path": dominant["path"],
            "class": dominant["class"],
            "tokens": dominant["tokens"],
            "bytes": dominant["bytes"],
        },
        "class_counts": {
            klass: sum(1 for r in inj if r["class"] == klass)
            for klass in sorted({r["class"] for r in inj})
        },
        "always_on_control_injected": True,
        "lazy_control_injected": False,
        "tokenizer_ne_len_quarter": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"SUCCESS:{UNIT}-probe1 file_token_sum={file_sum} "
        f"dominant={dominant['path']} tokens={dominant['tokens']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
