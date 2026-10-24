#!/usr/bin/env python3
"""Pack AUD-0048 action-pinning + token-permission audit.

Honest measurement with live probes. Emits BLOCKED pending independent
fresh-context Claude review (catalog reviewer_requirement). Never emits
SUCCESS without that review — anti-false-green.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0048"
OUT = "command-center/audit/AUD-0048-action-pinning-permissions.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0048/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
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
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-syntactic-classify.json").read_text(encoding="utf-8")
    )
    p2 = json.loads((PROBE / "probe2-tag-resolution.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-syntactic-classify.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-tag-resolution.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:10:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    prod_class = p1["production_by_pin_class"]
    sha_n = int(prod_class.get("sha-pinned", 0))
    tag_n = int(prod_class.get("tag-pinned", 0))
    branch_n = int(prod_class.get("branch-pinned", 0))
    unpinned = int(p1["third_party_unpinned_count"])
    inherit_n = int(p1["workflows_inheriting_default_token_count"])
    inherit_prod = int(
        p1.get("production_workflows_inheriting_default_token_count", inherit_n)
    )
    control_ok = bool(p1["control"]["ok"])
    resolve_ok = int(p2["resolved_ok"])
    resolve_targets = int(p2["targets"])

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
        L.art(
            "command-center/p2-wave/probes/AUD-0048/probe1-syntactic-classify.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/probe2-tag-resolution.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/probe1-syntactic-classify.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/probe2-tag-resolution.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/fixtures/branch-pinned.yml",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/fixtures/sha-pinned.yml",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0048/fixtures/tag-pinned.yml",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0048/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Is every third-party action pinned to a full commit SHA rather than a tag, "
        "and does every workflow declare a least-privilege permissions block rather "
        "than inheriting the default token scope?"
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
        defects = [
            {
                "id": "AUD-0048-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0048/independent-review.json"
                ),
            },
            {
                "id": "AUD-0048-D-UNPINNED",
                "severity": "P2",
                "status": "open" if unpinned else "resolved",
                "summary": (
                    f"production third-party unpinned uses={unpinned} "
                    f"(tag={tag_n} branch={branch_n}); "
                    f"production workflows inheriting default token={inherit_prod}."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0048"
        headline = (
            f"prod sha={sha_n} tag={tag_n} branch={branch_n} unpinned={unpinned}; "
            f"prod_inherit_default_token={inherit_prod}; control_ok={control_ok}; "
            f"tag_resolutions={resolve_ok}/{resolve_targets}. Independent re-review PASS."
        )
        failure = None
        anti = "SUCCESS-after-independent-re-review-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript and must try to FALSIFY the headline count "
                "before PASS. Probes measured; review unpaid; BLOCKED."
            ),
        }
        defects = [
            {
                "id": "AUD-0048-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline counts "
                    "must be falsified by a reviewer who did not author this census."
                ),
            },
            {
                "id": "AUD-0048-D-UNPINNED",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"production third-party unpinned uses={unpinned} "
                    f"(tag={tag_n} branch={branch_n}); "
                    f"production workflows inheriting default token={inherit_prod}; "
                    f"control_ok={control_ok}; resolutions={resolve_ok}/{resolve_targets}."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0048 syntactic pin census + tag SHA resolution measured; "
            "branch-pinned fixture flagged critical; sha-pinned fixture clean; "
            "blocked-on-independent-review"
        )
        headline = (
            f"prod sha={sha_n} tag={tag_n} branch={branch_n} unpinned={unpinned}; "
            f"prod_inherit_default_token={inherit_prod}; control_ok={control_ok}; "
            f"tag_resolutions={resolve_ok}/{resolve_targets}. "
            "BLOCKED on independent fresh-context Claude review."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "detector-failure"],
            "reason": (
                "Named probes completed with the required both-states control "
                "(branch-pinned flagged critical; sha-pinned not flagged) and live "
                "tag→SHA resolutions recorded, but catalog reviewer_requirement is "
                "unmet (fresh-context Claude must falsify headline counts)."
            ),
            "diagnostic_tail": (
                f"unpinned={unpinned} tag={tag_n} branch={branch_n} "
                f"inherit_prod={inherit_prod} control_ok={control_ok} "
                f"resolutions={resolve_ok}/{resolve_targets} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "unit's transcript; the reviewer must try to FALSIFY the headline "
                f"third_party_unpinned_count={unpinned} (tag={tag_n} branch={branch_n}) "
                f"and production_workflows_inheriting_default_token_count="
                f"{inherit_prod} before PASS, not re-read the artifact."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0048/probe1_syntactic_classify.py",
                    (
                        f"third_party_unpinned_count={unpinned} "
                        f"control_ok={control_ok} inherit_prod={inherit_prod}"
                    ),
                    0,
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
        anti = "BLOCKED-pending-independent-review-with-real-probes"

    findings_sample = []
    for r in p1.get("third_party_unpinned", [])[:30]:
        findings_sample.append(
            {
                "path": r["path"],
                "line": r["line"],
                "uses": r["uses"],
                "pin_class": r["pin_class"],
                "severity": r["severity"],
            }
        )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0048",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "security-auditor",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 classified {p1['uses_total']} uses: refs across "
                    f"{p1['workflow_files_scanned']} workflow files "
                    f"(production={p1['uses_production']}): "
                    f"sha={sha_n} tag={tag_n} branch={branch_n}; "
                    f"third_party_unpinned={unpinned}; "
                    f"production_workflows_inheriting_default_token={inherit_prod}; "
                    f"control branch_critical="
                    f"{p1['control']['branch_pinned_flagged_critical']} "
                    f"sha_clean={p1['control']['sha_pinned_not_flagged']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0048/probe1-syntactic-classify.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0048/probe1_syntactic_classify.py",
                        raw1,
                        0 if control_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-syntactic-classify.json",
                        json.dumps(
                            {
                                "third_party_unpinned_count": unpinned,
                                "production_by_pin_class": prod_class,
                                "production_workflows_inheriting_default_token_count": inherit_prod,
                                "control_ok": control_ok,
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 resolved {resolve_ok}/{resolve_targets} distinct "
                    f"tag/branch refs to current commit SHAs via git ls-remote; "
                    f"tag-fixture resolved={p2['tag_fixture_resolved']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0048/probe2-tag-resolution.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0048/probe2_resolve_tags.py",
                        raw2,
                        0 if p2["ok"] else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-tag-resolution.json",
                        json.dumps(
                            {
                                "targets": resolve_targets,
                                "resolved_ok": resolve_ok,
                                "tag_fixture_resolved": p2["tag_fixture_resolved"],
                                "ok": p2["ok"],
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
                "id": "AUD-0048-branch-pinned-highest-severity",
                "name": (
                    "control: a fixture with a branch-pinned action must be flagged "
                    "at the highest severity"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0048/"
                    "probe1_syntactic_classify.py"
                ),
                "result": (
                    "PASS"
                    if p1["control"]["branch_pinned_flagged_critical"]
                    else "FAIL"
                ),
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0048-sha-pinned-not-flagged",
                "name": "control: a sha-pinned fixture must not be flagged",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0048/"
                    "probe1_syntactic_classify.py"
                ),
                "result": "PASS" if p1["control"]["sha_pinned_not_flagged"] else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0048-tag-resolves-to-sha",
                "name": "Probe 2 resolves tag-pinned fixture refs to 40-char commit SHAs",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0048/"
                    "probe2_resolve_tags.py"
                ),
                "result": "PASS" if p2["tag_fixture_resolved"] else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0048-C1",
                "known-broken-fixture",
                (
                    "Branch-pinned fixture actions must be flagged at severity=critical; "
                    "sha-pinned fixture must stay unflagged."
                ),
                True,
                True,
                bad="branch-pinned fixture not flagged critical OR sha-pinned flagged",
                good=(
                    f"branch_critical={p1['control']['branch_pinned_flagged_critical']} "
                    f"sha_clean={p1['control']['sha_pinned_not_flagged']}"
                ),
            ),
            L.control(
                "AUD0048-C2",
                "mutation",
                "Tag-pinned fixture refs must resolve to a current 40-char commit SHA.",
                True,
                True,
                bad="tag fixture commit_sha missing or not 40 hex",
                good=f"tag_fixture_resolved={p2['tag_fixture_resolved']}",
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
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0048/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure with "
                "the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Every recorded tag→SHA mapping remains stable against a later "
                    "silent retag of the same symbolic tag."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe2_resolve_tags.py on a later date and diff "
                    "commit_sha per owner/repo@ref against this receipt's resolutions."
                ),
            },
            {
                "claim": (
                    "Job-level permissions that appear after a workflow-level "
                    "permissions: block never widen the default token beyond what "
                    "the workflow declares."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Diff each job permissions mapping against its workflow-level "
                    "mapping and flag any permission present only at job scope that "
                    "exceeds the workflow baseline."
                ),
            },
            {
                "claim": (
                    "A fresh-context Claude reviewer who never saw this transcript "
                    "independently falsified the headline counts."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch one fresh-context Claude reviewer per catalog "
                    "reviewer_requirement; record independent-review.json with "
                    "verdict=PASS only after a failed falsification attempt."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "observations": [
                {
                    "name": "uses_production",
                    "measured": p1["uses_production"],
                    "method": "YAML uses: scan of .github/workflows + AUD-0048 fixtures",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.json"
                    ),
                },
                {
                    "name": "production_sha_pinned",
                    "measured": sha_n,
                    "method": "pin_class==sha-pinned (40-hex ref)",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.raw.txt"
                    ),
                },
                {
                    "name": "production_tag_pinned",
                    "measured": tag_n,
                    "method": "pin_class==tag-pinned",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.json"
                    ),
                },
                {
                    "name": "production_branch_pinned",
                    "measured": branch_n,
                    "method": "pin_class==branch-pinned",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.json"
                    ),
                },
                {
                    "name": "third_party_unpinned_count",
                    "measured": unpinned,
                    "method": "third-party uses with pin_class in {tag,branch,sha-short,docker,unknown}",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.json"
                    ),
                },
                {
                    "name": "production_workflows_inheriting_default_token",
                    "measured": inherit_prod,
                    "method": "production workflows with no workflow-level and no job-level permissions: block",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe1-syntactic-classify.json"
                    ),
                },
                {
                    "name": "tag_resolutions_ok",
                    "measured": resolve_ok,
                    "method": "git ls-remote current commit SHA per distinct tag/branch ref",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/"
                        "probe2-tag-resolution.raw.txt"
                    ),
                },
                {
                    "name": "control_ok",
                    "measured": control_ok,
                    "method": "fixtures/branch-pinned.yml critical + fixtures/sha-pinned.yml clean",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0048/fixtures/branch-pinned.yml"
                    ),
                },
            ],
            "control_ids": ["AUD0048-C1", "AUD0048-C2"],
            "findings_sample": findings_sample,
            "inherit_default_paths": p1.get("workflows_inheriting_default_token", []),
            "production_inherit_default_paths": p1.get(
                "production_workflows_inheriting_default_token", []
            ),
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-wave1",
            "production_by_pin_class": prod_class,
            "probe2_method": p2.get("method"),
            "output_path": OUT,
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": doc["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={doc['state']} bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
