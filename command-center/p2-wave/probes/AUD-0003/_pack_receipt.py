#!/usr/bin/env python3
"""Pack AUD-0003 PR-history unique-content census receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline count is on disk (catalog `reviewer_requirement`);
then SUCCESS. Never stubs SUCCESS. Never invents independent-review.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0003"
OUT = "command-center/audit/AUD-0003-pr-unique-content.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0003/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0003/probe1-git-diff-missing.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0003/probe2-github-merge-reachability.json"
NC_JSON = "command-center/p2-wave/probes/AUD-0003/negative-control-local-delete.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0003/probe1-git-diff-missing.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0003/probe2-github-merge-reachability.raw.txt"
NC_RAW = "command-center/p2-wave/probes/AUD-0003/negative-control-local-delete.raw.txt"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline count is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((L.REPO / P1_JSON).read_text(encoding="utf-8"))
    p2 = json.loads((L.REPO / P2_JSON).read_text(encoding="utf-8"))
    nc = json.loads((L.REPO / NC_JSON).read_text(encoding="utf-8"))
    raw1 = (L.REPO / P1_RAW).read_text(encoding="utf-8")
    raw2 = (L.REPO / P2_RAW).read_text(encoding="utf-8")
    raw_nc = (L.REPO / NC_RAW).read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = p1.get("started_at") or "2026-09-07T22:17:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sample_count = int(p1["sample_count"])
    prs_with_findings = int(p1["prs_with_findings"])
    total_diff_paths = int(p1["total_missing_or_differing_paths"])
    p1_ok = bool(p1.get("ok"))
    p2_ok = bool(p2.get("ok"))
    nc_ok = bool(nc.get("ok"))
    agree_merged = int(p2["summary"]["agree_merged"])
    agree_not = int(p2["summary"]["agree_not_merged"])
    disagree = int(p2["summary"]["disagree"])
    deliberate_prs = int(p2["summary"]["deliberate_absent_prs"])
    deliberate_paths = int(p2["summary"]["deliberate_absent_paths"])
    never_merged_diff_paths = sum(
        len(r.get("never_merged_or_disagree_paths") or []) for r in p2["rows"]
    )
    never_merged_diff_prs = sum(
        1 for r in p2["rows"] if r.get("never_merged_or_disagree_paths")
    )
    selection = p1.get("selection") or {}
    bound_desc = selection.get("bound_description", "bounded sample")

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(P1_JSON, "supporting"),
        L.art(P2_JSON, "supporting"),
        L.art(NC_JSON, "control"),
        L.art(P1_RAW, "log"),
        L.art(P2_RAW, "log"),
        L.art(NC_RAW, "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0003/probe1_git_diff_missing.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0003/probe2_github_merge_reachability.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0003/negative_control_local_delete.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0003/sample_bound.py",
            "supporting",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0003/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which merged-or-closed pull requests contain file content that is "
        "absent from main today, and for each, was the loss deliberate "
        "(superseded) or accidental (revert, force-push, or a closed-without-merge)?"
    )
    headline = (
        f"Bounded census of {sample_count} PRs ({bound_desc}) against "
        f"origin/main@{p1.get('main_sha', '?')[:12]}. Probe1 "
        f"(git diff <head> main --name-only ∩ PR paths): "
        f"{prs_with_findings}/{sample_count} PRs still differ on "
        f"{total_diff_paths} path(s). Probe2 (merged_at ∧ merge_commit_sha "
        f"ancestor-of-main): agree_merged={agree_merged} "
        f"agree_not_merged={agree_not} disagree={disagree}. Cross-check "
        f"(catalog rule: deliberate only when both signals agree merged): "
        f"{deliberate_prs} merged PR(s) with {deliberate_paths} still-differing "
        f"path(s) classified deliberate/superseded; {never_merged_diff_prs} "
        f"closed-without-merge PR(s) with {never_merged_diff_paths} differing "
        f"path(s) classified never-merged/non-deliberate. Negative control PR "
        f"#{nc.get('control_pr')}: baseline_missing="
        f"{nc.get('baseline_missing_count')} after_delete_missing="
        f"{nc.get('after_delete_missing_count')} (expect 0 then 1) "
        f"ok={nc_ok}."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0003"
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0003-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0003/independent-review.json"
                ),
            },
            {
                "id": "AUD-0003-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Census bound to {sample_count} PRs; ~310 closed PRs exist "
                    "repo-wide. Full-history sweep is residual, not silently dropped."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not "
                "seen this unit's transcript; the reviewer must try to FALSIFY "
                "the headline count before PASS, not re-read the artifact. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0003 pr-unique-content census measured "
            f"sample={sample_count} prs_with_diff={prs_with_findings} "
            f"diff_paths={total_diff_paths} deliberate_prs={deliberate_prs} "
            f"deliberate_paths={deliberate_paths} "
            f"never_merged_diff_prs={never_merged_diff_prs} "
            f"disagree={disagree} control_ok={nc_ok}; "
            "blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "green-not-live",
                "detector-failure",
            ],
            "reason": (
                f"Named probes completed on a documented {sample_count}-PR bound "
                f"(probe1 ok={p1_ok}, probe2 ok={p2_ok}, negative control "
                f"ok={nc_ok}), but catalog reviewer_requirement is unmet."
            ),
            "diagnostic_tail": (
                f"sample={sample_count} diff_paths={total_diff_paths} "
                f"deliberate_paths={deliberate_paths} disagree={disagree} "
                f"control_ok={nc_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the headline deliberate-"
                "absent and never-merged differing path counts before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0003/probe1_git_diff_missing.py",
                    f"prs_with_findings={prs_with_findings} "
                    f"total_missing_or_differing_paths={total_diff_paths}",
                    0 if p1_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0003-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0003-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Census bound to {sample_count} PRs; ~310 closed PRs exist "
                    "repo-wide. Full-history sweep is residual, not silently dropped."
                ),
            },
        ]

    # Seed non-empty downstream_consumers before first schema validate.
    # main() replaces this with a live receipt_validate.py admit probe.
    seeded_consumers = [
        {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": False,
            "read_ok": False,
            "exit_code": 1,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                "seeded-before-first-admit; replaced after live run",
                1,
            ),
        }
    ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0003",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 git-diff missing/differing census over {sample_count} "
                    f"PRs ({bound_desc}): for each PR head, "
                    "`git diff <head> origin/main --name-only` filtered to paths "
                    f"the PR touched. {prs_with_findings} PR(s) still differ on "
                    f"{total_diff_paths} path(s). Selection and bound are "
                    "recorded in sample_bound.py / probe1 JSON (not silently "
                    f"truncated). probe1_ok={p1_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0003/probe1_git_diff_missing.py",
                        raw1,
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-git-diff-missing.json",
                        json.dumps(
                            {
                                "sample_count": sample_count,
                                "prs_with_findings": prs_with_findings,
                                "total_missing_or_differing_paths": total_diff_paths,
                                "ok": p1_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 GitHub merge reachability: for the same sample, "
                    "`gh api pulls/{n}` yields merged_at + merge_commit_sha; "
                    "`git merge-base --is-ancestor <merge_commit_sha> origin/main` "
                    "tests reachability. The two must agree on merged-ness before "
                    "any absence is called deliberate. "
                    f"agree_merged={agree_merged} agree_not_merged={agree_not} "
                    f"disagree={disagree}. Deliberate/superseded paths="
                    f"{deliberate_paths} across {deliberate_prs} PR(s); "
                    f"never-merged differing paths={never_merged_diff_paths} "
                    f"across {never_merged_diff_prs} PR(s)."
                ),
                "CONFIRMED" if p2_ok and disagree == 0 else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0003/probe2_github_merge_reachability.py",
                        raw2,
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-github-merge-reachability.json",
                        json.dumps(p2["summary"]),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Negative control (tests_required): fully-merged PR "
                    f"#{nc.get('control_pr')} against a disposable worktree of "
                    f"origin/main → baseline_missing="
                    f"{nc.get('baseline_missing_count')} (expect 0); delete "
                    f"`{nc.get('victim_path')}` → after_delete_missing="
                    f"{nc.get('after_delete_missing_count')} (expect 1). "
                    f"control_ok={nc_ok}."
                ),
                "CONFIRMED" if nc_ok else "REFUTED",
                NC_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0003/negative_control_local_delete.py",
                        raw_nc,
                        0 if nc_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read negative-control-local-delete.json",
                        json.dumps(
                            {
                                "baseline_missing_count": nc.get(
                                    "baseline_missing_count"
                                ),
                                "after_delete_missing_count": nc.get(
                                    "after_delete_missing_count"
                                ),
                                "ok": nc_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0003-fully-merged-zero-missing",
                "name": (
                    "tests_required: fully-merged control PR reports zero missing "
                    "files on a clean origin/main worktree"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0003/negative_control_local_delete.py",
                "result": "PASS"
                if nc.get("baseline_missing_count") == 0
                else "FAIL",
                "assertions": 1,
                "output_tail": raw_nc[-800:],
            },
            {
                "id": "AUD-0003-local-delete-exactly-one",
                "name": (
                    "tests_required: after deleting one of the control PR's files "
                    "locally, detector reports exactly one missing"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0003/negative_control_local_delete.py",
                "result": "PASS"
                if nc.get("after_delete_missing_count") == 1
                else "FAIL",
                "assertions": 1,
                "output_tail": raw_nc[-800:],
            },
            {
                "id": "AUD-0003-merge-signals-agree",
                "name": (
                    "probe2 precondition: merged_at and merge_commit reachability "
                    "must agree on every sampled PR before deliberate labels fire"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0003/probe2_github_merge_reachability.py",
                "result": "PASS" if disagree == 0 else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0003-C1",
                "other",
                (
                    f"Fully-merged PR #{nc.get('control_pr')} must report zero "
                    "missing files among its head-present paths on a clean "
                    "origin/main worktree."
                ),
                True,
                True,
                bad=f"baseline_missing={nc.get('baseline_missing')}",
                good=f"baseline_missing_count={nc.get('baseline_missing_count')}",
            ),
            L.control(
                "AUD0003-C2",
                "mutation",
                (
                    "Deleting one of the control PR's files in the disposable "
                    "worktree must make the detector report exactly that one "
                    "path as missing."
                ),
                True,
                True,
                bad=f"after_delete_missing={nc.get('after_delete_missing')}",
                good=(
                    f"victim={nc.get('victim_path')} "
                    f"after_delete_missing_count={nc.get('after_delete_missing_count')}"
                ),
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": seeded_consumers,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS "
                "sentinel; retrying against a missing input is a detector "
                "failure, not a transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether closed/merged PRs outside this "
                    f"{sample_count}-PR bound (repo has ~310 closed PRs) carry "
                    "additional unique content absent from main."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Raise MERGED_LIMIT / CLOSED_UNMERGED_LIMIT in "
                    "sample_bound.py (or page the full closed list), re-run "
                    "probe1+probe2, and compare deliberate_absent_paths to "
                    f"this pass's {deliberate_paths}."
                ),
            },
            {
                "claim": (
                    "Among the deliberate/superseded differing paths, which "
                    "are path-deleted from main vs content-evolved "
                    "(byte-different but still present)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "For each deliberate path, run "
                    "`git cat-file -e origin/main:<path>` and split the "
                    f"{deliberate_paths} paths into absent-vs-evolved buckets."
                ),
            },
            {
                "claim": (
                    "PRs whose base is not main (none in this sample's merged "
                    "set targeted a non-main base this pass, but the selector "
                    "does not filter base) may need a different reachability tip."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Filter sample to baseRefName!=main and re-run probe2 with "
                    "tip=origin/<base> as well as origin/main."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0003-C1", "AUD0003-C2"],
            "observations": [
                {
                    "name": "sample_count",
                    "measured": sample_count,
                    "method": bound_desc,
                    "anchor": P1_JSON,
                },
                {
                    "name": "prs_with_diff_findings",
                    "measured": prs_with_findings,
                    "method": "probe1: git diff head main --name-only ∩ PR paths nonempty",
                    "anchor": P1_RAW,
                },
                {
                    "name": "total_missing_or_differing_paths",
                    "measured": total_diff_paths,
                    "method": "sum of probe1 missing_or_differing_count",
                    "anchor": P1_JSON,
                },
                {
                    "name": "deliberate_absent_prs",
                    "measured": deliberate_prs,
                    "method": (
                        "probe2: agree_merged AND probe1 differing paths nonempty"
                    ),
                    "anchor": P2_JSON,
                },
                {
                    "name": "deliberate_absent_paths",
                    "measured": deliberate_paths,
                    "method": (
                        "probe2 cross-check: deliberate only when merged_at set "
                        "AND merge_commit_sha ancestor of main"
                    ),
                    "anchor": P2_RAW,
                },
                {
                    "name": "never_merged_differing_paths",
                    "measured": never_merged_diff_paths,
                    "method": "probe1 diffs on PRs where probe2 agree_not_merged",
                    "anchor": P2_JSON,
                },
                {
                    "name": "merge_signal_disagree_count",
                    "measured": disagree,
                    "method": "merged_at XOR merge_commit reachability",
                    "anchor": P2_JSON,
                },
                {
                    "name": "negative_control_ok",
                    "measured": nc_ok,
                    "method": (
                        f"PR #{nc.get('control_pr')}: 0 missing then local "
                        "delete → exactly 1"
                    ),
                    "anchor": NC_JSON,
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "sample_count": sample_count,
                "prs_with_findings": prs_with_findings,
                "total_missing_or_differing_paths": total_diff_paths,
                "ok": p1_ok,
                "main_sha": p1.get("main_sha"),
                "selection": selection,
            },
            "probe2_summary": {
                **p2["summary"],
                "ok": p2_ok,
                "never_merged_differing_prs": never_merged_diff_prs,
                "never_merged_differing_paths": never_merged_diff_paths,
            },
            "negative_control": {
                "control_pr": nc.get("control_pr"),
                "baseline_missing_count": nc.get("baseline_missing_count"),
                "after_delete_missing_count": nc.get("after_delete_missing_count"),
                "victim_path": nc.get("victim_path"),
                "ok": nc_ok,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        L.REPO / P1_JSON,
        L.REPO / P2_JSON,
        L.REPO / NC_JSON,
        L.REPO / P1_RAW,
        L.REPO / P2_RAW,
        L.REPO / NC_RAW,
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0003 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
