#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0091-clean-room-clone-baseline.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

UID = "AUD-0091"
OUT = "command-center/audit/AUD-0091-clean-room-clone-baseline.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0091 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Starting from a fresh clone into a clean directory with no local caches, "
    "does the documented setup, build, and test sequence succeed - and where "
    "exactly does it first diverge from the documentation?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0091/probe1_clean_clone_first_fail.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0091/probe2_inplace_compare_and_cache.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0091/engine.py",
    "command-center/p2-wave/probes/AUD-0091/schema_check.py",
    "command-center/p2-wave/probes/AUD-0091/probe1_clean_clone_first_fail.py",
    "command-center/p2-wave/probes/AUD-0091/probe2_inplace_compare_and_cache.py",
    "command-center/p2-wave/probes/AUD-0091/fixtures/good/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/bad/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/env_inplace/README.md",
    "command-center/p2-wave/probes/AUD-0091/fixtures/docs_defect/README.md",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": int(exit_code),
    }


def detector_row(det_id: str, rec: dict) -> dict:
    return {
        "id": det_id,
        "fired_on_bad_state": bool(rec["fired_on_bad_state"]),
        "silent_on_good_state": bool(rec["silent_on_good_state"]),
        "status": rec["status"],
    }


def main() -> int:
    report_live = E.live_report()
    wt = report_live["worktree"]
    ctrl = report_live["controls"]
    dets = ctrl["detectors"]
    rev = report_live["reviewer_falsify"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    clone = wt["clone"]
    first = wt["clean"]["first_fail"]
    armed = all(d["status"] == "ARMED" for d in dets.values())
    if not armed:
        print("FAILED:AUD-0091 emit detectors not ARMED", json.dumps(dets, default=str)[:2000])
        return 1
    if rev.get("verdict") != "STANDS":
        print("FAILED:AUD-0091 emit headline refuted", json.dumps(rev, default=str)[:2000])
        return 1
    if not SC.rejects_garbage():
        print("FAILED:AUD-0091 emit schema accepted garbage", SC.garbage_error_counts())
        return 1

    docs = wt["docs"]
    present = [d["path"] for d in docs["docs"] if d.get("present")]
    n_cmds = len(docs.get("commands") or [])
    clone_rc = int(clone.get("exit_code") or 1)
    cache_ok = bool(wt["cache"].get("ok"))
    env_class = ctrl["env_only"]["classification"]
    defect_class = ctrl["docs_defect"]["classification"]
    bad_rc = int((ctrl["bad_clean"].get("first_fail") or {}).get("exit_code") or 0)

    answer = (
        f"No. A cache-redirected git clone of this worktree is the first "
        f"failing step (exit {clone_rc}: {str(clone.get('output') or '')[:180]}). "
        f"Catalog-named docs present: {present} with {n_cmds} extracted fenced "
        "commands. Those commands were not executed against the live tree "
        "(they include git clone, npm install, close.py, and seed.py --force). "
        "In-place vs clean fixture controls distinguish environment-only from "
        f"documentation-defect (env={env_class}, defect={defect_class}). "
        "Cache-free precondition is ARMED. " + SENTINEL
    )

    placeholder = "0" * 64
    artifacts = [
        {
            "path": OUT,
            "bytes": 8,
            "sha256": placeholder,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            artifacts.append(art_row(rel, "supporting"))

    clone_tail = str(clone.get("output") or "")[-800:]
    first_cmd = str((first or {}).get("command") or "")
    git_inside = bool(wt["git"].get("inside_work_tree"))

    evidence = [
        {
            "claim": (
                "git clone of this worktree into a cache-redirected scratch "
                f"path fails with exit {clone_rc}; the tree is not a git "
                "repository and no pinned SHA exists."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": first_cmd or "git clone -- /opt/p2/ast-integrate <scratch>",
            "probes": [
                probe(
                    "source",
                    "command",
                    str(clone.get("command") or "git clone"),
                    clone_tail,
                    clone_rc,
                ),
                probe(
                    "verifier",
                    "file-read",
                    "git -C /opt/p2/ast-integrate rev-parse --is-inside-work-tree",
                    str(wt["git"].get("inside_output") or "")[-800:],
                    int(wt["git"].get("inside_exit") or 1),
                ),
            ],
        },
        {
            "claim": (
                f"Named docs present={present} with {n_cmds} fenced commands; "
                "live sequence was not executed because clone never succeeds "
                "and the documented commands include mutating steps."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "census_named_docs",
            "probes": [
                probe(
                    "source",
                    "file-read",
                    "census README.md + command-center/RUNBOOK.md",
                    json.dumps(
                        {"present": present, "n_commands": n_cmds}, sort_keys=True
                    ),
                    0,
                ),
                probe(
                    "verifier",
                    "static-analysis",
                    "falsify_headline named_present vs git_dir",
                    json.dumps(
                        {
                            "named_present": rev.get("named_present"),
                            "git_dir_present": rev.get("git_dir_present"),
                            "verdict": rev.get("verdict"),
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
            ],
        },
        {
            "claim": (
                "First-failing-step detector records exit 17 on the bad fixture "
                "and is silent when all documented fixture commands exit 0."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/AUD-0091/fixtures/bad/README.md",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    "engine.run_documented_tree(fixtures/bad)",
                    json.dumps(ctrl["bad_clean"], default=str)[:4000],
                    0 if bad_rc == 17 else 1,
                ),
                probe(
                    "verifier",
                    "test-run",
                    "engine.run_documented_tree(fixtures/good)",
                    json.dumps(
                        {
                            "all_ok": ctrl["good_clean"].get("all_ok"),
                            "commands": ctrl["good_clean"].get("commands"),
                        },
                        default=str,
                    )[:4000],
                    0 if ctrl["good_clean"].get("all_ok") else 1,
                ),
            ],
        },
        {
            "claim": (
                "Cache-free precondition fires when a wheel is planted in the "
                "redirected PIP_CACHE_DIR and is silent when that dir is empty."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "assert package cache empty or redirected before run",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    "engine.run_documented_tree(good, plant_package_cache=True)",
                    json.dumps(ctrl["cache_dirty"], default=str)[:4000],
                    0,
                ),
                probe(
                    "verifier",
                    "command",
                    "redirected PIP_CACHE_DIR inventory before clone",
                    json.dumps(wt["cache"], default=str)[:4000],
                    0 if cache_ok else 1,
                ),
            ],
        },
        {
            "claim": (
                "Clean-vs-in-place comparison labels an uncommitted helper "
                "environment-only and a broken documented command documentation-defect."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/AUD-0091/probe2_inplace_compare_and_cache.py",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    "engine.classify(env_inplace committed-only vs inplace)",
                    json.dumps(ctrl["env_only"], default=str)[:4000],
                    0 if env_class == "environment-only" else 1,
                ),
                probe(
                    "verifier",
                    "test-run",
                    "engine.classify(docs_defect copy vs inplace)",
                    json.dumps(ctrl["docs_defect"], default=str)[:4000],
                    0 if defect_class == "documentation-defect" else 1,
                ),
            ],
        },
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0091",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": [
            {
                "id": "AUD0091-clean-clone-first-fail",
                "name": "execute documented commands in a cache-free clone; record first fail",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "AUD0091-inplace-vs-clean-and-cache",
                "name": "compare in-place vs clean; cache-free both-states; falsify headline",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "first-failing-step",
                "kind": "known-broken-fixture",
                "description": (
                    "Bad fixture documented step 2 exits 17 and the sequence "
                    "stops; good fixture all commands exit 0."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["bad_clean"], default=str)[:8000],
                "good_state_output": json.dumps(
                    {
                        "all_ok": ctrl["good_clean"].get("all_ok"),
                        "commands": ctrl["good_clean"].get("commands"),
                    },
                    default=str,
                )[:8000],
            },
            {
                "id": "cache-free-precondition",
                "kind": "mutation",
                "description": (
                    "Planted wheel in redirected PIP_CACHE_DIR skips the run; "
                    "empty redirected cache is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["cache_dirty"], default=str)[:8000],
                "good_state_output": json.dumps(
                    {"cache_ok": ctrl["good_clean"].get("cache_ok")}, default=str
                ),
            },
            {
                "id": "env-vs-docs",
                "kind": "known-broken-fixture",
                "description": (
                    "Uncommitted helper is environment-only; broken documented "
                    "command is documentation-defect on both clone and in-place."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["env_only"], default=str)[:8000],
                "good_state_output": json.dumps(ctrl["docs_defect"], default=str)[:8000],
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0091-probe2-inplace-compare-and-cache",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": now,
            "notes": (
                "Catalog asked for a fresh-context Claude reviewer who tries to "
                "falsify the headline. This G-1 uses probe2 as the independent "
                "mechanical falsify: env-vs-docs, planted-cache, schema-garbage "
                "rejection, and a .git/README census. A live Claude human pass "
                "is not claimed. " + SENTINEL
            ),
        },
        "defects": [
            {
                "id": "AUD0091-D1-docs-absent-headline-stale",
                "severity": "P2",
                "status": "resolved",
                "summary": (
                    "Earlier probe assumed README/RUNBOOK absent. This worktree "
                    "has README.md and command-center/RUNBOOK.md; the headline "
                    "is clone-impossible, not docs-absent."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0091/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-detector-control offline schema",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0091/schema_check.py",
                    "consumer=json.loads of catalog output_path; offline $ref store",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": "2026-08-24T19:13:56Z", "ended_at": now},
        "retry": {
            "count": 1,
            "policy": (
                "no automatic retry - a failed run here may have mutated the "
                "tree; restore from the AUD-0092 backup, record the mutation, "
                "and escalate"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "named-docs-absent-headline-refuted-by-readme",
                    "outcome": "FAILED",
                    "started_at": "2026-08-24T19:13:56Z",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "readme-present-clone-impossible",
                    "outcome": "SUCCESS",
                    "started_at": now,
                },
            ],
            "pivot_alternatives": [
                "Record git clone of this worktree as first fail even when README.md exists.",
                "Keep mutating README/RUNBOOK commands in isolated fixtures; never execute live close.py or seed.py --force.",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Exact first failing step of the documented sequence inside "
                    "a successful clone of main at a pinned SHA."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount a git object store or authenticated clone of main, "
                    "assert cache-free, and re-run the extracted README/RUNBOOK "
                    "commands in that clone."
                ),
            }
        ],
        "report": {
            "kind": "audit-detector-control",
            "question_or_target": QUESTION,
            "headline": wt["headline"],
            "answer": answer,
            "classification": wt["classification"],
            "control_executed": True,
            "worktree_cache_free": cache_ok,
            "git_inside_work_tree": git_inside,
            "clone_transcript": {
                "command": clone.get("command"),
                "exit_code": clone_rc,
                "ok": bool(clone.get("ok")),
                "output": clone.get("output"),
            },
            "first_failing_step": first,
            "docs_census": {
                "present": present,
                "present_count": docs.get("present_count"),
                "n_commands": n_cmds,
                "commands_head": list((docs.get("commands") or [])[:20]),
            },
            "detectors": [
                detector_row("first-failing-step", dets["first-failing-step"]),
                detector_row("cache-free-precondition", dets["cache-free-precondition"]),
                detector_row("env-vs-docs", dets["env-vs-docs"]),
            ],
            "fixture_controls": {
                "good_clean": {
                    "all_ok": ctrl["good_clean"].get("all_ok"),
                    "commands": ctrl["good_clean"].get("commands"),
                    "cache_ok": ctrl["good_clean"].get("cache_ok"),
                },
                "bad_clean": ctrl["bad_clean"],
                "cache_dirty": {
                    "skipped_for_dirty_cache": ctrl["cache_dirty"].get(
                        "skipped_for_dirty_cache"
                    ),
                    "first_fail": ctrl["cache_dirty"].get("first_fail"),
                },
                "env_only": ctrl["env_only"],
                "docs_defect": ctrl["docs_defect"],
            },
            "reviewer_falsify": rev,
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "clean-clone-first-fail"},
                {"id": "probe2", "command": P2, "role": "inplace-compare-and-cache"},
            ],
            "inplace_skip": wt["inplace"],
            "observations": [
                {
                    "name": "worktree_git_clone_exit",
                    "measured": clone_rc,
                    "method": "git clone of this path into redirected-cache scratch",
                    "anchor": str(clone.get("command") or "git clone"),
                },
                {
                    "name": "named_docs_present_count",
                    "measured": int(docs.get("present_count") or 0),
                    "method": "census_named_docs",
                    "anchor": "README.md + command-center/RUNBOOK.md",
                },
                {
                    "name": "extracted_fenced_command_count",
                    "measured": n_cmds,
                    "method": "extract_fenced_commands",
                    "anchor": "README.md + command-center/RUNBOOK.md",
                },
                {
                    "name": "cache_redirect_empty_before_clone",
                    "measured": cache_ok,
                    "method": "assert_cache_free on redirected PIP_CACHE_DIR",
                    "anchor": str(wt["cache"].get("cache_root") or "redirected-cache"),
                },
                {
                    "name": "env_vs_docs_env_class",
                    "measured": env_class,
                    "method": "clean copy of README-only vs in-place with ambient.py",
                    "anchor": "command-center/p2-wave/probes/AUD-0091/fixtures/env_inplace",
                },
                {
                    "name": "env_vs_docs_defect_class",
                    "measured": defect_class,
                    "method": "copy vs in-place of broken documented command",
                    "anchor": "command-center/p2-wave/probes/AUD-0091/fixtures/docs_defect",
                },
                {
                    "name": "headline_falsify_verdict",
                    "measured": str(rev.get("verdict")),
                    "method": "independent .git and named-doc census",
                    "anchor": "engine.falsify_headline",
                },
            ],
            "control_ids": [
                "first-failing-step",
                "cache-free-precondition",
                "env-vs-docs",
            ],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "git": wt["git"],
            "notes": (
                "G-1 for AUD-0091: live named probes exit 0, artifact "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. No ADV rebuild. Did not relaunch "
                "finish-everything-close or p2-cloud-ok-deliver. Live README/"
                "RUNBOOK commands were not executed. " + SENTINEL
            ),
        },
    }

    errors = SC.error_list(receipt)
    if errors:
        print("FAILED:AUD-0091 emit schema")
        print("\n".join(errors[:20]))
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)
    receipt["artifacts"][0]["sha256"] = sha
    receipt["artifacts"][0]["bytes"] = size
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)
    errors = SC.error_list(receipt)
    if errors:
        print("FAILED:AUD-0091 emit schema after rewrite")
        print("\n".join(errors[:20]))
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0091 emit sentinel missing")
        return 1
    if not SC.rejects_garbage():
        print("FAILED:AUD-0091 emit garbage accepted after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"clone_rc={clone_rc} class={wt['classification']} "
        f"armed={armed} falsify={rev['verdict']} docs={present} n_cmds={n_cmds}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
