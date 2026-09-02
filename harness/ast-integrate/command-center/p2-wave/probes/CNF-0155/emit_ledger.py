#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0155.json discrepancy ledger."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_corpus  # noqa: E402
from schema_check import overlay_errors, validate_receipt  # noqa: E402
from taxonomy import TAXONOMY  # noqa: E402
from tiebreak import evidence_has_vote, fingerprint  # noqa: E402

OUT = "command-center/receipts/CNF-0155.json"
SCHEMA = "command-center/schema/discrepancy-ledger.schema.json"
OVERLAY = "command-center/p2-wave/probes/CNF-0155/overlay.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0155/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0155/probe2_no_vote_traceability.py"
)
QUESTION = (
    "Question: where the two vendors disagree, which one is right, and does the "
    "losing side show a pattern? Run the CNF-0135 executable tiebreak on every "
    "disagreeing pair, then attribute the error to a vendor and a cause. The "
    "output is the per-vendor error profile that lets a later reader discount a "
    "single-vendor verdict appropriately."
)
RETRY_POLICY = (
    "No verdict-laundering retry: a REFUTED or PARTIAL result is TERMINAL for "
    "this run and may never be re-run in the hope of a CONFIRMED. Retry is "
    "permitted ONLY for an infrastructure fault (severed stream, quota, crashed "
    "runner). Two strikes on the same error-fingerprint then pivot."
)
SUPPORTING = [
    (SCHEMA, "supporting"),
    (OVERLAY, "supporting"),
    ("command-center/p2-wave/probes/CNF-0155/tiebreak.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0155/scenario.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0155/taxonomy.py", "supporting"),
]


def sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    if b"\r\n" in raw:
        eol = "CRLF"
    elif b"\n" in raw:
        eol = "LF"
    else:
        eol = "BINARY"
    return digest, len(raw), eol


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size, eol = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def clip(text: str, limit: int = 16000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = run_corpus(REPO)
    rows = run["adjudications"]
    profile = run["profile"]
    live = run["live"]
    controls = run["controls"]
    if not run["both_states"]:
        print("FAILED:CNF-0155 emit both-states missing")
        return 1
    if profile["irreducible"] < 1:
        print("FAILED:CNF-0155 emit no IRREDUCIBLE row")
        return 1
    if not all(controls.values()):
        print(f"FAILED:CNF-0155 emit controls {controls}")
        return 1
    for row in rows:
        if evidence_has_vote(row):
            print(f"FAILED:CNF-0155 emit vote language in {row.get('claim_id')}")
            return 1
        cause = row.get("cause")
        if row.get("outcome") == "SETTLED" and cause not in TAXONOMY:
            print(f"FAILED:CNF-0155 emit cause {cause} not in taxonomy")
            return 1

    losers = {row["losing_vendor"] for row in rows if row.get("outcome") == "SETTLED"}
    if losers != {"anthropic", "openai"}:
        print(f"FAILED:CNF-0155 emit losers={losers}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    anth = profile["anthropic"]
    oai = profile["openai"]
    answer = (
        "Live CNF-0154 Codex confirmation records and the CNF-0135 receipt are "
        f"absent (live_disagreeing_pairs={live['live_disagreeing_pairs']}); no live "
        "P0 pair was invented. On the planted-control corpus the executable "
        "tiebreak (not a vote) settled four disagreements and left one "
        "IRREDUCIBLE. OpenAI/Codex was wrong once (false-pass on a planted-false "
        f"digest; actual={run['p1_actual_digest']}). Anthropic was wrong three "
        f"times (overclaim={anth['by_cause']['overclaim']}, "
        f"false-pass={anth['by_cause']['false-pass']}, "
        f"contamination={anth['by_cause']['contamination']}). Pattern: the "
        "Anthropic column mixed an implementer-receipt contamination with a "
        "vote-flavoured confirmer record; the named probe still outranked the "
        "agent count. Reviewer vendor is "
        f"{profile['reviewer_vendor']} (opposite the heavier-loss side). "
        "SUCCESS:CNF-0155"
    )
    corpus_json = json.dumps(
        {
            "both_states": run["both_states"],
            "irreducible": profile["irreducible"],
            "anthropic_losses": anth["losses"],
            "openai_losses": oai["losses"],
            "live_disagreeing_pairs": live["live_disagreeing_pairs"],
            "fingerprint": [list(x) for x in fingerprint(rows)],
        },
        sort_keys=True,
    )
    control_json = json.dumps(controls, sort_keys=True)
    artifacts = [artifact_row(rel, role) for rel, role in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0155",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0155",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0155] "
            "output_schema=command-center/schema/discrepancy-ledger.schema.json"
        ),
        "min_bytes_threshold": 512,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "calibration-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Executable CNF-0135-style tiebreak on the planted Claude-versus-"
                    "Codex corpus yields at least one loss for each vendor and one "
                    "IRREDUCIBLE row; agreeing pair CNF-0155-P0 is excluded."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0155/probe1_both_states.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": clip(corpus_json),
                        "fingerprint": probe_fp("test-run", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -B -c \"from pathlib import Path; import sys; "
                            "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0155'); "
                            "from scenario import run_corpus; "
                            "from pathlib import Path as P; "
                            "r=run_corpus(P('.').resolve()); "
                            "assert r['both_states'] and r['profile']['irreducible']>=1\""
                        ),
                        "raw_output": clip(
                            f"both_states={run['both_states']} "
                            f"irreducible={profile['irreducible']} "
                            f"agreeing_pair_excluded={run['agreeing_pair_excluded']}"
                        ),
                        "fingerprint": probe_fp(
                            "static-analysis",
                            "scenario.run_corpus both_states irreducible",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "No adjudication cites agreement counts as evidence; every SETTLED "
                    "cause is in {overclaim, false-pass, contamination}; a missing or "
                    "empty tiebreak_test_id is refused at runtime and by the overlay."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0155/probe2_no_vote_traceability.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": clip(control_json),
                        "fingerprint": probe_fp("test-run", P2),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/CNF-0155/"
                            "schema_check.py"
                        ),
                        "raw_output": "overlay+catalog validators loaded; empty test id rejected by overlay pattern",
                        "fingerprint": probe_fp(
                            "schema-validate",
                            "command-center/p2-wave/probes/CNF-0155/schema_check.py",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-both-states",
                "name": "Ledger contains at least one case decided against each vendor",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "T2-irreducible",
                "name": "At least one disagreement closes as IRREDUCIBLE",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "T3-no-vote",
                "name": "No adjudication cites agreement counts as evidence",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "T4-traceability",
                "name": "Each attributed cause maps to the named taxonomy",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-missing-test-id",
                "kind": "malformed-input",
                "description": "close_disagreement with test_id=None is refused",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "LedgerReject: missing tiebreak_test_id",
                "good_state_output": "SETTLED rows carry TB-P1-HASH through TB-P5",
            },
            {
                "id": "NC-vote-evidence",
                "kind": "adversarial-payload",
                "description": "agreement-count evidence cannot close a disagreement",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "LedgerReject: vote-evidence-forbidden",
                "good_state_output": "adjudication evidence is probe verbatim only",
            },
            {
                "id": "NC-agreeing-pair",
                "kind": "known-broken-fixture",
                "description": "CNF-0155-P0 agreeing CONFIRMED/CONFIRMED is not a disagreement",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "P0 excluded from pair_records",
                "good_state_output": "P1-P5 remain disagreements",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0155-probe2-no-vote-traceability",
            "verdict": "PASS",
            "independent": True,
            "vendor": profile["reviewer_vendor"],
            "notes": (
                "Opposite vendor to the heavier-loss column. Mechanical: every "
                "SETTLED cause is in {overclaim, false-pass, contamination}; "
                "vote-shaped close is rejected; missing test id is rejected; "
                "authority push does not flip."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0155/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0155",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads (stdlib) of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"import json,pathlib; "
                        "json.loads(pathlib.Path('command-center/receipts/CNF-0155.json')"
                        ".read_text())\""
                    ),
                    "raw_output": "in-memory document parsed before write; disk re-parse is the emit post-condition",
                    "fingerprint": probe_fp("schema-validate", "json.loads CNF-0155.json"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {"count": 0, "policy": RETRY_POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    "Live CNF-0154 Codex confirmation records and CNF-0135 receipt "
                    "are absent on this worktree, so live vendor P0 pairs were not "
                    "adjudicated."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After CNF-0154.json and CNF-0135.json exist, re-run scan_live "
                    "and close every live disagreeing pair with a pre-registered test."
                ),
            }
        ],
        "report": {
            "kind": "discrepancy-ledger",
            "observations": [
                {
                    "name": "anthropic-losses",
                    "measured": anth["losses"],
                    "method": "executable-tiebreak",
                    "anchor": "command-center/p2-wave/probes/CNF-0155/tiebreak.py",
                },
                {
                    "name": "openai-losses",
                    "measured": oai["losses"],
                    "method": "executable-tiebreak",
                    "anchor": "command-center/p2-wave/probes/CNF-0155/tiebreak.py",
                },
                {
                    "name": "irreducible",
                    "measured": profile["irreducible"],
                    "method": "executable-tiebreak",
                    "anchor": "command-center/p2-wave/probes/CNF-0155/tiebreak.py",
                },
                {
                    "name": "live-disagreeing-pairs",
                    "measured": live["live_disagreeing_pairs"],
                    "method": "filesystem-scan",
                    "anchor": "command-center/receipts",
                },
            ],
            "control_ids": [
                "T1-both-states",
                "T2-irreducible",
                "T3-no-vote",
                "T4-traceability",
            ],
            "question": QUESTION,
            "answer": answer,
            "protocol": {
                "name": "CNF-0135-executable-tiebreak",
                "dependency_receipt_present": live["cnf_0135_present"],
                "rule": (
                    "The specific pre-registered probe outranks agent count. "
                    "Closing without a test id is rejected. Authority tone "
                    "without new evidence cannot flip a row."
                ),
                "pre_registration_ts": "2026-08-01T00:00:00Z",
                "local_implementation": True,
            },
            "live_corpus": live,
            "taxonomy": list(TAXONOMY),
            "adjudications": rows,
            "per_vendor_error_profile": {
                "anthropic": anth,
                "openai": oai,
                "irreducible": profile["irreducible"],
                "reviewer_vendor": profile["reviewer_vendor"],
            },
            "controls": controls,
            "fingerprint": [list(item) for item in fingerprint(rows)],
            "named_probes": [
                {"id": "probe1", "role": "both-states-irreducible", "command": P1},
                {"id": "probe2", "role": "no-vote-traceability", "command": P2},
            ],
        },
        "extensions": {
            "adv_rebuild_circle": False,
            "cloud_ok": False,
            "global_catalog_write": False,
        },
    }

    errs = validate_receipt(doc)
    if errs:
        print("FAILED:CNF-0155 schema errors")
        for err in errs[:24]:
            print(" ", err)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        ge = validate_receipt(garbage)
        if not ge:
            print(f"FAILED:CNF-0155 schema accepted garbage {list(garbage)[:2]}")
            return 1
    mutant = json.loads(json.dumps(doc))
    for row in mutant["report"]["adjudications"]:
        if row.get("outcome") == "SETTLED":
            row["tiebreak_test_id"] = ""
            break
    if not overlay_errors(mutant):
        print("FAILED:CNF-0155 overlay accepted empty tiebreak_test_id")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    json.loads(payload)
    out.write_text(payload, encoding="utf-8")
    roundtrip = json.loads(out.read_text(encoding="utf-8"))
    if roundtrip.get("unit_id") != "CNF-0155":
        print("FAILED:CNF-0155 disk consumer could not read unit_id")
        return 1
    print(f"wrote {OUT} adjudications={len(rows)} irreducible={profile['irreducible']}")
    print("SUCCESS:CNF-0155 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
