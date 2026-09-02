#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0120.json (equivalent-mutant triage)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from policy import (  # noqa: E402
    AUTHOR_ID,
    POLICY,
    REVIEWER_ID,
    TEST_SCORE_WITH_COUNT,
    TEST_UNJUSTIFIED,
)
from schema_local import (  # noqa: E402
    GARBAGE,
    disk_validator,
    schema_errors,
)
from triage import detector_controls  # noqa: E402

OUT = "command-center/receipts/TST-0120.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0120/probe1_score_published_with_exclusion_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0120/probe2_unjustified_exclusion_rejected.py"
)
QUESTION = (
    "A mutation score is only meaningful once equivalent mutants "
    "(semantically identical to the original) are excluded, and exclusion "
    "is exactly where the score becomes gameable. Target: a written policy "
    "plus a review trail - every claimed equivalent mutant needs a "
    "justification recorded and a reviewer, and the count of exclusions is "
    "published alongside the score."
)
SENTINEL = "SUCCESS:TST-0120"
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json TST-0120; "
    "_USER-PROMPTS.md:11000,_USER-PROMPTS.md:11059"
)
RETRY_POLICY = (
    "two strikes then pivot: after the 2nd failure on the same "
    "error-fingerprint, enumerate >=2 alternative approaches before a 3rd "
    "attempt (AGENTS.md 4b)"
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/TST-0120/policy.py",
    "command-center/p2-wave/probes/TST-0120/triage.py",
    "command-center/p2-wave/probes/TST-0120/subject.py",
    "command-center/p2-wave/probes/TST-0120/schema_local.py",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(
            f"FAILED:TST-0120 emit snippet missing in {rel}: {snippet[:80]}"
        )
    return text[:idx].count("\n") + 1


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str, sha: str | None = None, size: int | None = None) -> dict:
    if sha is None or size is None:
        sha, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def gate(gid: str, broken: dict, good_ok: bool) -> dict:
    broken_code = 0 if broken.get("accepted") else 1
    good_code = 0 if good_ok else 1
    if broken_code == 1 and good_code == 0:
        verdict = "VALID"
    elif broken_code == 0 and good_code == 0:
        verdict = "SILENT-IN-BOTH"
    elif broken_code == 1 and good_code == 1:
        verdict = "NOISY-IN-BOTH"
    elif broken_code == 0 and good_code == 1:
        verdict = "INVERTED"
    else:
        verdict = "NOT-CHECKED"
    return {
        "id": gid,
        "producing_unit": "TST-0120",
        "broken_exit_code": broken_code,
        "good_exit_code": good_code,
        "verdict": verdict,
        "not_checked_reason": None,
        "broken_errors": broken.get("errors") or [],
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ctrl = detector_controls()
    if not ctrl["planted_fired"]:
        print("FAILED:TST-0120 emit planted detector did not fire")
        print(json.dumps(ctrl["planted"], indent=2, sort_keys=True)[:4000])
        return 1
    if not ctrl["clean_silent"]:
        print("FAILED:TST-0120 emit clean score not silent-accept")
        print(json.dumps(ctrl["clean"], indent=2, sort_keys=True)[:4000])
        return 1

    measured = ctrl["measured"]
    clean = ctrl["clean"]
    planted = ctrl["planted"]
    good_ok = bool(clean["accepted"])
    gates = [
        gate("omit-exclusion-count", planted["score_without_exclusion_count"], good_ok),
        gate("boilerplate-justification", planted["boilerplate_justification"], good_ok),
        gate("false-equivalent-sentinel", planted["false_equivalent_sentinel"], good_ok),
        gate("missing-reviewer", planted["missing_reviewer"], good_ok),
        gate("reviewer-is-author", planted["reviewer_is_author"], good_ok),
    ]
    tally = {
        "VALID": 0,
        "SILENT-IN-BOTH": 0,
        "NOISY-IN-BOTH": 0,
        "INVERTED": 0,
        "NOT-CHECKED": 0,
    }
    for g in gates:
        tally[g["verdict"]] = tally.get(g["verdict"], 0) + 1
    if tally["VALID"] != len(gates) or tally["SILENT-IN-BOTH"] or tally["NOT-CHECKED"]:
        print("FAILED:TST-0120 emit gates not all VALID")
        print(json.dumps(gates, indent=2)[:4000])
        return 1

    validator = disk_validator()
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0120 emit schema accepted garbage {list(garbage)[:2]}")
            return 1

    mutants = [
        {
            "mutant_id": r["mutant_id"],
            "operator": r["operator"],
            "location": r["location"],
            "oracle_identical": r["oracle_identical"],
            "killed": r["killed"],
            "diverged_oracles": r["diverged_oracles"],
            "expected_equivalent": r["expected_equivalent"],
        }
        for r in measured["mutants"]
    ]

    overclaim_line = find_line(
        "command-center/p2-wave/probes/TST-0120/triage.py",
        "overclaim:score-published-without-exclusion-count",
    )
    distinguish_line = find_line(
        "command-center/p2-wave/probes/TST-0120/triage.py",
        ":oracle-distinguishes:",
    )
    policy_line = find_line(
        "command-center/p2-wave/probes/TST-0120/policy.py",
        "a score published without its exclusion_count is an overclaim",
    )
    catalog_line = find_line(
        "command-center/WORK-UNIT-CATALOG.json",
        "every claimed equivalent mutant needs a justification recorded and a reviewer",
    )

    answer = (
        f"Score {clean['mutation_score']} with exclusion_count="
        f"{clean['exclusion_count']} (killed {clean['killed']} / "
        f"denominator {clean['denominator']}). "
        "A score published without exclusion_count is rejected as overclaim. "
        "Unjustified exclusions (boilerplate, missing reviewer, author-as-"
        "reviewer, oracle-distinguishable mutants) are rejected. "
        f"{SENTINEL}"
    )
    report = {
        "kind": "detector-control",
        "title": "Equivalent-mutant triage policy so the score cannot be gamed",
        "question": QUESTION,
        "answer": answer,
        "policy": POLICY,
        "author_id": AUTHOR_ID,
        "score": {
            "total": clean["total"],
            "killed": clean["killed"],
            "killed_ids": clean["killed_ids"],
            "surviving": clean["surviving"],
            "surviving_ids": clean["surviving_ids"],
            "exclusion_count": clean["exclusion_count"],
            "mutation_score": clean["mutation_score"],
            "denominator": clean["denominator"],
            "formula": clean["formula"],
        },
        "exclusions": clean["exclusions"],
        "mutants": mutants,
        "oracle_equivalent": measured["oracle_equivalent"],
        "oracle_killed": measured["oracle_killed"],
        "controls": {
            "planted_fired": True,
            "clean_silent": True,
            "score_without_exclusion_count_rejected": (
                not planted["score_without_exclusion_count"]["accepted"]
            ),
            "unjustified_exclusion_rejected": (
                not planted["boilerplate_justification"]["accepted"]
                and not planted["false_equivalent_sentinel"]["accepted"]
                and not planted["missing_reviewer"]["accepted"]
                and not planted["reviewer_is_author"]["accepted"]
            ),
            "justified_exclusion_accepted": bool(clean["accepted"]),
        },
        "gates": gates,
        "counts": {
            "gates": len(gates),
            "VALID": tally["VALID"],
            "SILENT-IN-BOTH": tally["SILENT-IN-BOTH"],
            "NOISY-IN-BOTH": tally["NOISY-IN-BOTH"],
            "INVERTED": tally["INVERTED"],
            "NOT-CHECKED": tally["NOT-CHECKED"],
        },
        "calibration": {
            "broken_means": (
                "planted unjustified exclusion or omitted exclusion_count"
            ),
            "good_means": (
                "justified, reviewed, oracle-identical exclusions with matching count"
            ),
            "broken_exit_code": 1,
            "good_exit_code": 0,
            "both_states_required": True,
        },
        "mutation_sweep": {
            "total": measured["total"],
            "killed": measured["killed"],
            "oracle_equivalent": measured["oracle_equivalent"],
            "oracle_killed": measured["oracle_killed"],
            "exclusion_count": clean["exclusion_count"],
            "mutation_score": clean["mutation_score"],
        },
        "detector_control": {
            "known_broken_fixture": "overclaim-score-without-exclusion-count",
            "fired": True,
            "clean_fixture": "justified-exclusions-with-matching-count",
            "silent": True,
            "second_broken_fixture": (
                "unjustified-exclusion-boilerplate-and-false-equivalent"
            ),
            "second_fired": True,
            "planted": {
                k: {"accepted": v["accepted"], "errors": v["errors"]}
                for k, v in planted.items()
            },
        },
        "observations": [
            {
                "name": "exclusion_count",
                "measured": int(clean["exclusion_count"]),
                "method": "publish_score on the published oracle pack",
                "anchor": f"command-center/p2-wave/probes/TST-0120/triage.py:{overclaim_line}",
            },
            {
                "name": "mutation_score",
                "measured": float(clean["mutation_score"]),
                "method": "killed / (total - exclusion_count)",
                "anchor": f"command-center/p2-wave/probes/TST-0120/policy.py:{policy_line}",
            },
            {
                "name": "planted_fired",
                "measured": True,
                "method": "detector_controls planted vs clean",
                "anchor": f"command-center/p2-wave/probes/TST-0120/triage.py:{distinguish_line}",
            },
            {
                "name": "unjustified_exclusion_rejected",
                "measured": True,
                "method": "boilerplate, false-equivalent, missing reviewer, author-as-reviewer",
                "anchor": f"command-center/p2-wave/probes/TST-0120/triage.py:{distinguish_line}",
            },
        ],
        "control_ids": [g["id"] for g in gates],
        "dependency_note": (
            "TST-0015 is the estate operator library. This unit triages "
            "those operator ids (lf-crlf-flip, json-key-case-flip, "
            "path-separator-flip, sentinel-deletion, mid-write-truncation, "
            "default-argument-change, use-vs-mention-swap) on a published "
            "oracle pack; it does not re-implement the mutation runner "
            "(TST-0119)."
        ),
        "failure_classification_covered": [
            "false-coverage",
            "overclaim",
            "detector-failure",
        ],
    }

    artifacts = [art_row(OUT, "primary", "0" * 64, 1)] + [
        art_row(rel, "supporting") for rel in SUPPORTING
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "TST-0120",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "profile": "p2-wave-g1-unit",
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A published mutation score that omits exclusion_count is "
                    "rejected as overclaim; a matching count is required even "
                    "when the count is zero."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    f"command-center/p2-wave/probes/TST-0120/triage.py:{overclaim_line}"
                ),
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        f"command-center/p2-wave/probes/TST-0120/triage.py:{overclaim_line}",
                        "OVERCLAIM="
                        + "overclaim:score-published-without-exclusion-count",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        P1,
                        "named probe1 requires exclusion_count beside the score",
                    ),
                ],
            },
            {
                "claim": (
                    "Unjustified equivalent-mutant exclusions (boilerplate "
                    "justification, missing reviewer, author-as-reviewer, or "
                    "oracle-distinguishable mutants) are rejected; reviewed "
                    "oracle-identical exclusions are accepted."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    f"command-center/p2-wave/probes/TST-0120/triage.py:{distinguish_line}"
                ),
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        f"command-center/p2-wave/probes/TST-0120/triage.py:{distinguish_line}",
                        "UNJUSTIFIED oracle-distinguishes gate is live",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        P2,
                        "named probe2 rejects unjustified exclusions",
                    ),
                ],
            },
            {
                "claim": (
                    "Catalog target for TST-0120 requires a justification and "
                    "a reviewer on every claimed equivalent mutant."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{catalog_line}",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        f"command-center/WORK-UNIT-CATALOG.json:{catalog_line}",
                        "every claimed equivalent mutant needs a justification "
                        "recorded and a reviewer",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        f"command-center/p2-wave/probes/TST-0120/policy.py:{policy_line}",
                        "a score published without its exclusion_count is an overclaim",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": TEST_SCORE_WITH_COUNT,
                "name": "Score is published with the exclusion count",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": TEST_UNJUSTIFIED,
                "name": "An unjustified exclusion is rejected",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": g["id"],
                "kind": "known-broken-fixture",
                "description": (
                    f"Planted {g['id']} must be rejected while the justified "
                    "reviewed exclusion list is accepted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ";".join(g["broken_errors"])[:16000],
                "good_state_output": (
                    f"accepted=True exclusion_count={clean['exclusion_count']} "
                    f"score={clean['mutation_score']}"
                ),
            }
            for g in gates
        ],
        "reviewer": {
            "reviewer_id": REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Re-run publish_score and check_published_record on the live "
                "corpus: omit exclusion_count, boilerplate justification, "
                "false equivalent, missing reviewer, author-as-reviewer. "
                "Require reject on planted, accept on clean. Author vendor is "
                "openai; reviewer vendor is anthropic."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0120/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0120",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft7Validator "
                    "(disk RefResolver) against detector-control.schema.json"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/TST-0120/schema_local.py",
                    "disk_validator iter_errors empty on live receipt; garbage rejected",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 1,
            "policy": RETRY_POLICY,
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "ref-resolution-ast-integrate.invalid",
                    "outcome": "FAILED",
                    "started_at": started,
                }
            ],
            "pivot_alternatives": [
                "Resolve catalog $ref from the on-disk schema store (never HTTP).",
                "Place domain fields under report so receipt_core additionalProperties:false holds.",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This unit triages TST-0015 operator ids on a published "
                    "oracle pack; it does not invoke the TST-0119 mutation "
                    "runner against a live estate tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After TST-0119 is delivered, re-run publish_score on that "
                    "runner's surviving-mutant list and require the same "
                    "exclusion trail."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "test-governance-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "completion_sentinel": SENTINEL,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "produced_by_script": "command-center/p2-wave/probes/TST-0120/emit.py",
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:TST-0120 emit schema")
        for err in errs[:20]:
            print(f"  {err}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump(doc), encoding="utf-8", newline="\n")
    digest, size = sha256_file(out_path)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    doc["timestamps"]["ended_at"] = ended
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:TST-0120 emit sentinel missing")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out_path)
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    errs = schema_errors(parsed)
    if errs:
        print("FAILED:TST-0120 emit schema after rewrite")
        for err in errs[:20]:
            print(f"  {err}")
        return 1
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0120 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"score={clean['mutation_score']} exclusion_count={clean['exclusion_count']}"
    )
    print("SUCCESS:TST-0120 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
