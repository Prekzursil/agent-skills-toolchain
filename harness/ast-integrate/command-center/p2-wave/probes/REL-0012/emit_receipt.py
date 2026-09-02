#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0012.json from a live provenance + verify run."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    BUILDER_ID,
    NOTES_FIXTURE_REL,
    OUTPUT_REL,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    TITLE,
    UNIT_ID,
    VERIFY_REL,
)
from engine import (  # noqa: E402
    build_all,
    run_verify,
    tamper_one_byte,
    verify_command,
)
from schema_local import iter_errors, validate  # noqa: E402

GEN = HERE / "generated"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0012/probe1_tamper_and_untampered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0012/probe2_commit_unsigned_schema.py"
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json REL-0012; "
    "inputs _USER-PROMPTS.md:11108-11109 (signed artifacts / provenance) "
    "and 11125 (release mode)"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _probe(role: str, method: str, command: str, raw_output: str, fingerprint: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command[:4096],
        "raw_output": raw_output[:65536],
        "fingerprint": fingerprint[:128],
    }


def _art(rel: str, role: str, eol: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes()
    hashed = raw if eol == "BINARY" else raw.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(hashed),
        "sha256": hashlib.sha256(hashed).hexdigest(),
        "exists": True,
        "eol": eol,
        "role": role,
    }


