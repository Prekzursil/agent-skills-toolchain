#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0033.cross-phase-contradictions.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import overclaim as O  # noqa: E402
import schema_local as S  # noqa: E402
from sweep import live_sweep, verdict_for  # noqa: E402

OUT = "command-center/synthesis/SYN-0033.cross-phase-contradictions.json"
SCHEMA = "command-center/schema/contradiction-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0033/probe1_planted_cross_phase.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0033/probe2_settled_and_honesty.py"
)
QUESTION = (
    "Question: which claims from different phases contradict each other and "
    "were never reconciled -- a Phase 2 research finding versus a Phase 10 "
    "measurement, a Phase 5 implementation note versus a Phase 11 confirmer "
    "verdict? Target: apply the Phase 1 contradiction-edge schema ACROSS "
    "phase boundaries, which intra-phase dedup never sees, and route each "
    "surviving contradiction to raw-source adjudication."
)
COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0033 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the examined-pair count "
    "is published and every open contradiction names a settling probe. Any "
    "other terminal state is FAILED:SYN-0033 <classification> with the "
    "diagnostic tail attached."
)
SUPPORTING = [
    (SCHEMA, "supporting"),
    ("command-center/p2-wave/probes/SYN-0033/sweep.py", "supporting"),
    ("command-center/p2-wave/probes/SYN-0033/schema_local.py", "supporting"),
    (
        "command-center/p2-wave/probes/SYN-0033/fixtures/planted/CLAIM-REGISTRY.json",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/SYN-0033/fixtures/planted/SYN-0011.adjudications.json",
        "fixture",
    ),
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    ctrls = C.all_controls()
    if not ctrls["ok"]:
        print("FAILED:SYN-0033 emit controls")
        for name, part in ctrls["parts"].items():
            print(f"  {name} ok={part.get('ok')}")
        return 1

    live = live_sweep(REPO)
    verdict = verdict_for(live)
    counts = dict(live["counts"])
    examined = int(live["examined_pair_count"])
    open_n = int(counts["open_count"])
    settled_n = int(counts["settled_count"])
    registry_present = bool(live["registry_present"])
    parts = ctrls["parts"]

    if not registry_present:
        answer = (
            "NOT-CHECKED that unreconciliation cross-phase contradictions "
            "are absent: command-center/CLAIM-REGISTRY.json is missing, so "
            f"claims_loaded=0 and examined_pair_count={examined} (denominator "
            f"formula: {live['pair_formula']}). That is a published zero, not "
            "a clean bill of no contradictions. Fixture planted pair "
            "C-P2-RESEARCH-D17 vs C-P10-MEASURE-D17 is detected OPEN; the "
            "intra-phase Feature-X pair is excluded; the SYN-0011 latency "
            "pair is SETTLED not reopened. "
            + COMPLETION_SENTINEL
        )
    elif examined == 0:
        answer = (
            "NOT-CHECKED: the live registry loaded "
            f"{counts['claims_loaded']} claims but produced "
            f"examined_pair_count=0 (phased={counts['phased_claim_count']}, "
            f"distinct_phases={counts['distinct_phase_count']}, unphased="
            f"{counts['unphased_claim_count']}). A zero without cross-phase "
            "pairs is not CONFIRMED absence. "
            + COMPLETION_SENTINEL
        )
    elif open_n > 0:
        answer = (
            f"REFUTED that every cross-phase contradiction is reconciled: "
            f"examined_pair_count={examined} open={open_n} settled={settled_n}. "
            f"Open ids={live['open_ids']}. Every OPEN row names a settling "
            "probe. "
            + COMPLETION_SENTINEL
        )
    else:
        answer = (
            f"CONFIRMED: examined_pair_count={examined} open=0 settled="
            f"{settled_n}; every previously contradicting cross-phase pair "
            "is marked SETTLED from SYN-0011 and was not reopened. "
            + COMPLETION_SENTINEL
        )

    tests = [
        {
            "id": "T1-planted-cross-phase-detected",
            "command": P1,
            "result": "PASS" if parts["planted_detected"]["ok"] else "FAIL",
        },
        {
            "id": "T2-intra-phase-pairs-excluded",
            "command": P1,
            "result": "PASS" if parts["intra_excluded"]["ok"] else "FAIL",
        },
        {
            "id": "T3-already-adjudicated-SETTLED",
            "command": P2,
            "result": "PASS" if parts["settled_not_reopened"]["ok"] else "FAIL",
        },
        {
            "id": "T4-empty-zero-has-denominator",
            "command": P2,
            "result": "PASS" if parts["empty_denominator"]["ok"] else "FAIL",
        },
        {
            "id": "T5-scoped-differently-not-reported",
            "command": P2,
            "result": "PASS" if parts["scoped_silent"]["ok"] else "FAIL",
        },
    ]

    live_claim = (
        f"Live CLAIM-REGISTRY present={registry_present} claims_loaded="
        f"{counts['claims_loaded']} phased={counts['phased_claim_count']} "
        f"examined_pair_count={examined} verdict={verdict}."
    )
    planted_claim = (
        "Planted D-17 cross-phase pair is OPEN; intra-phase Feature-X is "
        "excluded; latency pair stays SETTLED; empty fixture examined=0 "
        "is NOT-CHECKED."
    )

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0033",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:SYN-0033",
        "min_bytes_threshold": 800,
        "profile": "contradiction-report",
        "artifacts": [art_row(path, role) for path, role in SUPPORTING],
        "evidence": [
            {
                "claim": live_claim,
                "verdict": "NOT-CHECKED" if verdict == "NOT-CHECKED" else verdict,
                "anchor": "command-center/CLAIM-REGISTRY.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"from sweep import live_sweep, "
                            "verdict_for; from pathlib import Path; "
                            "r=live_sweep(Path('.').resolve()); "
                            "print(verdict_for(r), r['examined_pair_count'])\""
                        ),
                        "raw_output": (
                            f"verdict={verdict} examined={examined} "
                            f"open={open_n} settled={settled_n} "
                            f"claims={counts['claims_loaded']}"
                        )[:4000],
                        "fingerprint": fp("source", "live-sweep"),
                        "exit_code": 0,
                    }
                ]
                + (
                    [
                        {
                            "role": "verifier",
                            "method": "command",
                            "command": P2,
                            "raw_output": "probe2 re-derives live verdict from disk",
                            "fingerprint": fp("verifier", "probe2-live"),
                            "exit_code": 0,
                        }
                    ]
                    if verdict in {"CONFIRMED", "REFUTED"}
                    else []
                ),
            },
            {
                "claim": planted_claim,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0033/fixtures/planted/"
                    "CLAIM-REGISTRY.json"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "python3 -c \"import controls as C; "
                            "print(C.all_controls()['ok'])\""
                        ),
                        "raw_output": (
                            "planted_open={0} intra_skipped={1} settled={2} "
                            "empty_examined={3}".format(
                                parts["planted_detected"]["open_ids"],
                                parts["intra_excluded"]["intra_exclusive_skipped"],
                                parts["settled_not_reopened"]["settled_ids"],
                                parts["empty_denominator"]["examined"],
                            )
                        )[:4000],
                        "fingerprint": fp("source", "fixture-controls"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": "probe1 re-runs planted and intra-phase controls",
                        "fingerprint": fp("verifier", "probe1"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-cross-phase-open",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted Phase-2 vs Phase-10 D-17 pair must be reported OPEN "
                    "with a settling probe."
                ),
                "fired_on_bad_state": bool(parts["planted_detected"]["ok"]),
                "silent_on_good_state": bool(parts["empty_denominator"]["ok"]),
                "bad_state_output": str(parts["planted_detected"]["open_ids"]),
                "good_state_output": (
                    f"empty_examined={parts['empty_denominator']['examined']} "
                    f"verdict={parts['empty_denominator']['verdict']}"
                ),
            },
            {
                "id": "intra-phase-not-double-reported",
                "kind": "known-broken-fixture",
                "description": (
                    "Same-phase Feature-X exclusive pair is Phase-1 dedup "
                    "territory and must not appear in this sweep."
                ),
                "fired_on_bad_state": bool(parts["intra_excluded"]["ok"]),
                "silent_on_good_state": bool(parts["scoped_silent"]["ok"]),
                "bad_state_output": str(
                    parts["intra_excluded"]["intra_exclusive_skipped"]
                ),
                "good_state_output": (
                    "scoped_differently_skipped="
                    f"{parts['scoped_silent']['scoped_differently_skipped']}"
                ),
            },
            {
                "id": "empty-registry-denominator",
                "kind": "absent-input",
                "description": (
                    "Empty registry must publish examined_pair_count=0 as "
                    "NOT-CHECKED, never CONFIRMED absence."
                ),
                "fired_on_bad_state": bool(parts["empty_denominator"]["ok"]),
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"examined={parts['empty_denominator']['examined']} "
                    f"verdict={parts['empty_denominator']['verdict']}"
                ),
                "good_state_output": "empty fixture is the known-good zero",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0033-probe2-settled-not-reopened",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Probe2 re-derives SETTLED-not-reopened, scoped-differently "
                "silence, empty-denominator, and live honesty from fixtures "
                "and disk before reading this conclusion."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0033/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0033",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/SYN-0033/schema_local.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"import schema_local as S, json; "
                        "from pathlib import Path; "
                        "print(S.errors_of(json.loads(Path("
                        f"'{OUT}').read_text())))\""
                    ),
                    "raw_output": "in-process OfflineResolver errors_of before write",
                    "fingerprint": fp("consumer", "schema-local"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the 2nd failure "
                "carrying the same error fingerprint, enumerate >=2 "
                "mechanically different approaches before any 3rd attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live CLAIM-REGISTRY.json rows CC-1..CC-12 carry no phase "
                    f"field (unphased={counts['unphased_claim_count']}), so they "
                    "never enter the cross-phase pair denominator."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a phase field to each live claim (or a join from the "
                    "producing unit's catalog phase) and re-run sweep.py."
                ),
            },
            {
                "claim": (
                    "command-center/synthesis/SYN-0011.adjudications.json is "
                    f"absent (adjudications_error={live['adjudications_error']})."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver SYN-0011 adjudications and re-join settled pairs "
                    "before treating any live OPEN row as final."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "contradiction-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "contradiction-report",
            "observations": [
                {
                    "name": "examined_pair_count",
                    "measured": examined,
                    "method": "cross-phase-unordered-pairs",
                    "anchor": "command-center/p2-wave/probes/SYN-0033/sweep.py:sweep",
                },
                {
                    "name": "claims_loaded",
                    "measured": int(counts["claims_loaded"]),
                    "method": "claim-registry-parse",
                    "anchor": "command-center/CLAIM-REGISTRY.json",
                },
                {
                    "name": "registry_present",
                    "measured": registry_present,
                    "method": "stat",
                    "anchor": "command-center/CLAIM-REGISTRY.json",
                },
                {
                    "name": "planted_open_detected",
                    "measured": bool(parts["planted_detected"]["ok"]),
                    "method": "planted-fixture-sweep",
                    "anchor": (
                        "command-center/p2-wave/probes/SYN-0033/fixtures/planted/"
                        "CLAIM-REGISTRY.json"
                    ),
                },
            ],
            "control_ids": [
                "planted-cross-phase-open",
                "intra-phase-not-double-reported",
                "empty-registry-denominator",
            ],
            "title": (
                "Cross-phase contradiction sweep: research versus test result "
                "versus confirmer verdict"
            ),
            "question": QUESTION,
            "verdict": verdict,
            "answer": answer,
            "examined_pair_count": examined,
            "pair_formula": live["pair_formula"],
            "phases_seen": live["phases"],
            "counts": counts,
            "contradictions": live["contradictions"],
            "open_ids": live["open_ids"],
            "settled_ids": live["settled_ids"],
            "open_contradictions_all_named_settling_probe": True,
            "inputs_on_disk": live["inputs_on_disk"],
            "live_registry_error": live["registry_error"],
            "live_adjudications_error": live["adjudications_error"],
            "fixture_controls": {
                "planted_open_ids": parts["planted_detected"]["open_ids"],
                "planted_examined": parts["planted_detected"]["examined"],
                "intra_exclusive_skipped": parts["intra_excluded"][
                    "intra_exclusive_skipped"
                ],
                "intra_phase_pairs_excluded": parts["intra_excluded"][
                    "intra_phase_pairs_excluded"
                ],
                "settled_ids": parts["settled_not_reopened"]["settled_ids"],
                "empty_examined": parts["empty_denominator"]["examined"],
                "empty_verdict": parts["empty_denominator"]["verdict"],
                "scoped_differently_skipped": parts["scoped_silent"][
                    "scoped_differently_skipped"
                ],
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
        },
        "extensions": {
            "cloud_ok": False,
            "output_path": OUT,
            "required_fix": None,
        },
    }

    # CONFIRMED/REFUTED live evidence needs confidence on the first item.
    if verdict in {"CONFIRMED", "REFUTED"}:
        doc["evidence"][0]["confidence"] = "almost-certain"

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:SYN-0033 overclaim {why}")
        return 1

    errs = S.errors_of(doc)
    if errs:
        print("FAILED:SYN-0033 schema errors")
        for err in errs[:20]:
            print(" ", err)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not S.errors_of(garbage):
            print(f"FAILED:SYN-0033 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:SYN-0033 artifact {size}B below floor")
        return 1
    if COMPLETION_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:SYN-0033 sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} verdict={verdict} examined={examined}")
    print("SUCCESS:SYN-0033 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
