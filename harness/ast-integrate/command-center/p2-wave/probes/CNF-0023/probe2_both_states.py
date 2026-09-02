#!/usr/bin/env python3
"""Named probe 2: both-states plus the section-10 apostrophe inline control.

Mechanically different from probe1: independently recomputes the option-id
intersection on the fixtures, and proves that inlining a payload containing
an apostrophe fails while invoking the same file by path succeeds.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mechanise as M  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0023-mechanised-repros.json"
TOKEN = re.compile(r"\bM-\d{2}\b")


def shared_count(root: Path) -> int:
    a = set(TOKEN.findall((root / "option-universe.md").read_text(encoding="utf-8")))
    b = set(
        TOKEN.findall((root / "architecture-candidates.md").read_text(encoding="utf-8"))
    )
    return len(a & b)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0023-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0023":
        print("FAILED:CNF-0023-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0023" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0023-probe2 sentinel absent")
        return 1

    M.write_generated_scripts()
    errors = []
    for rid, path in M.write_generated_scripts().items():
        red = M.invoke_by_path(path, M.UNFIXED)
        green = M.invoke_by_path(path, M.FIXED)
        if red.returncode == 0:
            errors.append(f"{rid} unfixed exited 0")
        if green.returncode != 0:
            errors.append(f"{rid} fixed exited {green.returncode}")
    if errors:
        print("FAILED:CNF-0023-probe2 both-states")
        print("\n".join(errors))
        return 1

    unfixed_n = shared_count(M.UNFIXED)
    fixed_n = shared_count(M.FIXED)
    if unfixed_n != 31:
        print(f"FAILED:CNF-0023-probe2 unfixed intersection {unfixed_n} want 31")
        return 1
    if fixed_n != 0:
        print(f"FAILED:CNF-0023-probe2 fixed intersection {fixed_n} want 0")
        return 1

    inline = M.try_inline_apostrophe_payload()
    if inline.returncode == 0:
        print("FAILED:CNF-0023-probe2 inline apostrophe control succeeded (must fail)")
        print((inline.stderr or "")[-400:])
        return 1
    by_path = subprocess.run(
        [sys.executable, str(M.UNFIXED / "payload.py")],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if by_path.returncode != 0:
        print("FAILED:CNF-0023-probe2 path invocation of payload failed")
        return 1
    if "can't" not in (by_path.stdout or ""):
        print("FAILED:CNF-0023-probe2 payload stdout missing apostrophe text")
        print(repr(by_path.stdout))
        return 1

    frac = M.artifact_field(doc, "fraction_not_mechanisable") or {}
    if int(frac.get("denominator") or 0) < 1:
        print("FAILED:CNF-0023-probe2 empty-set fraction")
        return 1
    non = M.artifact_field(doc, "non_mechanisable") or []
    if len(non) != int(frac["numerator"]):
        print("FAILED:CNF-0023-probe2 non_mechanisable count mismatch")
        return 1
    for item in non:
        if not (item.get("blocking_step") or "").strip():
            print("FAILED:CNF-0023-probe2 blocking_step unnamed", item)
            return 1

    payload = json.dumps(
        {
            "pass": True,
            "probe": "probe2-both-states-and-apostrophe",
            "unit_id": "CNF-0023",
            "unfixed_option_intersection": unfixed_n,
            "fixed_option_intersection": fixed_n,
            "inline_apostrophe_exit": inline.returncode,
            "path_payload_exit": by_path.returncode,
            "fraction_not_mechanisable": frac.get("ratio_text"),
        },
        sort_keys=True,
    )
    print(payload)
    print(
        f"unfixed_ids={unfixed_n} fixed_ids={fixed_n} "
        f"inline_rc={inline.returncode} path_rc={by_path.returncode}"
    )
    print("SUCCESS:CNF-0023-probe2 both-states and apostrophe control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
