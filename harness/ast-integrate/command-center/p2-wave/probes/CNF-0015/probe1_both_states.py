#!/usr/bin/env python3
"""Probe 1: both-states collision test (pre-fix FAIL, post-fix PASS).

Opposite results are the unit. A test that PASSes in both states, or FAILs
in both, measures nothing and fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collision_test as C  # noqa: E402
import extract as X  # noqa: E402
import scenario as S  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0015-blocker-repro.json"
SENTINEL = (
    "SUCCESS:CNF-0015 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the test was executed "
    "against BOTH the pre-fix and post-fix document states and returned "
    "opposite results. Any other terminal state is FAILED:CNF-0015 "
    "<classification> with the diagnostic tail attached."
)


def main() -> int:
    files = S.write_fixtures()
    live = S.live_census()
    print(json.dumps({"live_census": live}, sort_keys=True))

    rc_pre, pre = C.run(files["option"], files["arch_pre"])
    rc_post, post = C.run(files["option"], files["arch_post"])
    print(
        json.dumps(
            {
                "pre_exit": rc_pre,
                "pre_shared": pre["shared_count"],
                "pre_result": pre["test_result"],
                "post_exit": rc_post,
                "post_shared": post["shared_count"],
                "post_result": post["test_result"],
                "extractor": X.extractor_anchor(),
            },
            sort_keys=True,
        )
    )

    if rc_pre == rc_post:
        print(
            "FAILED:CNF-0015-probe1 same result in both states "
            f"pre={rc_pre} post={rc_post} (vacuous test)"
        )
        return 1
    if rc_pre != 1:
        print(f"FAILED:CNF-0015-probe1 pre-fix must FAIL, got exit {rc_pre}")
        return 1
    if rc_post != 0:
        print(f"FAILED:CNF-0015-probe1 post-fix must PASS, got exit {rc_post}")
        return 1
    if pre["shared_count"] != 31:
        print(
            f"FAILED:CNF-0015-probe1 pre-fix shared_count={pre['shared_count']} want 31"
        )
        return 1
    if post["shared_count"] != 0:
        print(
            f"FAILED:CNF-0015-probe1 post-fix shared_count={post['shared_count']} want 0"
        )
        return 1
    if pre["option_count"] != 33:
        print(f"FAILED:CNF-0015-probe1 family M count={pre['option_count']} want 33")
        return 1
    if pre["mechanism_bare_m_count"] != 38:
        print(
            "FAILED:CNF-0015-probe1 pre-fix mechanism count="
            f"{pre['mechanism_bare_m_count']} want 38"
        )
        return 1
    if post["mechanism_mech_count"] != 38:
        print(
            "FAILED:CNF-0015-probe1 post-fix MECH count="
            f"{post['mechanism_mech_count']} want 38"
        )
        return 1
    if post["mechanism_bare_m_count"] != 0:
        print("FAILED:CNF-0015-probe1 post-fix still has bare M-NN mechanism decls")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0015-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    domain = SC.domain(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0015-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0015-probe1 completion sentinel absent from artifact")
        return 1
    both = domain.get("both_states") or {}
    if int(both.get("pre_fix", {}).get("shared_count", -1)) != 31:
        print("FAILED:CNF-0015-probe1 artifact pre-fix shared_count drift")
        return 1
    if int(both.get("post_fix", {}).get("shared_count", -1)) != 0:
        print("FAILED:CNF-0015-probe1 artifact post-fix shared_count drift")
        return 1
    if both.get("pre_fix", {}).get("test_result") != "FAIL":
        print("FAILED:CNF-0015-probe1 artifact pre-fix result not FAIL")
        return 1
    if both.get("post_fix", {}).get("test_result") != "PASS":
        print("FAILED:CNF-0015-probe1 artifact post-fix result not PASS")
        return 1
    if both.get("opposite_results") is not True:
        print("FAILED:CNF-0015-probe1 artifact opposite_results is not true")
        return 1

    print("SUCCESS:CNF-0015-probe1 both-states opposite results (31 vs 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
