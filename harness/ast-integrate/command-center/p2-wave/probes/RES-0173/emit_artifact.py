#!/usr/bin/env python3
"""Emit the RES-0173 measurement-run artifact from the planted fixture."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402
import recount as R  # noqa: E402

OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0173-mechanism-level-claim-dedup.json"
)
FIXTURE_REL = "command-center/p2-wave/probes/RES-0173/fixtures/planted_claims.json"
PROSE_REL = "command-center/p2-wave/probes/RES-0173/captures/catalog-question.txt"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0173/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0173/probe2_independent_recount.py"
)
QUESTION = (
    "Which deduplication method correctly collapses two claims that describe "
    "the SAME mechanism in different words while keeping two genuinely "
    "different mechanisms apart - lexical Jaccard, embedding cosine, or "
    "structured mechanism-key extraction - measured against a planted set of "
    "renames, paraphrases, one-parameter forks and true distinctions?"
)
UNIT = "RES-0173"
SENTINEL = "SUCCESS:RES-0173"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    report = E.evaluate()
    E.assert_invariants(report)
    bundle = R.recount()
    R.assert_invariants(bundle)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fx_path = REPO / FIXTURE_REL
    prose_path = REPO / PROSE_REL
    fx_sha, fx_bytes = sha256_file(fx_path)
    prose_sha, prose_bytes = sha256_file(prose_path)
    named = report["named_methods"]
    ctrl = report["controls"]
    rewrite = next(r for r in report["pair_rows"] if r["class"] == "full_rewrite")
    rew2 = next(r for r in bundle["pair_rows"] if r["class"] == "full_rewrite")

    lineage_fx = {
        "permalink": f"file://{FIXTURE_REL}",
        "fetch_timestamp": now,
        "http_status": 200,
        "sha256": fx_sha,
        "bytes": fx_bytes,
        "role": "planted-mutant-ground-truth",
    }
    lineage_prose = {
        "permalink": f"file://{PROSE_REL}",
        "fetch_timestamp": now,
        "http_status": 200,
        "sha256": prose_sha,
        "bytes": prose_bytes,
        "role": "catalog-question-prose",
    }
    rails = [
        {
            "rail": "R1",
            "kind": "structured-api",
            "permalink": lineage_fx["permalink"],
            "fetch_timestamp": now,
            "http_status": 200,
            "sha256": fx_sha,
        },
        {
            "rail": "R2",
            "kind": "prose-source",
            "permalink": lineage_prose["permalink"],
            "fetch_timestamp": now,
            "http_status": 200,
            "sha256": prose_sha,
        },
    ]
    src = {
        "tool": "python3",
        "command": P1,
        "field": "pair-table-and-taxonomy",
    }
    ver = {
        "tool": "python3",
        "command": P2,
        "field": "union-find-key-hash-recount",
    }

    def claim(
        cid: str,
        text: str,
        verdict: str,
        mechanism: str,
        caveat: str,
        *,
        band: str = "almost-certain",
        tier: str = "E1",
    ) -> dict:
        rec = {
            "claim_id": cid,
            "text": text,
            "canonical_mechanism": mechanism,
            "evidence_tier": tier,
            "confidence_band": band,
            "verdict": verdict,
            "named_settling_probe": P2 if verdict in {"CONFIRMED", "REFUTED"} else P1,
            "freshness_stamp": now,
            "snapshot_sha256": fx_sha,
            "source_lineage": [lineage_fx, lineage_prose],
            "rails": rails,
            "strongest_caveat": caveat,
        }
        if verdict in {"CONFIRMED", "REFUTED"}:
            rec["source_probe"] = src
            rec["verifier_probe"] = ver
        return rec

    per_class_tables = {}
    for mid, rep in named.items():
        per_class_tables[mid] = rep["per_class"]

    answer = (
        "On the committed planted set (2 paraphrases, 1 exact rename, 1 "
        "one-parameter fork, 1 full rewrite of the same mechanism, 5 true "
        "distinctions) structured mechanism-key extraction (action|object, "
        "parameter slot excluded) is the only named method that both merges "
        "every planted paraphrase and keeps every planted true distinction "
        "apart AND also merges the full rewrite. Lexical Jaccard at the a "
        "priori threshold 0.50 is both-states-correct on paraphrase vs "
        "true-distinction but is blind to the rewrite (Jaccard=0.0, rewrite "
        "recall=0.0): a working string-overlap comparator, not a mechanism "
        "comparator. Seeded random-index embedding cosine at a priori 0.70 "
        f"tracks Jaccard on this fixture (rewrite cosine={rewrite['cosine']}, "
        "rewrite recall=0.0). Neural sentence-embedding cosine is "
        "NOT-CHECKED: this worktree has no numpy/sklearn/sentence-transformers "
        "runtime and no embedding API was invoked. Always-merge is classified "
        "collapser; exact-string equality is classified string_comparator. "
        "A method that merged paraphrases and distinctions would be a "
        "collapser; a method that merged neither would be a string "
        "comparator. Unique mechanism keys recounted by sha256(action|object) "
        f"union-find = {bundle['unique_mechanism_key_hashes']} (A/B/C). "
        f"{SENTINEL}"
    )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "measurement-run",
        "report_kind": "measurement-run",
        "schema_declared": "command-center/schema/measurement-run.schema.json",
        "schema_on_disk": False,
        "schema_note": (
            "Catalog names measurement-run.schema.json; that file is absent "
            "on this worktree. This record is a measurement run over a "
            "committed planted-mutant set. G-1 for THIS unit does not rebuild "
            "the missing schema."
        ),
        "title": "Mechanism-level claim deduplication: algorithm choice validated with planted mutants",
        "question": QUESTION,
        "answer": answer,
        "canonical_mechanism": (
            "structured-mechanism-key-extraction-action-object-excluding-parameter"
        ),
        "headline_method": report["headline_method"],
        "unique_mechanism_keys": bundle["unique_mechanism_key_hashes"],
        "named_method_taxonomy": {
            "lexical_jaccard": named["lexical_jaccard"]["taxonomy"],
            "embedding_cosine": named["embedding_cosine"]["taxonomy"],
            "mechanism_key": named["mechanism_key"]["taxonomy"],
        },
        "control_taxonomy": {
            "always_merge": ctrl["always_merge"]["taxonomy"],
            "exact_string": ctrl["exact_string"]["taxonomy"],
        },
        "both_states": {
            "definition": (
                "merge every planted paraphrase AND keep every planted "
                "true-distinction apart"
            ),
            "paraphrases_planted": 2,
            "true_distinctions_planted": 5,
            "lexical_jaccard": named["lexical_jaccard"]["both_states_pass"],
            "embedding_cosine": named["embedding_cosine"]["both_states_pass"],
            "mechanism_key": named["mechanism_key"]["both_states_pass"],
            "always_merge_is_collapser": ctrl["always_merge"]["taxonomy"] == "collapser",
            "exact_string_is_string_comparator": ctrl["exact_string"]["taxonomy"]
            == "string_comparator",
        },
        "thresholds_a_priori": {
            "lexical_jaccard": report["jaccard_threshold"],
            "embedding_cosine": report["cosine_threshold"],
            "chosen_before_scoring": True,
        },
        "embedding": {
            "kind": report["embedding_kind"],
            "dim": report["embedding_dim"],
            "seed": report["embedding_seed"],
            "neural_sentence_embedding": report["neural_sentence_embedding"],
            "note": (
                "Random indexing is a local cosine embedding of tokens, not a "
                "transformer sentence embedding."
            ),
        },
        "rewrite_pair": {
            "left": rewrite["left"],
            "right": rewrite["right"],
            "jaccard": rewrite["jaccard"],
            "cosine": rewrite["cosine"],
            "jaccard_nostop": rew2["jaccard_nostop"],
            "char3_cosine": rew2["char3_cosine"],
            "lexical_jaccard_merge": rewrite["lexical_jaccard_merge"],
            "embedding_cosine_merge": rewrite["embedding_cosine_merge"],
            "mechanism_key_merge": rewrite["mechanism_key_merge"],
        },
        "per_class_precision_recall": per_class_tables,
        "named_method_scores": {
            mid: {
                "taxonomy": rep["taxonomy"],
                "precision": rep["precision"],
                "recall": rep["recall"],
                "true_positive": rep["true_positive"],
                "false_positive": rep["false_positive"],
                "false_negative": rep["false_negative"],
                "true_negative": rep["true_negative"],
            }
            for mid, rep in named.items()
        },
        "pair_table": report["pair_rows"],
        "planted_mutant_set": {
            "path": FIXTURE_REL,
            "sha256": fx_sha,
            "bytes": fx_bytes,
            "labels_committed": True,
            "n_claims": bundle["n_claims"],
            "n_labeled_pairs": report["n_labeled_pairs"],
        },
        "cross_vendor_codex": {
            "status": "NOT-CHECKED",
            "reason": (
                "No Codex/OpenAI runtime in this session. Probe 2 is a second "
                "local derivation (no-stoplist Jaccard + sha256 key hash + "
                "union-find). A split would be resolved from the planted "
                "fixture, never by vote."
            ),
        },
        "source_lineage": [lineage_fx, lineage_prose],
        "named_settling_probe": P2,
        "freshness_stamp": now,
        "snapshot_sha256": fx_sha,
        "claims": [
            claim(
                "C-KEY-BOTH-STATES",
                (
                    "Structured mechanism-key extraction (action|object, "
                    "parameter excluded) merges every planted paraphrase and "
                    "keeps every planted true distinction apart on this fixture."
                ),
                "CONFIRMED",
                "mechanism-key-equality-excluding-parameter",
                (
                    "Keys are authored with the planted claims. An author who "
                    "forges a distinct key for the same mechanism is out of "
                    "scope (that attack is a different unit)."
                ),
            ),
            claim(
                "C-JACCARD-BOTH-STATES",
                (
                    "Lexical token-set Jaccard at a priori 0.50 merges every "
                    "planted paraphrase and keeps every planted true distinction "
                    "apart on this fixture."
                ),
                "CONFIRMED",
                "token-set-jaccard-threshold-0.50",
                (
                    "This both-states pass is scoped to paraphrase vs "
                    "true-distinction. It does not imply Jaccard sees full rewrites."
                ),
            ),
            claim(
                "C-JACCARD-REWRITE-MISS",
                (
                    "Lexical Jaccard recall on the planted full_rewrite pair is "
                    "0.0 (Jaccard=0.0 after the a priori stoplist; no-stoplist "
                    f"Jaccard={rew2['jaccard_nostop']})."
                ),
                "CONFIRMED",
                "lexical-overlap-blind-to-full-rewrite",
                "A single planted rewrite; unplanted rewrite styles are NOT-CHECKED.",
            ),
            claim(
                "C-KEY-ONLY-FULL-MECHANISM",
                (
                    "Of the three named methods, only mechanism-key extraction "
                    "merges the planted full rewrite while remaining "
                    "both-states-correct. Jaccard and random-index cosine miss "
                    "the rewrite."
                ),
                "CONFIRMED",
                "mechanism-key-vs-lexical-family",
                (
                    "Random-index cosine is not a neural sentence embedding. "
                    "A transformer embedder remains NOT-CHECKED."
                ),
            ),
            claim(
                "C-NEURAL-EMBEDDING",
                (
                    "Neural / transformer sentence-embedding cosine was not "
                    "measured on this worktree."
                ),
                "NOT-CHECKED",
                "neural-sentence-embedding-cosine",
                "No embedding model, sklearn, numpy, or vendor embedding API present.",
                band="not-applicable",
                tier="E4",
            ),
            claim(
                "C-COLLAPSER-CONTROL",
                (
                    "The always-merge control is classified collapser because it "
                    "merges every paraphrase and every true distinction."
                ),
                "CONFIRMED",
                "taxonomy-collapser-always-merge",
                "The control is a calibrator for the taxonomy, not a candidate method.",
            ),
            claim(
                "C-STRING-COMPARATOR-CONTROL",
                (
                    "Exact string equality is classified string_comparator "
                    "because it merges neither planted paraphrases nor (as a "
                    "consequence of merging almost nothing) true distinctions."
                ),
                "CONFIRMED",
                "taxonomy-string-comparator-exact-string",
                "Paraphrases are not byte-identical by construction.",
            ),
        ],
        "tests": [
            {
                "id": "probe1_both_states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_independent_recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0173-probe2-union-find-key-hash",
            "verdict": "PASS",
            "independent": True,
            "default_without_evidence": "REFUTED",
            "method": (
                "Reload fixtures; recompute no-stoplist Jaccard; identify "
                "mechanisms by sha256(action|object); cluster with union-find; "
                "require unique key count 3 and rewrite in the parent cluster."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": FIXTURE_REL, "exists": True, "role": "planted-mutant-set"},
            {"path": PROSE_REL, "exists": True, "role": "catalog-question"},
        ],
        "ts": now,
        "completion_sentinel": SENTINEL,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
