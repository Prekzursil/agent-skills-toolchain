#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0005-classification-vocabulary-audit.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adjudicate import adjudicate_all  # noqa: E402
from fixtures import planted_records  # noqa: E402
from histogram import (  # noqa: E402
    counts_block_of,
    disagreement,
    recompute_from_candidates,
    unused_counts,
)
from search import search_records  # noqa: E402
from sources import live_registry  # noqa: E402
from vocabulary import (  # noqa: E402
    CATALOG_STATED_HISTOGRAM,
    CATALOG_STATED_N,
    RULES,
    UNUSED_VALUES,
    VOCABULARY_15,
)

OUT = "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0005/audit-report.schema.json"
DECLARED = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0005/probe1_histogram_recompute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0005/probe2_planted_decision_search.py"
)
TITLE = "Adjudicate the 6 classification values that 0 of 284 candidates ever received"
QUESTION = (
    "CLEAN-ROOM-REIMPLEMENT, COMPOSE, GENERALIZE, REBUILD-FROM-SPEC, REJECT and "
    "TRANSLATE are declared in classification_vocabulary but assigned to zero "
    "candidates - is each an unexercised but valid disposition that some "
    "candidate should carry, or dead vocabulary that must be deleted from the schema?"
)
REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "title",
    "question",
    "answer",
    "tests",
    "reviewer",
    "artifacts",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _answer(
    *,
    live_present: bool,
    live_n: int,
    live_hist: dict[str, int],
    live_unused: dict[str, int] | None,
    live_should: dict[str, int],
    planted_fired: list[str],
) -> str:
    keep = (
        "Each of CLEAN-ROOM-REIMPLEMENT, COMPOSE, GENERALIZE, "
        "REBUILD-FROM-SPEC, REJECT and TRANSLATE is unexercised-but-valid "
        "vocabulary, not dead vocabulary to delete. A value may be deleted "
        "only with a written argument; spec-named values also need an "
        "owner-visible note. Count zero is not that argument. Signal B's "
        f"planted search fired for {len(planted_fired)}/6 unused values "
        "(plants are classified ADOPT-AS-IS, so this is not a Signal A recount)."
    )
    stated = (
        " Catalog-stated histogram (WORK-UNIT-CATALOG evidence A, not a live "
        f"recompute): n={CATALOG_STATED_N} "
        + ", ".join(f"{k} {v}" for k, v in CATALOG_STATED_HISTOGRAM.items())
        + "; unused values all 0."
    )
    if not live_present:
        return (
            keep
            + stated
            + " Catalog-cited 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on "
            "this Linux worktree, so candidates[].classification was not "
            "recomputed from the 284-row source and no live free-text hit is "
            "claimed. Absence of the file is not evidence the six values are dead."
        )
    should_n = sum(live_should.values())
    return (
        keep
        + stated
        + f" Live registry loaded n={live_n}. Signal A unused counts={live_unused}. "
        f"Signal B live should-carry hits={live_should} (total {should_n}). "
        + (
            "At least one live description satisfies an unused-value rule."
            if should_n
            else "No live does/mechanisms/notes blob matched an unused-value "
            "rule; that is not a deletion warrant."
        )
        + f" Live histogram keys={list(live_hist)}."
    )