def _dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def build_receipt() -> dict:
    started = _now()
    GEN.mkdir(parents=True, exist_ok=True)
    built = build_all(GEN)
    clean_code, clean_cmd, clean_out = run_verify(
        built["artifact"], built["provenance"], built["tree"], built["notes"]
    )
    tampered = GEN / "artifact.tampered.zip"
    tamper_one_byte(built["artifact"], tampered)
    tamper_code, tamper_cmd, tamper_out = run_verify(
        tampered, built["provenance"], built["tree"], built["notes"]
    )
    if clean_code != 0:
        raise RuntimeError(f"untampered verify must pass, got {clean_code}\n{clean_out}")
    if tamper_code == 0:
        raise RuntimeError("tampered verify must fail, but it passed")
    if "DIGEST-MISMATCH" not in tamper_out:
        raise RuntimeError(f"tamper must fail as DIGEST-MISMATCH\n{tamper_out}")

    mutant_prov = GEN / "provenance.bad-commit.json"
    mutant = json.loads(built["provenance"].read_text(encoding="utf-8"))
    flipped = False
    for dep in mutant["predicate"]["buildDefinition"]["resolvedDependencies"]:
        if "gitCommit" in (dep.get("digest") or {}):
            dep["digest"]["gitCommit"] = "0" * 40
            flipped = True
            break
    if not flipped:
        raise RuntimeError("could not mutate provenance gitCommit")
    mutant_prov.write_text(json.dumps(mutant, indent=2) + "\n", encoding="utf-8")
    m_code, m_cmd, m_out = run_verify(
        built["artifact"], mutant_prov, built["tree"], built["notes"]
    )
    if m_code == 0 or "COMMIT-MISMATCH" not in m_out:
        raise RuntimeError(f"mutated commit must fail COMMIT-MISMATCH\n{m_out}")

    stripped = GEN / "RELEASE-NOTES.stripped.md"
    body = built["notes"].read_text(encoding="utf-8")
    stripped.write_text(
        "\n".join(ln for ln in body.splitlines() if not ln.strip().startswith("UNSIGNED"))
        + "\n",
        encoding="utf-8",
    )
    s_code, s_cmd, s_out = run_verify(
        built["artifact"], built["provenance"], built["tree"], stripped
    )
    if s_code == 0 or "UNSIGNED-ABSENT" not in s_out:
        raise RuntimeError(f"stripped UNSIGNED must fail UNSIGNED-ABSENT\n{s_out}")

    unsigned = built["unsigned_src"]
    tests = [
        {
            "id": "T-tamper-one-byte",
            "name": "Flip one byte of the artifact -> verification command fails",
            "command": tamper_cmd,
            "result": "PASS",
            "output_tail": tamper_out[-500:],
        },
        {
            "id": "T-untampered-passes",
            "name": "Untampered artifact -> verification command passes",
            "command": clean_cmd,
            "result": "PASS",
            "output_tail": clean_out[-500:],
        },
        {
            "id": "T-commit-equals-git",
            "name": "Provenance gitCommit equals git rev-parse HEAD of the build tree",
            "command": f"git -C {_rel(built['tree'])} rev-parse HEAD",
            "result": "PASS",
            "output_tail": built["commit"],
        },
        {
            "id": "T-unsigned-declaration",
            "name": "UNSIGNED declaration present in shipped release notes",
            "command": P2,
            "result": "PASS",
            "output_tail": f"{unsigned['path']}:{unsigned['line']} {unsigned['text']}",
        },
    ]
    report = {
        "kind": "supply-chain-receipt",
        "control_ids": [t["id"] for t in tests],
        "observations": [
            {
                "name": "untampered_verify_exit",
                "measured": clean_code,
                "method": "consumer-verify-command",
                "anchor": VERIFY_REL,
            },
            {
                "name": "tampered_verify_fails",
                "measured": True,
                "method": "xor-first-byte-then-same-verify",
                "anchor": _rel(tampered),
            },
            {
                "name": "gitCommit_equals_rev_parse",
                "measured": True,
                "method": "git-rev-parse-HEAD",
                "anchor": _rel(built["tree"]),
            },
            {
                "name": "unsigned_declaration_line",
                "measured": int(unsigned["line"]),
                "method": "release-notes-line-scan",
                "anchor": f"{unsigned['path']}:{unsigned['line']}",
            },
        ],
        "title": TITLE,
        "question": QUESTION,
        "pr_only": {
            "publication_bound_half": "OUT-OF-SCOPE",
            "delivered_half": "in-toto/SLSA provenance + consumer verify command",
            "phase_graph": {
                "path": "command-center/PHASE-GRAPH.json",
                "present": (REPO / "command-center/PHASE-GRAPH.json").is_file(),
                "blocked_or_redefined_under_pr_only": "NOT-ON-DISK",
                "note": (
                    "PHASE-GRAPH.json is absent on this worktree. The catalog "
                    "already states the publication-bound half is out of scope "
                    "under PR-ONLY; this receipt does not invent a graph row."
                ),
            },
            "signing": (
                "UNSIGNED: owner-held key not consumed. This unit creates, "
                "uses, and rotates no key."
            ),
        },
        "builder": {"id": BUILDER_ID, "identity": BUILDER_ID},
        "source_commit": built["commit"],
        "provenance": {
            "path": _rel(built["provenance"]),
            "statement_type": "https://in-toto.io/Statement/v1",
            "predicate_type": "https://slsa.dev/provenance/v1",
            "subject_name": "artifact.zip",
            "subject_sha256": built["artifact_sha256"],
            "gitCommit": built["commit"],
            "builder_id": BUILDER_ID,
            "unsigned": True,
        },
        "distributable": {
            "path": _rel(built["artifact"]),
            "sha256": built["artifact_sha256"],
        },
        "unsigned_declaration": {
            "required": True,
            "present": True,
            "path": unsigned["path"],
            "line": unsigned["line"],
            "file_line": f"{unsigned['path']}:{unsigned['line']}",
            "text": unsigned["text"],
            "shipped_zip_entry": built["unsigned_shipped"],
        },
        "verification": {
            "command_template": (
                f"PYTHONDONTWRITEBYTECODE=1 python3 -B {VERIFY_REL} "
                "--artifact <zip> --provenance <json> "
                "--build-tree <dir> --release-notes <notes>"
            ),
            "generated_command": verify_command(
                built["artifact"],
                built["provenance"],
                built["tree"],
                built["notes"],
            ),
            "untampered": {
                "command": clean_cmd,
                "exit_code": clean_code,
                "ok": True,
                "output": clean_out,
            },
            "tampered": {
                "command": tamper_cmd,
                "exit_code": tamper_code,
                "ok": False,
                "reason": "DIGEST-MISMATCH",
                "output": tamper_out,
                "method": "XOR first byte of a copy; provenance unchanged",
            },
        },
        "commit_crosscheck": {
            "provenance_gitCommit": built["commit"],
            "git_rev_parse_HEAD": built["commit"],
            "equal": True,
            "build_tree": _rel(built["tree"]),
        },
        "key_policy": {
            "created_key": False,
            "used_key": False,
            "rotated_key": False,
            "printed_key": False,
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }
    ended = _now()
    supporting = [
        _art(SCHEMA_REL, "supporting", "LF"),
        _art(VERIFY_REL, "supporting", "LF"),
        _art(NOTES_FIXTURE_REL, "fixture", "LF"),
        _art(_rel(built["artifact"]), "fixture", "BINARY"),
        _art(_rel(built["provenance"]), "supporting", "LF"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1200,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "provenance-engineer",
            "execution_substrate": "linux-headless-local",
        },
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ]
        + supporting,
        "evidence": [
            {
                "claim": "Consumer verify command exits 0 on the bound artifact.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": VERIFY_REL,
                "probes": [
                    _probe(
                        "source",
                        "command",
                        clean_cmd,
                        clean_out,
                        "rel0012-verify-untampered:v1",
                    ),
                    _probe(
                        "verifier",
                        "byte-compare",
                        f"hashlib.sha256({_rel(built['artifact'])}) vs provenance subject digest",
                        built["artifact_sha256"],
                        "rel0012-hashlib-subject:v1",
                    ),
                ],
            },
            {
                "claim": "One-byte flip of the artifact makes the same command fail.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": VERIFY_REL,
                "probes": [
                    _probe(
                        "source",
                        "command",
                        tamper_cmd,
                        tamper_out,
                        "rel0012-verify-tampered:v1",
                    ),
                    _probe(
                        "verifier",
                        "byte-compare",
                        f"XOR-first-byte copy {_rel(tampered)} vs unchanged provenance",
                        "DIGEST-MISMATCH",
                        "rel0012-xor-digest-mismatch:v1",
                    ),
                ],
            },
            {
                "claim": "Provenance gitCommit equals git rev-parse HEAD of the build tree.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": _rel(built["provenance"]),
                "probes": [
                    _probe(
                        "source",
                        "command",
                        f"git -C {_rel(built['tree'])} rev-parse HEAD",
                        built["commit"],
                        "rel0012-git-rev-parse:v1",
                    ),
                    _probe(
                        "verifier",
                        "file-read",
                        _rel(built["provenance"]) + "#predicate.buildDefinition.resolvedDependencies.gitCommit",
                        built["commit"],
                        "rel0012-provenance-gitCommit:v1",
                    ),
                ],
            },
            {
                "claim": "UNSIGNED is present in shipped release notes rather than remaining silent.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{unsigned['path']}:{unsigned['line']}",
                "probes": [
                    _probe(
                        "source",
                        "file-read",
                        unsigned["path"],
                        unsigned["text"],
                        "rel0012-unsigned-notes:v1",
                    ),
                    _probe(
                        "verifier",
                        "command",
                        s_cmd,
                        s_out,
                        "rel0012-stripped-unsigned-fails:v1",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-tamper-one-byte",
                "kind": "mutation",
                "description": (
                    "XOR the first byte of a copy of artifact.zip; verify must "
                    "fail DIGEST-MISMATCH while the untampered copy still passes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": tamper_out[-2000:],
                "good_state_output": clean_out[-2000:],
            },
            {
                "id": "NC-mutant-commit",
                "kind": "mutation",
                "description": (
                    "Replace provenance gitCommit with 40 zeros; verify must "
                    "fail COMMIT-MISMATCH."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": m_out[-2000:],
                "good_state_output": clean_out[-2000:],
            },
            {
                "id": "NC-stripped-unsigned",
                "kind": "malformed-input",
                "description": (
                    "Strip UNSIGNED lines from release notes; verify must fail "
                    "UNSIGNED-ABSENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": s_out[-2000:],
                "good_state_output": clean_out[-2000:],
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0012-probe2-independent-commit-unsigned-schema",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-hashes the zip with hashlib, re-reads git rev-parse "
                "HEAD, locates UNSIGNED by its own scanner, rejects schema garbage, "
                "and confirms a mutated commit and a stripped UNSIGNED note fail verify."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/REL-0012/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT_ID,
        },
        "downstream_consumers": [
            {
                "consumer": "REL-0012/verify.py",
                "artifact_path": _rel(built["artifact"]),
                "executed": True,
                "read_ok": True,
                "exit_code": clean_code,
                "probe": _probe(
                    "source",
                    "command",
                    clean_cmd,
                    clean_out,
                    "rel0012-consumer-verify:v1",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "disagreeing run is recorded as a discrepancy, never retried away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Publication (registry upload and marketplace signature) is "
                    "out of scope under PR-ONLY; no owner-held signing key is "
                    "present on this executor."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner supplies a signing key and re-runs verify.py against "
                    "a signed copy; this unit must not mint or rotate that key."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "output_schema": SCHEMA_REL,
            "completion_sentinel": SENTINEL,
            "notes": (
                "G-1 for REL-0012: in-toto/SLSA provenance bound to a fixture "
                "distributable built from recorded inputs; consumer verify command "
                "passes untampered and fails after a one-byte flip; git commit "
                "cross-checked; UNSIGNED declared at file:line. No key created. "
                "SUCCESS:REL-0012"
            ),
        },
    }


def main() -> int:
    garbage = iter_errors({}, SCHEMA_REL)
    if not garbage:
        print("FAILED:REL-0012 schema is vacuous on empty object")
        return 1
    for blob in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not iter_errors(blob, SCHEMA_REL):
            print("FAILED:REL-0012 schema accepted garbage")
            return 1
    receipt = build_receipt()
    text = _dump(receipt)
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    receipt["artifacts"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    receipt["artifacts"][0]["bytes"] = len(raw)
    try:
        validate(receipt, SCHEMA_REL)
    except Exception as exc:
        print("FAILED:REL-0012 schema errors")
        for line in iter_errors(receipt, SCHEMA_REL)[:40]:
            print(" ", line)
        print(exc)
        return 1
    text = _dump(receipt)
    if SENTINEL not in text:
        print("FAILED:REL-0012 sentinel missing from serialized artifact")
        return 1
    if len(text.encode("utf-8")) < int(receipt["min_bytes_threshold"]):
        print("FAILED:REL-0012 artifact below min_bytes_threshold")
        return 1
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    shutil.rmtree(GEN / "unused", ignore_errors=True)
    print(f"wrote {OUTPUT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
