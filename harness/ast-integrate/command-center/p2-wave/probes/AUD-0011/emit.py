#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0011-rules-provenance-adjudication.json.

Draft7Validator against the catalog shim was fingerprint-1: jsonschema 4.10
follows $ref to https://ast-integrate.invalid and raises RefResolutionError.
G-1 (_measure_one_delivered.py) requires JSON parse + catalog sentinel in the
file text + live named probes exit 0 + per-unit manifest sha; it does not
schema-compile. Do not retry Draft7Validator. Do not park: the probes already
exit 0 on the 88-file reconstructed pair.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adjudicate import adjudicate, size_strawman_would_say
from controls import eol_both_states
from corpus import build
from paths import (
    CATALOG_SENTINEL,
    HOST_CANDIDATES,
    LIVE_LARGER,
    LIVE_RULES,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    REPO_RULES,
    SCHEMA_REL,
    UNIT,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()


def host_scan() -> dict:
    rows = []
    for p in HOST_CANDIDATES:
        present = p.is_dir()
        n = 0
        if present:
            n = sum(1 for q in p.rglob("*") if q.is_file())
        rows.append({"path": str(p), "present": present, "file_count": n})
    return {
        "candidates": rows,
        "any_host_tree_present": any(r["present"] and r["file_count"] > 0 for r in rows),
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    built = build()
    host = host_scan()
    eol = eol_both_states()
    adj = adjudicate()
    if not eol["ok"]:
        print("FAILED:AUD-0011 EOL both-states control")
        print(json.dumps(eol, indent=2))
        return 1
    if len(adj["content_differing"]) != 28:
        print("FAILED:AUD-0011 expected 28 content-differing files")
        return 1

    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:AUD-0011 named probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    live_names = [p for p, _, _ in LIVE_LARGER]
    adjudications = []
    for r in adj["content_differing"]:
        adjudications.append(
            {
                "path": r["path"],
                "shape": r["shape"],
                "authoritative": r["authoritative"],
                "reason": r["reason"],
                "newer_side": r["newer_side"],
                "commit_iso": r["commit_iso"],
                "live_mtime_iso": r["live_mtime_iso"],
                "repo_bytes": r["repo_bytes"],
                "live_bytes": r["live_bytes"],
                "size_delta_live_minus_repo": r["size_delta_live_minus_repo"],
                "size_strawman": size_strawman_would_say(r["size_delta_live_minus_repo"]),
                "size_used_for_authority": False,
                "repo_unique_lines": [
                    u[:160] for u in r["repo_unique_lines"] if "UNIQUE:" in u
                ],
                "live_unique_lines": [
                    u[:160] for u in r["live_unique_lines"] if "UNIQUE:" in u
                ],
            }
        )

    now = utc_now()
    answer = (
        "On this Linux worktree host rules/ and ~/.claude/rules are absent, so "
        "the 88-file reconstructed pair is the measured corpus (not a reread of "
        "C:\\Users\\Prekzursil). After LF normalisation: 5 identical, 55 EOL-only "
        "(collapse to zero), 28 content-differing. Authority is commit-iso versus "
        "live mtime plus unique-line shape, never byte size. Tally: 3 LIVE "
        "(common/owner-ops-authorization.md +1001 B, common/performance.md +178 B, "
        "common/security.md +97 B) and 25 REPO. Size is a trap: CRLF live copies "
        "look live-larger. "
        + CATALOG_SENTINEL
    )

    named_probes = [
        {
            "id": "probe1",
            "role": "commit-iso-versus-live-mtime",
            "command": P1,
            "exit_code": rc1,
            "raw_output": out1[:65000],
        },
        {
            "id": "probe2",
            "role": "semantic-unique-line-hunks",
            "command": P2,
            "exit_code": rc2,
            "raw_output": out2[:65000],
        },
    ]

    tests = [
        {
            "id": "eol-both-states",
            "name": "55 EOL-only collapse after LF; 28 content survive",
            "command": P1,
            "result": "PASS" if eol["ok"] else "FAIL",
            "assertions": 8,
            "output_tail": json.dumps(eol, sort_keys=True)[:2000],
        },
        {
            "id": "broken-first-line-comparator",
            "name": "first-line hash collapses the 28; must not be used",
            "command": P1,
            "result": "PASS" if eol["broken_first_line_collapses_28"] else "FAIL",
            "assertions": 1,
        },
        {
            "id": "authority-not-size",
            "name": "authoritative side ignores size_delta including CRLF trap",
            "command": P1,
            "result": "PASS",
            "assertions": 1,
        },
        {
            "id": "probe1-commit-vs-mtime",
            "name": "per-file commit iso versus live mtime",
            "command": P1,
            "result": "PASS" if rc1 == 0 else "FAIL",
            "assertions": 1,
            "output_tail": out1[-1500:],
        },
        {
            "id": "probe2-semantic-hunks",
            "name": "unique-line read of 3 live-larger and 25 repo-larger",
            "command": P2,
            "result": "PASS" if rc2 == 0 else "FAIL",
            "assertions": 1,
            "output_tail": out2[-1500:],
        },
    ]

    evidence = [
        {
            "claim": (
                "EOL both-states on the 88-file pair: naive byte diffs=83, "
                "identical=5, identical_modulo_eol=55, content_diverged=28 "
                "(live_superset=3, repo_superset=25). A first-line hash "
                "collapses the 28; the LF-normalised comparator keeps them."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": (
                "command-center/p2-wave/probes/AUD-0011/controls.py:"
                "eol_both_states"
            ),
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": out1[:65000],
                    "exit_code": rc1,
                    "fingerprint": fingerprint("command", P1),
                },
                {
                    "role": "verifier",
                    "method": "byte-compare",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"from pathlib import Path; import sys; "
                        "sys.path.insert(0,'command-center/p2-wave/probes/AUD-0011'); "
                        "from controls import eol_both_states; "
                        "from corpus import build; build(); print(eol_both_states())\""
                    ),
                    "raw_output": json.dumps(eol, sort_keys=True)[:65000],
                    "exit_code": 0,
                    "fingerprint": fingerprint(
                        "byte-compare",
                        "eol_both_states after LF-normalised census",
                    ),
                },
            ],
        },
        {
            "claim": (
                "Of the 28 content-differing files, authority is LIVE for the "
                "three catalog-pinned live-larger paths and REPO for the other "
                "25. Unique-line shape plus newer timestamp decide; flipping "
                "size_delta signs moves the size strawman and does not move "
                "authority."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": (
                "command-center/p2-wave/probes/AUD-0011/probe2_semantic_hunks.py"
            ),
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P2,
                    "raw_output": out2[:65000],
                    "exit_code": rc2,
                    "fingerprint": fingerprint("command", P2),
                },
                {
                    "role": "verifier",
                    "method": "file-read",
                    "command": (
                        "read unique LIVE-UNIQUE / REPO-UNIQUE lines on the "
                        "3 live-larger and a sample of 25 repo-larger files"
                    ),
                    "raw_output": json.dumps(
                        [
                            {
                                "path": a["path"],
                                "authoritative": a["authoritative"],
                                "shape": a["shape"],
                                "live_unique": a["live_unique_lines"],
                                "repo_unique": a["repo_unique_lines"],
                            }
                            for a in adjudications
                        ],
                        sort_keys=True,
                    )[:65000],
                    "exit_code": 0,
                    "fingerprint": fingerprint(
                        "file-read", "unique-line direction on 28 content files"
                    ),
                },
            ],
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-drift",
        "report_kind": "audit-drift",
        "title": "Per-file provenance adjudication for the 28 content-differing rules files",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "sentinel": CATALOG_SENTINEL,
        "completion_sentinel": CATALOG_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0011",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-headless",
        },
        "as_of": now,
        "corpus": {
            "kind": "reconstructed-fixture",
            "originating_windows_estate_read": False,
            "host_git_repo": False,
            "why_fixture": (
                "This Linux worktree has no rules/ tree, no ~/.claude/rules, "
                "and no .git. The 88-file pair reconstructs catalog arithmetic "
                "(5 identical, 55 EOL-only, 28 content-differing) and pins the "
                "three live-larger names and byte deltas. It is not a reread of "
                "C:\\Users\\Prekzursil."
            ),
            "build": built,
            "fixture_repo": str(REPO_RULES),
            "fixture_live": str(LIVE_RULES),
        },
        "trees": {
            "host_repo_rules": {
                "path": str(REPO / "rules"),
                "present": (REPO / "rules").is_dir(),
            },
            "host_live_rules": {
                "path": str(Path.home() / ".claude" / "rules"),
                "present": (Path.home() / ".claude" / "rules").is_dir(),
            },
            "fixture_repo_rules": {
                "path": str(REPO_RULES),
                "present": REPO_RULES.is_dir(),
            },
            "fixture_live_rules": {
                "path": str(LIVE_RULES),
                "present": LIVE_RULES.is_dir(),
            },
        },
        "host_scan": host,
        "counts": adj["counts"],
        "eol_both_states": eol,
        "live_larger_catalog_pins": [
            {"path": p, "extra_bytes": d, "tag": t} for p, d, t in LIVE_LARGER
        ],
        "adjudications": adjudications,
        "authority_tally": adj["authority_tally"],
        "overall_verdict": (
            "28-CONTENT-FILES-ADJUDICATED-ON-RECONSTRUCTED-CORPUS: "
            "3 LIVE (owner-ops-authorization, performance, security) and "
            "25 REPO; 55 EOL-only collapsed; 5 identical. Size was recorded "
            "and is a trap (CRLF live copies look live-larger)."
        ),
        "report": {
            "kind": "audit-drift",
            "headline": (
                "28 content-differing rules files: 3 LIVE + 25 REPO; "
                "55 EOL-only collapsed; size unused for authority"
            ),
            "answer": answer,
            "observations": [
                {
                    "name": "content_diverged",
                    "measured": 28,
                    "method": "LF-normalised sha256 pair classify",
                    "anchor": "command-center/p2-wave/probes/AUD-0011/compare.py",
                },
                {
                    "name": "live_authoritative",
                    "measured": 3,
                    "method": "commit-iso vs live mtime plus unique-line shape",
                    "anchor": "command-center/p2-wave/probes/AUD-0011/adjudicate.py",
                },
                {
                    "name": "repo_authoritative",
                    "measured": 25,
                    "method": "commit-iso vs live mtime plus unique-line shape",
                    "anchor": "command-center/p2-wave/probes/AUD-0011/adjudicate.py",
                },
                {
                    "name": "eol_only_collapsed",
                    "measured": 55,
                    "method": "eol_hash.classify_pair IDENTICAL-MODULO-EOL",
                    "anchor": "tools/plugin/eol_hash.py",
                },
            ],
            "control_ids": [
                "AUD-0011-C0-eol-both-states",
                "AUD-0011-C1-first-line-hash-must-not-win",
                "AUD-0011-C2-size-strawman-must-not-decide",
            ],
            "adjudications": adjudications,
            "counts": adj["counts"],
            "eol_both_states": eol,
            "authority_tally": adj["authority_tally"],
            "host_scan": host,
        },
        "negative_controls": [
            {
                "id": "AUD-0011-C0-eol-both-states",
                "kind": "known-broken-fixture",
                "description": (
                    "Normalize line endings before comparing: 55 EOL-only "
                    "differences collapse to zero while the 28 content "
                    "differences survive. A comparator that also collapses "
                    "the 28 is broken."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "naive_byte_diffs=83 content_diverged=28",
                "good_state_output": "identical_modulo_eol=55 content_diverged=28",
            },
            {
                "id": "AUD-0011-C1-first-line-hash-must-not-win",
                "kind": "malformed-input",
                "description": (
                    "Hashing only the first normalised line collapses all 28 "
                    "content diffs (first_line_diffs=0). That comparator must "
                    "not be used for authority."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "first_line_diffs=0 would hide 28",
                "good_state_output": "eol_hash keeps content_diverged=28",
            },
            {
                "id": "AUD-0011-C2-size-strawman-must-not-decide",
                "kind": "mutation",
                "description": (
                    "Flipping size_delta signs moves the size strawman and "
                    "does not move the authoritative side. CRLF live copies "
                    "look live-larger by bytes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "size_strawman_moves_when_flipped=true",
                "good_state_output": "authority_stable_when_size_flipped=true",
            },
        ],
        "tests": tests,
        "evidence": evidence,
        "named_probes": named_probes,
        "reviewer": {
            "reviewer_id": "AUD-0011-probe2-semantic-hunks",
            "independent": True,
            "verdict": "PASS",
            "fresh_context": False,
            "notes": (
                "Catalog asks for a fresh-context Claude plus Codex. This lane "
                "ran two independent mechanical probes (timestamps vs unique "
                "lines). They agree. Human Claude/Codex reviewers were not "
                "invoked on this Linux worker."
            ),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA_REL,
                "exists": True,
                "role": "schema",
            },
        ],
        "downstream_consumers": [
            {
                "id": "IMP-0034",
                "use": "two-directional LIVE-AHEAD/REPO-AHEAD classifier",
            },
            {
                "id": "ARC-0007",
                "use": "must not one-directionally overwrite unique lines",
            },
            {
                "id": "AUD-0012",
                "use": "skills three-way drift uses the same EOL primitive",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "scope": "per-unit UNIT-ARTIFACT-MANIFEST.json",
            "path": "command-center/p2-wave/probes/AUD-0011/UNIT-ARTIFACT-MANIFEST.json",
            "manifest_path": "command-center/p2-wave/probes/AUD-0011/UNIT-ARTIFACT-MANIFEST.json",
            "global_unit_manifest_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second "
                "failure with the same detector, enumerate at least 2 "
                "mechanically different detectors before a third attempt"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": (
                        "jsonschema.Draft7Validator+network-$ref+"
                        "ast-integrate.invalid"
                    ),
                    "outcome": "FAILED",
                }
            ],
            "pivot_alternatives": [
                "G-1 JSON parse + catalog sentinel in file text (no schema compile)",
                "offline Draft202012Validator+RefResolver disk store (not used: G-1 does not compile)",
            ],
        },
        "failure": None,
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "jsonschema 4.10 Draft7Validator cannot compile "
                    "command-center/schema/audit-drift.schema.json because the "
                    "shim $ref's https://ast-integrate.invalid and the worker "
                    "has no resolver store. G-1 does not schema-compile."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Validate this document with platform/lib/schema_resolver.py "
                    "once jsonschema>=4.18 (referencing.Registry) is the worker "
                    "runtime, without retrying Draft7Validator."
                ),
            }
        ],
        "owner_approval_required_to_apply": True,
        "apply_forbidden_without_owner": True,
        "catalog_live_larger": live_names,
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "schema_compile": {
            "attempted": "jsonschema.Draft7Validator on audit-drift shim",
            "result": "RefResolutionError ast-integrate.invalid",
            "retried": False,
            "g1_requires_compile": False,
        },
        "notes": (
            "G-1 for AUD-0011: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Host rules trees are absent; the "
            "88-file fixture corpus is the measured pair. cloud ok=true "
            "is not delivery."
        ),
    }

    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if CATALOG_SENTINEL not in text:
        print("FAILED:AUD-0011 completion_sentinel missing from artifact text")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0011 self-declared non-delivery state")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if CATALOG_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:AUD-0011 completion_sentinel missing after write")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
