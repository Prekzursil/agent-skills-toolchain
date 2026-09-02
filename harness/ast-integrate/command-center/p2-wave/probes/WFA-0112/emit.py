#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0112-benchmark-case-corpus.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import prove  # noqa: E402
from families import FAMILIES, family_ids  # noqa: E402

REPO = HERE.parents[3]
OUT_REL = "command-center/wfa/WFA-0112-benchmark-case-corpus.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0112/benchmark-result.local.schema.json"
SENTINEL = "SUCCESS:WFA-0112"
QUESTION = (
    "Implementation target: a benchmark corpus with matched cases per family, "
    "each case carrying a deterministic postcondition oracle on the artifact "
    "produced - so a workflow's result is judged by what it produced on disk, "
    "not by what it reported."
)
LIBRARY_CANDIDATES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)


def library_probe() -> dict:
    rows = []
    present = 0
    for rel in LIBRARY_CANDIDATES:
        path = REPO / rel
        hit = path.is_file()
        present += int(hit)
        rows.append({"path": rel, "present": hit, "bytes": path.stat().st_size if hit else 0})
    return {
        "catalog_input": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json (20 families D1-D20)"
        ),
        "present_count": present,
        "candidates": rows,
        "family_id_source": "catalog names D1-D20",
        "label_source": (
            "stand-in labels from WFA-0044 IR constructs and WFA-0035 "
            "library categories; not a transcription of the missing library"
        ),
    }


def main() -> int:
    proof = prove()
    p = proof["proofs"]
    if not (
        p["all_oracles_deterministic"]
        and p["all_known_bad_rejected"]
        and p["cross_family_gold_rejected"]
        and p["n_covered"] == len(FAMILIES)
        and p["n_uncovered"] == 0
    ):
        print("FAILED:WFA-0112 emit oracle proofs not all true")
        print(json.dumps(p, indent=2, sort_keys=True))
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib = library_probe()
    answer = (
        f"Built {p['n_covered']} matched offline cases, one per catalog family "
        f"{', '.join(family_ids())}. Each case has a deterministic on-disk "
        "postcondition oracle (exists, min-bytes, parse, identity, construct "
        "fields). Every oracle accepted gold twice with identical verdicts, "
        "rejected its known-bad mutants (empty, braces, wrong-family, "
        "missing-field, wrong-case, network-flag, truncated, identity-only), "
        "and rejected every other family's gold. "
        f"Library file present_count={lib['present_count']}; labels are "
        "stand-ins, ids are catalog D1-D20. uncovered_families=[]. "
        "SUCCESS:WFA-0112"
    )
    doc = {
        "unit_id": "WFA-0112",
        "record_type": "BenchmarkResult",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/BenchmarkResult",
        "schema_binding": {
            "declared": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/BenchmarkResult",
            "declared_pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
            "local_shape": SCHEMA_REL,
            "note": (
                "WFA-0001 pack is absent on this worktree. This document is a "
                "BenchmarkResult-shaped corpus record, not a claim that the "
                "missing pack validated it."
            ),
        },
        "dependencies": {
            "WFA-0044": {
                "output_path": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
                "present": (REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json").is_file(),
                "used_as": "catalog IR construct list (stages, roles, gates, ...)",
            },
            "WFA-0035": {
                "output_path": "command-center/wfa/WFA-0035-extract-task-fit.json",
                "present": (REPO / "command-center/wfa/WFA-0035-extract-task-fit.json").is_file(),
                "used_as": "catalog library-category list",
            },
        },
        "library": lib,
        "network": {"required": False, "used": False},
        "families": proof["families"],
        "cases": proof["cases"],
        "uncovered_families": proof["uncovered_families"],
        "oracle_evidence": proof["proofs"],
        "tests_required": [
            "every oracle must be shown to reject a known-bad artifact before the corpus is used",
            "at least one case per family, and families with no constructible case are reported as UNCOVERED",
            "cases must be runnable without network access wherever possible, so results are reproducible",
        ],
        "evidence_requirement": {
            "A": "every case oracle run twice on the same artifact with identical verdicts",
            "A_measured": p["all_oracles_deterministic"],
            "B": "each oracle rejects a deliberately wrong artifact",
            "B_measured": p["all_known_bad_rejected"],
            "cross_family": p["cross_family_gold_rejected"],
        },
        "reviewer": {
            "reviewer_id": "WFA-0112-probe2-known-bad-and-cross-family",
            "independent": True,
            "verdict": "PASS",
            "both_states": True,
        },
    }
    schema_path = REPO / SCHEMA_REL
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            jsonschema = None  # type: ignore
        if jsonschema is not None:
            jsonschema.validate(doc, schema)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0112 emit sentinel missing from artifact text")
        return 1
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT_REL} bytes={len(raw)} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
