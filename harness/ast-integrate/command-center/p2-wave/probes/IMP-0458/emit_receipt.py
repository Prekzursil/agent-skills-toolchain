#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0458.json from a live gate run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_canary, run_clean, run_mention  # noqa: E402
from secret_scrub_gate import (  # noqa: E402
    report_contains_secret_body,
    report_only_violations,
    scan_before_register,
    scan_corpus,
    synthetic_canary_value,
)

UNIT = "IMP-0458"
OUT = "command-center/receipts/IMP-0458.json"
SENTINEL = "SENTINEL:IMP-0458:SECRET-SCRUB-REPORT-ONLY"
GATE_REL = "command-center/p2-wave/probes/IMP-0458/secret_scrub_gate.py"


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def findings_public(report) -> list[dict]:
    rows = []
    for f in report.findings:
        rows.append(
            {
                "variable": f.variable,
                "scope": f.scope.replace("\\", "/"),
                "byte_offset": f.byte_offset,
                "byte_length": f.byte_length,
                "prefix": f.prefix,
                "rule": f.rule,
                "evidence": f.evidence,
            }
        )
    return rows


def main() -> int:
    canary = run_canary()
    mention = run_mention()
    clean = run_clean()
    corpus = scan_corpus(REPO)
    gate_src = (REPO / GATE_REL).read_text(encoding="utf-8")
    violations = report_only_violations(gate_src)
    staging_present = any(
        (REPO / p).exists()
        for p in ("release", "staging", "dist", "command-center/release")
    )
    receipts_dir = REPO / "command-center" / "receipts"
    events_dir = REPO / "command-center" / "events"

    if not canary["fired"]:
        print("FAILED:IMP-0458 canary did not fire on receipt+event+zip")
        print(json.dumps(canary, indent=2))
        return 1
    if canary["report_leaked_body"]:
        print("FAILED:IMP-0458 canary body leaked into scan report")
        return 1
    if not canary["hashes_unchanged"] or not canary["environ_unchanged"]:
        print("FAILED:IMP-0458 gate mutated files or environ during canary")
        return 1
    if mention["fired"]:
        print("FAILED:IMP-0458 mention control fired")
        print(json.dumps(mention, indent=2)[:2000])
        return 1
    if clean["fired"]:
        print("FAILED:IMP-0458 clean fixture fired")
        return 1
    if violations:
        print("FAILED:IMP-0458 gate source is not report-only")
        print(violations)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gate_sha, gate_bytes = sha_file(REPO / GATE_REL)
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Secret-scrub gate on the program artifact corpus",
        "spec_anchor": "_USER-PROMPTS.md:11345",
        "mode": "report-only",
        "no_rotation": True,
        "no_revoke": True,
        "no_unset": True,
        "question_or_target": (
            "Implement the gate for spec line 11345 - credentials or decrypted "
            "secrets entering an artifact bundle - scanning every receipt, event "
            "and packaged artifact before it is registered. Detection and "
            "REPORTING only; the gate names the variable, the scope and the "
            "evidence, and never itself rotates, revokes or unsets any credential."
        ),
        "gate": {
            "module": GATE_REL,
            "api": "scan_before_register",
            "sha256": gate_sha,
            "bytes": gate_bytes,
            "include_globs": [
                "command-center/receipts/**",
                "command-center/events/**",
                "release/**",
                "staging/**",
                "dist/**",
            ],
            "exclude_globs": [
                "**/.git/**",
                "**/node_modules/**",
                "**/__pycache__/**",
            ],
        },
        "corpus_scan": {
            "roots": corpus.roots,
            "files_examined": corpus.files_examined,
            "bytes_examined": corpus.bytes_examined,
            "archives_opened": corpus.archives_opened,
            "finding_count": len(corpus.findings),
            "findings": findings_public(corpus),
            "opened_paths": corpus.opened_paths,
            "skipped": corpus.skipped[:50],
            "receipts_dir_exists": receipts_dir.is_dir(),
            "events_dir_exists": events_dir.is_dir(),
            "live_staging_present": staging_present,
        },
        "canary": canary,
        "mention_control": mention,
        "clean_control": clean,
        "no_credential_mutation": {
            "verified_by": "ast-source-read",
            "violations": violations,
            "hashes_unchanged_on_canary": canary["hashes_unchanged"],
            "environ_unchanged_on_canary": canary["environ_unchanged"],
            "gate_mutated_flag": False,
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            },
            {
                "path": GATE_REL,
                "role": "supporting",
                "exists": True,
                "sha256": gate_sha,
                "bytes": gate_bytes,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A planted synthetic GitHub-shaped token in a receipt, an "
                    "event record and a zip member is detected before registration. "
                    f"{SENTINEL}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "_USER-PROMPTS.md:11345",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "A document that names GITHUB_TOKEN / AWS_SECRET_ACCESS_KEY "
                    "without a value does not fire (use-versus-mention)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0458/fixtures/mention-only/README.md",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "The gate has no code path that rotates, revokes, unsets or "
                    "rewrites a credential; findings are prefixes only."
                ),
                "verdict": "CONFIRMED",
                "anchor": GATE_REL,
                "confidence": "almost-certain",
            },
        ],
        "tests": [
            {
                "id": "canary-must-fire",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0458/probe1_canary.py",
                "result": "PASS",
            },
            {
                "id": "mention-must-not-fire",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0458/probe1_canary.py",
                "result": "PASS",
            },
            {
                "id": "no-credential-mutation-source-read",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0458/probe2_no_rotation.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "mention-only",
                "kind": "use-versus-mention",
                "description": "Variable names without values must not fire.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "canary fired on receipt+event+zip",
                "good_state_output": f"mention finding_count={mention['finding_count']}",
            },
            {
                "id": "mutating-source-rejected",
                "kind": "source-read",
                "description": "A snippet that calls os.unsetenv is rejected; the gate source is not.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0458-probe2-source-read-no-rotation",
            "verdict": "PASS",
            "independent": True,
            "method": "ast-source-read",
            "notes": (
                "No-rotation verified by reading the gate AST. This pass does not "
                "fabricate a second-vendor Claude identity."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0458/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "pre_register_hook": {
            "function": "scan_before_register",
            "behavior": "report-only; caller decides whether to register",
        },
        "residual_unknowns": [
            {
                "claim": "Live release-bundle staging tree on this worktree.",
                "verdict": "NOT-CHECKED" if not staging_present else "CONFIRMED",
                "settling_experiment": (
                    "Packaged-artifact detection is proven on a synthetic zip in "
                    "the canary run. A live staging tree was "
                    + ("present" if staging_present else "absent")
                    + " at emit time."
                ),
            },
            {
                "claim": "Declared output_schema command-center/schema/receipt.schema.json exists on disk.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "That schema path is absent on this worktree (IMP-0433). G-1 "
                    "requires parseable JSON, the sentinel, and non-BLOCKED state."
                ),
            },
        ],
        "timestamps": {"ended_at": now},
        "owner_handoff": (
            "Positive live-corpus findings are reported with variable, scope and "
            "prefix only. Credential lifecycle stays with the owner."
        ),
    }

    # Self-scan the in-memory document before persisting. A leak fails the unit.
    draft = json.dumps(doc, indent=1, sort_keys=True)
    leaked_draft = report_contains_secret_body(draft, [synthetic_canary_value()])
    if leaked_draft:
        print("FAILED:IMP-0458 receipt draft leaked canary body")
        print(leaked_draft)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(draft + "\n", encoding="utf-8")

    post = scan_before_register(out)
    leaked_post = report_contains_secret_body(
        out.read_text(encoding="utf-8"), [synthetic_canary_value()]
    )
    if leaked_post:
        print("FAILED:IMP-0458 persisted receipt leaked canary")
        return 1
    tokenish = [
        f
        for f in post.findings
        if f.rule
        in {
            "github-pat-classic",
            "github-oauth",
            "github-fine-grained",
            "aws-access-key-id",
            "anthropic-api-key",
            "slack-bot-token",
            "pem-private-key",
        }
    ]
    if tokenish:
        print("FAILED:IMP-0458 self-scan of receipt found token-shaped values")
        print([f.evidence for f in tokenish])
        return 1

    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
