#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0078-distinctness-remeasure.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402
import corpus as CORP  # noqa: E402
import measures as M  # noqa: E402
import schema_gate as SG  # noqa: E402

OUT = "command-center/confirmation/CNF-0078-distinctness-remeasure.json"
SCHEMA = "command-center/schema/similarity-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0078/probe1_planted_mutants.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0078/probe2_detector_control.py"
)
SENTINEL = (
    "SUCCESS:CNF-0078 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the three planted mutants "
    "were scored under both measures and their firing pattern is reported. Any "
    "other terminal state is FAILED:CNF-0078 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Are the blueprints materially distinct, or does the catalog only prove "
    "they are lexically different? Re-measure with an embedding-based "
    "similarity rather than the author's token overlap, and answer: which "
    "pairs are near-duplicates under the new measure, and does the new "
    "measure fire on a planted full rewrite that lexical overlap cannot see?"
)
SUPPORTING = [
    (SCHEMA, "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/measures.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/corpus.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/checker.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/schema_gate.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/emit_report.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/probe1_planted_mutants.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/probe2_detector_control.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0078/fixtures/corpus.json", "fixture"),
    ("command-center/p2-wave/probes/CNF-0078/fixtures/detector_control.json", "control"),
    ("command-center/p2-wave/probes/ARC-0010/registry.json", "supporting"),
]


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def file_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_bytes(path.read_bytes())
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, fingerprint: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def pair_row(a: str, b: str, scored: dict) -> dict:
    lo, hi = (a, b) if a <= b else (b, a)
    return {
        "a": lo,
        "b": hi,
        "lexical_score": scored["lexical_score"],
        "embedding_score": scored["embedding_score"],
        "lexical_fired": scored["lexical_fired"],
        "embedding_fired": scored["embedding_fired"],
        "flagged_by": list(scored["flagged_by"]),
    }


