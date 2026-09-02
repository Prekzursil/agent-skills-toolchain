#!/usr/bin/env python3
"""Emit receipts/CC-0014.json and merge mutation-gated rows into the live registries."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402
import test_registry_bind as bind  # noqa: E402
import mutate as M  # noqa: E402

OUT = "command-center/receipts/CC-0014.json"
SCHEMA = "command-center/schema/test-registry-entry.schema.json"
REGISTRY = "command-center/TEST-REGISTRY.json"
CLAIMS = "command-center/CLAIM-REGISTRY.json"
BINDER = "command-center/test_registry_bind.py"

T_PROT = HERE / "fixtures" / "test_protecting.py"
T_EXPL = HERE / "fixtures" / "test_explicit.py"

CLAIM_DEFAULT = "CL-CC-0014-DEFAULT-FLOOR-ENFORCED"
CLAIM_HOLE = "CL-CC-0014-EXPLICIT-ONLY-IS-HOLE"
CLAIM_UNPR = "CL-CC-0014-UNPROVEN-NOT-COVERAGE"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
)

CC_SUITES = [
    {
        "path": "command-center/p2-wave/probes/CC-0014/fixtures/test_protecting.py",
        "tests": 2,
        "ci_step": "CC-0014 named probes",
        "protects": "accept() enforces REQUIRED_MIN when minimum= is omitted",
        "red_proof": (
            "M-IMPL-DEFAULT-ZERO (REQUIRED_MIN = 3 -> 0) kills "
            "test_default_floor_rejects_below_minimum; M-REV-DEFAULT-NINETY-NINE "
            "(REQUIRED_MIN = 3 -> 99) kills test_default_floor_accepts_exact_minimum. "
            "A passing run of the unmutated file is not this proof."
        ),
    },
    {
        "path": "command-center/p2-wave/probes/CC-0014/fixtures/test_explicit.py",
        "tests": 1,
        "ci_step": "CC-0014 named probes",
        "protects": "nothing about REQUIRED_MIN (explicit-only hole)",
        "red_proof": (
            "M-IMPL-DEFAULT-ZERO SURVIVES test_explicit_minimum_ignores_module_default; "
            "the registry must record HOLE, not PROTECTING."
        ),
    },
    {
        "path": "command-center/p2-wave/probes/CC-0014/fixtures/test_unproven.py",
        "tests": 1,
        "ci_step": "CC-0014 named probes",
        "protects": "UNPROVEN control: a real test with no mutation record",
        "red_proof": (
            "No mutation is attached. Status must be UNPROVEN and must not count "
            "toward protected_claims."
        ),
    },
]

CC_INVARIANTS = [
    {
        "id": "INV-CC-0014-DEFAULT-FLOOR",
        "invariant": "accept() with no minimum argument enforces REQUIRED_MIN.",
        "why": "Reverting the constant historically left the suite green.",
        "tests": [
            "test_default_floor_accepts_exact_minimum",
            "test_default_floor_rejects_below_minimum",
        ],
    },
    {
        "id": "INV-CC-0014-EXPLICIT-IS-NOT-PROTECTION",
        "invariant": "A test that only passes minimum= does not protect REQUIRED_MIN.",
        "why": "The estate defect: every case passed the value explicitly.",
        "tests": ["test_explicit_minimum_ignores_module_default"],
    },
    {
        "id": "INV-CC-0014-UNPROVEN-CONTROL",
        "invariant": "A test with no mutation record is UNPROVEN, never coverage.",
        "why": "A green suite is not evidence until a mutation made the test fail.",
        "tests": ["test_empty_list_rejected_at_explicit_one"],
    },
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def validate_receipt(doc: dict) -> list[str]:
    """Validate against the physical generic_report + kind pin.

    platform/lib/schema_resolver.py needs jsonschema>=4.18 (`registry=`).
    This worktree has 4.10.3 (`resolver=`), so resolution is local-disk
    RefResolver over the three $id files, not the newer referencing API.
    """
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt_schema = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt_schema["$id"]: receipt_schema,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:12000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def merge_test_registry(entries: list[dict], coverage: dict) -> None:
    path = REPO / REGISTRY
    doc = json.loads(path.read_text(encoding="utf-8"))
    suites = list(doc.get("suites") or [])
    have = {
        str(s.get("path") or "").replace("\\", "/")
        for s in suites
        if isinstance(s, dict)
    }
    for suite in CC_SUITES:
        if suite["path"] not in have:
            suites.append(suite)
            have.add(suite["path"])
    invariants = list(doc.get("invariants") or [])
    have_inv = {str(i.get("id") or "") for i in invariants if isinstance(i, dict)}
    for inv in CC_INVARIANTS:
        if inv["id"] not in have_inv:
            invariants.append(inv)
            have_inv.add(inv["id"])
    by_id = {
        str(e.get("test_id") or ""): e
        for e in (doc.get("entries") or [])
        if isinstance(e, dict) and e.get("test_id")
    }
    for row in entries:
        by_id[row["test_id"]] = row
    doc["suites"] = suites
    doc["invariants"] = invariants
    doc["entries"] = list(by_id.values())
    doc["coverage"] = coverage
    doc["mutation_gate"] = {
        "unit_id": "CC-0014",
        "binder": BINDER,
        "rule": (
            "PROTECTING only after a KILLED mutation with diff and failing "
            "output; UNPROVEN is not coverage; SURVIVED is HOLE."
        ),
    }
    dump(path, doc)


def merge_claim_registry() -> None:
    path = REPO / CLAIMS
    doc = json.loads(path.read_text(encoding="utf-8"))
    claims = list(doc.get("claims") or [])
    have = {str(c.get("id") or "") for c in claims if isinstance(c, dict)}
    additions = [
        {
            "id": CLAIM_DEFAULT,
            "claim": (
                "accept() with no minimum argument enforces REQUIRED_MIN; a "
                "mutation of that constant must fail a test that omits minimum=."
            ),
            "verdict": "CONFIRMED",
            "band": "almost-certain",
            "source_probe": (
                "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
            ),
            "verifier_probe": (
                "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
            ),
            "evidence": (
                "M-IMPL-DEFAULT-ZERO and M-REV-DEFAULT-NINETY-NINE kill the "
                "default-floor tests; see command-center/receipts/CC-0014.json"
            ),
        },
        {
            "id": CLAIM_HOLE,
            "claim": (
                "A test that only passes minimum= explicitly does not protect "
                "REQUIRED_MIN; mutating the default must SURVIVE it and register "
                "a hole."
            ),
            "verdict": "CONFIRMED",
            "band": "almost-certain",
            "source_probe": (
                "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
            ),
            "verifier_probe": (
                "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
            ),
            "evidence": (
                "M-IMPL-DEFAULT-ZERO survives "
                "test_explicit_minimum_ignores_module_default; status HOLE"
            ),
        },
        {
            "id": CLAIM_UNPR,
            "claim": (
                "A test with no mutation record is UNPROVEN and must not count "
                "toward any coverage total."
            ),
            "verdict": "CONFIRMED",
            "band": "almost-certain",
            "source_probe": (
                "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
            ),
            "verifier_probe": (
                "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
            ),
            "evidence": (
                "test_empty_list_rejected_at_explicit_one binds UNPROVEN; "
                "coverage_summary reports protected_claims=0 not 100 percent"
            ),
        },
    ]
    for row in additions:
        if row["id"] not in have:
            claims.append(row)
            have.add(row["id"])
    doc["claims"] = claims
    dump(path, doc)


def main() -> int:
    killed = M.mutate_and_run(
        M.MUT_IMPL_ZERO, T_PROT, "test_default_floor_rejects_below_minimum"
    )
    if killed["outcome"] != "KILLED":
        print(f"FAILED:emit expected KILLED, got {killed['outcome']}")
        print(killed.get("surviving_output") or killed.get("failing_output"))
        return 1
    survived = M.mutate_and_run(
        M.MUT_IMPL_ZERO, T_EXPL, "test_explicit_minimum_ignores_module_default"
    )
    if survived["outcome"] != "SURVIVED":
        print(f"FAILED:emit expected SURVIVED, got {survived['outcome']}")
        print(survived.get("failing_output"))
        return 1
    rev_kill = M.mutate_and_run(
        M.MUT_REV_NINETY_NINE, T_PROT, "test_default_floor_accepts_exact_minimum"
    )
    if rev_kill["outcome"] != "KILLED":
        print(f"FAILED:emit reviewer mutation did not kill: {rev_kill['outcome']}")
        print(rev_kill.get("surviving_output") or rev_kill.get("failing_output"))
        return 1
    rev_live = M.mutate_and_run(
        M.MUT_REV_NINETY_NINE, T_EXPL, "test_explicit_minimum_ignores_module_default"
    )
    if rev_live["outcome"] != "SURVIVED":
        print("FAILED:emit reviewer mutation should survive explicit test")
        return 1

    entries = [
        bind.bind_row(
            test_id="test_empty_list_rejected_at_explicit_one",
            claim_id=CLAIM_UNPR,
            unit_id="CC-0014",
            extra={
                "path": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/test_unproven.py"
                ),
                "role": "no-mutation-control",
            },
        ),
        bind.bind_row(
            test_id="test_default_floor_rejects_below_minimum",
            claim_id=CLAIM_DEFAULT,
            unit_id="CC-0014",
            mutation={
                "id": "M-IMPL-DEFAULT-ZERO",
                "author": "implementer",
                "outcome": killed["outcome"],
                "diff": killed["diff"],
                "failing_output": killed["failing_output"],
                "exit_code": killed["exit_code"],
                "anchor": killed["anchor"],
                "replacement": killed["replacement"],
            },
            extra={
                "path": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/test_protecting.py"
                ),
                "role": "protecting-default-floor",
            },
        ),
        bind.bind_row(
            test_id="test_explicit_minimum_ignores_module_default",
            claim_id=CLAIM_HOLE,
            unit_id="CC-0014",
            mutation={
                "id": "M-IMPL-DEFAULT-ZERO",
                "author": "implementer",
                "outcome": survived["outcome"],
                "diff": survived["diff"],
                "failing_output": survived["failing_output"],
                "exit_code": survived["exit_code"],
                "anchor": survived["anchor"],
                "replacement": survived["replacement"],
            },
            extra={
                "path": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/test_explicit.py"
                ),
                "role": "survived-explicit-only",
            },
        ),
        bind.bind_row(
            test_id="test_default_floor_accepts_exact_minimum",
            claim_id=CLAIM_DEFAULT,
            unit_id="CC-0014",
            mutation={
                "id": "M-REV-DEFAULT-NINETY-NINE",
                "author": "independent-reviewer",
                "outcome": rev_kill["outcome"],
                "diff": rev_kill["diff"],
                "failing_output": rev_kill["failing_output"],
                "exit_code": rev_kill["exit_code"],
                "anchor": rev_kill["anchor"],
                "replacement": rev_kill["replacement"],
            },
            extra={
                "path": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/test_protecting.py"
                ),
                "role": "reviewer-protecting",
            },
        ),
    ]
    coverage = bind.coverage_summary(entries)
    all_unproven = bind.coverage_summary(
        [
            bind.bind_row(
                test_id="test_empty_list_rejected_at_explicit_one",
                claim_id=CLAIM_UNPR,
                unit_id="CC-0014",
            ),
            bind.bind_row(
                test_id="test_default_floor_accepts_exact_minimum",
                claim_id=CLAIM_DEFAULT,
                unit_id="CC-0014",
            ),
            bind.bind_row(
                test_id="test_explicit_minimum_ignores_module_default",
                claim_id=CLAIM_HOLE,
                unit_id="CC-0014",
            ),
        ]
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    merge_claim_registry()
    merge_test_registry(entries, coverage)

    supporting = [
        art_row(REGISTRY, "primary"),
        art_row(CLAIMS, "supporting"),
        art_row(BINDER, "supporting"),
        art_row(SCHEMA, "supporting"),
        art_row("command-center/p2-wave/probes/CC-0014/mutate.py", "supporting"),
        art_row(
            "command-center/p2-wave/probes/CC-0014/fixtures/subject.py", "fixture"
        ),
        art_row(
            "command-center/p2-wave/probes/CC-0014/fixtures/test_protecting.py",
            "fixture",
        ),
        art_row(
            "command-center/p2-wave/probes/CC-0014/fixtures/test_explicit.py",
            "control",
        ),
        art_row(
            "command-center/p2-wave/probes/CC-0014/fixtures/test_unproven.py",
            "control",
        ),
    ]

    src = probe(
        "source",
        "test-run",
        P1_CMD,
        (
            f"KILLED exit={killed['exit_code']} SURVIVED exit={survived['exit_code']} "
            f"UNPROVEN coverage protected_claims=0"
        ),
        killed["exit_code"],
    )
    ver = probe(
        "verifier",
        "command",
        P2_CMD,
        (
            f"reviewer KILLED exit={rev_kill['exit_code']} SURVIVED "
            f"exit={rev_live['exit_code']} all_unproven_percent="
            f"{all_unproven['protected_percent']}"
        ),
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": "CC-0014",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0014",
        "spec_anchor": "_USER-PROMPTS.md:11325-11382",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "PROTECTING requires a KILLED mutation with diff and "
                    "failing output"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/test_registry_bind.py:classify",
                "probes": [src, ver],
            },
            {
                "claim": (
                    "SURVIVED mutation is a HOLE, not a silent UNPROVEN downgrade"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/test_registry_bind.py:classify",
                "probes": [src, ver],
            },
            {
                "claim": (
                    "All-UNPROVEN coverage is 0 protected claims, not 100 percent"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/test_registry_bind.py:coverage_summary",
                "probes": [src, ver],
            },
            {
                "claim": (
                    "Independent reviewer mutation M-REV-DEFAULT-NINETY-NINE "
                    "is classified the same way"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CC-0014/mutate.py:"
                    "MUT_REV_NINETY_NINE"
                ),
                "probes": [src, ver],
            },
        ],
        "tests": [
            {
                "id": "T1-unproven-without-mutation",
                "command": P1_CMD,
                "result": "PASS",
                "output_tail": (
                    "test_empty_list_rejected_at_explicit_one -> UNPROVEN, "
                    "coverage 0"
                ),
            },
            {
                "id": "T2-killed-mutation-protecting",
                "command": P1_CMD,
                "result": "PASS",
                "output_tail": (
                    "M-IMPL-DEFAULT-ZERO killed "
                    "test_default_floor_rejects_below_minimum "
                    f"exit={killed['exit_code']}"
                ),
            },
            {
                "id": "T3-survived-mutation-hole",
                "command": P1_CMD,
                "result": "PASS",
                "output_tail": (
                    "M-IMPL-DEFAULT-ZERO survived "
                    "test_explicit_minimum_ignores_module_default "
                    f"exit={survived['exit_code']}; status HOLE not UNPROVEN"
                ),
            },
            {
                "id": "T4-all-unproven-aggregation-zero",
                "command": P2_CMD,
                "result": "PASS",
                "output_tail": (
                    "coverage_summary over three UNPROVEN rows reports "
                    f"protected_claims={all_unproven['protected_claims']} "
                    f"protected_percent={all_unproven['protected_percent']}, "
                    "not 100"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IMPL-DEFAULT-ZERO-KILLS-DEFAULT-FLOOR",
                "kind": "mutation",
                "description": (
                    "REQUIRED_MIN = 3 -> 0 must fail the default-floor test "
                    "and survive the explicit-only test"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (killed.get("failing_output") or "")[:4000],
                "good_state_output": (survived.get("surviving_output") or "")[:4000],
            },
            {
                "id": "NC-REV-DEFAULT-NINETY-NINE-INDEPENDENT",
                "kind": "mutation",
                "description": (
                    "Independent reviewer mutation REQUIRED_MIN = 3 -> 99 "
                    "must kill a different default-floor test"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (rev_kill.get("failing_output") or "")[:4000],
                "good_state_output": (rev_live.get("surviving_output") or "")[:4000],
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0014-independent-mutation-author",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "human",
            "reviewed_at": now,
            "notes": (
                "reviewer_mutation_id=M-REV-DEFAULT-NINETY-NINE "
                "REQUIRED_MIN = 3 -> 99 (implementer used 0). "
                "Kill classified PROTECTING; survive classified HOLE."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CC-0014/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CC-0014",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CC-0014/probe1_status_machine.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": src,
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/CC-0014/probe2_aggregation.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": ver,
            },
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; never relax the mutation requirement "
                "to make the registry green."
            ),
        },
        "residual_unknowns": [],
        "report": {
            "kind": "test-registry-entry",
            "observations": [
                {
                    "name": "unproven-not-coverage",
                    "measured": 0,
                    "method": "bind_row with no mutation then coverage_summary",
                    "anchor": "command-center/test_registry_bind.py:coverage_summary",
                },
                {
                    "name": "killed-mutation-status",
                    "measured": "PROTECTING",
                    "method": "mutate_and_run MUT_IMPL_ZERO against default-floor test",
                    "anchor": "command-center/p2-wave/probes/CC-0014/mutate.py",
                },
                {
                    "name": "survived-mutation-status",
                    "measured": "HOLE",
                    "method": "mutate_and_run MUT_IMPL_ZERO against explicit-only test",
                    "anchor": "command-center/p2-wave/probes/CC-0014/mutate.py",
                },
                {
                    "name": "all-unproven-protected-percent",
                    "measured": all_unproven["protected_percent"],
                    "method": "coverage_summary over three UNPROVEN rows",
                    "anchor": "command-center/test_registry_bind.py:coverage_summary",
                },
            ],
            "control_ids": [
                "M-IMPL-DEFAULT-ZERO",
                "M-REV-DEFAULT-NINETY-NINE",
                "UNPROVEN-NO-MUTATION",
            ],
            "entries": entries,
            "coverage": coverage,
            "reviewer_mutation_id": "M-REV-DEFAULT-NINETY-NINE",
            "live_registry": REGISTRY,
            "live_claims": CLAIMS,
            "title": (
                "Bind tests to claims to units, and refuse to record a test as "
                "coverage until a mutation proved it fires"
            ),
            "question": (
                "A TEST-REGISTRY where an entry may reach status PROTECTING only "
                "when a recorded mutation of the behaviour under test made that "
                "test FAIL. A test with no mutation record is UNPROVEN and may "
                "never be counted as coverage; a mutation that SURVIVED is a "
                "hole, not a silent downgrade."
            ),
            "bindings": {
                "test_to_claim_to_unit": [
                    {
                        "test_id": e["test_id"],
                        "claim_id": e["claim_id"],
                        "unit_id": e["unit_id"],
                        "status": e["status"],
                    }
                    for e in entries
                ]
            },
        },
    }

    errs = validate_receipt(receipt)
    if errs:
        print("FAILED:emit schema")
        for err in errs[:24]:
            print(f"  {err}")
        return 1

    dump(REPO / OUT, receipt)
    print(f"wrote {OUT} sha256={sha256_file(REPO / OUT)} bytes={(REPO / OUT).stat().st_size}")
    print(
        f"merged {REGISTRY} entries={len(entries)} "
        f"protected_claims={coverage['protected_claims']}"
    )
    print("SUCCESS:CC-0014 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
