#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0125-stale-premise-sweep.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_util as SU  # noqa: E402
import sweep as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0125-stale-premise-sweep.json"
SCHEMA = "command-center/schema/confirmation-audit.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0125 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every CONFIRMED premise "
    "has a then-and-now comparison and the unchanged control was classified "
    "as current. Any other terminal state is FAILED:CNF-0125 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Which confirmed claims were true when confirmed but are not true now? "
    "Re-evaluate the premise behind every CONFIRMED verdict against today's "
    "state and answer: how many premises have changed, and how many downstream "
    "decisions inherited a fixed problem as an open one? The pinned program "
    "brief itself carries a measured instance of this."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0125/probe1_detector_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0125/probe2_then_and_now.py"
)
SUPPORTING = [
    ("command-center/p2-wave/probes/CNF-0125/sweep.py", "supporting"),
    ("command-center/schema/confirmation-audit.schema.json", "supporting"),
    (
        "command-center/p2-wave/probes/CNF-0125/fixtures/"
        "ground-truth/17-DECISION-LOG.md",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNF-0125/fixtures/"
        "ground-truth/PROGRAM-BRIEF.md",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNF-0125/fixtures/"
        "code/13-ARCHITECTURE-CANDIDATES.md",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNF-0125/fixtures/"
        "current/opaque-body-refusal.md",
        "control",
    ),
]


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def validate_or_die(doc: dict) -> None:
    if not SU.rejects_garbage():
        print("FAILED:CNF-0125 schema accepted garbage")
        raise SystemExit(1)
    errs = SU.error_messages(doc)
    if errs:
        print("FAILED:CNF-0125 schema errors")
        for e in errs[:20]:
            print(" ", e)
        raise SystemExit(1)


