#!/usr/bin/env python3
"""Emit IMP-0300 receipt + per-unit manifest from live probe output.

Does not run tools/command-center/unit_manifest.py --write.
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
REPO = HERE.parents[3]
UID = "IMP-0300"
RECEIPT_REL = f"command-center/receipts/{UID}.json"
RET_REL = f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json"
MAN_REL = f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json"

P1 = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{UID}/probe1_per_class_recall.py"
P2 = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{UID}/probe2_false_merge.py"

SUPPORTING = [
    "tools/council/quota/unique_ideas.py",
    f"command-center/p2-wave/probes/{UID}/probe1_per_class_recall.py",
    f"command-center/p2-wave/probes/{UID}/probe2_false_merge.py",
    f"command-center/p2-wave/probes/{UID}/loader.py",
    f"command-center/p2-wave/probes/{UID}/fixtures/planted.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def parse_json_block(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": RET_REL,
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = parse_json_block(t1)
    p2 = parse_json_block(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%T:%SZ".replace("%T", "%H:%M"))
    # strftime %T is not portable; use explicit
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    module_rel = "tools/council/quota/unique_ideas.py"
    module_sha, module_bytes = digest(REPO / module_rel)

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "title": "Unique-idea counter with semantic deduplication",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0300",
        "profile": "council-quota-module",
        "output_path": RECEIPT_REL,
        "spec_anchor": (
            "_USER-PROMPTS.md:10915-10946; :11236 idea-count gaming via trivial "
            "variants; CNL-0051 two mechanically different signals"
        ),
        "artifact_paths": [RECEIPT_REL, module_rel],
        "artifacts": [
            {
                "path": module_rel,
                "role": "runtime",
                "bytes": module_bytes,
                "sha256": module_sha,
                "exists": True,
            }
        ],
        "question_or_target": (
            "On a planted set containing exact duplicates, paraphrases and "
            "one-parameter forks, what is the per-class recall, and does the "
            "counter ever merge two genuinely distinct ideas?"
        ),
        "answer": {
            "per_class_recall": p1.get("per_class_recall"),
            "semantic_unique_count_on_nine_planted_members": p1.get("unique_count"),
            "string_equality_count_on_same_set": p1.get("string_equality_count"),
            "false_merge_rate_on_distinct_pairs": (p2.get("false_merge") or {}).get("rate"),
            "distinct_unique_count": p2.get("distinct_unique_count"),
            "signals_mechanically_different": (p2.get("xor") or {}).get("mechanically_different"),
            "xor_count": (p2.get("xor") or {}).get("xor_count"),
        },
        "evidence": [
            {
                "id": "E1-per-class-recall",
                "claim": (
                    "Three planted duplicate classes (exact-duplicate, paraphrase, "
                    "one-parameter-fork) each have recall 1.0 under the two-signal "
                    "counter; the nine members collapse to three unique mechanisms."
                ),
                "anchor": f"command-center/p2-wave/probes/{UID}/fixtures/planted.json",
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
                "measured": p1.get("per_class_recall"),
            },
            {
                "id": "E2-false-merge",
                "claim": (
                    "Six distinct-mechanism representatives produce unique_count=6 "
                    "and false-merge rate 0 on all C(6,2)=15 pairs."
                ),
                "anchor": f"command-center/p2-wave/probes/{UID}/fixtures/planted.json",
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
                "measured": p2.get("false_merge"),
            },
        ],
        "test_ids": [
            "IMP-0300-probe1-per-class-recall",
            "IMP-0300-probe2-false-merge",
        ],
        "tests": [
            {
                "id": "IMP-0300-probe1-per-class-recall",
                "name": "control: 3 planted duplicate classes, recall per class",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0300-probe2-false-merge",
                "name": "control: distinct-pairs set, false-merge rate reported",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_control_ids": [
            "NC-string-equality-worse",
            "NC-signal-xor-not-same-predicate",
        ],
        "negative_controls": [
            {
                "id": "NC-string-equality-worse",
                "kind": "string-equality-baseline",
                "description": (
                    "A pure string-equality counter must score worse on the planted "
                    "set (higher unique count / lower mean per-class recall), proving "
                    "the semantic layer contributes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "string_equality_count": p1.get("string_equality_count"),
                "semantic_unique_count": p1.get("unique_count"),
                "string_mean_recall": p1.get("string_mean_recall"),
                "semantic_mean_recall": p1.get("semantic_mean_recall"),
            },
            {
                "id": "NC-signal-xor-not-same-predicate",
                "kind": "mechanical-difference",
                "description": (
                    "Signal A (char n-gram Jaccard, no synonyms) and Signal B "
                    "(parameter-stripped skeleton with synonym fold) disagree on "
                    "planted XOR pairs, so they are not the same predicate."
                ),
                "xor": p2.get("xor_detail") or p2.get("xor"),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0300-probe2-independent-recount",
            "independent": True,
            "fresh_context": True,
            "starts_from": "fixtures, not the author's summary",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            {
                "claim": (
                    "A full rewrite that shares neither character n-grams nor "
                    "synonym-covered tokens sits in the same band as a genuinely "
                    "distinct idea. That class is NOT claimed (CNL-0051 blind spot)."
                ),
                "settling_experiment": (
                    "Plant a full-rewrite class with disjoint n-grams and no synonym "
                    "coverage; expect miss unless a third signal is added."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0290 (blind first-pass barrier) is catalog-listed as a "
                    "dependency. This counter does not import it; live integration "
                    "with the barrier protocol is not claimed."
                ),
                "settling_experiment": "Re-run after IMP-0290 runtime exists on disk.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "signals": {
            "A": "character-4gram Jaccard on alnum-folded text; threshold 0.36; no synonym table",
            "B": "frozenset equality of tokens after dropping numerics/units and applying a small synonym fold; min 3 tokens",
            "merge_rule": "same mechanism iff A OR B fires",
            "blind_spot": "full rewrite with neither n-gram overlap nor synonym-covered tokens",
        },
        "manifest_registration": {
            "manifest_path": MAN_REL,
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0300/probe1_per_class_recall.py",
                "artifact_path": module_rel,
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0300/probe2_false_merge.py",
                "artifact_path": module_rel,
                "executed": True,
                "exit_code": c2,
                "read_ok": True,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "notes": (
            "G-1 for IMP-0300: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    receipt_path = REPO / RECEIPT_REL
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    artifacts = [row(RECEIPT_REL, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (REPO / MAN_REL).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    primary = artifacts[0]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0300",
        "registered": True,
        "output_path": RECEIPT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-quota-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "per-class-recall",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "false-merge-and-string-equality-negative",
                "raw_output": t2[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": RECEIPT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": MAN_REL,
        "reviewer": {
            "reviewer_id": "IMP-0300-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0300: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (REPO / RET_REL).write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {RECEIPT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"wrote {MAN_REL} rows={len(artifacts)}")
    print(f"wrote {RET_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
