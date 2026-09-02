#!/usr/bin/env python3
"""Probe 2: mutated tree goes red; three random packages stay green; scanner fires."""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import controls  # noqa: E402
import executil  # noqa: E402
import guards  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0182-probe2 {msg}")
    return 1


def main() -> int:
    receipt = C.REPO / C.OUT_REL
    if not receipt.is_file():
        return fail("receipt missing")
    doc = C.load_json(receipt)
    packages = C.domain(doc, "packages") or []
    if len(packages) < 3:
        return fail(f"need >=3 packages, have {len(packages)}")

    mutant = controls.mutant_goes_red("CLAIM-P0-001")
    print(
        f"mutant went_red={mutant['went_red']} mutant_exit={mutant['mutant_exit']} "
        f"original_exit={mutant['original_exit']}"
    )
    if not (mutant["went_red"] and mutant["original_still_green"]):
        return fail(f"known-broken control failed {mutant}")

    planted = "aws_access_key_id=AKIAIOSFODNN7EXAMPLE"
    if not guards.scan_text(planted):
        return fail("scanner silent on planted AKIA value")
    print("planted-secret control fired")

    rng = random.Random(182)
    ids = [p["claim_id"] for p in packages]
    rng.shuffle(ids)
    sample = ids[:3]
    for cid in sample:
        pkg = next(p for p in packages if p["claim_id"] == cid)
        rc, tail = executil.run_cmd(pkg["one_command"])
        print(f"sample {cid} rc={rc}")
        if rc != 0:
            print(tail[-1500:])
            return fail(f"sample {cid} rc={rc}")
    print(f"reviewer_sample={sample}")
    print("SUCCESS:CNF-0182-probe2 known-broken and three-package rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