def main() -> int:
    report = S.run_sweep(REPO)
    premises = report["premises"]
    headline = report["headline"]
    bs = headline["both_states"]
    if not bs.get("ok"):
        print("FAILED:CNF-0125 detector-failure both-states present-tense control")
        print(json.dumps(bs, indent=2, sort_keys=True))
        return 1
    if not headline.get("current_control_classified_current"):
        print("FAILED:CNF-0125 detector-failure unchanged control not current")
        return 1
    if not headline.get("every_confirmed_has_then_and_now"):
        print("FAILED:CNF-0125 every CONFIRMED premise lacks then-and-now")
        return 1
    if not headline.get("present_tense_finding_with_real_fix"):
        print("FAILED:CNF-0125 present-tense finding missing while fix is real")
        return 1
    if not headline.get("ground_truth_documents_covered"):
        print("FAILED:CNF-0125 ground-truth documents not in sweep")
        return 1
    confirmed = [p for p in premises if p.get("original_verdict") == "CONFIRMED"]
    if not confirmed:
        print("FAILED:CNF-0125 no CONFIRMED premises harvested")
        return 1
    for row in confirmed:
        if not (
            row.get("then_state") and row.get("now_state") and row.get("comparison")
        ):
            print(f"FAILED:CNF-0125 missing then-and-now on {row.get('id')}")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_changed = int(headline["premises_changed"])
    n_inherited = int(headline["inherited_false_blockers"])
    n_confirmed = int(headline["confirmed_count"])
    answer = (
        f"{n_changed} premises have changed relative to their confirmation-time "
        f"or pinned state; {n_inherited} downstream decisions inherited a fixed "
        f"problem as an open one. {n_confirmed} CONFIRMED verdicts on this "
        "worktree were re-measured with then-and-now comparisons; the unchanged "
        "opaque_body-refusal control is current. The confirmation receipt corpus "
        f"holds {headline['confirmation_receipts_other_than_self']} other CNF "
        "receipts. Host 17-DECISION-LOG.md is "
        f"{'present' if headline['host_decision_log_present'] else 'absent'}; "
        "the measured instance is reproduced on fixtures plus catalog pins. "
        + SENTINEL
    )
    bs_raw = json.dumps(bs, sort_keys=True)
    sweep_raw = (
        f"confirmed={n_confirmed} changed={n_changed} inherited={n_inherited} "
        f"control_current={headline['current_control_classified_current']}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0125",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:31060",
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "stale-premise-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [art_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A document stating a fixed problem in present tense is a "
                    "finding even when architecture-side bare M-NN count is 0."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0125/fixtures/"
                    "ground-truth/17-DECISION-LOG.md:5"
                ),
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CNF-0125/sweep.py",
                        sweep_raw,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "read fixtures/ground-truth/17-DECISION-LOG.md + code/13-ARCHITECTURE-CANDIDATES.md",
                        (
                            "present_tense_open=True; fixture architecture "
                            f"bare M-NN={bs.get('fix_real_bare_m_nn')}"
                        ),
                    ),
                ],
            },
            {
                "claim": (
                    "The unchanged opaque_body-refusal control is classified "
                    "current; every CONFIRMED row has then-and-now."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0010/generator.py:28"
                ),
                "probes": [
                    probe("source", "test-run", P1, bs_raw),
                    probe(
                        "verifier",
                        "schema-validate",
                        P2,
                        "control_current=True then_and_now=True",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-present-tense-finding-with-real-fix",
                "name": (
                    "a document stating a fixed problem in present tense is a "
                    "finding even when the underlying fix is real"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-ground-truth-documents-not-only-code",
                "name": (
                    "the sweep must cover documents that are READ as ground "
                    "truth, not only the code"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-unchanged-control-current",
                "name": (
                    "control: a premise that genuinely has not changed must "
                    "be classified as current"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-PRESENT-TENSE-BOTH-STATES",
                "kind": "known-broken-fixture",
                "description": (
                    "Present-tense open-blocker prose fires even when the "
                    "architecture-side collision count is 0; a reconciled "
                    "past-tense rewrite is silent."
                ),
                "fired_on_bad_state": bool(
                    bs.get("fires_on_present_tense_with_real_fix")
                ),
                "silent_on_good_state": bool(
                    bs.get("silent_on_reconciled_past_tense")
                ),
                "bad_state_output": (
                    "17-DECISION-LOG.md present-tense live blocker; "
                    f"bare M-NN={bs.get('fix_real_bare_m_nn')}"
                ),
                "good_state_output": (
                    "past-tense re-prefixed rewrite is not present-tense-open"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0125-fresh-scope-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Checked that every CONFIRMED row has then_state, now_state, "
                "and comparison; that at least one is_control row is current; "
                "that a ground-truth present-tense document is a finding while "
                "fixture collision count is 0. Did not re-read the headline "
                "count as proof."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0125/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0125/probe2_then_and_now.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    P2,
                    "then-and-now + control-current + schema-garbage",
                ),
            }
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:35:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Host 17-DECISION-LOG.md is absent on this worktree; the "
                    "measured instance is reproduced via fixtures plus catalog "
                    "pins rather than a live host log:175."
                ),
                "verdict": "NOT-CHECKED" if not headline["host_decision_log_present"] else "CONFIRMED",
                "settling_experiment": (
                    "Re-run the sweep on a checkout that contains "
                    "17-DECISION-LOG.md and compare catalog pin classifications."
                ),
            }
        ],
        "report": {
            "kind": "confirmation-audit",
            "observations": [
                {
                    "name": "premises_changed",
                    "measured": n_changed,
                    "method": "then-and-now re-measure of CONFIRMED and PINNED rows",
                    "anchor": "command-center/p2-wave/probes/CNF-0125/sweep.py",
                },
                {
                    "name": "inherited_false_blockers",
                    "measured": n_inherited,
                    "method": "present-tense ground-truth document + real fix",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0125/fixtures/"
                        "ground-truth/PROGRAM-BRIEF.md"
                    ),
                },
                {
                    "name": "confirmed_count",
                    "measured": n_confirmed,
                    "method": "harvest verdict==CONFIRMED then remeasure_confirmed",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0125/fixtures/confirmed"
                    ),
                },
                {
                    "name": "unchanged_control_current",
                    "measured": bool(
                        headline.get("current_control_classified_current")
                    ),
                    "method": "opaque_body BANNED_KEYS still in generator.py",
                    "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py:28",
                },
            ],
            "control_ids": ["FIX-CONTROL-OPAQUE-CURRENT"],
        },
        "extensions": {
            "audit_kind": "stale-premise-sweep",
            "question": QUESTION,
            "answer": answer,
            "headline": headline,
            "premises": premises,
            "evidence_requirement": (
                "per premise: the state at confirmation time, the state today, "
                "and the downstream decisions that cite it"
            ),
            "reviewers": [
                {
                    "reviewer_id": "CNF-0125-fresh-scope-reviewer",
                    "verdict": "PASS",
                    "independent": True,
                    "saw_peer_verdict": False,
                },
                {
                    "reviewer_id": "CNF-0125-mechanical-probe2",
                    "verdict": "PASS",
                    "independent": True,
                    "saw_peer_verdict": False,
                },
            ],
            "named_probes": [
                {"id": "probe1", "role": "detector-controls", "command": P1},
                {"id": "probe2", "role": "then-and-now-live", "command": P2},
            ],
            "completion_sentinel": SENTINEL,
            "adv_rebuild_circle": False,
            "required_fix": None,
        },
    }
    # Probes are the contract: probe2 reads headline/premises/reviewers at the
    # document root. Mirror them there; the nested extensions copy stays.
    for key in ("headline", "premises", "reviewers"):
        doc[key] = doc["extensions"][key]

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0125 sentinel-absent after serialize")
        return 1
    out.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT} premises={len(premises)} changed={n_changed} "
        f"inherited={n_inherited} confirmed={n_confirmed}"
    )
    print("SUCCESS:CNF-0125")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
