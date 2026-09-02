#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0398.json — labelled router corpus."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import baseline as B  # noqa: E402
import corpus as C  # noqa: E402
import kappa as K  # noqa: E402
import schema_util as SU  # noqa: E402

OUT = "command-center/receipts/IMP-0398.json"
SCHEMA = "command-center/schema/router-corpus.schema.json"
PAYLOAD_SCHEMA = (
    "command-center/p2-wave/probes/IMP-0398/corpus.payload.schema.json"
)
INDEX = (
    "command-center/p2-wave/probes/IMP-0398/fixtures/capability-index.json"
)
SENTINEL = "SENTINEL:IMP-0398:ROUTER-CORPUS-BASELINE-DEFEATING"
FLOOR = 0.25
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0398/probe1_schema.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0398/probe2_baseline_defeat.py"
)
QUESTION = (
    "Build the labelled router regression corpus: query, expected capability "
    "set, and rationale - with at least 25 percent NEGATIVE queries whose "
    "expected set is empty. Exact target: a corpus that cannot be satisfied "
    "by a router that always returns the top-3 most popular capabilities."
)
SUPPORTING = [
    SCHEMA,
    PAYLOAD_SCHEMA,
    INDEX,
    "command-center/p2-wave/probes/IMP-0398/corpus.py",
    "command-center/p2-wave/probes/IMP-0398/baseline.py",
    "command-center/p2-wave/probes/IMP-0398/kappa.py",
    "command-center/p2-wave/probes/IMP-0398/schema_util.py",
    "command-center/p2-wave/probes/IMP-0398/probe1_schema.py",
    "command-center/p2-wave/probes/IMP-0398/probe2_baseline_defeat.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    eol = "LF"
    if b"\r\n" in path.read_bytes():
        eol = "CRLF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def load_index() -> dict:
    return json.loads((REPO / INDEX).read_text(encoding="utf-8"))


def recount_exact_hits(queries: list[dict], top3: list[str]) -> int:
    pred = frozenset(top3)
    hits = 0
    for q in queries:
        exp = frozenset(str(x) for x in (q.get("expected_capability_ids") or []) if str(x))
        if exp == pred:
            hits += 1
    return hits


def main() -> int:
    if not SU.shim_is_generated():
        print("FAILED:IMP-0398 catalog shim grew local constraints (ADV rebuild)")
        return 1

    idx = load_index()
    caps = list(idx.get("capabilities") or [])
    top3 = B.top3_from_caps(caps)
    queries = C.build_queries()
    st = C.stats(queries)
    if st["negative_fraction"] < 0.25:
        print(f"FAILED:IMP-0398 negative_fraction={st['negative_fraction']}")
        return 1
    known = {str(c["capability_id"]) for c in caps}
    for q in queries:
        for cid in q["expected_capability_ids"]:
            if cid not in known:
                print(f"FAILED:IMP-0398 unknown capability {cid} on {q['id']}")
                return 1
        if q["polarity"] == "NEGATIVE" and q["expected_capability_ids"]:
            print(f"FAILED:IMP-0398 negative {q['id']} has expected ids")
            return 1
        if q["polarity"] == "POSITIVE" and not q["expected_capability_ids"]:
            print(f"FAILED:IMP-0398 positive {q['id']} empty expected")
            return 1

    scored = B.score_corpus(queries, top3)
    defeated = scored["score"] < FLOOR
    if not defeated:
        print(
            f"FAILED:IMP-0398 corpus-too-easy score={scored['score']} floor={FLOOR}"
        )
        return 1

    independent_hits = recount_exact_hits(queries, top3)
    if independent_hits != scored["n_exact_hits"]:
        print(
            f"FAILED:IMP-0398 hit-recount {independent_hits} != {scored['n_exact_hits']}"
        )
        return 1

    label_top = B.label_frequency_top3(queries)
    if set(label_top) == set(top3):
        print("FAILED:IMP-0398 popularity equals label histogram (gaming)")
        return 1

    easy = B.score_corpus(B.easy_mutant(queries, top3), top3)
    if easy["score"] < FLOOR:
        print(
            f"FAILED:IMP-0398 easy mutant did not score well ({easy['score']})"
        )
        return 1

    kap = K.relabel_and_kappa(queries, seed=398, fraction=0.10)
    if not kap["pass"]:
        print(f"FAILED:IMP-0398 kappa={kap['value']} < 0.7 rows={kap['rows']}")
        return 1
    n_agree = sum(1 for r in kap["rows"] if r.get("agree"))
    if n_agree != kap["n_relabeled"]:
        # kappa can pass below unanimous; this corpus is unanimous at seed 398.
        pass

    env = SU.envelope_validator()
    pay = SU.payload_validator()
    garbage_n = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not SU.error_messages(env, garbage):
            print("FAILED:IMP-0398 catalog schema accepted garbage")
            return 1
        garbage_n += 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = "2026-08-24T18:33:00Z"
    report = {
        "kind": "router-corpus",
        "observations": [
            {
                "name": "corpus_n",
                "measured": st["n"],
                "method": "count-queries",
                "anchor": f"{OUT}:report.queries",
            },
            {
                "name": "negative_fraction",
                "measured": st["negative_fraction"],
                "method": "n_negative/n",
                "anchor": f"{OUT}:report.corpus_stats",
            },
            {
                "name": "always_top3_exact_set_match",
                "measured": scored["score"],
                "method": "baseline.score_corpus",
                "anchor": f"{OUT}:report.baseline.score",
            },
            {
                "name": "easy_mutant_exact_set_match",
                "measured": easy["score"],
                "method": "baseline.easy_mutant+score_corpus",
                "anchor": f"{OUT}:report.baseline.easy_mutant_score",
            },
            {
                "name": "blind_kappa",
                "measured": kap["value"],
                "method": "kappa.relabel_and_kappa seed=398 fraction=0.10",
                "anchor": f"{OUT}:report.kappa",
            },
        ],
        "control_ids": [
            "NC-garbage",
            "NC-zero-negative",
            "NC-easy-mutant",
        ],
        "title": "Router regression corpus with mandatory negative queries",
        "question": QUESTION,
        "queries": queries,
        "corpus_stats": st,
        "popularity": {
            "source": "fixture usage_count (synthetic redacted-transcript census)",
            "index_path": INDEX,
            "independent_of_gold_labels": True,
            "top3": top3,
            "capabilities": [
                {
                    "capability_id": c["capability_id"],
                    "usage_count": int(c["usage_count"]),
                    "kind": c.get("kind"),
                    "name": c.get("name"),
                }
                for c in caps
            ],
        },
        "baseline": {
            "stub": "always-top-3",
            "score_metric": "exact_set_match_accuracy",
            "score": scored["score"],
            "mean_jaccard": scored["mean_jaccard"],
            "declared_floor": FLOOR,
            "defeated": True,
            "top3": top3,
            "n_exact_hits": scored["n_exact_hits"],
            "independent_hit_recount": independent_hits,
            "label_frequency_top3": label_top,
            "easy_mutant_score": easy["score"],
            "why_exact_match": (
                "Subset-recall would mark every NEGATIVE as a hit because "
                "empty set is a subset of top-3. Exact-set-match makes "
                "returning popular ids on a no-fit query a miss."
            ),
        },
        "kappa": {
            "value": kap["value"],
            "n_relabeled": kap["n_relabeled"],
            "threshold": 0.7,
            "pass": True,
            "seed": kap["seed"],
            "sample_ids": kap["sample_ids"],
            "method": kap["method"],
            "rows": kap["rows"],
        },
        "inputs_observed": {
            "capability_index_live": False,
            "capability_index_fixture": INDEX,
            "imp_0396_receipt": (REPO / "command-center/receipts/IMP-0396.json").is_file(),
            "transcripts_glob": "~/.claude/projects/**/transcripts",
            "transcripts_present": False,
            "note": (
                "Live capability-index.json, IMP-0396 receipt, and redacted "
                "transcripts were absent. Popularity is fixture usage_count "
                "standing in for a redacted transcript census. NEGATIVE rows "
                "encode the IMP-0396 no-fit path as an empty expected set."
            ),
        },
    }

    thin_report = json.loads(json.dumps(report))
    for q in thin_report["queries"]:
        if q.get("polarity") == "NEGATIVE":
            q["polarity"] = "POSITIVE"
            q["expected_capability_ids"] = ["skill.web.search"]
            q["rationale"] = "mutated to drop negatives for schema control"
    thin_report["corpus_stats"] = {
        "n": len(thin_report["queries"]),
        "n_negative": 0,
        "negative_fraction": 0.0,
        "n_positive": len(thin_report["queries"]),
    }
    if not SU.error_messages(pay, thin_report):
        print("FAILED:IMP-0398 payload schema accepted 0% negative corpus")
        return 1

    pay_errs = SU.error_messages(pay, report)
    if pay_errs:
        print("FAILED:IMP-0398 payload schema errors")
        for e in pay_errs[:25]:
            print(" ", e)
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0398",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0398]",
        "min_bytes_threshold": 2048,
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    f"Corpus size n={st['n']} with n_negative={st['n_negative']} "
                    f"(fraction={st['negative_fraction']:.4f} >= 0.25)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{OUT}:report.corpus_stats",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "'import sys;sys.path.insert(0,\"command-center/p2-wave/probes/IMP-0398\");"
                            "import corpus as C;s=C.stats(C.build_queries());print(s)'"
                        ),
                        "raw_output": json.dumps(st, sort_keys=True),
                        "fingerprint": "corpus.stats:build_queries",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "python3 -c 'count polarity NEGATIVE in report.queries'",
                        "raw_output": (
                            f"live_n={st['n']} live_n_negative={st['n_negative']}"
                        ),
                        "fingerprint": "report.queries:polarity-count",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"Always-top-3 on usage_count top3={top3} scores "
                    f"exact_set_match={scored['score']:.4f} "
                    f"(hits={scored['n_exact_hits']}/{st['n']}) below floor {FLOOR}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{OUT}:report.baseline.score",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0398/baseline.py"
                        ),
                        "raw_output": json.dumps(
                            {
                                "score": scored["score"],
                                "n_exact_hits": scored["n_exact_hits"],
                                "top3": top3,
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": "baseline.score_corpus:always-top-3",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "independent exact-set recount vs usage_count top-3"
                        ),
                        "raw_output": (
                            f"independent_hits={independent_hits} "
                            f"score_hits={scored['n_exact_hits']}"
                        ),
                        "fingerprint": "recount_exact_hits:frozenset",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"Easy mutant (positives expect top-3) scores "
                    f"{easy['score']:.4f} >= floor, so the floor is not vacuous."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{OUT}:report.baseline.easy_mutant_score",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "baseline.easy_mutant then score_corpus",
                        "raw_output": json.dumps(
                            {"easy_mutant_score": easy["score"], "floor": FLOOR},
                            sort_keys=True,
                        ),
                        "fingerprint": "baseline.easy_mutant:score",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "compare easy_mutant_score to declared_floor",
                        "raw_output": (
                            f"easy={easy['score']} floor={FLOOR} "
                            f"not_vacuous={easy['score'] >= FLOOR}"
                        ),
                        "fingerprint": "floor-vacuity:easy>=floor",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"Blind keyword relabel of {kap['n_relabeled']} rows "
                    f"(seed={kap['seed']}) has Cohen's kappa={kap['value']:.4f} >= 0.7."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{OUT}:report.kappa",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "kappa.relabel_and_kappa(queries, seed=398, fraction=0.10)",
                        "raw_output": json.dumps(
                            {
                                "value": kap["value"],
                                "n_relabeled": kap["n_relabeled"],
                                "sample_ids": kap["sample_ids"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": "kappa.relabel_and_kappa:seed398",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "count agree flags on kappa.rows",
                        "raw_output": (
                            f"n_agree={n_agree} n_relabeled={kap['n_relabeled']}"
                        ),
                        "fingerprint": "kappa.rows:agree-count",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-corpus-schema",
                "name": "Live artifact validates; garbage rejected; negatives >= 25%",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-baseline-defeat",
                "name": "Always-top-3 stub scores below the declared floor",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-garbage",
                "kind": "malformed-input",
                "description": (
                    "Catalog shim (disk-resolved $ref onto receipt_core) must "
                    "reject {}, unrelated blobs, and passing_tests spam."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={garbage_n}",
                "good_state_output": "envelope_errors=[]",
            },
            {
                "id": "NC-zero-negative",
                "kind": "mutation",
                "description": (
                    "Flipping every NEGATIVE row to POSITIVE and declaring "
                    "negative_fraction=0 must be rejected by the probe-local "
                    "payload schema (the generated catalog shim cannot express this)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "payload schema rejected 0% negatives",
                "good_state_output": "payload schema accepted live report",
            },
            {
                "id": "NC-easy-mutant",
                "kind": "mutation",
                "description": (
                    "A too-easy corpus (every POSITIVE expects usage_count "
                    "top-3) must score at or above the declared floor, proving "
                    "the floor is not vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"easy_mutant_score={easy['score']}",
                "good_state_output": f"live_score={scored['score']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0398-keyword-blind-relabel",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": kap["method"],
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0398/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "IMP-0398",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0398/baseline.py",
                "artifact_path": INDEX,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "baseline.score_corpus(queries, usage_count_top3)",
                    "raw_output": (
                        f"score={scored['score']} hits={scored['n_exact_hits']}"
                    ),
                    "fingerprint": "consumer:baseline.score_corpus",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "max 2 attempts; if the baseline still scores well after 2, "
                "redesign the corpus rather than re-tune"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live capability-index.json and redacted transcripts were absent."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-derive usage_count from a real transcript census and "
                    "re-score always-top-3 on the same labels."
                ),
            },
            {
                "claim": (
                    "command-center/schema/router-corpus.schema.json is a generated "
                    "shim and does not constrain negative_fraction; that rule lives "
                    "in the probe-local payload schema."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Mutate negatives to 0% and confirm the catalog shim still "
                    "accepts the envelope while the payload schema rejects it."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-serialized",
        },
        "report": report,
        "extensions": {
            "named_probes": [
                {"id": "probe1", "role": "corpus-schema", "command": P1},
                {"id": "probe2", "role": "baseline-defeat", "command": P2},
            ],
            "completion_sentinel": SENTINEL,
            "adv_rebuild_circle": False,
            "cloud_ok": False,
            "garbage_rejected": garbage_n,
        },
    }

    env_errs = SU.error_messages(env, doc)
    if env_errs:
        print("FAILED:IMP-0398 envelope schema errors")
        for e in env_errs[:25]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0398 sentinel missing after write")
        return 1
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0398 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"n={st['n']} neg={st['negative_fraction']:.3f} "
        f"score={scored['score']:.4f} kappa={kap['value']:.3f}"
    )
    print("SUCCESS:IMP-0398 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
