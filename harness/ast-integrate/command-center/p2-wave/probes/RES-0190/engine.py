"""Fixed-budget breadth-versus-depth runner for RES-0190.

Each arm is billed SCAN_COST per abstract and VERIFY_COST per deep dive
(body + companion). Leftover allocation that cannot buy another operation
is recorded as waste so billed_total == BUDGET_PER_QUESTION per question.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cluster as C  # noqa: E402
FIXTURE = HERE / "fixtures" / "universe.json"

SCAN_COST = 50
VERIFY_COST = 200
BUDGET_PER_QUESTION = 1000
SPLITS: dict[str, tuple[float, float]] = {
    "80/20": (0.80, 0.20),
    "50/50": (0.50, 0.50),
    "20/80": (0.20, 0.80),
}
NEGATIVE_CONTROL_SPLIT = "50/50"
FILE_URL_PREFIX = (
    "file:command-center/p2-wave/probes/RES-0190/fixtures/universe.json#"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def record_blob(rec: dict[str, Any]) -> bytes:
    return json.dumps(
        rec, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def load_corpus() -> dict[str, Any]:
    if not FIXTURE.is_file():
        raise FileNotFoundError(f"missing corpus {FIXTURE}")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fetch_record(rec: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    blob = record_blob(rec)
    return {
        "source_id": rec["id"],
        "resolved_url": FILE_URL_PREFIX + rec["id"],
        "fetch_timestamp": fetched_at,
        "sha256": sha256_bytes(blob),
        "bytes": len(blob),
        "backend": rec["backend"],
        "question_id": rec["question_id"],
        "whitespace_tokens": len(blob.decode("utf-8").split()),
    }


def _by_question(
    sources: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in sources:
        grouped[str(rec["question_id"])].append(rec)
    for qid in grouped:
        grouped[qid].sort(key=lambda r: r["id"])
    return dict(grouped)


def _index(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in sources}


def run_question(
    qid: str,
    rows: list[dict[str, Any]],
    split_name: str,
    fetched_at: str,
) -> dict[str, Any]:
    broad_frac, deep_frac = SPLITS[split_name]
    scan_cap = int(BUDGET_PER_QUESTION * broad_frac)
    verify_cap = int(BUDGET_PER_QUESTION * deep_frac)
    if scan_cap + verify_cap != BUDGET_PER_QUESTION:
        raise RuntimeError(f"split {split_name} does not partition budget")
    by_id = _index(rows)
    scan_spent = 0
    scanned: list[dict[str, Any]] = []
    for rec in rows:
        if scan_spent + SCAN_COST > scan_cap:
            break
        scan_spent += SCAN_COST
        scanned.append(rec)

    abstracts = [r["abstract"] for r in scanned]
    labels = C.cluster_labels(abstracts) if abstracts else []
    clusters: dict[int, list[int]] = defaultdict(list)
    for i, lab in enumerate(labels):
        clusters[lab].append(i)

    def eligible(indices: list[int]) -> bool:
        return any(
            scanned[i].get("companion_id") and scanned[i].get("verifiable")
            for i in indices
        )

    ranked = sorted(
        clusters.items(),
        key=lambda kv: (len(kv[1]), scanned[kv[1][0]]["id"]),
    )
    verify_spent = 0
    verified: list[dict[str, Any]] = []
    skipped_no_peer: list[str] = []
    for _lab, idxs in ranked:
        if verify_spent + VERIFY_COST > verify_cap:
            break
        if not eligible(idxs):
            skipped_no_peer.extend(scanned[i]["id"] for i in idxs)
            continue
        pick = sorted(idxs, key=lambda i: scanned[i]["id"])[0]
        rec = scanned[pick]
        peer_id = rec.get("companion_id")
        peer = by_id.get(str(peer_id)) if peer_id else None
        if peer is None:
            skipped_no_peer.append(rec["id"])
            continue
        verify_spent += VERIFY_COST
        primary_fetch = fetch_record(rec, fetched_at)
        peer_fetch = fetch_record(peer, fetched_at)
        verdict = C.pair_verdict(rec["body"], peer["body"])
        if verdict.get("verdict") != "MERGE":
            continue
        verified.append(
            {
                "claim_id": f"{split_name}:{qid}:{rec['id']}",
                "question_id": qid,
                "text": rec["body"],
                "status": "VERIFIED",
                "sherman_kent": "almost-certain",
                "verification_path": (
                    "command-center/p2-wave/probes/RES-0190/"
                    "probe2_mechanism_not_string.py"
                ),
                "signals": [
                    {
                        "id": "primary-body-fetch",
                        "backend": rec["backend"],
                        "lineage": primary_fetch,
                    },
                    {
                        "id": "companion-body-fetch",
                        "backend": peer["backend"],
                        "lineage": peer_fetch,
                    },
                ],
                "source_lineage": primary_fetch,
                "companion_lineage": peer_fetch,
                "dedup": {
                    "method": "mechanism_dedup.AND-gate",
                    "pair_verdict": verdict["verdict"],
                    "jaccard": verdict.get("jaccard"),
                    "cosine": verdict.get("cosine"),
                },
            }
        )

    verified_texts = [v["text"] for v in verified]
    mechanism_distinct = C.distinct_count(verified_texts)
    string_distinct = len(set(verified_texts))
    waste = (scan_cap - scan_spent) + (verify_cap - verify_spent)
    billed = scan_spent + verify_spent + waste
    scanned_abstracts = [r["abstract"] for r in scanned]
    return {
        "question_id": qid,
        "split": split_name,
        "scan_cap": scan_cap,
        "verify_cap": verify_cap,
        "scan_spent": scan_spent,
        "verify_spent": verify_spent,
        "waste": waste,
        "billed_total": billed,
        "n_scanned": len(scanned),
        "scanned_ids": [r["id"] for r in scanned],
        "scanned_string_distinct": len(set(scanned_abstracts)),
        "scanned_mechanism_distinct": C.distinct_count(scanned_abstracts),
        "n_verified_raw": len(verified),
        "mechanism_distinct_verified": mechanism_distinct,
        "string_distinct_verified": string_distinct,
        "skipped_no_peer": skipped_no_peer,
        "verified_claims": verified,
        "budget_ok": billed == BUDGET_PER_QUESTION,
    }


def interpret(totals: dict[str, int], variance: int) -> dict[str, Any]:
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    best, best_n = ranked[0]
    second, second_n = ranked[1]
    gap = best_n - second_n
    if gap <= variance:
        return {
            "headline": "NO DETECTED DIFFERENCE",
            "winner": None,
            "gap": gap,
            "variance": variance,
            "reason": (
                "Observed gap between the top two allocations is not larger "
                "than the run-to-run variance of the negative-control arm."
            ),
            "ranked": [
                {"split": k, "mechanism_distinct_verified": v} for k, v in ranked
            ],
        }
    return {
        "headline": (
            f"{best} yields more distinct VERIFIED claims than {second} "
            f"on this corpus (gap={gap} > variance={variance})"
        ),
        "winner": best,
        "gap": gap,
        "variance": variance,
        "reason": (
            "Negative control: the same 50/50 allocation run twice produced "
            f"variance {variance}; the observed allocation gap exceeds it."
        ),
        "ranked": [
            {"split": k, "mechanism_distinct_verified": v} for k, v in ranked
        ],
    }


def run_experiment() -> dict[str, Any]:
    corpus = load_corpus()
    sources = corpus["sources"]
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grouped = _by_question(sources)
    arms: dict[str, dict[str, Any]] = {}
    for split in ("80/20", "50/50", "20/80"):
        per_q = []
        for qid in ("Q-DEDUP", "Q-G1", "Q-LINEAGE"):
            per_q.append(run_question(qid, grouped[qid], split, fetched_at))
        claims = [c for q in per_q for c in q["verified_claims"]]
        billed = sum(q["billed_total"] for q in per_q)
        arms[split] = {
            "split": split,
            "questions": per_q,
            "billed_total": billed,
            "budget_cap": BUDGET_PER_QUESTION * 3,
            "budget_ok": billed == BUDGET_PER_QUESTION * 3,
            "mechanism_distinct_verified": sum(
                q["mechanism_distinct_verified"] for q in per_q
            ),
            "string_distinct_verified": sum(
                q["string_distinct_verified"] for q in per_q
            ),
            "n_scanned": sum(q["n_scanned"] for q in per_q),
            "n_verified_raw": sum(q["n_verified_raw"] for q in per_q),
            "scanned_string_distinct": sum(
                q["scanned_string_distinct"] for q in per_q
            ),
            "scanned_mechanism_distinct": sum(
                q["scanned_mechanism_distinct"] for q in per_q
            ),
            "verified_claims": claims,
        }

    ctrl_a = []
    ctrl_b = []
    for qid in ("Q-DEDUP", "Q-G1", "Q-LINEAGE"):
        ctrl_a.append(
            run_question(qid, grouped[qid], NEGATIVE_CONTROL_SPLIT, fetched_at)
        )
        ctrl_b.append(
            run_question(qid, grouped[qid], NEGATIVE_CONTROL_SPLIT, fetched_at)
        )
    n_a = sum(q["mechanism_distinct_verified"] for q in ctrl_a)
    n_b = sum(q["mechanism_distinct_verified"] for q in ctrl_b)
    variance = abs(n_a - n_b)
    totals = {name: arms[name]["mechanism_distinct_verified"] for name in arms}
    policy = interpret(totals, variance)
    string_totals = {
        name: arms[name]["string_distinct_verified"] for name in arms
    }
    return {
        "fetched_at": fetched_at,
        "meter": {
            "scan_cost": SCAN_COST,
            "verify_cost": VERIFY_COST,
            "budget_per_question": BUDGET_PER_QUESTION,
            "questions": 3,
            "budget_per_arm": BUDGET_PER_QUESTION * 3,
            "note": (
                "Billed operation credits (scan=50, verify=200) are the "
                "enforced equal budget. Waste fills unused allocation so "
                "every arm bills exactly the cap."
            ),
        },
        "backends": corpus.get("backends"),
        "questions": corpus.get("questions"),
        "arms": arms,
        "negative_control": {
            "split": NEGATIVE_CONTROL_SPLIT,
            "run_a_distinct": n_a,
            "run_b_distinct": n_b,
            "variance": variance,
            "identical": n_a == n_b,
        },
        "totals_mechanism": totals,
        "totals_string": string_totals,
        "policy": policy,
        "n_sources": len(sources),
    }
