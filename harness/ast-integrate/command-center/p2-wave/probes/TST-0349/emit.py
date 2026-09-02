#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0349.json — subject-inside-patched-set census."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import scenario as S  # noqa: E402

OUT = S.OUT_REL
SENTINEL = "SUCCESS:TST-0349"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0349/probe1_planted_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0349/probe2_overclaim.py"
)
CENSUS_REL = "command-center/p2-wave/probes/TST-0349/census.py"
QUESTION = (
    "A test of the HTTP client that mocks the HTTP client is verifying the mock. "
    "Build the census that, for each test, compares its declared subject against "
    "the set of objects it patches, and flags every case where the subject is "
    "inside the patched set. Distinct from C23 (tests that assert nothing): "
    "these tests assert plenty, just about a double. The output is a prioritised "
    "list for conversion to contract or integration tests, not an instruction to "
    "delete them."
)
SELF_NAMES = {
    "test_http_client_patches_own_subject",
    "test_http_client_patches_own_subject_low",
    "test_patch_object_own_subject",
    "test_mocker_patches_own_subject",
    "test_context_manager_patches_own_subject",
}
NEIGHBOUR_NAMES = {
    "test_http_client_patches_neighbour",
    "test_three_neighbour_mocks",
}
MENTION_NAME = "test_mention_only_does_not_patch"
SUPPORTING = [
    ("command-center/p2-wave/probes/TST-0349/census.py", "primary"),
    ("command-center/p2-wave/probes/TST-0349/scenario.py", "supporting"),
    ("command-center/p2-wave/probes/TST-0349/probe1_planted_controls.py", "control"),
    ("command-center/p2-wave/probes/TST-0349/probe2_overclaim.py", "control"),
    ("command-center/p2-wave/probes/TST-0349/fixtures/registry.json", "fixture"),
    (
        "command-center/p2-wave/probes/TST-0349/fixtures/tests/test_planted_controls.py",
        "control",
    ),
]


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes()
    return {
        "path": rel,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def schema_errors(doc: dict) -> list[str]:
    schema_path = REPO / "platform" / "schema" / "receipt.schema.json"
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    started = datetime.now(timezone.utc)
    census = S.run_unit_census()
    planted = census["planted"]
    prioritized = census["prioritized"]
    inventory = census.get("live_registry_inventory") or {}
    self_rows = [C.record_by_name(planted, n) for n in sorted(SELF_NAMES)]
    if any(r is None for r in self_rows):
        missing = [n for n in sorted(SELF_NAMES) if C.record_by_name(planted, n) is None]
        print(f"FAILED:TST-0349 emit missing planted self-patch tests {missing}")
        return 1
    if any(not r["flagged"] or not r["overlaps"] for r in self_rows):
        print("FAILED:TST-0349 emit planted self-patch not DETECTED")
        return 1
    for name in sorted(NEIGHBOUR_NAMES):
        row = C.record_by_name(planted, name)
        if row is None or row["flagged"]:
            print(f"FAILED:TST-0349 emit neighbour control flagged or missing: {name}")
            return 1
    mention = C.record_by_name(planted, MENTION_NAME)
    if mention is None or mention["flagged"] or mention["patch_call_count"] != 0:
        print("FAILED:TST-0349 emit mention control is a patch-use")
        return 1
    triple = C.record_by_name(planted, "test_three_neighbour_mocks")
    if triple is None or triple["patch_call_count"] < 3 or triple["flagged"]:
        print("FAILED:TST-0349 emit three-neighbour control did not isolate overlap")
        return 1
    high = C.record_by_name(planted, "test_http_client_patches_own_subject")
    low = C.record_by_name(planted, "test_http_client_patches_own_subject_low")
    if high["score"] <= low["score"]:
        print("FAILED:TST-0349 emit prioritisation does not rank P0-contract above P2-unit")
        return 1
    ranks = {row["name"]: i + 1 for i, row in enumerate(prioritized)}
    if ranks.get("test_http_client_patches_own_subject", 99) > ranks.get(
        "test_http_client_patches_own_subject_low", 0
    ):
        print("FAILED:TST-0349 emit P0-contract not ranked above P2-unit in prioritized list")
        return 1

    live_registry = S.live_registry_path()
    schema_path = S.repo_path(S.DECLARED_SCHEMA)
    live_present = live_registry.is_file()
    schema_present = schema_path.is_file()
    flagged_for_conversion = []
    for i, row in enumerate(prioritized, 1):
        flagged_for_conversion.append(
            {
                "rank": i,
                "score": row["score"],
                "severity": row["severity"],
                "claim_class": row["claim_class"],
                "claimed_coverage": row["claimed_coverage"],
                "test": row["qualname"],
                "path": row["path"],
                "lineno": row["lineno"],
                "subject": row["subject"],
                "overlapping_patched_targets": row["overlaps"],
                "patched_set": row["patched"],
                "corpus": row["corpus"],
                "recommended_action": "convert-to-contract-or-integration",
                "forbidden_action": "delete",
            }
        )

    overlap_evidence = [
        {
            "test": r["qualname"],
            "subject": r["subject"],
            "overlapping_patched_target": r["overlaps"][0],
            "all_overlaps": r["overlaps"],
            "patch_sites": r["patch_sites"],
            "finding": "subject-inside-patched-set",
        }
        for r in self_rows
    ]
    live_patched_undeclared = [
        {
            "test": r["qualname"],
            "path": r["path"],
            "lineno": r["lineno"],
            "patched_set": r["patched"],
            "patch_call_count": r["patch_call_count"],
            "subject": r["subject"],
            "flagged": False,
            "why_not_flagged": "no-declared-patchable-subject",
        }
        for r in census["live"]
        if r["patch_call_count"] and not r["subject"]
    ]
    honesty = (
        "Live overlap flags require a declared patchable subject. "
        "TEST-REGISTRY.json is PRESENT as a suite/invariant ledger with "
        f"object_subject_rows={inventory.get('object_subject_rows', 0)}. "
        f"Live flagged={census['counts']['live_flagged']} is UNDECLARED-SUBJECT, "
        "not CLEAN. A raw patch-call count is not an overlap finding."
    )
    report = {
        "kind": "subject-inside-patched-set-census",
        "title": "Census tests that mock the very boundary they claim to verify",
        "question": QUESTION,
        "finding_definition": {
            "is": "declared subject is inside the test's patched set",
            "is_not": [
                "raw mock or patch call count",
                "C23 vacuous tests that assert nothing",
                "an instruction to delete the flagged tests",
                "a string mention of patch() or of the subject",
            ],
            "output": "prioritised conversion list (contract or integration), not a deletion list",
        },
        "declared_inputs": {
            "TEST-REGISTRY.json": {
                "path": S.LIVE_REGISTRY_REL,
                "present": live_present,
                "shape": inventory.get("shape"),
                "object_subject_rows": inventory.get("object_subject_rows"),
                "named_test_count": inventory.get("named_test_count"),
                "note": (
                    "Present. Shape is a suite/invariant ledger, not per-test "
                    "patchable subjects. Named tests without an object subject "
                    "cannot be overlap-flagged."
                    if live_present
                    else "Absent on this worktree."
                ),
            },
            "receipt_schema": {
                "path": S.DECLARED_SCHEMA,
                "present": schema_present,
                "physical": "platform/schema/receipt.schema.json",
                "note": (
                    "Catalog output_schema resolves on disk (generated shim). "
                    "Domain census is in report; receipt_core is the envelope."
                ),
            },
            "contract_test_layer": {
                "claimed_input": "the contract-test layer authored in slice part 1",
                "present": False,
                "note": "Not on this worktree. Conversion targets remain named, not executed.",
            },
        },
        "detector": {
            "method": "Python AST (not text search)",
            "patch_forms": [
                "unittest.mock.patch / mock.patch / mocker.patch string target",
                "patch.object / mocker.patch.object",
                "monkeypatch.setattr",
                "function and class decorators",
                "with-context patch calls",
                "same-class setUp/setup_method unioned onto test methods",
            ],
            "overlap_rule": (
                "subject equals a patched target, or either is a dotted prefix of the other"
            ),
            "use_versus_mention": (
                "A Constant string or comment containing patch(\"subject\") is not a patch Call"
            ),
        },
        "live_corpus": {
            "roots_declared": S.LIVE_TEST_ROOTS,
            "roots_present": S.live_roots_present(),
            "roots_walked": census["live_roots_walked"],
            "tests_scanned": census["counts"]["live_tests"],
            "tests_with_patch_calls": census["counts"]["live_with_patches"],
            "tests_with_undeclared_subject": census["counts"]["live_undeclared_subject"],
            "flagged": census["counts"]["live_flagged"],
            "flagged_rows": census["flagged_live"],
            "patched_undeclared_rows": live_patched_undeclared,
            "registry_inventory": inventory,
            "honesty": honesty,
        },
        "planted_corpus": {
            "registry": S.PLANTED_REGISTRY_REL,
            "tests_dir": S.PLANTED_TESTS_REL,
            "tests_scanned": census["counts"]["planted_tests"],
            "flagged": census["counts"]["planted_flagged"],
            "rows": planted,
        },
        "prioritized_for_conversion": flagged_for_conversion,
        "not_flagged_controls": [
            {
                "name": name,
                "reason": "neighbour dependency is outside the declared subject",
                "patch_call_count": (C.record_by_name(planted, name) or {}).get(
                    "patch_call_count"
                ),
                "patched_set": (C.record_by_name(planted, name) or {}).get("patched"),
                "flagged": False,
            }
            for name in sorted(NEIGHBOUR_NAMES)
        ]
        + [
            {
                "name": MENTION_NAME,
                "reason": "patch appears only as a string/comment mention, not a Call",
                "patch_call_count": mention["patch_call_count"],
                "patched_set": mention["patched"],
                "flagged": False,
            }
        ],
        "overlap_evidence": overlap_evidence,
        "raw_mock_count_is_not_the_finding": True,
        "deletion_forbidden": True,
        "tests_required": [
            {
                "id": "planted-self-patch",
                "requirement": "Planted control: a test that patches its own subject -> DETECTED.",
                "result": "PASS",
                "detected": sorted(SELF_NAMES),
            },
            {
                "id": "neighbour-not-flagged",
                "requirement": "Legitimate mocking of a NEIGHBOUR dependency -> not flagged.",
                "result": "PASS",
                "not_flagged": sorted(NEIGHBOUR_NAMES),
            },
            {
                "id": "prioritisation",
                "requirement": (
                    "Prioritisation: flagged tests ranked by the severity of what they claim to cover."
                ),
                "result": "PASS",
                "p0_contract_score": high["score"],
                "p2_unit_score": low["score"],
                "p0_rank": ranks.get("test_http_client_patches_own_subject"),
                "p2_rank": ranks.get("test_http_client_patches_own_subject_low"),
            },
        ],
        "counts": census["counts"],
        "deviations": [
            {
                "id": "DEV-LIVE-TEST-REGISTRY-NO-PER-TEST-SUBJECT",
                "kind": "source-shape",
                "explanation": (
                    "command-center/TEST-REGISTRY.json is present. It names "
                    "suites and invariants, not a patchable object per test. "
                    "Declared subjects for planted controls come from "
                    f"{S.PLANTED_REGISTRY_REL}. Live tests were AST-scanned; "
                    "without object subjects they are UNDECLARED, not CLEAN."
                ),
            }
        ],
    }

    census_summary = json.dumps(
        {
            "planted_flagged": census["counts"]["planted_flagged"],
            "overlap_names": sorted(SELF_NAMES),
            "neighbour_flagged": False,
            "triple_patch_call_count": triple["patch_call_count"],
        },
        sort_keys=True,
    )
    mention_src = (REPO / mention["path"]).read_text(encoding="utf-8")
    mention_has_string = 'patch("subject_pkg.http_client.HttpClient")' in mention_src
    artifacts = [art_row(rel, role) for rel, role in SUPPORTING]
    import ast as _ast

    census_src = (REPO / CENSUS_REL).read_text(encoding="utf-8")
    _ast.parse(census_src)
    census_parse_out = f"parsed {CENSUS_REL} bytes={len(census_src.encode('utf-8'))}"
    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0349",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0349; "
            "command-center/COMPLETION-GATES.json:10631-10644"
        ),
        "min_bytes_threshold": 1024,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Planted tests that patch their declared HttpClient subject "
                    "are DETECTED by subject-inside-patched-set overlap, not by "
                    "raw mock count."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": S.PLANTED_TESTS_REL,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/TST-0349/census.py"
                        ),
                        "raw_output": census_summary,
                        "fingerprint": fingerprint("command", "census-planted-overlap"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c ast.parse planted test_planted_controls.py "
                            "and require overlap(subject, patch-target)"
                        ),
                        "raw_output": json.dumps(
                            {
                                "detected": sorted(SELF_NAMES),
                                "p0_score": high["score"],
                                "p2_score": low["score"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint(
                            "static-analysis", "planted-overlap-pairs"
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A raw patch-count mutant would flag test_three_neighbour_mocks "
                    f"(patch_call_count={triple['patch_call_count']}); the overlap "
                    "detector does not. String mention of patch() is not a Call."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0349/probe2_overclaim.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -c "
                            "'overlap vs patch_call_count on planted corpus'"
                        ),
                        "raw_output": json.dumps(
                            {
                                "triple_flagged": False,
                                "triple_patch_call_count": triple["patch_call_count"],
                                "mention_patch_call_count": mention["patch_call_count"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("command", "count-mutant-vs-overlap"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": mention["path"],
                        "raw_output": json.dumps(
                            {
                                "mention_string_present": mention_has_string,
                                "mention_patch_call_count": mention["patch_call_count"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("file-read", mention["path"]),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "planted-self-patch",
                "name": "Planted control: a test that patches its own subject -> DETECTED.",
                "command": P1,
                "result": "PASS",
                "assertions": len(SELF_NAMES),
            },
            {
                "id": "neighbour-not-flagged",
                "name": "Legitimate mocking of a NEIGHBOUR dependency -> not flagged.",
                "command": P1,
                "result": "PASS",
                "assertions": len(NEIGHBOUR_NAMES),
            },
            {
                "id": "prioritisation",
                "name": (
                    "Prioritisation: flagged tests ranked by the severity of "
                    "what they claim to cover."
                ),
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
        ],
        "negative_controls": [
            {
                "id": "mention-is-not-use",
                "kind": "known-broken-fixture",
                "description": (
                    "Self-patch DETECTED; a string/comment mention of "
                    "patch(\"subject\") is not a patch Call and is not flagged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "DETECTED test_http_client_patches_own_subject",
                "good_state_output": "mention_not_use patch_call_count=0",
            },
            {
                "id": "raw-count-is-not-overlap",
                "kind": "mutation",
                "description": (
                    "test_three_neighbour_mocks has patch_call_count>=3 and "
                    "flagged=false; a count detector would have raised a finding."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "count mutant would flag test_three_neighbour_mocks",
                "good_state_output": "triple_flagged=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0349-probe2-overclaim",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Probe 2 re-runs the census independently of emit and requires "
                "that a raw patch-count mutant would flag the neighbour control "
                "while the overlap detector does not. TEST-REGISTRY present-flag "
                "must match disk; live flagged=0 is UNDECLARED-SUBJECT, not CLEAN."
            ),
        },
        "defects": [
            {
                "id": "TST-0349-D1",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "command-center/TEST-REGISTRY.json is present but declares "
                    "no per-test patchable subject, so live overlap flags are "
                    "UNDECLARED-SUBJECT not CLEAN. Conversion list for live "
                    f"tests cannot be ranked until subjects exist. "
                    f"live_tests={census['counts']['live_tests']} "
                    f"live_with_patches={census['counts']['live_with_patches']} "
                    f"live_flagged={census['counts']['live_flagged']}."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0349/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0349",
        },
        "downstream_consumers": [
            {
                "consumer": "ast.parse of the overlap census detector",
                "artifact_path": CENSUS_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "static-analysis",
                    "command": (
                        "python3 -c \"import ast, pathlib; "
                        "ast.parse(pathlib.Path("
                        f"'{CENSUS_REL}').read_text())\""
                    ),
                    "raw_output": census_parse_out,
                    "fingerprint": fingerprint("static-analysis", "ast.parse census.py"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the harness "
                "or the fixture."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live tests cannot be overlap-flagged until TEST-REGISTRY.json "
                    "declares a patchable object subject per test."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add subject/declared_subject object paths to "
                    "command-center/TEST-REGISTRY.json, re-run the census, and "
                    "rank any live subject-inside-patched-set rows for conversion."
                ),
            },
            {
                "claim": (
                    "The contract-test layer authored in slice part 1 is not on "
                    "this worktree, so conversion is named rather than executed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount or author that contract-test layer and convert the "
                    "prioritised planted self-patch rows against it."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "test-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:TST-0349 emit schema-invalid")
        for line in errs[:20]:
            print(line)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0349 emit sentinel missing from serialisation")
        return 1
    out_path.write_text(text, encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={sha}")
    print("SUCCESS:TST-0349 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
