#!/usr/bin/env python3
"""Signal 2: independent recomputation from raw metadata; sets must match.

Also asserts the unknown-compatibility default is conservative and that an
empty result with an empty reason fails (negative control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import compat as C  # noqa: E402
from independent import independent_accepted, load_packages  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0085.json"
INDEX = REPO / "tools/marketplace/fixtures/compat-index.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0085-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0085" not in json.dumps(doc):
        print("FAILED:IMP-0085-probe2 sentinel absent")
        return 1

    packages = load_packages(INDEX)
    raw_prod = C.load_candidates(INDEX)
    if [C.candidate_key(p) for p in raw_prod] != [_k(p) for p in packages]:
        print("FAILED:IMP-0085-probe2 fixture identity mismatch")
        return 1

    mismatches = []
    compared = []
    for plat in ("windows", "macos", "linux"):
        for ver in ("1.2.0", "3.1.0"):
            prod = C.filter_candidates(
                raw_prod, platform=plat, client_version=ver, client_name="claude"
            )
            indep = independent_accepted(
                packages, platform=plat, client_version=ver, client_name="claude"
            )
            compared.append(
                {
                    "platform": plat,
                    "client_version": ver,
                    "production": list(prod.accepted),
                    "independent": list(indep),
                }
            )
            if tuple(prod.accepted) != indep:
                mismatches.append(
                    {
                        "platform": plat,
                        "client_version": ver,
                        "production": list(prod.accepted),
                        "independent": list(indep),
                    }
                )

    extra = [
        ("linux", "0.9.0", "claude"),
        ("linux", "1.2.0", "codex"),
        ("windows", "0.9.0", "claude"),
    ]
    for plat, ver, name in extra:
        prod = C.filter_candidates(
            raw_prod, platform=plat, client_version=ver, client_name=name
        )
        indep = independent_accepted(
            packages, platform=plat, client_version=ver, client_name=name
        )
        compared.append(
            {
                "platform": plat,
                "client_version": ver,
                "client_name": name,
                "production": list(prod.accepted),
                "independent": list(indep),
            }
        )
        if tuple(prod.accepted) != indep:
            mismatches.append(
                {
                    "platform": plat,
                    "client_version": ver,
                    "client_name": name,
                    "production": list(prod.accepted),
                    "independent": list(indep),
                }
            )
        if not prod.accepted:
            try:
                C.assert_nonempty_reason_on_empty(prod)
            except AssertionError:
                print("FAILED:IMP-0085-probe2 empty set lacked reason")
                return 1

    if mismatches:
        print("FAILED:IMP-0085-probe2 set mismatch")
        print(json.dumps(mismatches, indent=2)[:4000])
        return 1

    # Conservative unknown default: independent subtracts undeclared first.
    unknown = {"demo.unknown-compat@9.9.9", "demo.empty-compat-object@0.0.1"}
    for row in compared:
        leaked = unknown.intersection(row["independent"])
        if leaked:
            print("FAILED:IMP-0085-probe2 independent treated unknown as compatible", leaked)
            return 1

    class BareEmpty:
        accepted = ()
        unmet_requirement = ""

    try:
        C.assert_nonempty_reason_on_empty(BareEmpty())
    except AssertionError:
        neg_fired = True
    else:
        print("FAILED:IMP-0085-probe2 negative control did not fire")
        return 1

    payload = {
        "probe": "probe2-independent-recompute",
        "unit_id": "IMP-0085",
        "pass": True,
        "cells_compared": len(compared),
        "identical_sets": True,
        "unknown_conservative": True,
        "negative_control_fired": neg_fired,
        "reviewer": "IMP-0085-independent-set-algebra",
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"compared={len(compared)} identical=True unknown_conservative=True neg={neg_fired}")
    print("SUCCESS:IMP-0085-probe2 independent recomputation")
    return 0


def _k(pkg: dict) -> str:
    return f"{pkg['id']}@{pkg['version']}"


if __name__ == "__main__":
    raise SystemExit(main())
