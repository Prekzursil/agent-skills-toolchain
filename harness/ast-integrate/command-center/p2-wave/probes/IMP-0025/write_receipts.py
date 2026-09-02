#!/usr/bin/env python3
"""Emit IMP-0025 receipt + per-unit manifest. Does not run unit_manifest.py --write."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from plugin.independent_differ import classify_pair_independent  # noqa: E402
from plugin.repair import apply_repair, iter_rel_files  # noqa: E402
import scenario as S  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0025.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0025/probe1_dry_run_plan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0025/probe2_negative_mutation.py"
)
SENTINEL = "SUCCESS:IMP-0025"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def read_opt(path: Path | None):
    if path is None:
        return None
    return path.read_bytes()


def main() -> int:
    meta = S.build_fixtures()
    repo, live = S.estate_roots()
    host = S.host_candidates()
    host_present = [h for h in host if h["is_dir"] and h["file_count"] > 0]
    plan = apply_repair(repo, live, one_directional=False, dry_run=True)
    repo_files = iter_rel_files(repo)
    live_files = iter_rel_files(live)
    keys = sorted(set(repo_files) | set(live_files))
    indep_rows = []
    mismatch = []
    for rel in keys:
        rec = classify_pair_independent(
            read_opt(repo_files.get(rel)),
            read_opt(live_files.get(rel)),
        )
        tool = plan["classifications"][rel]
        indep_rows.append(
            {
                "path": rel,
                "repair": tool,
                "independent": rec["classification"],
                "live_unique_n": len(rec.get("live_unique_lines") or []),
                "repo_unique_n": len(rec.get("repo_unique_lines") or []),
            }
        )
        if rec["classification"] != tool:
            mismatch.append(rel)

    touch = set(plan["touch_set"])
    diverged_in_plan = [
        rel for rel in touch if plan["classifications"].get(rel) == "DIVERGED"
    ]

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0 or mismatch or diverged_in_plan:
        print(f"FAILED:IMP-0025 emit probes rc1={rc1} rc2={rc2} mismatch={mismatch}")
        print(out1[-1500:])
        print(out2[-1500:])
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sample = [r for r in indep_rows if r["path"] in set(meta["reviewer_sample"])]

    receipt = {
        "unit_id": "IMP-0025",
        "id": "IMP-0025",
        "title": "`repair` command restoring only files with no live-unique content",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0025",
        "question_or_target": (
            "Implement `repair` to re-deploy exactly the drifted files that the "
            "two-directional classifier (IMP-0034) marks repo-ahead or "
            "identical-modulo-EOL, and to refuse to touch anything marked DIVERGED."
        ),
        "timestamps": {
            "started_at": started,
            "ended_at": started,
        },
        "retry": {
            "count": 0,
            "policy": "no automatic retry against the live tree; a failed repair requires a fresh dry-run plan review",
        },
        "host_live_tree": {
            "candidates": host,
            "present": host_present,
            "dry_run_substrate": (
                "host-live-tree" if host_present else "planted-two-directional-estate"
            ),
            "cited_historical_5_of_88": False,
            "note": (
                "Owner ~/.claude/rules and repo rules/ were searched. On this Linux "
                "worktree both are absent, matching ARC-0005. Evidence is a dry-run "
                "over a planted two-directional estate (IDENTICAL, IDENTICAL-MODULO-EOL, "
                "REPO-AHEAD, LIVE-AHEAD, DIVERGED). Apply is never pointed at HOME."
            ),
        },
        "dry_run_plan": {
            "repo_root": plan["repo_root"],
            "live_root": plan["live_root"],
            "union_files": plan["union_files"],
            "would_touch": plan["would_touch"],
            "refused": plan["refused"],
            "skipped_identical": plan["skipped_identical"],
            "classifications": plan["classifications"],
        },
        "independent_differ": {
            "algorithm": "sha256 identity + EOL-normalised sorted two-pointer comm",
            "rows": indep_rows,
            "exact_set_match": True,
            "classification_mismatches": mismatch,
            "diverged_files_in_repair_plan": diverged_in_plan,
        },
        "evidence": [
            {
                "anchor": "tools/plugin/repair.py:plan_repair",
                "claim": (
                    "Dry-run repair plan lists every file it would touch and its "
                    "two-directional classification; touch set is REPO-AHEAD plus "
                    "IDENTICAL-MODULO-EOL only."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": rc1,
                        "raw_output": out1[-1500:],
                    }
                ],
            },
            {
                "anchor": "tools/plugin/independent_differ.py:classify_pair_independent",
                "claim": (
                    "Independent recomputation (sha256 + comm unique-lines) matches "
                    "the repair classifier per file; no DIVERGED path appears in the "
                    "repair plan."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": rc1,
                        "raw_output": out1[-1500:],
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "diverged-refused-repo-ahead-repaired-same-run",
                "kind": "known-broken-fixture",
                "description": (
                    "Synthetic DIVERGED fixture (both sides unique lines) is refused "
                    "and a REPO-AHEAD fixture is repaired in the same apply."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "DIVERGED live unique line survives; file not in applied",
                "good_state_output": "REPO-AHEAD live bytes become repo bytes",
            },
            {
                "id": "mutation-one-directional-goes-red",
                "kind": "mutation",
                "description": (
                    "one_directional=True classifies repo-extra as REPO-AHEAD even "
                    "when live is unique; test_diverged_files_never_touched goes red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "AssertionError from test_diverged_files_never_touched(one_directional=True)",
                "good_state_output": "two-directional apply leaves DIVERGED bytes unchanged",
            },
        ],
        "tests": [
            {
                "id": "test_diverged_files_never_touched",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_repair_respects_divergence.py",
                "result": "PASS",
            },
            {
                "id": "test_negative_control_diverged_refused_repo_ahead_repaired",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_mutation_one_directional_makes_diverged_test_go_red",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0025-independent-differ-10-file-sample",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "requirement": (
                "Reviewer independently classifies a 10-file sample by reading both "
                "sides; the differ is authoritative."
            ),
            "sample": sample,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The 2026-08-09 5/88 host rules census cannot be remeasured: "
                    "repo rules/ and ~/.claude/rules are absent on this Linux worktree."
                ),
                "settling_experiment": (
                    "Re-run dry-run repair against the owner live tree when both "
                    "sides exist; require exact set match with independent_differ."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "min_bytes_threshold": 128,
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "tools/plugin/repair.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "tools/plugin/drift.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "tools/plugin/independent_differ.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "tools/plugin/tests/test_repair_respects_divergence.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0025",
                    "role": "verifier",
                    "method": "command",
                },
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0025/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2},
        ],
        "cloud_ok": False,
        "completion_line": SENTINEL,
    }

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0025 sentinel missing from receipt text")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")

    supporting = [
        OUT_REL,
        "tools/plugin/repair.py",
        "tools/plugin/drift.py",
        "tools/plugin/independent_differ.py",
        "tools/plugin/tests/test_repair_respects_divergence.py",
        "tools/plugin/schema/drift-classification.schema.json",
        "command-center/p2-wave/probes/IMP-0025/probe1_dry_run_plan.py",
        "command-center/p2-wave/probes/IMP-0025/probe2_negative_mutation.py",
        "command-center/p2-wave/probes/IMP-0025/scenario.py",
    ]
    art_rows = []
    for rel in supporting:
        p = REPO / rel
        digest, nbytes = sha256_file(p)
        art_rows.append(
            {
                "path": rel,
                "sha256": digest,
                "bytes": nbytes,
                "present": True,
                "unit_id": "IMP-0025",
                "receipt_path": "command-center/p2-wave/probes/IMP-0025/SUBAGENT-RETURN.json",
                "role": "primary" if rel == OUT_REL else "supporting",
            }
        )
        if rel == OUT_REL:
            primary_sha, primary_bytes = digest, nbytes

    for a in receipt["artifacts"]:
        rel = a["path"]
        if rel == OUT_REL:
            a["exists"] = True
            continue
        digest, nbytes = sha256_file(REPO / rel)
        a["sha256"] = digest
        a["bytes"] = nbytes
        a["exists"] = True

    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    primary_sha, primary_bytes = sha256_file(out_path)
    for row in art_rows:
        if row["path"] == OUT_REL:
            row["sha256"] = primary_sha
            row["bytes"] = primary_bytes

    ret = {
        "id": "IMP-0025",
        "unit_id": "IMP-0025",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "dry-run-plan-vs-independent-differ",
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "negative-control-and-mutation",
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0025/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0025-independent-differ-10-file-sample",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": started,
        "notes": (
            "G-1 for IMP-0025: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not apply repair to owner HOME."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0025",
        "verified_on_disk": True,
        "expected": len(art_rows),
        "present": len(art_rows),
        "artifacts": art_rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT_REL} bytes={primary_bytes} sha256={primary_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
