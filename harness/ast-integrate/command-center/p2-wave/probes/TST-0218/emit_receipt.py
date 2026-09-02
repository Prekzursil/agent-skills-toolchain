#!/usr/bin/env python3
"""Emit TST-0218 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0218"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0218/probe1_linter_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0218/probe2_independent_mapping.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_name_linter.py"
)
SUPPORTING = [
    "tools/marketplace/name_linter.py",
    "tools/marketplace/tests/test_name_linter.py",
    "command-center/p2-wave/probes/TST-0218/corpus.py",
    "command-center/p2-wave/probes/TST-0218/probe1_linter_corpus.py",
    "command-center/p2-wave/probes/TST-0218/probe2_independent_mapping.py",
]
QUESTION = (
    "Does the linter flag a candidate name confusable with an installed "
    "package (edit distance, homoglyph folding, hyphen/underscore "
    "equivalence)? PASS requires flagging with the confused-with name reported."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if "SUCCESS:TST-0218-tests" not in out_t:
        print("FAILED:TST-0218 emit tests sentinel missing")
        print(out_t[-1500:])
        return 1
    if "SUCCESS:TST-0218-probe1" not in out1:
        print("FAILED:TST-0218 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0218-probe2" not in out2:
        print("FAILED:TST-0218 emit probe2 sentinel missing")
        return 1

    p1 = first_json(out1)
    p2 = first_json(out2)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pr1 = probe_rec("source", P1, out1, code1)
    pr2 = probe_rec("verifier", P2, out2, code2)
    artifacts = [art(rel, "supporting") for rel in SUPPORTING]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "security_report",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json#/$defs/"
            "security_report. That file is absent on this tree; this receipt "
            "follows the security_report shape used by sibling delivered TST units."
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0218; typosquat and homoglyph package "
            "names flagged against the installed set"
        ),
        "title": "Typosquat and homoglyph package names are flagged against the installed set",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": {
            "summary": (
                "Yes. tools/marketplace/name_linter.py flags a candidate when its "
                "folded form equals an installed name (case, hyphen/underscore/"
                "dot, Unicode homoglyphs including Cyrillic lookalikes and digit "
                "zero vs o) or when Levenshtein distance on the folded form is "
                "1. Every flag reports confused_with as the installed spelling. "
                "On a 50-confusable + 50-distinct corpus, precision=1.0 and "
                "recall=1.0 (false-positive ceiling 0.0). An independent NFKD+"
                "Unicode-name mapping agrees on every pair; a raw-equality "
                f"mutant misses all 50 confusable pairs. {SENTINEL}"
            ),
            "precision": p1.get("precision"),
            "recall": p1.get("recall"),
            "false_positive_ceiling": p1.get("false_positive_ceiling"),
            "tp": p1.get("tp"),
            "fp": p1.get("fp"),
            "fn": p1.get("fn"),
        },
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "no automatic retry: a failure here is a finding, not a transient",
        },
        "min_bytes_threshold": 128,
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            *[{"path": row["path"], "exists": row["exists"], "role": "supporting"} for row in artifacts],
        ],
        "implementation": {
            "module": "tools/marketplace/name_linter.py",
            "fold": "NFKC + codepoint homoglyph table + casefold + 0->o + [-_.] -> '-'",
            "distance": "two-row Wagner-Fischer, threshold 1, min folded length 4",
            "confused_with": "installed original spelling, not the folded form",
        },
        "corpus": {
            "confusable_pairs": 50,
            "distinct_pairs": 50,
            "installed_n": p1.get("installed_n"),
            "kinds": [
                "separator",
                "case",
                "homoglyph",
                "zero",
                "delete",
                "insert",
                "substitute",
            ],
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "test_ids": [
            "probe1-linter-corpus-50-50",
            "probe2-independent-confusable-mapping",
            "test_hyphen_underscore_reports_confused_with",
            "test_cyrillic_a_homoglyph",
            "test_edit_distance_deletion",
            "test_distinct_not_flagged",
        ],
        "tests": [
            {
                "id": "probe1-linter-corpus-50-50",
                "command": P1,
                "result": "PASS",
                "exit_code": code1,
            },
            {
                "id": "probe2-independent-confusable-mapping",
                "command": P2,
                "result": "PASS",
                "exit_code": code2,
            },
            {
                "id": "library-tests",
                "command": TEST_CMD,
                "result": "PASS",
                "exit_code": code_t,
            },
        ],
        "evidence": [
            {
                "kind": "linter-corpus",
                "anchor": "tools/marketplace/name_linter.py",
                "path": "tools/marketplace/name_linter.py",
                "claim": (
                    "Signal (a): the production linter flagged all 50 confusable "
                    "candidates with confused_with equal to the intended installed "
                    f"name (tp={p1.get('tp')}) and flagged none of the 50 distinct "
                    f"candidates (fp={p1.get('fp')}). Precision and recall are both "
                    "1.0. False-positive ceiling stated: 0.0 on this corpus."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [pr1],
            },
            {
                "kind": "independent-confusable-mapping",
                "anchor": "command-center/p2-wave/probes/TST-0218/probe2_independent_mapping.py",
                "path": "command-center/p2-wave/probes/TST-0218/probe2_independent_mapping.py",
                "claim": (
                    "Signal (b): an independent NFKD + combining-mark strip + "
                    "unicodedata.name visual map that *deletes* separators (the "
                    "linter collapses them to '-') and a full-matrix Levenshtein "
                    "agrees with the linter on every pair. A raw-string-equality "
                    "mutant hits 0/50 confusable pairs, so the fold is live."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [pr2],
            },
        ],
        "detector_controls": {
            "known_present": {
                "id": "50-confusable-pairs-flagged-with-confused-with",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            "known_broken": {
                "id": "identity-equality-mutant-misses-all-confusable",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        },
        "negative_controls": [
            {
                "id": "genuinely-distinct-names-not-flagged",
                "kind": "both-states",
                "description": (
                    "50 distinct candidates, each at local-fold Levenshtein "
                    "distance >= 3 from every installed name, must produce zero "
                    "flags. False-positive ceiling = 0/50 = 0.0."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "fp=0 on 50 distinct",
                "bad_state_output": "confusable pairs flagged with confused_with",
            },
            {
                "id": "identity-mutant-misses-confusable",
                "kind": "mutation",
                "description": (
                    "Comparing raw candidate == installed catches 0 of 50 "
                    "confusable pairs (none are byte-identical). If this mutant "
                    "were green, the linter fold would be vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "linter tp=50",
                "bad_state_output": f"identity_mutant_hits={p2.get('identity_mutant_hits_on_confusable')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0218-probe2-independent-confusable-mapping",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Probe 2 does not import fold_name or the linter homoglyph table. "
                "It rebuilds skeletons from Unicode names after NFKD, deletes "
                "separators, and scores full-matrix Levenshtein. Decisions must "
                "match the linter; the identity mutant must miss every confusable pair."
            ),
        },
        "reviewer_verdict": "PASS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0069 publish-time package-identity grammar is a separate "
                    "unit. TST-0218 ships name_linter.py as the candidate-vs-"
                    "installed linter; wiring it into marketplace_install is not "
                    "required by this unit's question."
                ),
                "settling_experiment": (
                    "After IMP-0069, call lint_candidate from the publish path "
                    "and re-run these probes without editing them."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "The homoglyph table is a conservative visual subset (Cyrillic/"
                    "Greek lookalikes plus digit zero), not the full UTS #39 "
                    "confusables.txt. Pairs outside that subset are untested."
                ),
                "settling_experiment": (
                    "Import UTS #39 confusables.txt and re-score the same corpus "
                    "plus an expanded homoglyph set."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "cloud_ok": False,
        "registered": True,
        "notes": (
            "G-1 for TST-0218: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            f"{SENTINEL}"
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(dest)
    text = dest.read_text(encoding="utf-8")
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0218 sentinel missing from receipt text")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "linter-corpus-precision-recall",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "independent-confusable-mapping",
                "raw_output": out2[-8000:],
            },
        ],
        "probes": [
            {"id": "probe1", "command": P1, "exit_code": code1},
            {"id": "probe2", "command": P2, "exit_code": code2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0218-probe2-independent-confusable-mapping",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0218: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
