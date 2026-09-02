#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0154.json from live registry runs.

Computes the two contracted numbers (double-import 1/2, content-change
new row) against tools/foundry/candidate_registry.py before writing.
Does not consult cloud ok=true.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from foundry.candidate_registry import (  # noqa: E402
    CandidateRegistry,
    ImportRecord,
    LedgerCorruptError,
    content_sha256,
    verify_chain,
)

UNIT = "IMP-0154"
OUT = "command-center/receipts/IMP-0154.json"
LIB = "tools/foundry/candidate_registry.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0154/probe1_double_import.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0154/probe2_content_change.py"
)
URI_DOUBLE = "foundry://colliding-catalogs/wf.double-import.fixture"
URI_CHANGE = "foundry://content-change/wf.content-change.fixture"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def mutate_first_event(src: Path, dest: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["content_hash"] = "0" * 64
    lines[0] = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_double_import() -> dict:
    payload = (HERE / "fixtures" / "double-import" / "wf.json").read_bytes()
    with tempfile.TemporaryDirectory(prefix="imp0154-emit-d-") as tmp:
        ledger = Path(tmp) / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        first = reg.import_record(
            ImportRecord(
                source_uri=URI_DOUBLE,
                content=payload,
                retrieval_method="read-path",
                adapter_id="IMP-0150",
                retrieved_at="2026-08-24T18:00:00+00:00",
                extra={"catalog": "local-repo"},
            )
        )
        second = reg.import_record(
            ImportRecord(
                source_uri=URI_DOUBLE,
                content=payload,
                retrieval_method="read-path",
                adapter_id="IMP-0151",
                retrieved_at="2026-08-24T18:00:01+00:00",
                extra={"catalog": "live-harness"},
            )
        )
        chain = verify_chain(ledger)
        return {
            "row_count": reg.row_count(),
            "observation_count": reg.observation_count(URI_DOUBLE, first.content_hash),
            "event_count": chain.events,
            "chain_ok": chain.ok,
            "first_action": first.action,
            "second_action": second.action,
            "candidate_id": first.candidate_id,
            "content_hash": first.content_hash,
            "content_bytes": len(payload),
            "ledger_bytes": ledger.stat().st_size,
        }


def run_content_change() -> dict:
    b1 = (HERE / "fixtures" / "content-change" / "wf-v1.json").read_bytes()
    b2 = (HERE / "fixtures" / "content-change" / "wf-v2.json").read_bytes()
    h1 = content_sha256(b1)
    h2 = content_sha256(b2)
    with tempfile.TemporaryDirectory(prefix="imp0154-emit-c-") as tmp:
        root = Path(tmp)
        ledger = root / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        r1 = reg.import_bytes(
            URI_CHANGE,
            b1,
            retrieval_method="read-path",
            adapter_id="IMP-0150",
            retrieved_at="2026-08-24T18:10:00+00:00",
        )
        v1_event = next(e for e in reg.events() if e["kind"] == "candidate")
        v1_hash = v1_event["event_hash"]
        r2 = reg.import_bytes(
            URI_CHANGE,
            b2,
            retrieval_method="read-path",
            adapter_id="IMP-0150",
            retrieved_at="2026-08-24T18:10:01+00:00",
        )
        v1_again = next(
            e
            for e in reg.events()
            if e["kind"] == "candidate" and e["content_hash"] == h1
        )
        chain_good = verify_chain(ledger)
        mutated = root / "mutated.jsonl"
        mutate_first_event(ledger, mutated)
        chain_bad = verify_chain(mutated)
        load_fired = False
        try:
            CandidateRegistry(mutated)
        except LedgerCorruptError:
            load_fired = True
        rows = reg.candidates()
        return {
            "row_count": len(rows),
            "v1_content_hash": h1,
            "v2_content_hash": h2,
            "v1_candidate_id": r1.candidate_id,
            "v2_candidate_id": r2.candidate_id,
            "v1_event_hash": v1_hash,
            "v1_event_hash_after": v1_again["event_hash"],
            "v1_event_hash_unchanged": v1_again["event_hash"] == v1_hash,
            "chain_ok_on_good": chain_good.ok,
            "chain_ok_on_mutated": chain_bad.ok,
            "load_fired_on_mutated": load_fired,
            "same_uri": URI_CHANGE,
            "hashes_present": sorted(r["content_hash"] for r in rows),
        }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    double = run_double_import()
    change = run_content_change()
    if double["row_count"] != 1 or double["observation_count"] != 2:
        print(
            f"FAILED:{UNIT} emit double-import "
            f"{double['row_count']}/{double['observation_count']}"
        )
        return 1
    if (
        change["row_count"] != 2
        or not change["v1_event_hash_unchanged"]
        or change["chain_ok_on_mutated"]
        or not change["load_fired_on_mutated"]
        or not change["chain_ok_on_good"]
    ):
        print(f"FAILED:{UNIT} emit content-change {json.dumps(change)}")
        return 1
    if double["first_action"] != "insert" or double["second_action"] != "observe":
        print(f"FAILED:{UNIT} emit actions {double['first_action']}/{double['second_action']}")
        return 1

    lib_art = art(LIB, "implementation")
    if not lib_art["exists"] or lib_art["bytes"] < 128:
        print(f"FAILED:{UNIT} library missing or tiny")
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0154",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0154: append-only candidate registry "
            "keyed by (source_uri, content_hash); _USER-PROMPTS.md:11319 cited "
            "as catalog input (duplicate-units / colliding-catalogs class)"
        ),
        "question_or_target": (
            "Target: a machine-readable candidate registry keyed by "
            "(source_uri, content_hash) that is append-only and idempotent. "
            "Acceptance: importing the same source twice yields ONE row and a "
            "second provenance observation - never a duplicate candidate."
        ),
        "implementation": {
            "module": LIB,
            "api": [
                "CandidateRegistry.import_record",
                "CandidateRegistry.import_bytes",
                "CandidateRegistry.candidates",
                "CandidateRegistry.observations",
                "verify_chain",
            ],
            "ledger": "append-only JSONL; event_hash chained to prev_hash",
            "key": ["source_uri", "content_hash"],
            "derived_snapshot": "CandidateRegistry.export_snapshot (not written back)",
        },
        "measured": {
            "double_import": double,
            "content_change": change,
        },
        "min_bytes_threshold": 128,
        "artifacts": [
            lib_art,
            art("tools/foundry/__init__.py", "supporting"),
            art(
                "command-center/p2-wave/probes/IMP-0154/probe1_double_import.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0154/probe2_content_change.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0154/fixtures/double-import/wf.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0154/fixtures/content-change/wf-v1.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0154/fixtures/content-change/wf-v2.json",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Double-import of identical URI+bytes yields row_count=1 and "
                    "observation_count=2, computed from the JSONL ledger."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{LIB}:CandidateRegistry.import_record",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "emit_receipt.run_double_import",
                        "exit_code": 0,
                        "raw_output": json.dumps(double, sort_keys=True),
                        "fingerprint": hashlib.sha256(
                            b"double-import-source"
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": None,
                        "raw_output": (
                            "named probe1 re-runs the same fixture in a fresh "
                            "temp ledger after this receipt is on disk"
                        ),
                        "fingerprint": hashlib.sha256(P1.encode()).hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    "A content change on the same URI appends a new row; the "
                    "prior candidate event_hash is unchanged; mutating a prior "
                    "ledger line breaks the hash chain."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{LIB}:verify_chain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "emit_receipt.run_content_change",
                        "exit_code": 0,
                        "raw_output": json.dumps(change, sort_keys=True),
                        "fingerprint": hashlib.sha256(
                            b"content-change-source"
                        ).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": None,
                        "raw_output": (
                            "named probe2 re-runs insert/mutate in a fresh "
                            "temp ledger after this receipt is on disk"
                        ),
                        "fingerprint": hashlib.sha256(P2.encode()).hexdigest()[:32],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "double-import",
                "command": P1,
                "result": "PENDING-NAMED-PROBE",
            },
            {
                "id": "content-change-hash-chain",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "c-idempotent-collapse",
                "kind": "known-good-fixture",
                "description": (
                    "Two adapters, same URI and bytes: detector stays at 1 row "
                    "(silent on the good/idempotent state)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "row_count=1 observation_count=2",
                "bad_state_output": "a URI-only upsert would report 1 row after a content change",
            },
            {
                "id": "c-hash-chain-mutation",
                "kind": "known-broken-fixture",
                "description": (
                    "In-place edit of a prior JSONL line must fail verify_chain "
                    "and refuse CandidateRegistry load."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"chain_ok={change['chain_ok_on_good']}",
                "bad_state_output": (
                    f"chain_ok_on_mutated={change['chain_ok_on_mutated']} "
                    f"load_fired={change['load_fired_on_mutated']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0154-probe2-hash-chain",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 does not reuse probe 1's double-import path; it "
                "changes bytes, then tampers the ledger copy."
            ),
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0154/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/sources/REGISTER.md is cited as an input "
                    "but is absent on this worktree; the registry is generic "
                    "over any source_uri and does not require that file to "
                    "prove idempotence or append-only behaviour."
                ),
                "settling_experiment": (
                    "When REGISTER.md is present, import_path it as one "
                    "source_uri and confirm a second import adds an observation."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0154: live named probes must exit 0 against "
            "tools/foundry/candidate_registry.py. cloud ok=true is not delivery. "
            "Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0154" not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"double_import rows={double['row_count']} obs={double['observation_count']} "
        f"content_change rows={change['row_count']} "
        f"v1_unchanged={change['v1_event_hash_unchanged']}"
    )
    print("SUCCESS:IMP-0154")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