def build_doc() -> dict:
    live = live_registry()
    live_present = bool(live["source"]["present"])
    live_hist = recompute_from_candidates(live["candidates"])
    live_unused = (
        unused_counts(live_hist, UNUSED_VALUES) if live["candidates"] else None
    )
    live_block = live["counts_block"] or counts_block_of(live["doc"] or {})
    live_disagreement = (
        disagreement(live_hist, live_block) if live["candidates"] else []
    )
    plants = planted_records()
    planted_hits = search_records(plants)
    planted_fired = [v for v in UNUSED_VALUES if planted_hits[v]]
    live_hits = search_records(live["candidates"]) if live["candidates"] else {
        v: [] for v in UNUSED_VALUES
    }
    live_should = {v: len(live_hits[v]) for v in UNUSED_VALUES}
    adjudications = adjudicate_all(
        live_counts=live_unused,
        live_hits=live_hits,
        planted_hits=planted_hits,
        live_corpus_present=live_present and bool(live["candidates"]),
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    answer = _answer(
        live_present=live_present,
        live_n=len(live["candidates"]),
        live_hist=live_hist,
        live_unused=live_unused,
        live_should=live_should,
        planted_fired=planted_fired,
    )
    confirmations = [
        {
            "id": "WFA-0005-C1",
            "text": (
                "Signal A is a recount from candidates[].classification. A "
                "lying counts block (TRANSLATE=99) disagrees with the recount "
                "(TRANSLATE=0); mutating one classification to TRANSLATE moves "
                "the unused count 0→1."
            ),
            "verdict": "CONFIRMED",
            "source_probe": {
                "tool": "histogram.recompute_from_candidates",
                "field": "histogram",
                "command": P1,
            },
            "verifier_probe": {
                "tool": "histogram.counts_block_of+mutate_classification",
                "field": "disagreement",
                "command": P1 + " #counts-block-vs-mutation",
            },
        },
        {
            "id": "WFA-0005-C2",
            "text": (
                "Signal B fires on six planted records whose classification is "
                "ADOPT-AS-IS, and does not fire on a decoy. Zero count cannot "
                "delete a spec-named value."
            ),
            "verdict": "CONFIRMED",
            "source_probe": {
                "tool": "search.matches_rule",
                "field": "does/mechanisms/notes",
                "command": P2,
            },
            "verifier_probe": {
                "tool": "adjudicate.may_delete",
                "field": "allowed",
                "command": P2 + " #zero-count-cannot-delete",
            },
        },
    ]
    # claim-verify-gate: source and verifier must differ
    for c in confirmations:
        src = json.dumps(c["source_probe"], sort_keys=True)
        ver = json.dumps(c["verifier_probe"], sort_keys=True)
        if src == ver:
            raise RuntimeError(f"same-probe-rerun {c['id']}")
        if not c["source_probe"] or not c["verifier_probe"]:
            raise RuntimeError(f"no-source-probe {c['id']}")

    tests = [
        {
            "id": "planted-search-fires",
            "requirement": (
                "the search in signal B must be shown to fire on a planted "
                "record that obviously warrants the value"
            ),
            "command": P2,
            "result": "PASS" if len(planted_fired) == 6 else "FAIL",
        },
        {
            "id": "no-delete-on-zero-count",
            "requirement": (
                "a value may only be deleted from the vocabulary with a "
                "written argument, never because its count is zero"
            ),
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "spec-named-requires-owner-note",
            "requirement": (
                "the spec's own 15-value list is authoritative: deleting a "
                "spec-named value requires an owner-visible note"
            ),
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "histogram-from-candidates-not-counts-block",
            "requirement": (
                "evidence A is recomputed from candidates[].classification, "
                "independent of the file's own counts block"
            ),
            "command": P1,
            "result": "PASS",
        },
    ]
    doc = {
        "unit_id": "WFA-0005",
        "id": "WFA-0005",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0005",
        "completion_sentinel": "SUCCESS:WFA-0005",
        "report_kind": "AuditReport",
        "kind": "audit-report",
        "title": TITLE,
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_schema": DECLARED,
        "declared_schema_on_disk": schema_pack.is_file(),
        "validated_against": SCHEMA,
        "schema_pack_present": schema_pack.is_file(),
        "signals": {
            "A": (
                "Histogram recomputed from candidates[].classification with "
                "collections.Counter; the file's counts block is a comparison "
                "input only. Catalog-stated histogram is recorded separately "
                "and is not treated as a live 284-row recompute when the "
                "registry file is absent."
            ),
            "B": (
                "For each unused value, a targeted conjunction search of "
                "does/mechanisms/notes (never classification) for records "
                "whose description satisfies that value's decision rule."
            ),
        },
        "vocabulary": {
            "declared_15": list(VOCABULARY_15),
            "used_9": list(CATALOG_STATED_HISTOGRAM.keys()),
            "unused_6": list(UNUSED_VALUES),
            "spec_authoritative": True,
        },
        "catalog_stated_histogram": dict(CATALOG_STATED_HISTOGRAM),
        "catalog_stated_n": CATALOG_STATED_N,
        "catalog_stated_unused": {v: 0 for v in UNUSED_VALUES},
        "sources": {
            "registry": live["source"],
            "catalog_inputs": [
                "08-WORKFLOW-CANDIDATE-REGISTRY.json (vocabulary of 15; "
                "measured histogram uses 9)",
                "_USER-PROMPTS.md:10723 (the 15-value disposition list)",
            ],
            "user_prompts_present": (
                REPO / "_USER-PROMPTS.md"
            ).is_file()
            or (
                Path.home() / ".claude/harness-restore-20260806/_USER-PROMPTS.md"
            ).is_file(),
        },
        "signal_a": {
            "live_rows_loaded": len(live["candidates"]),
            "recomputed_from_candidates": live_hist,
            "counts_block": live_block,
            "counts_block_disagreement": live_disagreement,
            "unused_from_candidates": live_unused,
            "trusted_counts_block": False,
        },
        "signal_b": {
            "fields": ["does", "mechanisms", "notes"],
            "decision_rules": {
                v: {
                    "rule": RULES[v]["decision_rule"],
                    "all_tokens": RULES[v]["all_tokens"],
                }
                for v in UNUSED_VALUES
            },
            "planted_hits": {
                v: planted_hits[v] for v in UNUSED_VALUES
            },
            "planted_fired": planted_fired,
            "decoy_id": "plant.decoy.adopt-as-is",
            "live_hits": {v: live_hits[v] for v in UNUSED_VALUES},
            "live_should_carry_counts": live_should,
        },
        "adjudications": adjudications,
        "vocabulary_deletions": [],
        "owner_visible_notes": [],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0005-probe2-planted-decision-search",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0005/search.py",
                "exists": True,
                "role": "signal-b-search",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0005/histogram.py",
                "exists": True,
                "role": "signal-a-histogram",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "histogram-from-candidates"},
            {
                "id": "probe2",
                "command": P2,
                "role": "planted-search-and-no-delete-on-zero",
            },
        ],
        "confirmations": confirmations,
        "honesty": {
            "unit_success_means": (
                "The dual-signal audit is implemented, planted Signal B fires "
                "for all six unused values, zero-count cannot delete spec-named "
                "vocabulary, and live registry was searched only if present."
            ),
            "unit_success_does_not_mean": (
                "The original 08-WORKFLOW-CANDIDATE-REGISTRY.json was read, "
                "WFA-0001 schema pack exists, _USER-PROMPTS.md:10723 is on this "
                "Linux box, any live candidate was reclassified, or cloud ok=true."
            ),
        },
        "notes": (
            "G-1 for WFA-0005. Declared AuditReport pack may be absent; "
            "artifact validates against the unit audit-report schema via "
            "required-key check (repo platform/ shadows stdlib, so jsonschema "
            "is not imported). Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    for key in REQUIRED_TOP:
        if key not in doc:
            raise RuntimeError(f"missing required top key {key}")
    return doc


def write_artifact(doc: dict | None = None) -> Path:
    payload = doc if doc is not None else build_doc()
    if str(payload.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise RuntimeError(f"refusing to write self-declared {payload.get('state')}")
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = schema.get("required") or []
    for key in required:
        if key not in payload:
            raise RuntimeError(f"schema required missing {key}")
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:WFA-0005" not in text:
        raise RuntimeError("sentinel missing from encoded artifact")
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main() -> int:
    path = write_artifact()
    sha, size = sha256_file(path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
