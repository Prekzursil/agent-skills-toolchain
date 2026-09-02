#!/usr/bin/env python3
"""Named probe 2: CI console script + independent reviewer.

Mechanically different from probe 1: subprocesses ci_console.py (console-script
argv0, not python -m) and infers two dismissal classes from raw test source
without reading original_reason. Also requires the unfalsifiable control to
land UNVERIFIED and the packaging-gap detector to fire.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revalidate import run_console_script  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0024.json"
SRC = HERE / "fixtures" / "suite" / "test_dismissed.py"
SENTINEL = "SUCCESS:BLD-0024"
REVIEW = ("F-CRLF-1", "F-POSIX-1")
TEST_OF = {
    "F-CRLF-1": "test_crlf_text_lines",
    "F-POSIX-1": "test_posix_win_abs_path",
}


def infer_class(fn: ast.FunctionDef) -> str:
    blob = ast.unparse(fn) if hasattr(ast, "unparse") else ast.dump(fn)
    if "ntpath" in blob or "C:\\\\Users" in blob or "C:\\Users" in blob:
        return "posix-only"
    if "endswith" in blob and "\\r" in blob:
        return "windows-crlf"
    if "sibling_still_red" in blob or "sibling_now_green" in blob:
        return "sibling-tdd-red"
    if "undocumented" in blob:
        return "unfalsifiable"
    return "unknown"


def source_functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0024-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0024-probe2 sentinel-absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0024-probe2 self-declared {doc.get('state')}")
        return 1
    if not (doc.get("runner_control") or {}).get("console_script_exercised"):
        print("FAILED:BLD-0024-probe2 console_script_exercised false")
        return 1

    rc, console = run_console_script("as_is")
    if rc != 0:
        print(f"FAILED:BLD-0024-probe2 console rc={rc} {console}")
        return 1
    if "parse_error" in console:
        print(f"FAILED:BLD-0024-probe2 console unparseable {console}")
        return 1
    crlf1 = console.get("test_crlf_text_lines") or {}
    if crlf1.get("outcome") != "FAIL":
        print(f"FAILED:BLD-0024-probe2 console F-CRLF-1 as_is {crlf1}")
        return 1
    rc_lf, console_lf = run_console_script("lf_norm")
    if rc_lf != 0:
        print(f"FAILED:BLD-0024-probe2 console lf rc={rc_lf}")
        return 1
    crlf1_lf = (console_lf.get("test_crlf_text_lines") or {})
    if crlf1_lf.get("outcome") != "PASS":
        print(f"FAILED:BLD-0024-probe2 console LF-norm not green {crlf1_lf}")
        return 1
    gap = console.get("test_packaging_in_tree_helper") or {}
    if gap.get("outcome") != "FAIL":
        print(f"FAILED:BLD-0024-probe2 console packaging helper not FAIL {gap}")
        return 1

    unf = next(
        (
            d
            for d in doc.get("dismissals") or []
            if d.get("class") == "unfalsifiable"
        ),
        None,
    )
    if not unf or unf.get("verdict") != "UNVERIFIED" or unf.get("requeued") is not True:
        print(f"FAILED:BLD-0024-probe2 unfalsifiable {unf}")
        return 1

    fns = source_functions()
    by_id = {d["id"]: d for d in doc.get("dismissals") or []}
    reproduced = []
    for uid in REVIEW:
        test_name = TEST_OF[uid]
        fn = fns.get(test_name)
        if fn is None:
            print(f"FAILED:BLD-0024-probe2 missing source {test_name}")
            return 1
        inferred = infer_class(fn)
        claimed = by_id[uid]["class"]
        # Independent of original_reason: class must match source, not the reason string.
        if inferred != claimed:
            print(
                f"FAILED:BLD-0024-probe2 reviewer {uid} inferred={inferred} claimed={claimed}"
            )
            return 1
        if "original_reason" in ast.dump(fn):
            print(f"FAILED:BLD-0024-probe2 source embeds original_reason {uid}")
            return 1
        reproduced.append(uid)

    printable = {
        "probe": "probe2-console-reviewer",
        "unit_id": "BLD-0024",
        "console_rc": rc,
        "console_crlf1_as_is": crlf1.get("outcome"),
        "console_crlf1_lf_norm": crlf1_lf.get("outcome"),
        "packaging_gap_console_fail": True,
        "unfalsifiable": "UNVERIFIED",
        "reviewer_reproduced": reproduced,
        "pass": True,
    }
    print(json.dumps(printable, sort_keys=True))
    print("SUCCESS:BLD-0024-probe2 console-script runner and reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
