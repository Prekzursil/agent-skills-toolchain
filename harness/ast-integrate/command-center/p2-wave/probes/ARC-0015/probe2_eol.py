#!/usr/bin/env python3
"""Probe 2: line-ending control — CRLF worktree vs LF blob, identical verdicts.

Evidence is git cat-file -p versus working-tree bytes. git archive is not used.
A naive raw compare is required to disagree (otherwise the probe is not
exercising the CRLF dimension). After LF normalisation the determinism /
round-trip verdicts must match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/TEST-PLAN.json"


def main() -> int:
    report = S.measure()
    eol = report["eol"]
    rt = report["roundtrip"]
    gap = report["gitattributes_gap"]
    print(
        json.dumps(
            {
                "probe": "probe2-eol",
                "unit_id": "ARC-0015",
                "evidence_route": eol["evidence_route"],
                "git_archive_used": eol["git_archive_used"],
                "blob_crlf_count": eol["blob_crlf_count"],
                "worktree_crlf_count": eol["worktree_crlf_count"],
                "verdict_on_lf_blob": eol["verdict_on_lf_blob"],
                "verdict_on_crlf_worktree": eol["verdict_on_crlf_worktree"],
                "verdicts_identical": eol["verdicts_identical_after_lf_norm"],
                "naive_platform_dependent": eol["platform_dependent_without_lf_norm"],
                "roundtrip_pass": rt["pass"],
                "gitattributes_present": gap["gitattributes_present"],
                "pass": bool(
                    eol["verdicts_identical_after_lf_norm"]
                    and eol["platform_dependent_without_lf_norm"]
                    and not eol["git_archive_used"]
                    and rt["pass"]
                ),
            },
            sort_keys=True,
        )
    )
    print(
        f"route={eol['evidence_route']} archive_used={eol['git_archive_used']} "
        f"blob_crlf={eol['blob_crlf_count']} wt_crlf={eol['worktree_crlf_count']} "
        f"norm_verdicts={eol['verdict_on_lf_blob']}/{eol['verdict_on_crlf_worktree']} "
        f"naive_blob={eol['naive_verdict_on_lf_blob']} "
        f"naive_wt={eol['naive_verdict_on_crlf_worktree']}"
    )
    print(
        f"roundtrip={rt['pass']} clean_match={rt['clean_verdicts_identical']} "
        f"mutant_match={rt['mutant_verdicts_identical']} "
        f"naive_platform_dependent={rt['naive_classify_platform_dependent']} "
        f"gitattributes={gap['gitattributes_present']}"
    )
    if eol["git_archive_used"] or eol["evidence_route"] != "git cat-file -p":
        print("FAILED:ARC-0015-probe2 evidence route is not git cat-file -p")
        return 1
    if eol["blob_crlf_count"] != 0:
        print("FAILED:ARC-0015-probe2 blob is not LF")
        return 1
    if eol["worktree_crlf_count"] < 1:
        print("FAILED:ARC-0015-probe2 working tree is not CRLF")
        return 1
    if eol["raw_worktree_equals_blob"]:
        print("FAILED:ARC-0015-probe2 worktree raw bytes equal blob (no CRLF dimension)")
        return 1
    if not eol["verdicts_identical_after_lf_norm"]:
        print("FAILED:ARC-0015-probe2 LF-norm verdicts differ (platform-dependent)")
        return 1
    if eol["verdict_on_lf_blob"] != "PASS" or eol["verdict_on_crlf_worktree"] != "PASS":
        print("FAILED:ARC-0015-probe2 LF-norm verdict was not PASS on both forms")
        return 1
    if not eol["platform_dependent_without_lf_norm"]:
        print("FAILED:ARC-0015-probe2 naive compare did not disagree; CRLF not exercised")
        return 1
    if not rt["pass"]:
        print("FAILED:ARC-0015-probe2 CRLF round-trip classify")
        return 1
    if not rt.get("naive_classify_platform_dependent"):
        print("FAILED:ARC-0015-probe2 naive classify was not platform-dependent")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0015-probe2 TEST-PLAN.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:ARC-0015" not in text:
        print("FAILED:ARC-0015-probe2 sentinel absent")
        return 1
    lec = doc.get("line_ending_control") or {}
    if lec.get("git_archive_used") is not False:
        print("FAILED:ARC-0015-probe2 artifact used or omitted git_archive_used=false")
        return 1
    if "git cat-file -p" not in str(lec.get("evidence_route") or ""):
        print("FAILED:ARC-0015-probe2 artifact evidence_route is not cat-file")
        return 1
    if not lec.get("verdicts_identical_after_lf_norm"):
        print("FAILED:ARC-0015-probe2 artifact verdicts not identical")
        return 1
    print("SUCCESS:ARC-0015-probe2 CRLF vs LF blob identical verdicts via cat-file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
