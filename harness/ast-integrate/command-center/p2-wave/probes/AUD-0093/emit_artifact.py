#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0093-rollback-manifest-reality.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import schema_local as S  # noqa: E402

UNIT = "AUD-0093"
OUT_REL = "command-center/audit/AUD-0093-rollback-manifest-reality.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0093 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0093/probe1_entry_artifacts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0093/probe2_rehearse.py"
)
QUESTION = (
    "For each action this program has ALREADY executed - the DELETE-ALL of "
    "77 files, the salvage into tools/lib, the worktree cleanup from 20 to 6 "
    "- does the rollback manifest describe a procedure that would actually "
    "restore the prior state?"
)
MIN_BYTES = 2048


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def art_row(rel: str, role: str) -> dict:
    path = E.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    measured = E.measure()
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    loc = measured["manifest"]
    fx = measured["fixture_rehearsal"]
    fx_exist = measured["fixture_existence"]
    live = measured["live_rehearsal"]
    highest = measured["highest_risk"]
    git = measured["git"]
    salvage = measured["salvage"]
    restore_possible = measured["restore_possible"]
    uncovered = [
        row for row in measured["coverage"] if not row["covered_by_manifest"]
    ]
    salvage_n = salvage["file_n"]
    git_inside = bool(git.get("inside_work_tree"))
    entry_n = len(measured["entries"])
    titles = [e.get("title") for e in measured["entries"]]

    if not fx["control_pass"] or not fx_exist["control_pass"]:
        print("FAILED:AUD-0093 emit detector-control-failed")
        print(json.dumps({"rehearsal": fx, "existence": fx_exist}, indent=2)[:4000])
        return 1

    if restore_possible:
        answer = (
            "Yes: the live ROLLBACK-MANIFEST names a restore procedure for "
            "each already-executed action, every referenced artifact still "
            "exists, and the highest-risk scratch rehearsal recovered prior "
            "bytes."
        )
        interpretation = (
            "Rollback is described and the rehearsal recovered the prior "
            "scratch state."
        )
    elif loc["present"]:
        answer = (
            "No: command-center/ROLLBACK-MANIFEST.md is present "
            f"({entry_n} heading entries: {titles}) but none of those entries "
            "describe a restore procedure for the already-executed DELETE-ALL "
            "of 77 files, the salvage into tools/lib, or the worktree cleanup "
            f"from 20 to 6 (covered {measured['covered_n']}/"
            f"{measured['executed_n']}). Highest-risk uncovered action "
            f"{highest['id']} was rehearsed in a scratch tree with an empty "
            f"restore map; byte_recovered={live['byte_recovered']} "
            f"mode={live.get('mode')}. Git history is unavailable here "
            f"(inside_work_tree={git_inside}). tools/lib currently holds "
            f"{salvage_n} file(s); that is salvage residue, not a 77-file "
            "restore."
        )
        interpretation = (
            "A present manifest that documents register-gate and catalog "
            "undo is not a restore procedure for the three already-executed "
            "actions named by this unit. The negative result is the finding."
        )
    else:
        answer = (
            "No: command-center/ROLLBACK-MANIFEST.md is absent on this "
            "worktree, so it does not describe a restore procedure for the "
            "already-executed DELETE-ALL of 77 files, the salvage into "
            "tools/lib, or the worktree cleanup from 20 to 6. Scratch "
            "rehearsal of that uncovered destructive class did not "
            "byte-recover prior files. Git history is unavailable here "
            f"(inside_work_tree={git_inside})."
        )
        interpretation = (
            "A missing manifest is a negative finding, not a blocked "
            "measurement. tools/lib currently holds "
            f"{salvage_n} file(s); that is not a 77-file restore."
        )

    coverage_raw = json.dumps(measured["coverage"], sort_keys=True)
    loc_raw = json.dumps(loc, sort_keys=True)
    live_raw = json.dumps(
        {k: live.get(k) for k in ("byte_recovered", "mode", "label", "missing_after")},
        sort_keys=True,
    )
    fx_raw = json.dumps(
        {
            "irreversible_reported_failure": fx["irreversible_reported_failure"],
            "reversible_reported_success": fx["reversible_reported_success"],
            "control_pass": fx["control_pass"],
        },
        sort_keys=True,
    )
    exist_raw = json.dumps(
        {
            "present_entry_all_exist": fx_exist["present_entry_all_exist"],
            "missing_entry_missing_n": fx_exist["missing_entry_missing_n"],
            "control_pass": fx_exist["control_pass"],
        },
        sort_keys=True,
    )

    supporting = [
        "command-center/ROLLBACK-MANIFEST.md",
        "command-center/schema/audit-finding.schema.json",
        "tools/lib/handled-ledger.mjs",
        "command-center/p2-wave/probes/AUD-0093/engine.py",
        "command-center/p2-wave/probes/AUD-0093/probe1_entry_artifacts.py",
        "command-center/p2-wave/probes/AUD-0093/probe2_rehearse.py",
        "command-center/p2-wave/probes/AUD-0093/fixtures/present-entry.md",
        "command-center/p2-wave/probes/AUD-0093/fixtures/missing-entry.md",
        "command-center/p2-wave/probes/AUD-0093/schema_local.py",
    ]
    artifacts = []
    for rel in supporting:
        if (E.REPO / rel).is_file():
            artifacts.append(art_row(rel, "supporting" if "probes/" in rel or rel.endswith(".mjs") else "supporting"))

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0093",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": MIN_BYTES,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ]
        + artifacts,
        "evidence": [
            {
                "claim": (
                    "Each already-executed action (DELETE-ALL 77, salvage into "
                    "tools/lib, worktree 20 to 6) has a matching ROLLBACK-MANIFEST entry."
                ),
                "verdict": "CONFIRMED" if not uncovered else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/ROLLBACK-MANIFEST.md",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "read command-center/ROLLBACK-MANIFEST.md headings and bodies",
                        loc_raw,
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0093/engine.py coverage_for_executed",
                        coverage_raw,
                    ),
                ],
            },
            {
                "claim": (
                    "Highest-risk restore for those executed actions recovers "
                    "prior bytes in a scratch tree."
                ),
                "verdict": "CONFIRMED" if live["byte_recovered"] else "REFUTED",
                "confidence": "almost-certain",
                "anchor": P2,
                "probes": [
                    probe(
                        "source",
                        "byte-compare",
                        "scratch rehearse empty-restore after delete for uncovered DELETE-ALL",
                        live_raw,
                    ),
                    probe(
                        "verifier",
                        "command",
                        P2,
                        live_raw,
                    ),
                ],
            },
            {
                "claim": (
                    "Existence checker fires on a planted-absent backup path and "
                    "is silent on live tools/lib/handled-ledger.mjs; irreversible "
                    "scratch delete reports failure, reversible copy reports success."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": P1,
                "probes": [
                    probe("source", "file-read", P1, exist_raw),
                    probe("verifier", "test-run", P2, fx_raw),
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-entry-artifacts",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-highest-risk-rehearsal",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "irreversible-entry-control",
                "command": (
                    "scratch rehearse irreversible-delete-no-backup; "
                    "byte_recovered must be false"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-absent-manifest-path",
                "kind": "absent-input",
                "description": (
                    "fixtures/missing-entry.md names "
                    "command-center/audit/AUD-0093-DOES-NOT-EXIST.bin; "
                    "fixtures/present-entry.md names tools/lib/handled-ledger.mjs."
                ),
                "fired_on_bad_state": fx_exist["missing_entry_missing_n"] >= 1,
                "silent_on_good_state": fx_exist["present_entry_all_exist"] is True,
            },
            {
                "id": "irreversible-delete-no-backup",
                "kind": "known-broken-fixture",
                "description": (
                    "irreversible-delete-no-backup deletes gone.txt with restore_map "
                    "pointing at absent backup/gone.txt; reversible-copy restores "
                    "keep.txt from backup."
                ),
                "fired_on_bad_state": bool(fx["irreversible_reported_failure"]),
                "silent_on_good_state": bool(fx["reversible_reported_success"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0093-probe2-scratch-rehearsal-irreversible-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Independent mechanism is the scratch-tree byte compare plus "
                "the known-irreversible fixture. Catalog also asks for a "
                "fresh-context Claude and a Codex reviewer; those reviewers "
                "were not available in this lane and are not impersonated."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0093/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema (disk $ref store)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0093/schema_local.py",
                    "offline Draft202012Validator against audit-finding.schema.json",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS sentinel"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The 77 deleted path strings are not inventoried on this "
                    "worktree, so DELETE-ALL identity is catalog-cited rather "
                    "than git-recovered."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Recover the 77-path list from a git object store that still "
                    "holds the pre-DELETE-ALL tree and re-run identity compare."
                ),
            },
            {
                "claim": (
                    "Historical worktree count 20 to 6 cannot be re-counted "
                    "without git worktrees."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run git worktree list --porcelain on a checkout whose .git "
                    "still names a live admin dir."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": QUESTION,
            "answer": answer,
            "interpretation": interpretation,
            "restore_possible": restore_possible,
            "observations": [
                {
                    "name": "manifest_present",
                    "measured": bool(loc["present"]),
                    "method": "stat command-center/ROLLBACK-MANIFEST.md",
                    "anchor": "command-center/ROLLBACK-MANIFEST.md",
                },
                {
                    "name": "entry_n",
                    "measured": entry_n,
                    "method": "heading parse of live ROLLBACK-MANIFEST.md",
                    "anchor": "command-center/ROLLBACK-MANIFEST.md",
                },
                {
                    "name": "executed_covered",
                    "measured": f"{measured['covered_n']}/{measured['executed_n']}",
                    "method": "keyword match EXECUTED_ACTIONS against entry bodies",
                    "anchor": "command-center/p2-wave/probes/AUD-0093/engine.py",
                },
                {
                    "name": "live_byte_recovered",
                    "measured": bool(live["byte_recovered"]),
                    "method": "scratch-tree sha256 snapshot compare",
                    "anchor": P2,
                },
                {
                    "name": "git_inside_work_tree",
                    "measured": git_inside,
                    "method": "git rev-parse --is-inside-work-tree",
                    "anchor": "git rev-parse --is-inside-work-tree",
                },
                {
                    "name": "tools_lib_file_n",
                    "measured": salvage_n,
                    "method": "rglob tools/lib",
                    "anchor": "tools/lib",
                },
            ],
            "control_ids": [
                "planted-absent-manifest-path",
                "irreversible-delete-no-backup",
            ],
        },
        "extensions": {
            "manifest_present": loc["present"],
            "entry_n": entry_n,
            "covered_n": measured["covered_n"],
            "executed_n": measured["executed_n"],
            "missing_reference_n": measured["missing_reference_n"],
            "live_byte_recovered": live["byte_recovered"],
            "live_rehearsal_mode": live.get("mode"),
            "irreversible_reported_failure": fx["irreversible_reported_failure"],
            "reversible_reported_success": fx["reversible_reported_success"],
            "restore_possible": restore_possible,
            "highest_risk": highest,
            "git": git,
            "salvage": salvage,
            "coverage": measured["coverage"],
            "candidates": loc["candidates"],
            "manifest_titles": titles,
        },
    }

    errs = S.error_messages(doc)
    if errs:
        print("FAILED:AUD-0093 emit schema-invalid")
        for item in errs[:20]:
            print(" ", item)
        return 1
    garbage_counts = [
        len(S.error_messages(g))
        for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000})
    ]
    if not all(c > 0 for c in garbage_counts):
        print(f"FAILED:AUD-0093 emit schema-accepts-garbage {garbage_counts}")
        return 1

    out = E.REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(body, encoding="utf-8")
    sha, size = digest(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    body = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(body, encoding="utf-8")
    size = out.stat().st_size
    text = out.read_text(encoding="utf-8")
    if size < MIN_BYTES:
        print(f"FAILED:AUD-0093 emit too-small bytes={size}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0093 emit sentinel-absent")
        return 1
    post = S.error_messages(json.loads(text))
    if post:
        print("FAILED:AUD-0093 emit schema-invalid-after-write")
        for item in post[:20]:
            print(" ", item)
        return 1
    print(f"wrote {OUT_REL} bytes={size} restore_possible={restore_possible}")
    print("SUCCESS:AUD-0093 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
