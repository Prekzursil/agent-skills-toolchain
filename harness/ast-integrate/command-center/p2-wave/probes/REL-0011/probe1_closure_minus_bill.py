#!/usr/bin/env python3
"""Named probe 1: closure-minus-bill fires for two independent causes.

1. Vendor an undeclared component into the tree (generator does not walk vendor/).
2. Hand-delete a lockfile component from the bill (same direction, different hit).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import generator as G  # noqa: E402
import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0011.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    gen_src = (HERE / "generator.py").read_text(encoding="utf-8")
    res_src = (HERE / "resolver.py").read_text(encoding="utf-8")

    def _imports(src: str, mod: str) -> bool:
        for raw in src.splitlines():
            line = raw.strip()
            if line.startswith("#"):
                continue
            if line == f"import {mod}" or line.startswith(f"import {mod} "):
                return True
            if line.startswith(f"from {mod} import"):
                return True
        return False

    if _imports(gen_src, "resolver"):
        print("FAILED:REL-0011-probe1 generator imports resolver")
        return 1
    if _imports(res_src, "generator"):
        print("FAILED:REL-0011-probe1 resolver imports generator")
        return 1
    if G.TOOL_NAME == R.TOOL_NAME:
        print("FAILED:REL-0011-probe1 tools share a name")
        return 1
    if _sha(HERE / "generator.py") == _sha(HERE / "resolver.py"):
        print("FAILED:REL-0011-probe1 generator and resolver are the same file")
        return 1

    u = S.control_undeclared()
    d = S.control_hand_delete()
    print(json.dumps({"undeclared": u, "hand_delete": d}, indent=2, default=str)[:4000])
    if not u.get("pass"):
        print("FAILED:REL-0011-probe1 undeclared vendored did not fire closure-minus-bill")
        return 1
    if not d.get("pass"):
        print("FAILED:REL-0011-probe1 hand-delete did not fire closure-minus-bill")
        return 1
    if u.get("hit") == d.get("hit"):
        print("FAILED:REL-0011-probe1 both hits are the same component")
        return 1
    if S.PLANTED_PURL not in (u.get("closure_minus_bill") or []):
        print("FAILED:REL-0011-probe1 planted purl missing from undeclared diff")
        return 1
    if S.DELETE_PURL not in (d.get("closure_minus_bill") or []):
        print("FAILED:REL-0011-probe1 deleted purl missing from hand-delete diff")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:REL-0011-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0011-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:REL-0011" not in text:
        print("FAILED:REL-0011-probe1 sentinel absent")
        return 1
    if doc.get("generator", {}).get("tool") == doc.get("resolver", {}).get("tool"):
        print("FAILED:REL-0011-probe1 receipt tools are not distinct")
        return 1
    print(
        f"undeclared_hit={u['hit']} delete_hit={d['hit']} "
        f"tools={G.TOOL_NAME} vs {R.TOOL_NAME}"
    )
    print("SUCCESS:REL-0011-probe1 closure-minus-bill two causes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
