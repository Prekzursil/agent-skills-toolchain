#!/usr/bin/env python3
"""Signal 1: resolver filtered candidate sets for Windows/macOS/Linux × two clients."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import compat as C  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0085.json"
TEST = REPO / "tools/marketplace/tests/test_compat_resolution.py"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0085-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0085-probe1 unparseable:{exc}")
        return 1
    if doc.get("unit_id") != "IMP-0085":
        print("FAILED:IMP-0085-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0085" not in text:
        print("FAILED:IMP-0085-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0085-probe1 self-declared:{st}")
        return 1

    import os

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        print(out[-2000:])
        print(f"FAILED:IMP-0085-probe1 tests rc={proc.returncode}")
        return 1

    pkgs = C.load_candidates()
    first = C.resolution_matrix(pkgs, client_name="claude")
    second = C.resolution_matrix(pkgs, client_name="claude")
    if first != second:
        print("FAILED:IMP-0085-probe1 matrix nondeterministic")
        return 1

    cells = {}
    for plat in C.MATRIX_PLATFORMS:
        for ver in C.MATRIX_CLIENTS:
            result = C.filter_candidates(
                pkgs, platform=plat, client_version=ver, client_name="claude"
            )
            cells[f"{plat}|{ver}"] = list(result.accepted)
            if not result.accepted:
                C.assert_nonempty_reason_on_empty(result)

    unknown = {"demo.unknown-compat@9.9.9", "demo.empty-compat-object@0.0.1"}
    leaked = []
    for label, accepted in cells.items():
        hit = unknown.intersection(accepted)
        if hit:
            leaked.append((label, sorted(hit)))
    if leaked:
        print("FAILED:IMP-0085-probe1 unknown leaked", leaked)
        return 1

    empty = C.filter_candidates(
        pkgs, platform="linux", client_version="0.9.0", client_name="claude"
    )
    if empty.accepted != ():
        print("FAILED:IMP-0085-probe1 expected empty", empty.accepted)
        return 1
    if empty.unmet_requirement != "requires client >= 1.0.0, you have 0.9.0":
        print("FAILED:IMP-0085-probe1 unmet", empty.unmet_requirement)
        return 1

    digest = hashlib.sha256(
        json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "probe": "probe1-resolver-sets",
        "unit_id": "IMP-0085",
        "pass": True,
        "matrix": first,
        "cells": cells,
        "empty_unmet": empty.unmet_requirement,
        "matrix_sha256": digest,
        "tests_ok": True,
    }
    print(json.dumps({"adjudicated_cells": len(cells), "matrix_sha256": digest, "pass": True}))
    for label, accepted in cells.items():
        print(f"cell {label} accepted={accepted}")
    print(f"empty_unmet={empty.unmet_requirement}")
    print("SUCCESS:IMP-0085-probe1 resolver filtered sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
