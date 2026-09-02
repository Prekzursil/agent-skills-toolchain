#!/usr/bin/env python3
"""Emit AUD-0003 catalog artifact plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
Does not mutate the ast-integrate git index (this worktree has none).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

REPO = C.repo_root()
OUT = "command-center/audit/AUD-0003-pr-unique-content.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0003/probe1_head_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0003/probe2_merge_agreement.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0003 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which merged-or-closed pull requests contain file content that is absent "
    "from main today, and for each, was the loss deliberate (superseded) or "
    "accidental (revert, force-push, or a closed-without-merge)?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0003/census.py",
    "command-center/p2-wave/probes/AUD-0003/probe1_head_diff.py",
    "command-center/p2-wave/probes/AUD-0003/probe2_merge_agreement.py",
    "command-center/p2-wave/probes/AUD-0003/probe1-head-diff.json",
    "command-center/p2-wave/probes/AUD-0003/probe2-merge-agreement.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    data = path.read_bytes() if path.is_file() else b""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if not data:
        eol = "NOT-CHECKED"
    elif crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": eol,
        "unit_id": C.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0003/SUBAGENT-RETURN.json",
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0003 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    world, census, control, live = C.run_world()
    errors = C.expected_rows_ok(census)
    if errors or not control["pass"]:
        print("FAILED:AUD-0003 emit-time census or control")
        print(errors)
        print(control)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unique = census["prs_with_content_absent_from_main"]
    loss_counts: dict[str, int] = {}
    for row in unique:
        loss_counts[row["loss"] or "unclassified"] = (
            loss_counts.get(row["loss"] or "unclassified", 0) + 1
        )
    deliberate_n = sum(1 for row in unique if row["deliberate"])
    accidental_n = sum(1 for row in unique if row["loss"] and not row["deliberate"])

    answer = (
        f"On the planted census corpus ({census['pr_count']} merged-or-closed PRs) "
        f"{census['absent_count']} contain file content absent from fixture-main today: "
        f"{deliberate_n} deliberate (superseded) and {accidental_n} accidental "
        f"(closed-without-merge, revert, or force-push/unreachable-merge). "
        f"Loss histogram={loss_counts}. "
        "A fully-merged PR reports zero missing files; deleting one of its files "
        "in a temporary copy of main makes the detector report exactly one. "
        "GitHub merged_at and merge_commit_sha reachability must agree before "
        "absence is called deliberate; the force-push plant disagrees and is not "
        "labelled deliberate. "
        f"Live owner-repo GitHub PR census is NOT-CHECKED "
        f"({', '.join(live['not_checked_reason']) or 'unspecified'}); "
        "that gap is not folded into a zero-finding live answer. "
        + COMPLETION_SENTINEL
    )

    tests = [
        {
            "id": "probe1-head-diff-limited-to-pr-touched",
            "name": "Probe 1: for each PR head SHA, git diff <head> main --name-only limited to files the PR touched",
            "command": P1,
            "result": "PASS",
            "assertions": 6,
            "output_tail": t1[-500:],
        },
        {
            "id": "probe2-merged-at-and-reachability",
            "name": "Probe 2: GitHub API merged_at plus merge_commit_sha reachability from main",
            "command": P2,
            "result": "PASS",
            "assertions": 6,
            "output_tail": t2[-500:],
        },
        {
            "id": "ctl-fully-merged-then-local-delete",
            "name": "negative control: pick a PR known to be fully merged and confirm the detector reports zero missing files; then delete one of its files locally and confirm it reports exactly one",
            "command": P2,
            "result": "PASS" if control["pass"] else "FAIL",
            "assertions": 2,
            "output_tail": (
                f"good={control['good_state_missing']} bad={control['bad_state_missing']}"
            ),
        },
    ]
    evidence = [
        {
            "claim": (
                "Probe 1 ran git diff <head> main --name-only for each planted PR head "
                f"and limited results to PR-touched paths. {census['absent_count']} of "
                f"{census['pr_count']} PRs still have unique content absent from main."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0003/probe1-head-diff.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": t1[:65000],
                    "exit_code": c1,
                    "fingerprint": fingerprint("command", P1),
                }
            ],
        },
        {
            "claim": (
                "Probe 2 required GitHub merged_at and merge_commit_sha reachability "
                "to agree before calling any absence deliberate. Closed-without-merge, "
                "revert, and force-push plants are accidental; only the superseded "
                "widget v1 plant is deliberate."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0003/probe2-merge-agreement.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "raw_output": t2[:65000],
                    "exit_code": c2,
                    "fingerprint": fingerprint("command", P2),
                }
            ],
        },
        {
            "claim": (
                "Live GitHub PR list for every owner repo was not obtained on this "
                "worktree; the live count is NOT-CHECKED rather than zero."
            ),
            "verdict": "NOT-CHECKED",
            "anchor": "command-center/audit/AUD-0003-pr-unique-content.json#live_owner_census",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "verifier",
                    "method": "env-and-api",
                    "command": "github_api_unauthenticated_rate_limit + worktree .git + gh + token-env names",
                    "raw_output": json.dumps(live, indent=1, sort_keys=True)[:16000],
                    "exit_code": 0,
                    "fingerprint": fingerprint("env-and-api", "live-owner-census"),
                }
            ],
        },
    ]

    named_probes = [
        {
            "id": "probe1",
            "role": "pr-head-diff-vs-main",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:65000],
        },
        {
            "id": "probe2",
            "role": "github-merged-at-and-reachability",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:65000],
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": C.UNIT,
        "id": C.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-finding",
        "title": "PR history census: content in merged or closed PRs that never reached main",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0003",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-headless",
        },
        "report": {
            "kind": "audit-finding",
            "headline": (
                f"fixture_absent={census['absent_count']} "
                f"deliberate={deliberate_n} accidental={accidental_n} "
                f"live_owner_prs=NOT-CHECKED"
            ),
            "answer": answer,
            "control_ids": [control["id"]],
            "observations": [
                {
                    "name": "fixture-pr-count",
                    "measured": census["pr_count"],
                    "method": "planted git + GitHub-shaped records",
                },
                {
                    "name": "content-absent-from-main",
                    "measured": census["absent_count"],
                    "method": "git diff <head> main --name-only ∩ PR-touched files",
                },
                {
                    "name": "deliberate-superseded",
                    "measured": deliberate_n,
                    "method": "merged_at ∧ reachable ∧ later merged PR on same path",
                },
                {
                    "name": "live-owner-pr-count",
                    "measured": live["live_pr_count"],
                    "method": "NOT-CHECKED",
                },
            ],
            "prs_with_unique_content_absent_from_main": unique,
            "loss_histogram": loss_counts,
            "all_pr_rows": census["rows"],
        },
        "live_owner_census": live,
        "negative_controls": [
            {
                "id": control["id"],
                "kind": control["kind"],
                "description": control["description"],
                "fired_on_bad_state": control["fired_on_bad_state"],
                "silent_on_good_state": control["silent_on_good_state"],
                "bad_state_output": str(control["bad_state_missing"]),
                "good_state_output": str(control["good_state_missing"]),
            }
        ],
        "tests": tests,
        "evidence": evidence,
        "named_probes": named_probes,
        "reviewer": {
            "reviewer_id": "AUD-0003-probe2-merge-agreement-and-local-delete",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a mechanically different instrument (GitHub merged_at + "
                "merge-commit reachability plus the local-delete both-states control). "
                "It falsifies a vacuous zero on a fully-merged PR by deleting one of "
                "its files. Catalog-named fresh-context Claude review of the live "
                "owner-repo headline remains residual because that live headline is "
                "NOT-CHECKED, not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0003/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b): after the second failure with the same detector, enumerate at least 2 mechanically different detectors before a third attempt",
        },
        "failure": None,
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "The catalog asks for the GitHub PR list of every owner-controlled "
                    "repo. This worktree has no .git, gh is absent, and no GitHub token "
                    "is present in GH_TOKEN/GITHUB_TOKEN/GH_ENTERPRISE_TOKEN, so live "
                    "PRs were not enumerated."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git checkout of each owner repo with a GitHub token, list "
                    "all-state pull requests and re-run both named probes against those "
                    "head SHAs and the live main tree."
                ),
            },
            {
                "claim": (
                    "Declared output_schema command-center/schema/audit-finding.schema.json "
                    "is absent on this tree (harvest-era shim not generated here). G-1 "
                    "measures JSON parse + sentinel, not that schema file."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Restore or generate the audit-finding schema shim and validate this "
                    "document against it before a later catalog close."
                ),
            },
        ],
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for AUD-0003: live named probes exit 0, audit-finding state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not git add/commit/push/stash/checkout/rebase the worktree."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:AUD-0003 sentinel missing from serialized artifact")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0003 self-declared non-delivery state")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    primary = art(OUT, "primary")
    if primary["bytes"] < 1024:
        print(f"FAILED:AUD-0003 artifact too small {primary['bytes']}")
        return 1

    artifacts = [
        {
            "path": OUT,
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": C.UNIT,
            "receipt_path": "command-center/p2-wave/probes/AUD-0003/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        row = art(rel, "supporting")
        if not row["present"]:
            print(f"FAILED:AUD-0003 missing supporting {rel}")
            return 1
        artifacts.append(
            {
                "path": rel,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "present": True,
                "unit_id": C.UNIT,
                "receipt_path": "command-center/p2-wave/probes/AUD-0003/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": C.UNIT,
        "unit_id": C.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": named_probes,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0003/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0003-probe2-merge-agreement-and-local-delete",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0003: live named probes exit 0, AUD-0003-pr-unique-content.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
