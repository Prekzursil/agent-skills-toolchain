#!/usr/bin/env python3
"""Probe 2: determinism + offline typed DEGRADED (no silent lexical fallback).

Mechanically independent of probe 1's recall table: this probe hides or mutates
the pinned model file and checks the typed fallback, then re-ranks the same
query twice for byte-identical output.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.embed_model import CODE_ABSENT, CODE_DIGEST, CODE_ID  # noqa: E402
from router.lexical import lexical_rank  # noqa: E402
from router.semantic_matcher import load_planted, match, pin_identity  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0390-probe2 {msg}")
    return 1


def main() -> int:
    planted = load_planted()
    caps = planted["capabilities"]
    seed = int(planted["seed"])
    k = int(planted["k"])
    query = planted["paraphrase_queries"][0]["query"]
    verbatim = planted["verbatim_queries"][0]["query"]

    a = match(query, caps, k=k, seed=seed)
    b = match(query, caps, k=k, seed=seed)
    identical = a.status == "OK" and a.ranking_bytes() == b.ranking_bytes()

    missing = Path(tempfile.mkdtemp()) / "absent-imp0390-model.json"
    degraded = match(verbatim, caps, k=k, seed=seed, model_path=missing)
    lex = lexical_rank(verbatim, caps, k=k, seed=seed)
    copied_lexical = any(
        row.get("method") == "lexical-jaccard" for row in degraded.ranking
    )
    absent_ok = (
        degraded.status == "DEGRADED"
        and degraded.stage == "semantic"
        and degraded.code == CODE_ABSENT
        and degraded.ranking == []
        and degraded.lexical_results_suppressed is True
        and bool(lex)
        and not copied_lexical
    )

    ident = pin_identity()
    model_path = REPO / ident["path"]
    mutated_doc = json.loads(model_path.read_text(encoding="utf-8"))
    mutated_doc["dim"] = int(mutated_doc.get("dim") or 64) + 1
    mutated = Path(tempfile.mkdtemp()) / "mutated-imp0390-model.json"
    mutated.write_text(json.dumps(mutated_doc, sort_keys=True), encoding="utf-8")
    mismatch = match(query, caps, k=k, seed=seed, model_path=mutated)
    mismatch_ok = (
        mismatch.status == "DEGRADED"
        and mismatch.code in {CODE_DIGEST, CODE_ID}
        and mismatch.ranking == []
    )

    ok = identical and absent_ok and mismatch_ok
    payload = {
        "probe": "probe2-determinism-and-offline",
        "unit_id": "IMP-0390",
        "pass": ok,
        "determinism": {
            "byte_identical": identical,
            "ranking_sha256_run1": hashlib.sha256(a.ranking_bytes()).hexdigest(),
            "ranking_sha256_run2": hashlib.sha256(b.ranking_bytes()).hexdigest(),
            "status": a.status,
            "code": a.code,
            "n_ranked": len(a.ranking),
        },
        "offline_absent": {
            "status": degraded.status,
            "code": degraded.code,
            "stage": degraded.stage,
            "ranking": degraded.ranking,
            "lexical_results_suppressed": degraded.lexical_results_suppressed,
            "lexical_still_recovers_verbatim": bool(lex),
            "copied_lexical_into_semantic": copied_lexical,
        },
        "digest_mismatch": {
            "status": mismatch.status,
            "code": mismatch.code,
            "ranking_empty": mismatch.ranking == [],
        },
        "pinned_model_id": ident.get("model_id"),
        "pinned_model_digest": ident.get("pinned_sha256"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return fail(
            f"identical={identical} absent_ok={absent_ok} mismatch_ok={mismatch_ok}"
        )
    print(
        "SUCCESS:IMP-0390-probe2 byte-identical ranking; "
        "model-absent and digest-mismatch are typed DEGRADED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