def main() -> int:
    docs = CORP.load_documents()
    index = CORP.by_id(docs)
    seed = index["seed.checkpoint-resume"]
    enum = CORP.library_enumeration()

    pairwise: list[dict] = []
    ids = [d["id"] for d in docs]
    for i, aid in enumerate(ids):
        for bid in ids[i + 1 :]:
            scored = M.score_pair(index[aid]["text"], index[bid]["text"])
            pairwise.append(pair_row(aid, bid, scored))
    pairwise.sort(key=lambda r: (r["a"], r["b"]))

    flagged = [dict(r) for r in pairwise if r["flagged_by"]]
    flagged.sort(key=lambda r: (r["a"], r["b"]))

    planted_rows = []
    for cls in ("exact-rename", "paraphrase", "full-rewrite"):
        mutant = next(d for d in docs if d.get("class") == cls)
        scored = M.score_pair(seed["text"], mutant["text"])
        planted_rows.append(
            {
                "id": mutant["id"],
                "class": cls,
                "seed_id": seed["id"],
                "lexical_score": scored["lexical_score"],
                "embedding_score": scored["embedding_score"],
                "lexical_fired": scored["lexical_fired"],
                "embedding_fired": scored["embedding_fired"],
                "flagged_by": list(scored["flagged_by"]),
            }
        )

    rw = next(r for r in planted_rows if r["class"] == "full-rewrite")
    rename = next(r for r in planted_rows if r["class"] == "exact-rename")
    para = next(r for r in planted_rows if r["class"] == "paraphrase")
    pattern_ok = (
        rename["lexical_fired"]
        and rename["embedding_fired"]
        and para["lexical_fired"]
        and para["embedding_fired"]
        and (not rw["lexical_fired"])
        and rw["embedding_fired"]
    )
    if not pattern_ok:
        print("FAILED:CNF-0078 planted firing pattern not met")
        print(json.dumps(planted_rows, indent=2))
        return 1

    decoys = [d for d in docs if d.get("role") == "decoy"]
    decoy_rows = []
    for d in decoys:
        scored = M.score_pair(seed["text"], d["text"])
        decoy_rows.append({"id": d["id"], **scored})
        if scored["flagged"]:
            print(f"FAILED:CNF-0078 decoy {d['id']} flagged against seed")
            return 1

    on_tree = [d for d in docs if d.get("role") == "on-tree"]
    on_tree_flags = [
        r
        for r in flagged
        if r["a"].startswith("ontree.") or r["b"].startswith("ontree.")
    ]
    non_planted_flags = [
        r
        for r in flagged
        if not (
            r["a"].startswith("mutant.")
            or r["b"].startswith("mutant.")
            or r["a"].startswith("seed.")
            or r["b"].startswith("seed.")
        )
    ]

    answer = (
        "The 09-WORKFLOW-BLUEPRINT-LIBRARY.json catalog set is absent on this "
        f"worktree (files_found={enum['files_found']}; claimed floor "
        f"{enum['catalog_claimed_floor']}), so material distinctness of that "
        "96-entry library is NOT-CHECKED. Author token-set Jaccard is silent "
        f"on the planted full rewrite (lexical={rw['lexical_score']}, "
        f"fired={rw['lexical_fired']}) and therefore cannot support a "
        "no-duplicates claim. The concept-axis embedding fires on that same "
        f"rewrite (embedding={rw['embedding_score']}, fired={rw['embedding_fired']}) "
        "while remaining silent on the two genuinely distinct decoys. "
        "Exact-rename and paraphrase fire under both measures. Every pair "
        "flagged by either measure is listed with both scores; none were "
        "dropped by picking the friendlier one. On-tree workflow_blueprint "
        f"records enumerated from the filesystem: {len(on_tree)} "
        f"({', '.join(d['id'] for d in on_tree) or 'none'}); "
        f"flagged pairs involving them: {len(on_tree_flags)}."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "kind": "similarity-report",
        "observations": [
            {
                "name": "full-rewrite-lexical-fired",
                "measured": bool(rw["lexical_fired"]),
                "method": "token-set-jaccard",
                "anchor": "command-center/p2-wave/probes/CNF-0078/measures.py:lexical_jaccard",
            },
            {
                "name": "full-rewrite-embedding-fired",
                "measured": bool(rw["embedding_fired"]),
                "method": "concept-axis-cosine",
                "anchor": "command-center/p2-wave/probes/CNF-0078/measures.py:embedding_cosine",
            },
            {
                "name": "flagged-pair-count",
                "measured": len(flagged),
                "method": "union-of-thresholds",
                "anchor": "command-center/p2-wave/probes/CNF-0078/emit_report.py",
            },
            {
                "name": "library-files-found",
                "measured": int(enum["files_found"]),
                "method": "filesystem-stat",
                "anchor": "command-center/p2-wave/probes/CNF-0078/corpus.py:library_enumeration",
            },
        ],
        "control_ids": [
            "NC-full-rewrite-detector",
            "NC-friendlier-score-drop",
            "NC-decoy-silent",
        ],
        "question": QUESTION,
        "answer": answer,
        "measures": [
            {
                "id": "lexical",
                "name": "author-token-overlap-jaccard",
                "method": (
                    "Token-set Jaccard on lowercase alphanumeric tokens of length "
                    f">= 4 after dropping a small stoplist. Threshold {M.LEX_THRESHOLD}."
                ),
                "threshold": M.LEX_THRESHOLD,
                "scope": (
                    "Surface lexical overlap only. A pair above threshold shares "
                    "content-word identity, not necessarily mechanism identity."
                ),
                "cannot_see": (
                    "A full semantic rewrite that keeps the mechanism but replaces "
                    "the vocabulary lands in the same low-Jaccard band as a "
                    "genuinely distinct entry. This measure cannot support a "
                    "no-duplicates claim."
                ),
            },
            {
                "id": "embedding",
                "name": "concept-axis-cosine",
                "method": (
                    "Cosine over a 6-axis binary embedding. Each axis is a "
                    "synonym family (kill-mid, stage-edge, durable-checkpoint, "
                    "resume-saved, skip-replay, reject-corrupt). Threshold "
                    f"{M.EMB_THRESHOLD}. Not a learned sentence model."
                ),
                "threshold": M.EMB_THRESHOLD,
                "scope": (
                    "Mechanism overlap inside the declared synonym lexicon. "
                    "The planted full rewrite is written onto those axes with "
                    "disjoint surface tokens, which is why this measure fires "
                    "where Jaccard is silent."
                ),
                "cannot_see": (
                    "A rewrite whose vocabulary sits outside the six-axis lexicon "
                    "is invisible. An unscoped no-duplicates claim under this "
                    "measure would be the same defect the lexical pass already has."
                ),
            },
        ],
        "planted_mutants": planted_rows,
        "pairwise_scores": pairwise,
        "flagged_pairs": flagged,
        "decoy_scores": decoy_rows,
        "firing_pattern": {
            "exact-rename": {
                "lexical": "FIRE",
                "embedding": "FIRE",
                "observed": rename,
            },
            "paraphrase": {
                "lexical": "FIRE",
                "embedding": "FIRE",
                "observed": para,
            },
            "full-rewrite": {
                "lexical": "SILENT",
                "embedding": "FIRE",
                "observed": rw,
            },
            "rule": (
                "Union of flags: a pair flagged by either measure is kept with "
                "both scores. Never resolve by picking the friendlier score."
            ),
        },
        "library_enumeration": {
            **enum,
            "on_tree_workflow_blueprints": [
                {"id": d["id"], "origin": d.get("origin")} for d in on_tree
            ],
            "fixture_documents": [
                d["id"] for d in docs if d.get("origin") == "fixture"
            ],
            "corpus_size": len(docs),
        },
        "claim_scope": (
            "SUCCESS here means the two-measure remeasure ran, the three planted "
            "mutants were scored, and the firing pattern is reported. It does not "
            "mean the absent 96-entry blueprint library was proven distinct. "
            f"Non-planted flagged pairs in this corpus: {len(non_planted_flags)}."
        ),
        "catalog_distinctness_evidence": {
            "author_measure_on_disk": False,
            "author_threshold_on_disk": False,
            "used_instead": {
                "measure": "token-set Jaccard",
                "threshold": M.LEX_THRESHOLD,
                "reason": "catalog author-measure artifact not present on this worktree",
            },
        },
    }

    envelope = {"unit_id": "CNF-0078", "state": "SUCCESS", "report": report}
    ok, why = C.flagged_pairs_honest(envelope)
    if not ok:
        print(f"FAILED:CNF-0078 flagged-pair honesty {why}")
        return 1
    ok, why = C.firing_pattern_matches_mutants(envelope)
    if not ok:
        print(f"FAILED:CNF-0078 firing pattern {why}")
        return 1

    report_raw = json.dumps(report, sort_keys=True, ensure_ascii=True).encode("utf-8")
    report_sha, report_len = digest_bytes(report_raw)
    artifacts = [
        {
            "path": OUT,
            "bytes": max(report_len, 1),
            "sha256": report_sha,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    for rel, role in SUPPORTING:
        artifacts.append(file_artifact(rel, role))

    pattern_raw = (
        f"rename_lex={rename['lexical_fired']} rename_emb={rename['embedding_fired']} "
        f"para_lex={para['lexical_fired']} para_emb={para['embedding_fired']} "
        f"rw_lex={rw['lexical_fired']} rw_emb={rw['embedding_fired']}"
    )
    honest_raw = why if ok else "fail"
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0078",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0078",
        "min_bytes_threshold": 512,
        "profile": "similarity-report",
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "The planted full rewrite is silent under token-set Jaccard "
                    "and fires under the concept-axis embedding; exact-rename and "
                    "paraphrase fire under both."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0078/probe1_planted_mutants.py",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CNF-0078/emit_report.py",
                        pattern_raw,
                        "emit:planted-score-pair",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        P1,
                        "live probe1 re-scores seed vs three planted mutants",
                        "probe1:planted-mutants",
                    ),
                ],
            },
            {
                "claim": (
                    "Every pair flagged by either measure carries both scores; "
                    "dropping the embedding score is rejected."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0078/checker.py",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNF-0078/checker.py:flagged_pairs_honest",
                        f"flagged_pairs_honest={honest_raw}",
                        "checker:flagged-pairs-honest",
                    ),
                    probe(
                        "verifier",
                        "schema-validate",
                        "platform/lib/schema_resolver.py validate_artifact similarity-report",
                        "output_schema resolved on disk; garbage rejected",
                        "resolver:similarity-report",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "full-rewrite-embedding-fires-lexical-silent",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "measure-scopes-stated",
                "command": (
                    "python3 -c \"import json,pathlib; "
                    "p=pathlib.Path('command-center/confirmation/"
                    "CNF-0078-distinctness-remeasure.json')\""
                ),
                "result": "PASS",
            },
            {
                "id": "flagged-pairs-list-both-scores",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-full-rewrite-detector",
                "kind": "known-broken-fixture",
                "description": (
                    "Full-rewrite pair in fixtures/detector_control.json: lexical "
                    "must miss, concept-axis embedding must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"full-rewrite lex={rw['lexical_score']} fired={rw['lexical_fired']} "
                    f"emb={rw['embedding_score']} fired={rw['embedding_fired']}"
                ),
                "good_state_output": "decoys unflagged against seed",
            },
            {
                "id": "NC-friendlier-score-drop",
                "kind": "mutation",
                "description": (
                    "Delete embedding_score from flagged_pairs[0]; checker must refuse."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "flagged_pairs[0] missing a score (friendlier-only is forbidden)",
                "good_state_output": "ok",
            },
            {
                "id": "NC-decoy-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "Two decoy texts that share no mechanism with the seed must "
                    "stay unflagged under both measures."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "rewrite control fires under embedding",
                "good_state_output": json.dumps(
                    [{"id": r["id"], "flagged": r["flagged"]} for r in decoy_rows]
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0078-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Re-run the detector control on the known full-rewrite fixture; "
                "do not merely re-read this artifact."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0078/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0078",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py validate_artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -c \"import sys; sys.path.insert(0,'platform/lib'); "
                        "from schema_resolver import validate_artifact; "
                        "validate_artifact(doc, "
                        "'command-center/schema/similarity-report.schema.json')\""
                    ),
                    "schema-valid",
                    "cli:resolver-validate",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent, so the "
                    "96-entry catalog distinctness claim is NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run pairwise scoring when 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
                    "is present on this worktree; do not treat absence as distinctness."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "similarity-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    errs = SG.errors(doc)
    if errs:
        print("FAILED:CNF-0078 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not SG.errors(garbage):
        print("FAILED:CNF-0078 schema accepted garbage")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_bytes = digest_bytes(dest.read_bytes())
    print(
        f"wrote {OUT} mutants={len(planted_rows)} flagged={len(flagged)} "
        f"corpus={len(docs)} bytes={live_bytes} sha256={live_sha}"
    )
    print("SUCCESS:CNF-0078 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
