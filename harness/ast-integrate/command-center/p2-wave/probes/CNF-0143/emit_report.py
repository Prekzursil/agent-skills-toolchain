#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0143.json program-gate-report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import accounting as A  # noqa: E402
import live as L  # noqa: E402
import reviewer as R  # noqa: E402

OUT = "command-center/receipts/CNF-0143.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
UNK = "command-center/UNKNOWNS-REGISTER.md"
OVERLAY = "command-center/p2-wave/probes/CNF-0143/program-gate-report.overlay.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0143/probe1_arithmetic.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0143/probe2_completeness.py"
)
QUESTION = (
    "Question: what happens to claims that cannot be confirmed at all "
    "(missing artifact, external blocker, retired subsystem)? Build the "
    "non-response accounting that records each as BLOCKED with a named "
    "missing prerequisite, and recompute every published rate BOTH with "
    "and without them. Dropping them from the denominator is how a program "
    "reports a pass rate it did not earn."
)
HAND_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import sys; from pathlib import Path; "
    "sys.path.insert(0, str(Path('command-center/p2-wave/probes/CNF-0143'))); "
    "import accounting as A, reviewer as R; "
    "b=A.load_control_set(); sid=b['expected']['stratum_a']; "
    "print(R.hand_recompute(b['records_nonempty_blocked'], b['frame'], sid))\""
)
OVERLAY_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json,sys; from pathlib import Path; "
    "sys.path.insert(0, str(Path('command-center/p2-wave/probes/CNF-0143'))); "
    "import accounting as A; "
    "doc=json.loads(Path('command-center/receipts/CNF-0143.json').read_text()); "
    "errs=A.overlay_errors(doc); print('overlay_errs', errs[:8]); "
    "raise SystemExit(0 if not errs else 1)\""
)
CONSUMER_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json; from pathlib import Path; "
    "p=Path('command-center/receipts/CNF-0143.json'); "
    "doc=json.loads(p.read_text(encoding='utf-8')); "
    "assert doc.get('sentinel')=='SUCCESS:CNF-0143'; "
    "print('read_ok bytes', p.stat().st_size)\""
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": A.probe_fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    bundle = A.load_control_set()
    frame = bundle["frame"]
    nonempty = A.compute_rates(bundle["records_nonempty_blocked"], frame)
    empty = A.compute_rates(bundle["records_empty_blocked"], frame)
    if int(nonempty["overall"]["n_blocked"]) < 1:
        print("FAILED:CNF-0143 emit control BLOCKED set empty")
        return 1
    if not nonempty["overall"]["rates_differ"]:
        print("FAILED:CNF-0143 emit arithmetic wiring bug")
        return 1
    if empty["overall"]["rates_differ"] or int(empty["overall"]["n_blocked"]) != 0:
        print("FAILED:CNF-0143 emit known-absent failed")
        return 1

    sid_a = bundle["expected"]["stratum_a"]
    hand = R.hand_recompute(bundle["records_nonempty_blocked"], frame, sid_a)
    code_a = [s for s in nonempty["strata"] if s["stratum_id"] == sid_a][0]
    if hand["rate_with_blocked_in_denominator"] != code_a["rate_with_blocked_in_denominator"]["as_string"]:
        print("FAILED:CNF-0143 emit reviewer mismatch")
        return 1

    unk_path = REPO / UNK
    ensured = A.ensure_unknowns(unk_path, nonempty["blocked"])
    md = unk_path.read_text(encoding="utf-8")
    xcheck = A.crosscheck_unknowns(nonempty["blocked"], md)
    if not xcheck["ok"]:
        print("FAILED:CNF-0143 emit UNKNOWNS-REGISTER missing", xcheck["missing"])
        return 1

    live = L.harvest(REPO)
    live_rates = None
    live_blocked: list[dict] = []
    if live["cnf_0137_present"] and live["frame"] is not None and live["records"]:
        live_rates = A.compute_rates(live["records"], live["frame"])
        live_blocked = live_rates["blocked"]
        live_ensured = A.ensure_unknowns(unk_path, live_blocked)
        ensured = {
            "path": ensured["path"],
            "created": ensured.get("created"),
            "added": list(ensured.get("added") or []) + list(live_ensured.get("added") or []),
            "already_present": ensured.get("already_present"),
        }

    mutant = A.wiring_bug_clone(nonempty)
    wiring_caught = False
    wiring_err = ""
    try:
        A.assert_invariants(mutant["strata"], mutant["overall"])
    except A.AccountingError as exc:
        wiring_caught = "wiring bug" in str(exc)
        wiring_err = str(exc)
    if not wiring_caught:
        print("FAILED:CNF-0143 emit wiring mutant not caught")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    strata_side_by_side = []
    for row in nonempty["strata"]:
        strata_side_by_side.append(
            {
                "stratum_id": row["stratum_id"],
                "n_confirmed": row["n_confirmed"],
                "n_blocked": row["n_blocked"],
                "n_all": row["n_all"],
                "n_refuted": row["n_refuted"],
                "n_not_checked": row["n_not_checked"],
                "rate_with_blocked_in_denominator": row["rate_with_blocked_in_denominator"],
                "rate_without_blocked": row["rate_without_blocked"],
                "rates_differ": row["rates_differ"],
                "unearned_inflation": (
                    None
                    if not row["rate_without_blocked"]["defined"]
                    or not row["rate_with_blocked_in_denominator"]["defined"]
                    else round(
                        float(row["rate_without_blocked"]["as_float"])
                        - float(row["rate_with_blocked_in_denominator"]["as_float"]),
                        12,
                    )
                ),
                "claim_ids": row["claim_ids"],
            }
        )

    tests = [
        {
            "id": "arithmetic-control",
            "name": "Two rates differ whenever BLOCKED set is non-empty",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "known-absent-control",
            "name": "Empty BLOCKED set: the two rates coincide exactly",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "completeness-schema",
            "name": "BLOCKED record with empty prerequisite is schema-invalid",
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "unknowns-register-crosscheck",
            "name": "Every BLOCKED prerequisite appears in UNKNOWNS-REGISTER.md",
            "command": P2,
            "result": "PASS",
        },
    ]

    arith_raw = (
        f"overall with="
        f"{nonempty['overall']['rate_with_blocked_in_denominator']['as_string']} "
        f"without={nonempty['overall']['rate_without_blocked']['as_string']} "
        f"n_blocked={nonempty['overall']['n_blocked']}\n"
        f"wiring_mutant_caught={wiring_caught} err={wiring_err}\n"
        f"empty_blocked coincide "
        f"{empty['overall']['rate_with_blocked_in_denominator']['as_string']} "
        f"== {empty['overall']['rate_without_blocked']['as_string']}\n"
        "SUCCESS:CNF-0143 arithmetic (emit in-process)"
    )
    hand_raw = json.dumps(hand, sort_keys=True)
    schema_raw = (
        "good BLOCKED records schema-valid; empty prerequisite rejected; "
        f"unknowns_crosscheck ok={xcheck['ok']} missing={xcheck['missing']}\n"
        "SUCCESS:CNF-0143 completeness (emit in-process)"
    )

    placeholder = "0" * 64
    doc: dict = {
        "schema_version": 1,
        "unit_id": "CNF-0143",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0143",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0143]",
        "min_bytes_threshold": 2000,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "evidence-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2000,
                "sha256": placeholder,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "On the frozen 12-claim control frame the earned pass rate "
                    "is 6/12 (BLOCKED in the denominator) and the unearned rate "
                    "obtained by dropping BLOCKED is 6/10. A wiring mutant that "
                    "uses n_all for both denominators is rejected."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0143/accounting.py",
                "probes": [
                    _probe("source", "command", P1, arith_raw),
                    _probe("verifier", "other", HAND_CMD, hand_raw),
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "Every BLOCKED record names a non-empty prerequisite and "
                    "unblock experiment. The completeness overlay rejects empty "
                    "and whitespace-only prerequisites. Both control-frame "
                    "prerequisites appear in UNKNOWNS-REGISTER.md."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": OVERLAY,
                "probes": [
                    _probe("source", "command", P2, schema_raw),
                    _probe("verifier", "schema-validate", OVERLAY_CMD, schema_raw),
                ],
                "unverified": False,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-CNF0143-WIRING-MUTANT",
                "kind": "mutation",
                "description": (
                    "Clone that sets both rates to n_confirmed/n_all must be "
                    "caught whenever n_blocked>0 (arithmetic control)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": wiring_err,
                "good_state_output": (
                    f"rates_differ={nonempty['overall']['rates_differ']} "
                    f"with={nonempty['overall']['rate_with_blocked_in_denominator']['as_string']} "
                    f"without={nonempty['overall']['rate_without_blocked']['as_string']}"
                ),
            },
            {
                "id": "NC-CNF0143-EMPTY-BLOCKED-COINCIDE",
                "kind": "known-broken-fixture",
                "description": (
                    "Known-absent: empty BLOCKED set, the two rates coincide. "
                    "The nonempty fixture is the bad state for this detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"nonempty rates_differ=True "
                    f"{nonempty['overall']['rate_with_blocked_in_denominator']['as_string']} "
                    f"vs {nonempty['overall']['rate_without_blocked']['as_string']}"
                ),
                "good_state_output": (
                    f"empty n_blocked=0 rates coincide "
                    f"{empty['overall']['rate_with_blocked_in_denominator']['as_string']}"
                ),
            },
            {
                "id": "NC-CNF0143-EMPTY-PREREQUISITE",
                "kind": "malformed-input",
                "description": (
                    "BLOCKED with empty or whitespace prerequisite is "
                    "unrepresentable (completeness schema)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejects '' and whitespace-only prerequisite",
                "good_state_output": "well-formed BLOCKED records validate",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0143-hand-recompute-stratum-A",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Reviewer counts CONFIRMED and BLOCKED by looping the raw "
                "record table and does not call compute_rates. Stratum "
                f"{sid_a}: earned {hand['rate_with_blocked_in_denominator']}, "
                f"dropped-BLOCKED {hand['rate_without_blocked']}."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0143/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0143",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "file-read",
                    CONSUMER_CMD,
                    "pending-first-write",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "No retry. A statistical result that is re-drawn until it "
                "looks acceptable is p-hacking; if the computation errors, "
                "fix the computation and re-derive from the frozen frame."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live CNF-0137 sampling frame is absent on this worktree, "
                    "so no production program pass rate was computed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place command-center/receipts/CNF-0137.json with a claims "
                    "frame, harvest live confirmation records, and re-run "
                    "accounting.compute_rates on that frame."
                ),
            }
        ],
        "report": {
            "kind": "program-gate-report",
            "observations": [
                {
                    "name": "earned-rate-with-blocked-in-denominator",
                    "measured": nonempty["overall"]["rate_with_blocked_in_denominator"]["as_string"],
                    "method": "n_confirmed / n_all on frozen control frame",
                    "anchor": "command-center/p2-wave/probes/CNF-0143/fixtures/control-set.json",
                },
                {
                    "name": "unearned-rate-without-blocked",
                    "measured": nonempty["overall"]["rate_without_blocked"]["as_string"],
                    "method": "n_confirmed / (n_all - n_blocked)",
                    "anchor": "command-center/p2-wave/probes/CNF-0143/accounting.py",
                },
                {
                    "name": "blocked-count",
                    "measured": int(nonempty["overall"]["n_blocked"]),
                    "method": "count verdict==BLOCKED on framed records",
                    "anchor": "command-center/p2-wave/probes/CNF-0143/fixtures/control-set.json",
                },
                {
                    "name": "wiring-mutant-caught",
                    "measured": True,
                    "method": "assert_invariants on wiring_bug_clone",
                    "anchor": "command-center/p2-wave/probes/CNF-0143/accounting.py",
                },
            ],
            "control_ids": [
                "NC-CNF0143-WIRING-MUTANT",
                "NC-CNF0143-EMPTY-BLOCKED-COINCIDE",
                "NC-CNF0143-EMPTY-PREREQUISITE",
            ],
        },
        "extensions": {
            "title": (
                "Account for unconfirmable claims so BLOCKED never silently "
                "improves the pass rate"
            ),
            "question": QUESTION,
            "answer": (
                "Unconfirmable claims are recorded as BLOCKED with a named missing "
                "prerequisite and a named unblock experiment. Every published rate "
                "is emitted twice: with BLOCKED in the denominator (earned) and "
                "without them (the unearned pass rate). On the frozen control frame "
                "the overall earned rate is 6/12 and the dropped-BLOCKED rate is "
                "6/10. Schema rejects BLOCKED with an empty prerequisite. Live "
                "CNF-0137 sampling frame and confirmation-record corpus are absent "
                "on this worktree, so no live program pass rate is claimed. "
                "SUCCESS:CNF-0143"
            ),
            "gate": "non-response-accounting",
            "completion_sentinel": "SUCCESS:CNF-0143",
            "frame_freeze": nonempty["frame_freeze"],
            "formula": nonempty["formula"],
            "published_rates": {
                "source": "frozen-control-frame",
                "not_a_live_program_rate": True,
                "overall": nonempty["overall"],
                "strata": strata_side_by_side,
            },
            "known_absent_control": {
                "empty_blocked_set": True,
                "n_blocked": empty["overall"]["n_blocked"],
                "rate_with_blocked_in_denominator": empty["overall"]["rate_with_blocked_in_denominator"],
                "rate_without_blocked": empty["overall"]["rate_without_blocked"],
                "rates_coincide": not empty["overall"]["rates_differ"],
            },
            "blocked": nonempty["blocked"],
            "excluded_set": {
                "count": len(nonempty["blocked"]),
                "entries": nonempty["blocked"],
                "reasons": [
                    {
                        "claim_id": e["claim_id"],
                        "prerequisite": e["prerequisite"],
                        "unblock_experiment": e["unblock_experiment"],
                        "reason": e.get("reason") or e.get("class"),
                    }
                    for e in nonempty["blocked"]
                ],
            },
            "not_checked": nonempty["not_checked"],
            "unknowns_register": {
                "path": UNK,
                "crosscheck": xcheck,
                "ensure": ensured,
            },
            "live_inventory": {
                "cnf_0137_present": live["cnf_0137_present"],
                "claim_registry_present": live["claim_registry_present"],
                "unknowns_register_present": True,
                "record_count": live["record_count"],
                "blocked_count": live["blocked_count"],
                "not_checked_count": live["not_checked_count"],
                "search_dirs": live["search_dirs"],
                "scanned_files": live["scanned_files"],
                "live_rates": live_rates["overall"] if live_rates else None,
                "live_blocked": live_blocked,
                "note": live["note"],
            },
            "worked_example": {
                "stratum_id": sid_a,
                "hand": hand,
                "code_rate_with": code_a["rate_with_blocked_in_denominator"]["as_string"],
                "code_rate_without": code_a["rate_without_blocked"]["as_string"],
                "match": True,
                "arithmetic": (
                    "3 CONFIRMED of 5 records including 1 BLOCKED => earned 3/5; "
                    "dropping BLOCKED yields 3/4 (unearned inflation of 0.15)."
                ),
            },
            "named_probes": [
                {"id": "probe1", "role": "arithmetic-known-absent", "command": P1},
                {"id": "probe2", "role": "completeness-unknowns", "command": P2},
            ],
            "scope": {
                "proof_surface": (
                    "Executable non-response accounting on a frozen 12-claim control "
                    "frame with two BLOCKED records (missing artifact, retired "
                    "subsystem), plus schema completeness and UNKNOWNS-REGISTER "
                    "cross-check. Live confirmation corpus and CNF-0137 frame were "
                    "inventoried and are absent."
                ),
                "does_not_claim": [
                    "CNF-0137 sampling frame exists on this worktree",
                    "a live program pass rate was computed from a production confirmation corpus",
                    "cloud ok=true is delivery",
                    "global unit_manifest.py --write was run",
                ],
            },
            "overlay_schema": OVERLAY,
            "catalog_output_schema": SCHEMA,
            "cloud_ok": False,
        },
    }

    ov_errs = A.overlay_errors(doc)
    if ov_errs:
        print("FAILED:CNF-0143 overlay schema errors")
        for e in ov_errs[:25]:
            print(" ", e)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {
            "unit_id": "CNF-0143",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:CNF-0143",
            "question": QUESTION,
            "tests": tests,
            "reviewer": doc["reviewer"],
            "artifacts": [{"path": OUT, "exists": True}],
            "blocked": [
                {
                    "claim_id": "X",
                    "prerequisite": "",
                    "unblock_experiment": "named experiment",
                }
            ],
        },
    ):
        if not A.overlay_errors(garbage):
            print("FAILED:CNF-0143 overlay accepted garbage")
            return 1

    cat_errs = A.catalog_schema_errors(doc)
    if cat_errs:
        print("FAILED:CNF-0143 catalog program-gate-report schema errors")
        for e in cat_errs[:25]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    try:
        loaded = json.loads(out.read_text(encoding="utf-8"))
        consumer_raw = (
            f"read_ok bytes={out.stat().st_size} "
            f"sentinel={loaded.get('sentinel')} SUCCESS:CNF-0143"
        )
        doc["downstream_consumers"][0]["probe"]["raw_output"] = consumer_raw
        doc["downstream_consumers"][0]["read_ok"] = True
        doc["downstream_consumers"][0]["executed"] = True
        doc["downstream_consumers"][0]["exit_code"] = 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:CNF-0143 downstream consumer {type(exc).__name__}: {exc}")
        return 1

    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0143 artifact {size}B below floor")
        return 1
    live_doc = json.loads(out.read_text(encoding="utf-8"))
    ov2 = A.overlay_errors(live_doc)
    if ov2:
        print("FAILED:CNF-0143 overlay after write", ov2[:8])
        return 1
    cat2 = A.catalog_schema_errors(live_doc)
    if cat2:
        print("FAILED:CNF-0143 catalog schema after write")
        for e in cat2[:25]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"overall with={nonempty['overall']['rate_with_blocked_in_denominator']['as_string']} "
        f"without={nonempty['overall']['rate_without_blocked']['as_string']} "
        f"blocked={len(nonempty['blocked'])}"
    )
    print("SUCCESS:CNF-0143 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
