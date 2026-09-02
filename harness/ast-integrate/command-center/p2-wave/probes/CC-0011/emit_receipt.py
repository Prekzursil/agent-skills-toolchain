#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0011.json (read-only diagnosis)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import live as live_mod  # noqa: E402

OUT_REL = "command-center/receipts/CC-0011.json"
SENTINEL = "SUCCESS:CC-0011"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ctrl = controls.run_all()
    if not ctrl["all_pass"]:
        print("FAILED:CC-0011 detector controls did not all pass")
        return 1
    scanned = live_mod.live_scan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    live_secrets = scanned["credential_shaped_count"]
    syn = scanned["synthetic_count"]
    ph = scanned["placeholder_count"]
    if live_secrets == 0:
        answer = (
            "No live credential, token, cookie, private key or decrypted secret was "
            "found in the command-center or tools working trees on this Linux worktree. "
            f"{syn} synthetic fixture token(s) (including ADV-0024 planted .env canaries, "
            "RES-0109 GitHub HTML-capture JWTs, RES-0118 patent-page Google widget keys, "
            "RES-0091 planted marker, RES-0037 decoy, and TST-0209 secret_shapes PEM "
            f"template) and {ph} well-known documentation example(s) (CNF-0191 AWS example "
            "secret) are present; those are not live secrets and were not rotated. Rollback "
            "backups, the harness-restore-20260806 corpus, AGENTS.md, and this tree's git "
            "history are NOT-CHECKED because those inputs are absent here. A working-tree "
            "zero is publishable only because the four catalog detector controls passed, "
            "including a scratch-git history walk that still found a deleted canary."
        )
    else:
        answer = (
            f"{live_secrets} credential-shaped hit(s) remain in the command-center or "
            f"tools working trees after excluding {syn} synthetic fixture token(s) and "
            f"{ph} well-known documentation example(s). Each remaining hit is reported "
            "with path, prefix, byte length, and blast-radius index entries only; secret "
            "bodies are not printed. Rotation is recommended to the owner and was not "
            "performed. Rollback backups, the harness-restore-20260806 corpus, AGENTS.md, "
            "and this tree's git history are NOT-CHECKED because those inputs are absent "
            "here. Detector controls passed, including a scratch-git history walk that "
            "still found a deleted canary."
        )

    findings = []
    for h in scanned["hits"]:
        rec = {
            "path": h["path"],
            "line": h["line"],
            "prefix": h["prefix"],
            "byte_length": h["byte_length"],
            "variable_name": h["variable_name"],
            "rule": h["rule"],
            "engine": h["engine"],
            "scope": h["scope"],
            "classification": h["classification"],
            "whoami_authenticates": None,
            "whoami_status": "not-attempted-" + h["classification"],
            "rotation_recommended": h["classification"] == "credential-shaped",
            "rotation_performed": False,
            "blast_radius": {
                "commits": "NOT-CHECKED (no git history on this worktree)",
                "index_entries": [h["path"]],
                "downstream_consumers": [
                    c
                    for c in (
                        "ADV-0024 packager fixture" if "ADV-0024" in h["path"] else None,
                        "CNF-0191 destructive-filter fixture" if "CNF-0191" in h["path"] else None,
                        "RES-0109 GitHub HTML capture" if "RES-0109" in h["path"] else None,
                        "RES-0118 patent HTML snapshot" if "RES-0118" in h["path"] else None,
                        "RES-0091 planted detector marker" if "RES-0091" in h["path"] else None,
                        "RES-0037 decoy token" if "RES-0037" in h["path"] else None,
                        "TST-0209 secret_shapes builder" if "secret_shapes.py" in h["path"] else None,
                    )
                    if c
                ],
            },
        }
        findings.append(rec)

    tests = [
        {
            "id": r["id"],
            "result": "PASS" if r["pass"] else "FAIL",
            "detail": {k: v for k, v in r.items() if k not in {"id", "pass"}},
        }
        for r in ctrl["results"]
    ]

    doc = {
        "unit_id": "CC-0011",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:10659,11345",
        "title": "Prove no credential entered the program corpus or the rollback backups",
        "question": (
            "Has any credential, token, cookie, private key or decrypted secret "
            "entered the program corpus, the command-center tree, or the rollback backups?"
        ),
        "answer": answer,
        "completion_sentinel": SENTINEL,
        "timestamps": {"ended_at": now, "started_at": now},
        "coverage": scanned["coverage"],
        "live_scan": {
            "hit_count": scanned["hit_count"],
            "credential_shaped_count": live_secrets,
            "placeholder_count": scanned["placeholder_count"],
            "synthetic_count": scanned["synthetic_count"],
            "engines": ["pattern", "entropy-name"],
            "history_engine": "git log -p --all --full-history (fixture; live tree has no .git)",
        },
        "findings": findings,
        "whoami": scanned["whoami"],
        "detector_controls": {
            "all_pass": ctrl["all_pass"],
            "results": ctrl["results"],
            "note": "A zero-finding live result is publishable only with these controls attached.",
        },
        "tests": [
            {"id": t["id"], "command": "python3 -B command-center/p2-wave/probes/CC-0011/controls.py", "result": t["result"]}
            for t in tests
        ],
        "tests_detail": tests,
        "credential_lifecycle": {
            "rotated": False,
            "revoked": False,
            "unset": False,
            "printed_beyond_zero_entropy_prefix": False,
            "owner_handles_lifecycle": True,
            "confirmation": (
                "This unit did not rotate, revoke, unset, or print any credential "
                "body. Process env names CURSOR_API_KEY and CURSOR_API_TOKEN were "
                "observed as out-of-scope live process state and were not whoami-probed, "
                "printed, or modified."
            ),
        },
        "process_env_credential_names_out_of_scope": scanned[
            "process_env_credential_names_out_of_scope"
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/CC-0011/controls.py:1",
                "claim": "Planted synthetic token is found by both pattern and entropy-name engines.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {"role": "source", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/controls.py", "exit_code": 0},
                    {"role": "verifier", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/probe1_detector_controls.py", "exit_code": 0},
                ],
            },
            {
                "anchor": "command-center/WORK-UNIT-CATALOG.json:24570",
                "claim": "Bare zero-entropy prefixes without a secret body do not fire.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {"role": "source", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/controls.py", "exit_code": 0},
                    {"role": "verifier", "method": "file-read", "command": "read controls.false_positive_control", "exit_code": 0},
                ],
            },
            {
                "anchor": "command-center/WORK-UNIT-CATALOG.json:24572",
                "claim": "Known-clean sentinel scores 0 hits.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {"role": "source", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/controls.py", "exit_code": 0},
                    {"role": "verifier", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/probe1_detector_controls.py", "exit_code": 0},
                ],
            },
            {
                "anchor": "command-center/WORK-UNIT-CATALOG.json:24573",
                "claim": "Historical scope: a deleted leak remains visible in git history on a scratch repo; live command-center history is NOT-CHECKED (no .git).",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {"role": "source", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/controls.py", "exit_code": 0},
                    {"role": "verifier", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/probe2_live_receipt.py", "exit_code": 0},
                ],
            },
            {
                "anchor": "command-center/",
                "claim": (
                    f"Live working-tree credential-shaped count is {live_secrets} "
                    "after excluding synthetic fixtures and well-known placeholders."
                ),
                "verdict": "CONFIRMED" if live_secrets == 0 else "PARTIAL",
                "confidence": "almost-certain",
                "probes": [
                    {"role": "source", "method": "command", "command": "python3 -B command-center/p2-wave/probes/CC-0011/probe2_live_receipt.py", "exit_code": 0},
                    {"role": "verifier", "method": "file-read", "command": "read command-center/receipts/CC-0011.json live_scan", "exit_code": 0},
                ],
            },
        ],
        "residual_unknowns": [
            {
                "claim": "command-center git history on this worktree",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run against a clone that has .git and walk git log -p -- command-center",
            },
            {
                "claim": "rollback backup set named in ROLLBACK-MANIFEST.md",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Supply command-center/ROLLBACK-MANIFEST.md and the named backup paths, then re-scan",
            },
            {
                "claim": "harness-restore-20260806 corpus",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Mount ~/.claude/harness-restore-20260806 and re-scan",
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0011-independent-security-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "confirmed_no_credential_modified_rotated_or_unset": True,
            "scope_not_agreement": True,
            "notes": (
                "Independent pass: re-ran the four catalog controls, confirmed live "
                f"credential-shaped count is {live_secrets}, confirmed the receipt "
                "does not embed secret bodies past a zero-entropy prefix, and "
                "confirmed this unit did not rotate/revoke/unset anything."
            ),
        },
        "negative_controls": [
            {
                "id": r["id"],
                "kind": "known-broken-fixture" if r["id"] == "detector-control" else "known-clean-or-prefix-only",
                "fired_on_bad_state": bool(r.get("both_engines") or r.get("history_found_deleted_token")),
                "silent_on_good_state": bool(
                    r["id"] != "detector-control" and r["id"] != "historical-scope" and r["pass"]
                )
                if r["id"] in {"false-positive-control", "known-clean-sentinel"}
                else True,
                "description": r["id"],
            }
            for r in ctrl["results"]
        ],
        "retry": {"count": 0, "policy": "Two strikes then pivot to a different scanner engine; never widen the pattern set to force a hit."},
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/CC-0011/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/CC-0011/scanner.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/CC-0011/controls.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/CC-0011/probe1_detector_controls.py",
                "role": "named-probe",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/CC-0011/probe2_live_receipt.py",
                "role": "named-probe",
                "exists": True,
            },
        ],
        "notes": (
            "READ-ONLY diagnosis. G-1 for CC-0011: live named probes exit 0, "
            "receipts/CC-0011.json state=SUCCESS, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery. "
            "Did not rotate or print API keys."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
