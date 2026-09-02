#!/usr/bin/env python3
"""Probe 1: fail-first oracles, trivial reject, totality.

Re-runs the generator against a fresh two-commit scratch product.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import run  # noqa: E402

ART = REPO / "command-center/receipts/REL-0024.json"


def domain(rec: dict) -> dict:
    report = rec.get("report")
    return report if isinstance(report, dict) else rec


def main() -> int:
    doc = run()
    accepted = doc["generated_tests"]
    if len(accepted) < 1:
        print("FAILED:REL-0024-probe1 zero accepted tests")
        return 1
    for t in accepted:
        if t.get("pre_fix_outcome") != "RED":
            print(f"FAILED:REL-0024-probe1 {t.get('test_id')} not RED on pre-fix")
            return 1
        if t.get("post_fix_outcome") != "GREEN":
            print(f"FAILED:REL-0024-probe1 {t.get('test_id')} not GREEN on post-fix")
            return 1
        if t.get("pre_fix_sha") == t.get("post_fix_sha"):
            print("FAILED:REL-0024-probe1 pre/post SHA collided")
            return 1
        if len(str(t.get("pre_fix_sha") or "")) != 40:
            print("FAILED:REL-0024-probe1 pre_fix_sha is not a git SHA1")
            return 1

    triv = doc.get("rejected_trivial") or []
    if not triv:
        print("FAILED:REL-0024-probe1 trivial candidate was not rejected")
        return 1
    if triv[0].get("reason") != "green-on-both-commits":
        print("FAILED:REL-0024-probe1 trivial reason", triv[0])
        return 1
    if triv[0].get("pre_fix_outcome") != "GREEN" or triv[0].get("post_fix_outcome") != "GREEN":
        print("FAILED:REL-0024-probe1 trivial was not green-on-both")
        return 1

    tot = doc["totality"]
    if not tot.get("complete"):
        print("FAILED:REL-0024-probe1 totality incomplete", tot)
        return 1
    if tot.get("harvested") != tot.get("mapped") + tot.get("unmapped"):
        print("FAILED:REL-0024-probe1 totality arithmetic", tot)
        return 1
    if tot.get("mapped") != len(accepted):
        print("FAILED:REL-0024-probe1 mapped != accepted")
        return 1

    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:REL-0024-probe1 receipt missing or tiny")
        return 1
    text = ART.read_text(encoding="utf-8")
    rec = json.loads(text)
    if rec.get("unit_id") != "REL-0024":
        print("FAILED:REL-0024-probe1 unit_id", rec.get("unit_id"))
        return 1
    if "SUCCESS:REL-0024" not in text:
        print("FAILED:REL-0024-probe1 sentinel absent")
        return 1
    if str(rec.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:REL-0024-probe1 self-declared", rec.get("state"))
        return 1
    rec_tests = domain(rec).get("generated_tests") or rec.get("generated_tests") or []
    if len(rec_tests) != len(accepted):
        print(
            f"FAILED:REL-0024-probe1 receipt tests {len(rec_tests)} != live {len(accepted)}"
        )
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-fail-first",
                "unit_id": "REL-0024",
                "accepted": len(accepted),
                "trivial_rejected": True,
                "totality": tot,
                "pre_fix_sha": accepted[0]["pre_fix_sha"],
                "post_fix_sha": accepted[0]["post_fix_sha"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"accepted={len(accepted)} trivial_rejected=True "
        f"totality_complete={tot['complete']}"
    )
    print("SUCCESS:REL-0024-probe1 fail-first trivial-reject totality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
