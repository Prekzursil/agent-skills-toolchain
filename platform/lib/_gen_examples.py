"""Generate the two durable example receipts used as CLI proof and as fixtures.

  receipt.valid.example.json      - must PASS schema + all 12 conditions
  receipt.malformed.example.json  - must be REJECTED, and must fail loudly

The valid example points at a small dedicated artifact this unit owns
(sample-artifact.json) rather than at a file other agents are also writing, so
its sha256 does not false-alarm when a sibling touches the tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EX = REPO / "platform" / "schema" / "examples"
EX.mkdir(parents=True, exist_ok=True)

ART_REL = "platform/schema/examples/sample-artifact.json"
art = REPO / ART_REL

# Written as a SINGLE LINE with NO newline bytes, deliberately.
#
# This repo has core.autocrlf=true and .gitattributes declares no rule for
# *.json, so a text file's working-tree bytes are CRLF on Windows while its blob
# (and any Linux checkout) is LF. A sha256 recorded over one form fails
# condition 3 against the other, which is the CRLF-vs-blob trap. A payload with
# zero newline bytes is invariant under EOL conversion, so this artifact's hash
# is stable on every platform without needing a .gitattributes change (that file
# is repo-wide governance and is not this unit's to edit).
payload = json.dumps(
    {
        "note": "Dedicated fixture artifact for receipt.valid.example.json.",
        "why": "A receipt must point at bytes that really exist; the reducer re-hashes this file.",
        "newlines": "none, on purpose: makes the recorded sha256 invariant under CRLF/LF conversion",
        "padding": "x" * 2048,
    },
    separators=(",", ":"),
)
assert "\n" not in payload and "\r" not in payload, "fixture must stay newline-free"
art.write_bytes(payload.encode("utf-8"))
raw = art.read_bytes()
assert b"\n" not in raw and b"\r" not in raw, "fixture on disk must stay newline-free"

valid = {
    "schema_version": 1,
    "unit_id": "IMP-0001",
    "state": "SUCCESS",
    "sentinel": "SUCCESS:IMP-0001",
    "spec_anchor": "_USER-PROMPTS.md:10631-10644",
    "min_bytes_threshold": 1024,
    "artifacts": [
        {
            "path": ART_REL,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ],
    "evidence": [
        {
            "claim": "All 14 $defs fragments the catalog references by JSON pointer resolve.",
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "platform/lib/_probe_schema_selfcheck.py:1",
            "probes": [
                {
                    "role": "source",
                    "method": "schema-validate",
                    "command": "python platform/lib/_probe_schema_selfcheck.py",
                    "raw_output": "[PASS] all 14 catalog fragments resolve :: []",
                    "fingerprint": "selfcheck:fragments",
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "static-analysis",
                    "command": "python -c \"import json;print(sorted(json.load(open('platform/schema/receipt.schema.json'))['$defs']))\"",
                    "raw_output": "14 referenced names all present in $defs",
                    "fingerprint": "defs-keys:enumerate",
                    "exit_code": 0,
                },
            ],
        },
        {
            "claim": "The suite protects the schema: 21/22 mutations turn it red, 1 proved equivalent, 0 unexplained survivors.",
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "platform/lib/_probe_mutation_battery.py:1",
            "probes": [
                {
                    "role": "source",
                    "method": "test-run",
                    "command": "python -m pytest platform/lib/test_receipt_schema_gate.py -q",
                    "raw_output": "59 passed",
                    "fingerprint": "pytest:full-suite",
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "command",
                    "command": "python platform/lib/_probe_mutation_battery.py",
                    "raw_output": "mutations: 22  killed: 21  equivalent: 1  survived: 0",
                    "fingerprint": "mutation:battery",
                    "exit_code": 0,
                },
            ],
        },
    ],
    "tests": [
        {
            "id": "T-SUITE",
            "name": "receipt schema + predicate conformance suite",
            "command": "python -m pytest platform/lib/test_receipt_schema_gate.py -q",
            "result": "PASS",
            "assertions": 59,
            "duration_seconds": 1.28,
        }
    ],
    "negative_controls": [
        {
            "id": "NC-MALFORMED",
            "kind": "malformed-input",
            "description": "receipt.malformed.example.json must be rejected by the schema.",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "FAILED:IMP-0002 schema-invalid",
            "good_state_output": "SUCCESS:IMP-0001",
        },
        {
            "id": "NC-MUTATION",
            "kind": "mutation",
            "description": "22 deliberate weakenings of the schema/reducer; each must turn the suite red.",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "21 KILLED, 1 EQUIVALENT (proved), 0 SURVIVED",
            "good_state_output": "[CONTROL] unmutated suite rc=0 :: 59 passed",
        },
    ],
    "reviewer": {
        "reviewer_id": "PENDING-INDEPENDENT-REVIEW",
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "unassigned",
        "notes": "EXAMPLE FIXTURE ONLY. This reviewer block is illustrative: no independent reviewer has audited this example. A real receipt must name a real reviewer.",
    },
    "defects": [],
    "manifest_registration": {
        "registered": True,
        "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        "entry_id": "IMP-0001",
    },
    "downstream_consumers": [
        {
            "consumer": "platform/lib/receipt_schema_gate.py (evaluate_gate_a)",
            "artifact_path": ART_REL,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": {
                "role": "verifier",
                "method": "command",
                "command": "python platform/lib/receipt_schema_gate.py platform/schema/examples/receipt.valid.example.json --repo-root .",
                "raw_output": "SUCCESS:IMP-0001 with 12/12 conditions SATISFIED",
                "fingerprint": "cli:gate-a",
                "exit_code": 0,
            },
        }
    ],
    "timestamps": {
        "started_at": "2026-08-09T22:20:00Z",
        "ended_at": "2026-08-09T22:55:00Z",
        "duration_seconds": 2100,
    },
    "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
    "residual_unknowns": [
        {
            "claim": "No independent reviewer has audited this schema; the reviewer block above is illustrative.",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "Dispatch a fresh-context adversarial reviewer over platform/schema/receipt.schema.json and record its verdict here.",
        },
        {
            "claim": "The 2,007 units declare command-center/schema/receipt.schema.json; this file lives at platform/schema/.",
            "verdict": "CONFIRMED",
            "settling_experiment": "Resolved by deploying/copying to the declared path, or by rewriting output_schema across the catalog. Owner decision.",
        },
    ],
    "produced_by": {
        "vendor": "anthropic",
        "model": "opus",
        "role": "implementer",
        "execution_substrate": "local-windows-pwsh7",
    },
}

# Deliberately broken, EIGHT ways at once. Each defect is annotated so a reader
# can check the validator reports it rather than trusting the count.
malformed = {
    "schema_version": 2,
    "unit_id": "imp-2",
    "state": "probably done",
    "sentinel": "all good, ship it",
    "spec_anchor": "",
    "min_bytes_threshold": 0,
    "artifacts": [
        {"path": "platform\\schema\\does-not-exist.json", "bytes": 0, "sha256": "deadbeef", "exists": False}
    ],
    "evidence": [
        {
            "claim": "it works",
            "verdict": "probably",
            "anchor": "",
            "probes": [],
        }
    ],
    "tests": [{"id": "t", "command": "pytest", "result": "mostly passing"}],
    "negative_controls": [],
    "reviewer": {"reviewer_id": "self", "verdict": "PASS", "independent": False},
    "defects": [{"id": "D-0", "severity": "P0", "status": "open", "summary": "rce in the loader"}],
    "manifest_registration": {"registered": False, "manifest_path": "nope.json"},
    "downstream_consumers": [],
    "timestamps": {"started_at": "yesterday", "ended_at": "2026-08-09T20:00:00"},
    "retry": {"count": -3, "policy": ""},
    "surprise_field": "additionalProperties must reject this",
}

(EX / "receipt.valid.example.json").write_text(json.dumps(valid, indent=2) + "\n", encoding="utf-8")
(EX / "receipt.malformed.example.json").write_text(json.dumps(malformed, indent=2) + "\n", encoding="utf-8")
print(f"wrote {ART_REL} ({len(raw)} B, sha256={hashlib.sha256(raw).hexdigest()[:16]}...)")
print("wrote platform/schema/examples/receipt.valid.example.json")
print("wrote platform/schema/examples/receipt.malformed.example.json")
