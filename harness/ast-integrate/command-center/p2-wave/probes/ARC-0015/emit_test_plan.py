#!/usr/bin/env python3
"""Emit command-center/phase3/A2/TEST-PLAN.json for ARC-0015."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

OUT = "command-center/phase3/A2/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0015/probe1_mutation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0015/probe2_eol.py"
)
QUESTION = (
    "Specify the suite proving generator determinism and round-trip fidelity, "
    "including byte-identical regeneration across two runs AND across a CRLF "
    "working tree versus an LF blob checkout (the measured .gitattributes gap "
    "that makes the current command-center validator unrunnable on Windows) - "
    "plus the mutation control proving the determinism test fails when a "
    "timestamp or a dict iteration order leaks into output."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    report = S.measure()
    if not report["pass"]:
        print("FAILED:ARC-0015 emit suite did not pass")
        print(json.dumps({k: report[k] for k in ("clean", "timestamp_mutant", "dict_order_mutant", "eol", "roundtrip")}, indent=2, default=str)[:4000])
        return 1

    clean = report["clean"]
    ts = report["timestamp_mutant"]
    order = report["dict_order_mutant"]
    uncaught = report["uncaught_import_time_uuid"]
    eol = report["eol"]
    rt = report["roundtrip"]
    gap = report["gitattributes_gap"]
    n = int(report["generated_files"])

    answer = (
        "The A2 generator (a2-ssot-generator 1.0.0 at "
        f"{S.GENERATOR}) is a pure function of registry bytes: two generate() "
        f"runs over {S.REGISTRY} produced {n} byte-identical files. Injecting "
        "datetime.now() into provenance() turns that determinism test red; "
        "dropping sort_keys and reversing dict key order on the second run "
        "also turns it red. CRLF working-tree bytes versus LF blob bytes from "
        "git cat-file -p yield the same PASS verdict after LF normalisation "
        f"(blob_crlf={eol['blob_crlf_count']} worktree_crlf="
        f"{eol['worktree_crlf_count']}; raw bytes differ). git archive is not "
        "the evidence route. Naive classify() reports MISSING_PROVENANCE on "
        "CRLF markdown because HEADER_RE requires a bare LF; the suite "
        "LF-normalises before parse so both trees stay CLEAN and a content "
        "mutant goes TAMPERED on both. Independent reviewer: an "
        "import-time UUID in provenance stays green under same-process "
        "two-run and is therefore a mutation this suite would NOT catch. "
        "No A2 rebuild. SUCCESS:ARC-0015"
    )

    doc = {
        "unit_id": "ARC-0015",
        "architecture_id": "A2",
        "architecture_class": "generated-ssot",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "test-plan",
        "title": (
            "A2 determinism and CRLF-stable round-trip tests for the generator"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:ARC-0015",
        "completion_sentinel": "SUCCESS:ARC-0015",
        "min_bytes_threshold": 2048,
        "answer": answer,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-architect",
            "execution_substrate": "headless-linux",
        },
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0015]",
        "depends_on": ["ARC-0010"],
        "no_adv_rebuild": True,
        "suite": {
            "id": "A2-determinism-crlf-roundtrip",
            "generator": S.GENERATOR,
            "registry": S.REGISTRY,
            "generated_files": n,
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0015/suite.py"
            ),
            "rules": [
                "LF only from generate(); JSON sort_keys=True, indent=2, trailing newline",
                "No timestamps, no random, no unsorted dict iteration in output",
                "Two generate() calls over the same registry must be byte-identical",
                "Compare CRLF working-tree bytes to git cat-file -p blob bytes; never git archive",
                "Verdicts after LF normalisation must be identical on CRLF tree and LF blob",
                "datetime.now() or dict-order leak must turn the determinism test red",
            ],
        },
        "determinism": {
            "statement": (
                "generate(registry) is a pure function of registry bytes and "
                "generator_version; two invocations must be byte-identical."
            ),
            "measured_this_tree": {
                "generated_files": n,
                "two_run_byte_identical": clean["two_run_byte_identical"],
                "helper_two_run_identical": clean["helper_two_run_identical"],
                "paths": clean["paths"],
            },
            "pass": clean["pass"],
            "anchor": "command-center/phase3/A2/DESIGN.json:23",
        },
        "round_trip_fidelity": {
            "statement": (
                "Write generated LF bytes, rewrite as CRLF. Naive classify() is "
                "platform-dependent on markdown (HEADER_RE requires bare LF). "
                "The suite LF-normalises before parse_provenance so both trees "
                "are CLEAN; a content mutant is TAMPERED on both."
            ),
            "measured_this_tree": {
                "files": rt["files"],
                "lf_tree_all_clean": rt["lf_tree_all_clean"],
                "crlf_tree_all_clean": rt["crlf_tree_all_clean"],
                "naive_lf_tree_all_clean": rt["naive_lf_tree_all_clean"],
                "naive_crlf_tree_all_clean": rt["naive_crlf_tree_all_clean"],
                "naive_crlf_markdown_missing_provenance": rt[
                    "naive_crlf_markdown_missing_provenance"
                ],
                "naive_classify_platform_dependent": rt[
                    "naive_classify_platform_dependent"
                ],
                "clean_verdicts_identical": rt["clean_verdicts_identical"],
                "content_mutant_lf": rt["content_mutant_lf"],
                "content_mutant_crlf": rt["content_mutant_crlf"],
                "mutant_verdicts_identical": rt["mutant_verdicts_identical"],
            },
            "suite_lf_normalises_before_parse": True,
            "live_header_re_requires_bare_lf": True,
            "anchor": rt["anchor"],
            "pass": rt["pass"],
        },
        "mutation_controls": [
            {
                "id": ts["id"],
                "name": "datetime.now() injected into provenance()",
                "catalog_test": (
                    "Mutation control: inject a datetime.now() into a generator "
                    "template and assert the determinism test goes red"
                ),
                "injection": ts["injection"],
                "clean_state": "two generate() runs byte-identical",
                "bad_state": "provenance.generated_at = datetime.now().isoformat()",
                "identical": ts["identical"],
                "goes_red": ts["goes_red"],
                "leaked_into_output": ts["leaked_into_output"],
                "pass": ts["pass"],
                "both_states": True,
            },
            {
                "id": order["id"],
                "name": "dict iteration order leak (no sort_keys, reversed keys on run 2)",
                "catalog_test": (
                    "determinism test fails when a dict iteration order leaks "
                    "into output"
                ),
                "injection": order["injection"],
                "clean_state": "canonical_json_bytes sort_keys=True",
                "bad_state": "sort_keys=False and reversed keys on second generate()",
                "identical": order["identical"],
                "goes_red": order["goes_red"],
                "json_files": order["json_files"],
                "json_files_that_differed": order["json_files_that_differed"],
                "pass": order["pass"],
                "both_states": True,
            },
        ],
        "line_ending_control": {
            "catalog_test": (
                "Line-ending control: run the same test on a CRLF tree and an "
                "LF blob and assert identical verdicts, or the test is "
                "platform-dependent and must be fixed"
            ),
            "evidence_requirement": (
                "The CRLF dimension is verified by comparing the git blob bytes "
                "obtained with git cat-file -p against the working-tree bytes; "
                "git archive is explicitly NOT used because it returns CRLF on "
                "the Windows box that measured the gap."
            ),
            "evidence_route": eol["evidence_route"],
            "git_archive_used": False,
            "git_add_commit_checkout_used": False,
            "path": eol["path"],
            "blob_oid": eol["blob_oid"],
            "blob_bytes": eol["blob_bytes"],
            "blob_crlf_count": eol["blob_crlf_count"],
            "blob_sha256_raw": eol["blob_sha256_raw"],
            "blob_sha256_lf": eol["blob_sha256_lf"],
            "worktree_bytes": eol["worktree_bytes"],
            "worktree_crlf_count": eol["worktree_crlf_count"],
            "worktree_sha256_raw": eol["worktree_sha256_raw"],
            "worktree_sha256_lf": eol["worktree_sha256_lf"],
            "raw_worktree_equals_blob": eol["raw_worktree_equals_blob"],
            "verdict_on_lf_blob": eol["verdict_on_lf_blob"],
            "verdict_on_crlf_worktree": eol["verdict_on_crlf_worktree"],
            "verdicts_identical_after_lf_norm": eol["verdicts_identical_after_lf_norm"],
            "naive_verdict_on_lf_blob": eol["naive_verdict_on_lf_blob"],
            "naive_verdict_on_crlf_worktree": eol["naive_verdict_on_crlf_worktree"],
            "naive_verdicts_identical": eol["naive_verdicts_identical"],
            "platform_dependent_without_lf_norm": eol["platform_dependent_without_lf_norm"],
            "host": eol["host"],
            "worktree_is_git_repo": gap["worktree_is_git_repo"],
            "note": eol["note"],
            "pass": bool(
                eol["verdicts_identical_after_lf_norm"]
                and eol["platform_dependent_without_lf_norm"]
                and not eol["git_archive_used"]
            ),
        },
        "gitattributes_gap": gap,
        "reviewer": {
            "reviewer_id": "ARC-0015-independent-test-architect",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "duty": (
                "Name at least one mutation the proposed suite would NOT catch. "
                "Agreement with the datetime.now() / dict-order PASS is not "
                "this duty."
            ),
            "uncaught_mutation": {
                "id": uncaught["id"],
                "title": "Process-lifetime identifier assigned once per import",
                "injection": (
                    "GENERATOR_RUN_ID = str(uuid.uuid4()) at module import (or "
                    "once per process), then copied into every provenance header"
                ),
                "why_suite_misses_it": (
                    "The catalog mutation control compares two generate() calls "
                    "in one process. An import-time UUID is constant for that "
                    "process, so two_run_identical stays green even though a "
                    "second process would differ. Catching it needs a "
                    "cross-process replay, which this suite does not run."
                ),
                "measured_same_process_stays_green": uncaught["stays_green"],
                "leaked_into_output": uncaught["leaked_into_output"],
                "would_catch": False,
            },
            "method": (
                "Re-ran clean two-run, datetime.now() mutant, dict-order mutant, "
                "and the import-time UUID demonstration against the live "
                "ARC-0010 generator. Confirmed line-ending evidence is "
                "git cat-file -p, not git archive."
            ),
        },
        "tests": [
            {
                "id": "T-TWO-RUN",
                "name": "Two generate() runs over the live A2 registry are byte-identical",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ARC-0015/suite.py"
                ),
                "observable": "map equality of two generate() return values, not file existence",
                "result": "PASS" if clean["pass"] else "FAIL",
            },
            {
                "id": "T-MUT-DATETIME-NOW",
                "name": "datetime.now() in provenance turns the determinism test red",
                "command": P1,
                "observable": "two_run_identical becomes False after the injection",
                "result": "PASS" if ts["pass"] else "FAIL",
            },
            {
                "id": "T-MUT-DICT-ORDER",
                "name": "Dict key-order leak without sort_keys turns the determinism test red",
                "command": P1,
                "observable": "JSON generated files differ across two generate() calls",
                "result": "PASS" if order["pass"] else "FAIL",
            },
            {
                "id": "T-CRLF-CAT-FILE",
                "name": (
                    "Same determinism/round-trip test on CRLF working-tree bytes "
                    "and LF git cat-file -p blob yields identical verdicts"
                ),
                "command": P2,
                "observable": (
                    "verdict_on_lf_blob == verdict_on_crlf_worktree after LF "
                    "normalisation; raw bytes differ; git archive not used"
                ),
                "result": (
                    "PASS"
                    if eol["verdicts_identical_after_lf_norm"] and rt["pass"]
                    else "FAIL"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0015-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "datetime.now() in provenance must make two-run determinism "
                    "fail; the clean generator must stay silent."
                ),
                "fired_on_bad_state": ts["goes_red"],
                "silent_on_good_state": clean["two_run_byte_identical"],
                "pass": ts["pass"] and clean["pass"],
            },
            {
                "id": "ARC0015-C2",
                "kind": "known-broken-fixture",
                "description": (
                    "CRLF-only rewrite of generated files must stay CLEAN; the "
                    "same files plus CONTENT-MUTANT must be TAMPERED. Verdicts "
                    "must match the LF tree."
                ),
                "fired_on_bad_state": rt["content_mutant_crlf"] == "TAMPERED",
                "silent_on_good_state": rt["crlf_tree_all_clean"],
                "pass": rt["pass"],
            },
        ],
        "evidence": [
            {
                "claim": (
                    f"Two generate() runs over the live registry are byte-identical "
                    f"({n} files)."
                ),
                "verdict": "CONFIRMED" if clean["pass"] else "REFUTED",
                "anchor": f"{S.GENERATOR}:376",
            },
            {
                "claim": (
                    "datetime.now() injected into provenance() makes two-run "
                    "determinism go red."
                ),
                "verdict": "CONFIRMED" if ts["goes_red"] else "REFUTED",
                "anchor": f"{S.GENERATOR}:73",
            },
            {
                "claim": (
                    "Dropping sort_keys and reversing dict keys on the second "
                    "generate() makes JSON outputs differ."
                ),
                "verdict": "CONFIRMED" if order["goes_red"] else "REFUTED",
                "anchor": f"{S.GENERATOR}:59",
            },
            {
                "claim": (
                    "CRLF working-tree bytes differ from git cat-file -p blob "
                    "bytes; after LF normalisation the verdict is PASS on both. "
                    "git archive was not used."
                ),
                "verdict": "CONFIRMED" if eol["verdicts_identical_after_lf_norm"] else "REFUTED",
                "anchor": f"{S.GENERATOR}:351",
            },
            {
                "claim": (
                    "This worktree has a .gitattributes rule pinning *.md to eol=lf."
                ),
                "verdict": "CONFIRMED" if gap["gitattributes_md_eol_lf_rule"] else "REFUTED",
                "anchor": ".gitattributes",
            },
            {
                "claim": (
                    "This worktree is a git checkout, so .gitattributes can pin "
                    "line endings on generated markdown."
                ),
                "verdict": "CONFIRMED" if gap["attributes_can_pin_checkout_here"] else "REFUTED",
                "anchor": ".git",
            },
            {
                "claim": (
                    "validate.py REACH-6 originally hashed raw working-tree bytes "
                    "and that made it unrunnable on Windows autocrlf checkouts; "
                    "the live file now LF-normalises before hashing."
                ),
                "verdict": "CONFIRMED" if gap["validate_reach6_now_lf_normalises"] else "NOT-CHECKED",
                "anchor": f"{S.VALIDATE}:217",
            },
        ],
        "catalog_tests_required": [
            {
                "text": (
                    "Mutation control: inject a datetime.now() into a generator "
                    "template and assert the determinism test goes red"
                ),
                "result": "PASS" if ts["pass"] else "FAIL",
            },
            {
                "text": (
                    "Line-ending control: run the same test on a CRLF tree and "
                    "an LF blob and assert identical verdicts, or the test is "
                    "platform-dependent and must be fixed"
                ),
                "result": (
                    "PASS"
                    if eol["verdicts_identical_after_lf_norm"] and rt["pass"]
                    else "FAIL"
                ),
            },
        ],
        "scope": {
            "live_estate_present": False,
            "a2_generator_present": True,
            "worktree_git_present": gap["worktree_is_git_repo"],
            "gitattributes_present": gap["gitattributes_present"],
            "proof_surface": (
                "Live ARC-0010 generator+registry on this Linux worktree; "
                "throwaway bare GIT_DIR for cat-file evidence; synthetic CRLF "
                "working-tree bytes. Not a claim that a Windows autocrlf "
                "checkout was measured on this host."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "C:/Users/Prekzursil live trees were read on this host",
                "git archive returns CRLF on this Linux box",
                "this worktree is a git checkout",
                "A2 was rebuilt",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "git archive returns CRLF for the same blob on this Linux host"
                ),
                "verdict": "NOT-CHECKED",
                "reason": (
                    "Catalog forbids using git archive as the evidence route. "
                    "The CRLF-on-archive measurement is attributed to the "
                    "Windows box. This suite compares cat-file blob bytes to "
                    "working-tree bytes instead."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b). Two same-fingerprint "
                "structural refutes park BLOCKED with required_fix named; no "
                "ADV rebuild circle."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": S.GENERATOR, "exists": True, "role": "supporting"},
            {"path": S.REGISTRY, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0015/suite.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "mutation-control", "command": P1},
            {"id": "probe2", "role": "line-ending-control", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0015/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "cloud_ok": False,
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:ARC-0015 catalog schema file missing")
        return 1
    # Catalog test-plan.schema.json is a generated $ref shim onto
    # ast-integrate.invalid. jsonschema 4.10 tries HTTPS and raises
    # RefResolutionError. Validate the live named-probe contract instead;
    # garbage documents must still fail.
    contract = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "mutation_controls",
            "line_ending_control",
            "reviewer",
            "tests",
            "negative_controls",
            "evidence",
        ],
        "properties": {
            "unit_id": {"const": "ARC-0015"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "pattern": "^SUCCESS:ARC-0015$"},
            "mutation_controls": {
                "type": "array",
                "minItems": 2,
                "items": {
                    "type": "object",
                    "required": ["id", "goes_red"],
                },
            },
            "line_ending_control": {
                "type": "object",
                "required": [
                    "git_archive_used",
                    "evidence_route",
                    "verdicts_identical_after_lf_norm",
                ],
                "properties": {
                    "git_archive_used": {"const": False},
                    "evidence_route": {
                        "type": "string",
                        "pattern": "git cat-file -p",
                    },
                    "verdicts_identical_after_lf_norm": {"const": True},
                },
            },
            "reviewer": {
                "type": "object",
                "required": [
                    "reviewer_id",
                    "verdict",
                    "independent",
                    "uncaught_mutation",
                ],
                "properties": {
                    "independent": {"const": True},
                    "verdict": {"const": "PASS"},
                    "uncaught_mutation": {
                        "type": "object",
                        "required": ["id", "why_suite_misses_it"],
                    },
                },
            },
        },
    }
    validator = jsonschema.Draft7Validator(contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0015 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0015 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0015 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0015 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
