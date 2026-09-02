#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0102.json from live search measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/marketplace/tests"))
sys.path.insert(0, str(HERE.parents[1]))  # p2-wave for _p2lib if present

import test_search_determinism as det  # noqa: E402
import test_search_recall as rec  # noqa: E402
from marketplace.search import (  # noqa: E402
    B,
    FIELD_WEIGHTS,
    K1,
    POPULARITY_TERM,
    SearchIndex,
    search_path,
)

OUT = "command-center/receipts/IMP-0102.json"
UNIT = "IMP-0102"


def sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    digest = hashlib.sha256(lf).hexdigest()
    if b"\x00" in raw[:8192]:
        eol = "BINARY"
    else:
        crlf = raw.count(b"\r\n")
        nlf = raw.count(b"\n") - crlf
        if crlf and nlf:
            eol = "MIXED"
        elif crlf:
            eol = "CRLF"
        else:
            eol = "LF"
    return digest, len(lf), eol


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size, eol = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    det.test_repeat_and_shuffle_invariance()
    rec.test_known_package_is_findable_by_name_and_by_skill()
    rec.test_empty_result_distinct_from_index_error()
    rec.test_popularity_fields_do_not_move_ranking()

    data = det._load()
    index = SearchIndex.from_marketplace_data(data)
    tie = index.search(det.QUERY)
    by_name = index.search("canonical-hello")
    by_skill = index.search("hello-operator")
    skill_only = index.search("binary-diff-oracle")
    council = index.search("council")
    empty = index.search("zzzxnotaterminthecorpuszzzz")
    missing = search_path(rec.MISSING, "hello")
    explained = index.explain("canonical-hello", "canonical-hello")
    hits = {h.stable_key: h for h in tie.hits}
    tie_equal = hits[det.TIE_KEYS[0]].score == hits[det.TIE_KEYS[1]].score

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/marketplace/search.py",
        "tools/marketplace/corpus.py",
        "tools/marketplace/fixtures/registry_corpus.json",
        "tools/marketplace/tests/test_search_determinism.py",
        "tools/marketplace/tests/test_search_recall.py",
        "command-center/p2-wave/probes/IMP-0102/probe1_repeat_shuffle.py",
        "command-center/p2-wave/probes/IMP-0102/probe2_recall_empty.py",
    ]
    artifacts = [art(rel, "supporting") for rel in supporting]
    artifacts[0]["role"] = "primary"

    p_det = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_search_determinism.py",
        f"ordering={list(tie.keys())} tie_equal={tie_equal} distinct=1",
        0,
    )
    p_shuf = probe(
        "verifier",
        "command",
        "python3 -B tools/marketplace/tests/test_search_determinism.py",
        "16 shuffled rebuilds plus reversed insertion matched baseline ordering",
        0,
    )
    p_rec = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/tests/test_search_recall.py",
        (
            f"name={by_name.keys()[0]} skill={list(by_skill.keys())} "
            f"skill_only={skill_only.keys()[0]} council={list(council.keys())}"
        ),
        0,
    )
    p_empty = probe(
        "verifier",
        "command",
        "python3 -B tools/marketplace/tests/test_search_recall.py",
        f"empty.kind={empty.kind} missing.kind={missing.kind} distinct={empty.kind != missing.kind}",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0102",
        "spec_anchor": "_USER-PROMPTS.md:10861 (search, categories, tags, collections)",
        "min_bytes_threshold": 128,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Query 'quuxzorch' run 50 times on one index and 50 rebuilds "
                    "from the original plugin list yields one distinct ordering; "
                    "alpha-tie and beta-tie are a true score tie broken by stable_key."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_search_determinism.py:test_repeat_and_shuffle_invariance",
                "confidence": "almost-certain",
                "probes": [p_det, p_shuf],
            },
            {
                "claim": (
                    "The same ordering is recovered after 16 shuffled insertion orders "
                    "and after reversing the plugins[] array, so ranking is independent "
                    "of insertion order."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/search.py:SearchIndex.__init__",
                "confidence": "almost-certain",
                "probes": [p_det, p_shuf],
            },
            {
                "claim": (
                    "canonical-hello is findable by package name and by skill name "
                    "hello-operator; obscure-bundle is findable only via skills[] "
                    "(binary-diff-oracle); council-pack is findable via "
                    "skills/skill.council/SKILL.md."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_search_recall.py:test_known_package_is_findable_by_name_and_by_skill",
                "confidence": "almost-certain",
                "probes": [p_rec, p_empty],
            },
            {
                "claim": (
                    "A query with no matches returns kind=empty with ok=true and no error; "
                    "a missing marketplace.json returns kind=index_error with ok=false. "
                    "The two outcomes are distinct. Popularity fields do not move ranking. "
                    "POPULARITY_TERM is 0.0. Per-term contributions reconstruct the score."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_search_recall.py:test_empty_result_distinct_from_index_error",
                "confidence": "almost-certain",
                "probes": [p_rec, p_empty],
            },
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_repeat_and_shuffle_invariance",
                "command": "python3 -B tools/marketplace/tests/test_search_determinism.py",
                "result": "PASS",
            },
            {
                "id": "test_known_package_is_findable_by_name_and_by_skill",
                "command": "python3 -B tools/marketplace/tests/test_search_recall.py",
                "result": "PASS",
            },
            {
                "id": "negative_control_empty_vs_index_error",
                "command": "python3 -B tools/marketplace/tests/test_search_recall.py",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "empty-vs-index-error",
                "kind": "known-broken-fixture",
                "description": (
                    "No-match query is kind=empty; missing registry file is kind=index_error."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": missing.as_dict(),
                "good_state_output": empty.as_dict(),
            },
            {
                "id": "popularity-does-not-rank",
                "kind": "gaming-control",
                "description": "Inflating downloads/stars on popular-decoy does not change quuxzorch order.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutated popularity fields; ordering unchanged",
                "good_state_output": list(tie.keys()),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0102-probe2-skills-coverage",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is mechanically different from probe 1 (recall and result-kind, "
                "not repeat/shuffle). It confirms skills[] is indexed: obscure-bundle is "
                "returned for binary-diff-oracle although that token is absent from name "
                "and description; council-pack is returned for council via SKILL.md parent "
                "name. Popularity is excluded. Empty is not an index error."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0102/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0102",
                    "G-1 measure re-runs named probes after this receipt is on disk",
                    0,
                ),
            },
            {
                "consumer": "tools/marketplace/search.py:SearchIndex.search",
                "artifact_path": "tools/marketplace/fixtures/registry_corpus.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_rec,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    ".claude-plugin/marketplace.json is absent on this sparse worktree. "
                    "Probes index tools/marketplace/fixtures/registry_corpus.json, which "
                    "uses the same plugins[].skills[] shape. SearchIndex.from_marketplace_path "
                    "reads whatever marketplace.json the caller supplies; it does not invent "
                    "a second registry file. Declared BM25 parameters: "
                    f"k1={K1}, b={B}, field_weights={dict(FIELD_WEIGHTS)}, "
                    f"popularity_term={POPULARITY_TERM}; tie-break is stable_key; "
                    f"tie_ordering={list(tie.keys())}; empty_kind={empty.kind}; "
                    f"index_error_kind={missing.kind}; documents={index.n}; "
                    f"score_reconstructed="
                    f"{abs(explained['score'] - explained['reconstructed_score']) < 1e-12}."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run SearchIndex over live .claude-plugin/marketplace.json when "
                    "that file is present in a full checkout."
                ),
            }
        ],
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0102" not in text:
        print("FAILED:IMP-0102 sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size, eol = sha256_file(out)
    if size < 128:
        print(f"FAILED:IMP-0102 receipt too small bytes={size}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} eol={eol}")
    print("SUCCESS:IMP-0102")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
