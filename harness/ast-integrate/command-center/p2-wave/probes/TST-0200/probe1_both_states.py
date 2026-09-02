#!/usr/bin/env python3
"""Named probe 1: both-states control for TST-0200.

Short-path install must succeed with a complete tree. The same package to a
>260 character dest with LongPathsEnabled=false must refuse, name the limit,
and leave the destination absent or empty.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # .../probes/TST-0200 -> ast-integrate
sys.path.insert(0, str(HERE))

from installer import EXIT_MAX_PATH, EXIT_OK, LIMIT_NAME, POLICY_NAME, WIN32_MAX_PATH  # noqa: E402
from scenario import names_limit, run_matrix  # noqa: E402

ART = REPO / "command-center/receipts/TST-0200.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0200-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0200-p1-") as tmp:
        matrix = run_matrix(Path(tmp))
    c = matrix["contract"]
    short = matrix["short"]
    deep = matrix["deep_long_paths_false"]
    print(
        f"short_exit={short['cli']['exit_code']} "
        f"short_listing={short['listing']['state']} "
        f"short_chars={short['meta']['longest_measured_chars']}"
    )
    print(
        f"deep_off_exit={deep['cli']['exit_code']} "
        f"deep_off_listing={deep['listing']['state']} "
        f"deep_chars={deep['meta']['longest_measured_chars']} "
        f"names_limit={c['deep_off_names_limit']}"
    )
    for key in (
        "short_in_budget",
        "deep_over_budget",
        "short_succeeds",
        "deep_off_refuses",
        "deep_off_names_limit",
        "deep_off_not_partial",
    ):
        print(f"{key}={c[key]}")
        if not c[key]:
            return fail(key)

    if short["cli"]["exit_code"] != EXIT_OK:
        return fail("short-path installer exit")
    if deep["cli"]["exit_code"] != EXIT_MAX_PATH:
        return fail("deep-path installer exit")
    msg = deep["cli"]["message"]
    if not names_limit(msg):
        return fail("refusal message does not name MAX_PATH/260/LongPathsEnabled")
    print(f"refusal_message={msg[:240]}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0200" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    bs = doc.get("both_states") or {}
    if bs.get("short_path", {}).get("listing_state") != "COMPLETE":
        return fail("artifact short listing not COMPLETE")
    if bs.get("deep_path_long_paths_false", {}).get("listing_state") not in {
        "ABSENT",
        "EMPTY",
    }:
        return fail("artifact deep listing not empty/absent")
    if LIMIT_NAME not in json.dumps(doc) or POLICY_NAME not in text:
        return fail("artifact does not name the limit")
    if int(bs.get("deep_path_long_paths_false", {}).get("longest_measured_chars") or 0) <= WIN32_MAX_PATH:
        return fail("artifact deep path not over 260")
    print("SUCCESS:TST-0200-probe1 both-states short-ok deep-refuse empty-dest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
