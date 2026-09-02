#!/usr/bin/env python3
"""Run the frozen 50-doc measurement. Shared by emit and probes."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    INDEX_PATH,
    MARGIN,
    N_DOCS,
    N_PER_CLASS,
    WILSON_FLOOR,
    sha256_bytes,
)
from dataset import assert_corpus_shape, load_docs  # noqa: E402
from lexical import lexical_score, predict_label as lex_predict  # noqa: E402
from score import decide, score_coin_flip, score_predictions  # noqa: E402
from statsfeat import predict_label as stats_predict  # noqa: E402
from statsfeat import stats_score  # noqa: E402


def _compact(block: dict) -> dict:
    out = dict(block)
    per = []
    for row in block.get("per_doc") or []:
        per.append(
            {
                "id": row["id"],
                "gold": row["gold"],
                "pred": row["pred"],
                "ok": row["ok"],
            }
        )
    out["per_doc"] = per
    return out


def run_measurement() -> dict:
    docs = load_docs()
    assert_corpus_shape(docs)
    lex = score_predictions(docs, lex_predict)
    st = score_predictions(docs, stats_predict)
    coin = score_coin_flip(docs)
    dec = decide(lex, st, MARGIN, WILSON_FLOOR)
    features = []
    for d in docs:
        features.append(
            {
                "id": d["id"],
                "gold": d["label"],
                "lexical": lexical_score(d["text"]),
                "stats": stats_score(d["text"]),
            }
        )
    index_raw = INDEX_PATH.read_bytes().replace(b"\r\n", b"\n")
    return {
        "n": N_DOCS,
        "n_practitioner": N_PER_CLASS,
        "n_mill": N_PER_CLASS,
        "index_sha256": sha256_bytes(index_raw),
        "docs": [
            {
                "id": d["id"],
                "label": d["label"],
                "permalink": d["permalink"],
                "fetch_timestamp": d["fetch_timestamp"],
                "http_status": d["http_status"],
                "sha256": d["sha256"],
                "bytes": d["bytes"],
                "path": d["path"],
                "provenance_kind": d["provenance_kind"],
                "provenance_basis": d["provenance_basis"],
                "text_chars": len(d["text"]),
            }
            for d in docs
        ],
        "lexical": _compact(lex),
        "stats": _compact(st),
        "coin_flip": _compact(coin),
        "decision": dec,
        "features": features,
    }


def classifier_source_fingerprint() -> dict:
    files = ["lexical.py", "statsfeat.py", "score.py"]
    out = {}
    for name in files:
        raw = (HERE / name).read_bytes().replace(b"\r\n", b"\n")
        out[name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    return out
