#!/usr/bin/env python3
"""Named probe 2: independent listing + naive-partial negative control.

Signal (b) is an os.scandir walk, not the installer exit code. A planted
partial tree must be classified PARTIAL (the listing can fire). The refused
deep dest must not be PARTIAL. LongPathsEnabled=true on the same deep shape
must complete rather than truncate.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # .../probes/TST-0200 -> ast-integrate
sys.path.insert(0, str(HERE))

from installer import EXIT_OK, EXIT_PARTIAL_NAIVE  # noqa: E402
from scenario import run_matrix  # noqa: E402

ART = REPO / "command-center/receipts/TST-0200.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0200-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0200-p2-") as tmp:
        matrix = run_matrix(Path(tmp))
    c = matrix["contract"]
    naive = matrix["naive_partial_control"]
    deep = matrix["deep_long_paths_false"]
    on = matrix["deep_long_paths_true"]
    print(
        f"naive_state={naive['listing']['state']} "
        f"naive_files={naive['listing']['file_count']} "
        f"naive_exit={naive['cli']['exit_code']}"
    )
    print(
        f"deep_off_state={deep['listing']['state']} "
        f"deep_off_files={deep['listing']['file_count']}"
    )
    print(
        f"deep_on_state={on['listing']['state']} "
        f"deep_on_files={on['listing']['file_count']} "
        f"deep_on_exit={on['cli']['exit_code']}"
    )
    for key in (
        "listing_detects_naive_partial",
        "deep_off_not_partial",
        "listing_cli_agrees_deep_off",
        "deep_on_complete",
        "listing_cli_agrees_short",
    ):
        print(f"{key}={c[key]}")
        if not c[key]:
            return fail(key)

    if naive["cli"]["exit_code"] != EXIT_PARTIAL_NAIVE:
        return fail("naive control did not take the partial-write path")
    if naive["listing"]["file_count"] < 1:
        return fail("naive control wrote no files; listing cannot discriminate")
    if deep["listing"]["partial"]:
        return fail("policy path left a PARTIAL dest")
    if on["cli"]["exit_code"] != EXIT_OK or not on["listing"]["complete"]:
        return fail("LongPathsEnabled=true did not complete the deep tree")

    # Independence: listing state is not copied from installer.ok.
    if deep["cli"]["exit_code"] == 0:
        return fail("deep-off installer unexpectedly succeeded")
    if deep["listing"]["state"] == "COMPLETE":
        return fail("listing COMPLETE on a refused install")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:TST-0200" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    ev = doc.get("evidence") or []
    kinds = {e.get("kind") for e in ev if isinstance(e, dict)}
    if "control" not in kinds or "observation" not in kinds:
        return fail("artifact missing two-signal evidence kinds")
    nc = doc.get("naive_partial_control") or {}
    if nc.get("listing_state") != "PARTIAL":
        return fail("artifact naive control not PARTIAL")
    print("SUCCESS:TST-0200-probe2 listing-independent naive-partial deep-on-complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
