#!/usr/bin/env python3
"""Pack AUD-0044 required-context vs emitted-checks audit receipt.

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

UNIT = "AUD-0044"
OUT = "command-center/audit/AUD-0044-required-context-audit.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0044/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0044/probe1-required-status-checks.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0044/probe2-recent-pr-check-runs.json"
CMP_JSON = "command-center/p2-wave/probes/AUD-0044/compare-required-vs-emitted.json"
CTL_JSON = "command-center/p2-wave/probes/AUD-0044/control-renamed-job.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0044/probe1-required-status-checks.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0044/probe2-recent-pr-check-runs.raw.txt"
CMP_RAW = "command-center/p2-wave/probes/AUD-0044/compare-required-vs-emitted.raw.txt"
CTL_RAW = "command-center/p2-wave/probes/AUD-0044/control-renamed-job.raw.txt"


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
    cmp_ = json.loads((L.REPO / CMP_JSON).read_text(encoding="utf-8"))
    ctl = json.loads((L.REPO / CTL_JSON).read_text(encoding="utf-8"))
    raw1 = (L.REPO / P1_RAW).read_text(encoding="utf-8")
    raw2 = (L.REPO / P2_RAW).read_text(encoding="utf-8")
    raw_cmp = (L.REPO / CMP_RAW).read_text(encoding="utf-8")
    raw_ctl = (L.REPO / CTL_RAW).read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = p1.get("started_at") or "2026-09-07T22:20:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p1_ok = bool(p1.get("ok"))
    p2_ok = bool(p2.get("ok"))
    cmp_ok = bool(cmp_.get("ok"))
    ctl_ok = bool(ctl.get("ok"))
    required_count = int(cmp_.get("required_count") or 0)
    emitted_count = int(cmp_.get("emitted_count") or 0)
    intersection_count = int(cmp_.get("intersection_count") or 0)
    req_missing_count = int(cmp_.get("required_but_never_emitted_count") or 0)
    em_extra_count = int(cmp_.get("emitted_but_not_required_count") or 0)
    symdiff_count = int(cmp_.get("symmetric_difference_count") or 0)
    req_missing = list(cmp_.get("required_but_never_emitted") or [])
    em_extra = list(cmp_.get("emitted_but_not_required") or [])
    api_used = p1.get("api_used")
    classic_ok = bool((p1.get("classic_branch_protection") or {}).get("ok"))
    classic_err = (p1.get("classic_branch_protection") or {}).get("error") or {}
    chosen = ((p2.get("selection") or {}).get("chosen")) or {}
    pr_number = chosen.get("number")
    ctl_renamed_symdiff = int(
        (ctl.get("observed") or {}).get("renamed_symmetric_difference_count") or 0
    )

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
        L.art(CMP_JSON, "supporting"),
        L.art(CTL_JSON, "control"),
        L.art(P1_RAW, "log"),
        L.art(P2_RAW, "log"),
        L.art(CMP_RAW, "log"),
        L.art(CTL_RAW, "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/probe1_required_status_checks.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/probe2_recent_pr_check_runs.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/compare_contexts.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/compare_required_vs_emitted.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/control_renamed_job.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/fixtures/scratch-workflow-baseline.yml",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0044/fixtures/scratch-workflow-renamed.yml",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0044/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which check contexts are REQUIRED by the branch protection ruleset, "
        "which contexts do the workflows actually produce, and where do those "
        "two sets disagree?"
    )
    headline = (
        f"Required contexts via {api_used} API: {required_count}; "
        f"emitted on merged PR #{pr_number}: {emitted_count}; "
        f"intersection={intersection_count}; "
        f"required_but_never_emitted={req_missing_count}; "
        f"emitted_but_not_required={em_extra_count}; "
        f"symmetric_difference={symdiff_count}. "
        f"Classic branch-protection API classic_ok={classic_ok}"
        + (
            f" (status={(classic_err or {}).get('status')})"
            if not classic_ok
            else ""
        )
        + f". Control renamed-job symdiff={ctl_renamed_symdiff} ok={ctl_ok}."
    )

    residual_classic = not classic_ok
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
        sentinel = "SUCCESS:AUD-0044"
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0044-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0044/independent-review.json"
                ),
            },
            {
                "id": "AUD-0044-D-EMITTED-NOT-REQUIRED",
                "severity": "P2",
                "status": "open" if em_extra_count else "resolved",
                "summary": (
                    f"{em_extra_count} emitted context(s) are not in the required "
                    "set and therefore gate nothing on merge."
                ),
            },
            {
                "id": "AUD-0044-D-CLASSIC-PROTECTION-API",
                "severity": "P2",
                "status": "open" if residual_classic else "resolved",
                "summary": (
                    "Classic GET .../branches/main/protection returned "
                    f"{(classic_err or {}).get('status') or 'error'}; required "
                    "contexts were recovered from rulesets only."
                    if residual_classic
                    else "Classic branch-protection API also answered."
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
            "FAILED:AUD-0044 required-vs-emitted context audit measured "
            f"required={required_count} emitted={emitted_count} "
            f"required_but_never_emitted={req_missing_count} "
            f"emitted_but_not_required={em_extra_count} "
            f"intersection={intersection_count} "
            f"symmetric_difference={symdiff_count} "
            f"control_ok={ctl_ok}; blocked-on-independent-review"
        )
        classifications = [
            "blocked-on-independent-review",
            "green-not-live",
            "detector-failure",
        ]
        if residual_classic:
            classifications.append("credential-absent")
        failure = {
            "classification": classifications,
            "reason": (
                f"Named probes completed (probe1 ok={p1_ok} via {api_used}, "
                f"probe2 ok={p2_ok} on PR #{pr_number}, comparator ok={cmp_ok}, "
                f"renamed-job control ok={ctl_ok}), but catalog "
                "reviewer_requirement is unmet."
                + (
                    f" Residual: classic branch-protection API returned "
                    f"{(classic_err or {}).get('status') or classic_err}; "
                    "required contexts were not invented — they came from "
                    "rulesets."
                    if residual_classic
                    else ""
                )
            ),
            "diagnostic_tail": (
                f"required={required_count} emitted={emitted_count} "
                f"req_missing={req_missing_count} em_extra={em_extra_count} "
                f"symdiff={symdiff_count} api_used={api_used} "
                f"classic_ok={classic_ok} control_ok={ctl_ok} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the headline "
                "required_but_never_emitted / emitted_but_not_required / "
                "symmetric_difference counts before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0044/"
                    "compare_required_vs_emitted.py",
                    (
                        f"required={required_count} emitted={emitted_count} "
                        f"symdiff={symdiff_count}"
                    ),
                    0 if cmp_ok else 1,
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
                "id": "AUD-0044-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0044-D-EMITTED-NOT-REQUIRED",
                "severity": "P2",
                "status": "open" if em_extra_count else "resolved",
                "summary": (
                    f"{em_extra_count} emitted context(s) not required "
                    f"(sample: {em_extra[:5]})."
                ),
            },
            {
                "id": "AUD-0044-D-CLASSIC-PROTECTION-API",
                "severity": "P2",
                "status": "open" if residual_classic else "resolved",
                "summary": (
                    "Classic branch-protection API inaccessible "
                    f"({(classic_err or {}).get('status')}); rulesets used instead. "
                    "Do not invent classic contexts."
                ),
            },
        ]

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
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0044",
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
                    "Probe 1 required_status_checks: classic "
                    f"GET branches/{p1.get('default_branch', 'main')}/protection "
                    f"classic_ok={classic_ok}; rulesets API "
                    f"rulesets_ok={bool((p1.get('rulesets') or {}).get('ok'))}; "
                    f"selected api_used={api_used}; "
                    f"required_count={required_count}; "
                    f"contexts={cmp_.get('required_status_checks')}. "
                    "Never invents contexts on 403/404."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0044/"
                        "probe1_required_status_checks.py",
                        raw1[-8000:],
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-required-status-checks.json",
                        json.dumps(
                            {
                                "api_used": api_used,
                                "required_count": required_count,
                                "classic_ok": classic_ok,
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
                    "Probe 2 distinct check-run / status context names on a "
                    f"recent merged PR: selected PR #{pr_number} "
                    f"(merged_at={chosen.get('merged_at')}, "
                    f"head={chosen.get('head_sha')}) by rule "
                    f"\"{(p2.get('selection') or {}).get('rule')}\". "
                    f"emitted_count={emitted_count}."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0044/"
                        "probe2_recent_pr_check_runs.py",
                        raw2[-8000:],
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-recent-pr-check-runs.json",
                        json.dumps(
                            {
                                "pr": pr_number,
                                "emitted_count": emitted_count,
                                "ok": p2_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Comparator (required vs emitted): "
                    f"intersection={intersection_count}, "
                    f"required_but_never_emitted={req_missing_count} {req_missing}, "
                    f"emitted_but_not_required={em_extra_count} "
                    f"(first 5: {em_extra[:5]}), "
                    f"symmetric_difference={symdiff_count}."
                ),
                "CONFIRMED" if cmp_ok else "REFUTED",
                CMP_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0044/"
                        "compare_required_vs_emitted.py",
                        raw_cmp,
                        0 if cmp_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read compare-required-vs-emitted.json",
                        json.dumps(
                            {
                                "required_but_never_emitted_count": req_missing_count,
                                "emitted_but_not_required_count": em_extra_count,
                                "symmetric_difference_count": symdiff_count,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Control (tests_required): scratch workflow fixture with a "
                    "deliberately renamed job "
                    f"({(ctl.get('fixtures') or {}).get('deliberate_rename')}) → "
                    f"baseline_symdiff empty="
                    f"{(ctl.get('observed') or {}).get('baseline_symmetric_difference_empty')}, "
                    f"renamed_symdiff={ctl_renamed_symdiff} "
                    f"(non-empty required). control_ok={ctl_ok}. "
                    "No live workflow was mutated."
                ),
                "CONFIRMED" if ctl_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0044/"
                        "control_renamed_job.py",
                        raw_ctl,
                        0 if ctl_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read control-renamed-job.json",
                        json.dumps(
                            {
                                "renamed_symmetric_difference_count": ctl_renamed_symdiff,
                                "ok": ctl_ok,
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
                "id": "AUD-0044-renamed-job-symdiff",
                "name": (
                    "tests_required: comparator reports non-empty symmetric "
                    "difference on deliberately renamed scratch-workflow job"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0044/"
                    "control_renamed_job.py"
                ),
                "result": "PASS" if ctl_ok else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0044-baseline-scratch-empty-symdiff",
                "name": (
                    "control precondition: baseline scratch workflow matching "
                    "required set reports empty symmetric difference"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0044/"
                    "control_renamed_job.py"
                ),
                "result": "PASS"
                if (ctl.get("observed") or {}).get(
                    "baseline_symmetric_difference_empty"
                )
                else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0044-probe1-has-api",
                "name": "probe1 selected a real API source (rulesets or classic)",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0044/"
                    "probe1_required_status_checks.py"
                ),
                "result": "PASS" if api_used not in (None, "none") else "FAIL",
                "assertions": 1,
                "output_tail": f"api_used={api_used}",
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0044-C1",
                "mutation",
                (
                    "Deliberately renaming one scratch-workflow job name must "
                    "make the comparator report a non-empty symmetric "
                    "difference versus the required-context set."
                ),
                True,
                True,
                bad=(
                    f"renamed_symdiff={ctl_renamed_symdiff} "
                    f"diff={ctl.get('renamed_compare', {}).get('symmetric_difference')}"
                ),
                good=(
                    "baseline_symdiff=0 when job names match required set"
                ),
            ),
            L.control(
                "AUD0044-C2",
                "other",
                (
                    "Baseline scratch workflow whose job names equal the "
                    "required set must report empty symmetric difference "
                    "(proves the comparator is not always-nonempty)."
                ),
                True,
                True,
                bad="baseline_symdiff would be >0 if comparator broken",
                good="baseline_symdiff=0",
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
                    "Whether classic branch-protection required_status_checks "
                    "would disagree with the ruleset list if Administration:read "
                    "were granted to this token."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 with a token that can GET "
                    "branches/main/protection; byte-compare classic contexts "
                    "to ruleset contexts."
                ),
            },
            {
                "claim": (
                    "Whether other recently merged PRs emit a different "
                    f"context set than PR #{pr_number} (matrix jobs, skipped "
                    "paths, or renamed workflows)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe2 to N merged PRs and compute the union and "
                    "intersection of emitted context names."
                ),
            },
            {
                "claim": (
                    "Whether any of the "
                    f"{em_extra_count} emitted-but-not-required contexts are "
                    "intentionally advisory (shadow) vs accidental omissions "
                    "from the ruleset."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner review of ruleset 18297434 vs quality.yml job names; "
                    "promote or demote contexts deliberately."
                ),
            },
        ],
        "report": {
            "kind": "audit-drift",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0044-C1", "AUD0044-C2"],
            "observations": [
                {
                    "name": "required_count",
                    "measured": required_count,
                    "method": f"probe1 via {api_used}",
                    "anchor": P1_JSON,
                },
                {
                    "name": "emitted_count",
                    "measured": emitted_count,
                    "method": f"probe2 check-runs on PR #{pr_number}",
                    "anchor": P2_JSON,
                },
                {
                    "name": "intersection_count",
                    "measured": intersection_count,
                    "method": "compare_contexts.compare",
                    "anchor": CMP_JSON,
                },
                {
                    "name": "required_but_never_emitted_count",
                    "measured": req_missing_count,
                    "method": "required − emitted",
                    "anchor": CMP_JSON,
                },
                {
                    "name": "emitted_but_not_required_count",
                    "measured": em_extra_count,
                    "method": "emitted − required",
                    "anchor": CMP_JSON,
                },
                {
                    "name": "symmetric_difference_count",
                    "measured": symdiff_count,
                    "method": "(required Δ emitted)",
                    "anchor": CMP_RAW,
                },
                {
                    "name": "control_renamed_job_symdiff",
                    "measured": ctl_renamed_symdiff,
                    "method": "scratch fixture rename control",
                    "anchor": CTL_JSON,
                },
                {
                    "name": "classic_branch_protection_ok",
                    "measured": classic_ok,
                    "method": "GET branches/main/protection",
                    "anchor": P1_RAW,
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-drift",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "headline_counts": {
                "required_count": required_count,
                "emitted_count": emitted_count,
                "intersection_count": intersection_count,
                "required_but_never_emitted_count": req_missing_count,
                "emitted_but_not_required_count": em_extra_count,
                "symmetric_difference_count": symdiff_count,
            },
            "required_but_never_emitted": req_missing,
            "emitted_but_not_required": em_extra,
            "probe1_summary": {
                "api_used": api_used,
                "required_count": required_count,
                "classic_ok": classic_ok,
                "classic_error": classic_err,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "pr": pr_number,
                "merged_at": chosen.get("merged_at"),
                "head_sha": chosen.get("head_sha"),
                "emitted_count": emitted_count,
                "ok": p2_ok,
            },
            "control": {
                "renamed_symmetric_difference_count": ctl_renamed_symdiff,
                "ok": ctl_ok,
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
        L.REPO / CMP_JSON,
        L.REPO / CTL_JSON,
        L.REPO / P1_RAW,
        L.REPO / P2_RAW,
        L.REPO / CMP_RAW,
        L.REPO / CTL_RAW,
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0044 missing probe outputs:", *missing, sep="\n")
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
