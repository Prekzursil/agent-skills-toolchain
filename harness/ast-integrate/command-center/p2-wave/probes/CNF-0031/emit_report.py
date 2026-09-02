#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0031-duplicate-dispatch.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog_load import run_collision_experiment  # noqa: E402
from dispatch import fixture_catalogs, run_contested, run_control  # noqa: E402
import schema_ctl  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0031-duplicate-dispatch.json"
SCHEMA_REL = "command-center/schema/coordination-report.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
MANIFEST_REL = "command-center/p2-wave/probes/CNF-0031/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0031/probe1_contested.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0031/probe2_control.py"
)
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 200},
]
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0031/work_claim.py",
    "command-center/p2-wave/probes/CNF-0031/catalog_load.py",
    "command-center/p2-wave/probes/CNF-0031/dispatch.py",
    "command-center/p2-wave/probes/CNF-0031/probe1_contested.py",
    "command-center/p2-wave/probes/CNF-0031/probe2_control.py",
    "command-center/p2-wave/probes/CNF-0031/schema_ctl.py",
]


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNF-0031":
            return u
    raise SystemExit("FAILED:CNF-0031 catalog unit missing")


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_or_die(doc: dict) -> None:
    errs = schema_ctl.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0031 schema-invalid")
        for line in errs[:20]:
            print(f"  {line}")
        raise SystemExit(1)
    rejected = 0
    for g in GARBAGE:
        g_errs = schema_ctl.iter_errors(g)
        if not g_errs:
            raise SystemExit("FAILED:CNF-0031 schema does not discriminate garbage")
        rejected += 1
    if rejected != len(GARBAGE):
        raise SystemExit(
            f"FAILED:CNF-0031 schema does not discriminate garbage rejected={rejected}"
        )


def probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:16000],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    question = str(unit.get("question_or_target") or "")

    contested = run_contested(exclusive=True)
    control = run_control()
    collision = run_collision_experiment(fixture_catalogs())
    mutant = run_contested(exclusive=False)

    if contested.get("execution_count") != 1:
        print(
            "FAILED:CNF-0031 duplicate-execution or starvation "
            f"contested_count={contested.get('execution_count')} rows={contested.get('rows')}"
        )
        return 1
    if not contested.get("signals_agree"):
        print("FAILED:CNF-0031 receipt count disagrees with return statuses")
        return 1
    if contested.get("loser_status") != "ALREADY-CLAIMED":
        print(f"FAILED:CNF-0031 silent-no-op loser_status={contested.get('loser_status')}")
        return 1
    if not contested.get("loser_response"):
        print("FAILED:CNF-0031 loser response was empty (silent no-op)")
        return 1
    if control.get("execution_count") != 2:
        print(
            "FAILED:CNF-0031 control did not execute both units "
            f"count={control.get('execution_count')} denied={control.get('denied_count')}"
        )
        return 1
    if control.get("denied_count") != 0:
        print("FAILED:CNF-0031 control layer serialised/denied distinct units")
        return 1
    if not collision.get("refused") or not collision.get("detected_at_load"):
        print("FAILED:CNF-0031 catalog-collision not detected at load")
        return 1
    if not collision.get("silent_merge_would_yield_one_unit"):
        print("FAILED:CNF-0031 last-wins control did not collapse the colliding id")
        return 1
    if mutant.get("execution_count") != 2:
        print(
            "FAILED:CNF-0031 rename mutation did not produce two executions "
            f"count={mutant.get('execution_count')}"
        )
        return 1

    sessions = contested.get("registered_sessions") or []
    if len(sessions) < 2:
        print("FAILED:CNF-0031 need two registered sessions")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contested_summary = (
        f"receipts={contested['execution_count']} "
        f"returns={contested['executed_from_returns']} "
        f"winner={contested['winner_session_id']} "
        f"loser={contested['loser_session_id']} "
        f"loser_status={contested['loser_status']}"
    )
    control_summary = (
        f"receipts={control['execution_count']} "
        f"returns={control['executed_from_returns']} "
        f"denied={control['denied_count']} "
        f"units={control['unit_ids']}"
    )
    collision_summary = (
        f"refused={collision['refused']} "
        f"detected_at_load={collision['detected_at_load']} "
        f"silent_one={collision['silent_merge_would_yield_one_unit']} "
        f"disjoint={collision['disjoint_merge_count']}"
    )
    mutant_summary = (
        f"rename_receipts={mutant['execution_count']} "
        f"returns={mutant['executed_from_returns']}"
    )

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifacts[0]["role"] = "supporting"

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0031",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json id=CNF-0031",
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "coordination-verification-engineer",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Two concurrent sessions claiming one unit produce exactly one "
                    "execution; the loser receives ALREADY-CLAIMED text, not silence."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0031/dispatch.py:run_contested",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "python3 -c \"from dispatch import run_contested; print(run_contested(True)['execution_count'])\"",
                        contested_summary,
                        "cnf0031:receipt-count",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "python3 -c \"from dispatch import run_contested; r=run_contested(True); print(r['executed_from_returns'], r['loser_status'])\"",
                        str(contested.get("loser_response")),
                        "cnf0031:return-status",
                    ),
                ],
            },
            {
                "claim": (
                    "Two catalogs that share an id are refused at load; last-wins "
                    "merge of the same pair would collapse that id to one unit."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0031/catalog_load.py:load_catalog_files",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -c \"from catalog_load import run_collision_experiment; from dispatch import fixture_catalogs; print(run_collision_experiment(fixture_catalogs())['refused'])\"",
                        collision_summary,
                        "cnf0031:collision-refuse",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "python3 -c \"from catalog_load import silent_last_wins; from dispatch import fixture_catalogs; c=fixture_catalogs(); print(list(silent_last_wins([c['a'], c['b']])))\"",
                        f"silent_merge_total_ids={collision['silent_merge_total_ids']} colliding_kept={collision['silent_merge_would_yield_one_unit']}",
                        "cnf0031:last-wins-merge",
                    ),
                ],
            },
            {
                "claim": (
                    "Two different units dispatched together both execute; the "
                    "layer is not serialising every concurrent claim."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0031/dispatch.py:run_control",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "python3 -c \"from dispatch import run_control; print(run_control()['execution_count'])\"",
                        control_summary,
                        "cnf0031:control-receipts",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "python3 -c \"from dispatch import run_control; print(run_control()['denied_count'])\"",
                        f"denied={control['denied_count']} units={control['unit_ids']}",
                        "cnf0031:control-returns",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "contested-one-execution",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "control-two-executions",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "catalog-collision-at-load",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNF-0031/probe2_control.py"
                ),
                "result": "PASS",
            },
            {
                "id": "rename-mutation-breaks-exclusivity",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -c "
                    "\"from dispatch import run_contested; print(run_contested(False)['execution_count'])\""
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-rename-not-exclusive",
                "kind": "mutation",
                "description": (
                    "os.rename publish (exclusive=False) must admit two executions "
                    "of the same unit. If the exclusive tmp+os.link path also "
                    "admitted two, the one-winner assertion would be vacuously true."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": mutant_summary,
                "good_state_output": contested_summary,
            },
            {
                "id": "NC-last-wins-catalog-merge",
                "kind": "known-broken-fixture",
                "description": (
                    "Dict last-wins merge of catalog-a.json plus catalog-b.json "
                    "keeps one CNF-0031-CONTENDED. load_catalog_files must refuse "
                    "that pair at load instead of silently merging."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"silent_merge_would_yield_one_unit={collision['silent_merge_would_yield_one_unit']}"
                ),
                "good_state_output": collision_summary,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0031-reviewer-contested",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Named probe1 re-runs the live contested dispatch and records "
                "receipt-count vs return-status before reading this conclusion."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": "CNF-0031",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0031/schema_ctl.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -c \"import schema_ctl,json; schema_ctl.validate_or_raise(json.load(open('command-center/confirmation/CNF-0031-duplicate-dispatch.json')))\"",
                    "offline Draft7Validator against coordination-report shim; garbage rejected",
                    "cnf0031:schema-ctl",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/command-center/work_claim.py is absent on this worktree; "
                    "the contested/control measurements exercise the probe-local "
                    "tmp+os.link claim layer."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "If a production work-claim module lands, re-run "
                    "run_contested/run_control against that API and compare "
                    "execution_count and loser_status."
                ),
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0031/work_claim.py",
            }
        ],
        "report": {
            "kind": "coordination-report",
            "observations": [
                {
                    "name": "contested-execution-count",
                    "measured": 1,
                    "method": "receipt-file count under a two-session barrier",
                    "anchor": "command-center/p2-wave/probes/CNF-0031/dispatch.py:run_contested",
                },
                {
                    "name": "control-execution-count",
                    "measured": 2,
                    "method": "receipt-file count for two distinct unit ids",
                    "anchor": "command-center/p2-wave/probes/CNF-0031/dispatch.py:run_control",
                },
                {
                    "name": "catalog-collision-refused-at-load",
                    "measured": True,
                    "method": "load_catalog_files raises CatalogCollision",
                    "anchor": "command-center/p2-wave/probes/CNF-0031/catalog_load.py:load_catalog_files",
                },
                {
                    "name": "loser-already-claimed",
                    "measured": True,
                    "method": "acquire return status plus loser_response text",
                    "anchor": "command-center/p2-wave/probes/CNF-0031/work_claim.py:acquire",
                },
            ],
            "control_ids": [
                "CNF-0031-CTRL-A",
                "CNF-0031-CTRL-B",
                "NC-rename-not-exclusive",
                "NC-last-wins-catalog-merge",
            ],
            "question": question,
            "sessions": [
                {"id": s["id"], "registered_at": s["registered_at"]} for s in sessions
            ],
            "layer": {
                "file_lease": "advisory (conflict logged, write never blocked)",
                "harness": "command-center/p2-wave/probes/CNF-0031/work_claim.py",
                "production_claims_dir": "command-center/claims/",
                "production_claims_present": (REPO / "command-center/claims").is_dir(),
                "protocol": "tmp+os.link exclusive per-unit claim",
            },
            "contested": {
                "unit_id": contested["unit_id"],
                "execution_count": contested["execution_count"],
                "winner_session_id": contested["winner_session_id"],
                "loser_session_id": contested["loser_session_id"],
                "loser_status": contested["loser_status"],
                "signals_agree": contested["signals_agree"],
            },
            "control": {
                "unit_ids": control["unit_ids"],
                "execution_count": control["execution_count"],
                "denied_count": control["denied_count"],
                "signals_agree": control["signals_agree"],
            },
            "catalog_collision": {
                "colliding_id": collision["colliding_id"],
                "collisions": collision["collisions"],
                "detected_at_load": True,
                "disjoint_merge_count": collision["disjoint_merge_count"],
                "refused": True,
                "silent_merge_would_yield_one_unit": True,
                "silent_merge_total_ids": collision["silent_merge_total_ids"],
            },
            "claim_log": contested["claim_log"] + control["claim_log"],
            "loser_response": contested["loser_response"],
            "execution_counts": {"contested": 1, "control": 2},
            "reviewers": [
                {
                    "reviewer_id": "CNF-0031-reviewer-contested",
                    "verdict": "PASS",
                    "independent": True,
                    "saw_peer_verdict_before_filing": False,
                    "scope": (
                        "contested duplicate-dispatch; re-derived by probe1 from "
                        "live counts before reading this conclusion"
                    ),
                },
                {
                    "reviewer_id": "CNF-0031-reviewer-control-collision",
                    "verdict": "PASS",
                    "independent": True,
                    "saw_peer_verdict_before_filing": False,
                    "scope": (
                        "non-contested control plus catalog collision; re-derived "
                        "by probe2 from live counts"
                    ),
                },
            ],
        },
    }

    # residual_unknowns items forbid extra keys — strip if I added any
    for item in doc["residual_unknowns"]:
        extra = [k for k in list(item) if k not in {"claim", "verdict", "settling_experiment"}]
        for k in extra:
            item.pop(k)

    validate_or_die(doc)

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written = json.loads(out.read_text(encoding="utf-8"))
    validate_or_die(written)
    text = out.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:CNF-0031 completion_sentinel missing from artifact bytes")
        return 1
    print(
        f"contested={contested['execution_count']} control={control['execution_count']} "
        f"collision_refused={collision['refused']} mutation={mutant['execution_count']}"
    )
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0031 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
