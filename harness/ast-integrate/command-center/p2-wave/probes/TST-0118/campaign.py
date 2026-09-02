"""Campaign + catalog-named tests for TST-0118."""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from classify import LAYER_SEMANTIC, classify_bytes, classify_text, grammar_sha256
from generator import (
    SEED_DEFAULT,
    byte_mutants,
    cyclic_subworkflow,
    dumps,
    grammar_campaign,
    loop_no_convergence,
    valid_library,
    zero_producer_barrier,
)
from semantic import (
    BARRIER_ZERO_PRODUCERS,
    CYCLIC_SUBWORKFLOW,
    HANG_BOUND_EXCEEDED,
    INTERNAL_CRASH,
    LOOP_NO_CONVERGENCE,
    analyze,
)

HANG_DEADLINE_S = 1.25
GRAMMAR_REACH_FLOOR = 0.95
BYTE_REACH_CEILING = 0.35


def _run_one(item: dict[str, Any]) -> dict[str, Any]:
    text = dumps(item["doc"])
    cls = classify_text(text)
    row: dict[str, Any] = {
        "tag": item["tag"],
        "layer": cls["layer"],
        "syntax_error_count": len(cls.get("syntax_errors") or []),
    }
    if cls["layer"] == LAYER_SEMANTIC:
        verdict = analyze(cls["value"], mode="safe")
        row["accepted"] = verdict["accepted"]
        row["codes"] = verdict["codes"]
        row["elapsed_ms"] = verdict["elapsed_ms"]
        row["visits"] = verdict["visits"]
        row["hung"] = verdict["hung"]
        row["crashed"] = verdict["crashed"]
    else:
        row["accepted"] = False
        row["codes"] = []
        row["hung"] = False
        row["crashed"] = False
    return row


def run_grammar_campaign(seed: int = SEED_DEFAULT, n: int = 80) -> dict[str, Any]:
    items = grammar_campaign(seed, n)
    rows = [_run_one(it) for it in items]
    semantic_n = sum(1 for r in rows if r["layer"] == LAYER_SEMANTIC)
    hung_n = sum(1 for r in rows if r.get("hung"))
    crash_n = sum(1 for r in rows if r.get("crashed"))
    fingerprint = hashlib.sha256(
        repr([(r["tag"], r["layer"], tuple(r.get("codes") or [])) for r in rows]).encode()
    ).hexdigest()
    return {
        "seed": seed,
        "generated": len(rows),
        "semantic_layer_count": semantic_n,
        "reach_rate": semantic_n / len(rows) if rows else 0.0,
        "hung": hung_n,
        "crashed": crash_n,
        "grammar_sha256": grammar_sha256(),
        "fingerprint": fingerprint,
        "rows": rows,
    }


def run_byte_campaign(seed: int = SEED_DEFAULT, n: int = 80) -> dict[str, Any]:
    base = dumps(valid_library())
    blobs = byte_mutants(seed, base, n)
    layers = [classify_bytes(b)["layer"] for b in blobs]
    semantic_n = sum(1 for layer in layers if layer == LAYER_SEMANTIC)
    return {
        "seed": seed,
        "generated": len(layers),
        "semantic_layer_count": semantic_n,
        "reach_rate": semantic_n / len(layers) if layers else 0.0,
        "lexer_or_syntax": len(layers) - semantic_n,
    }


def test_semantic_reach_rate_is_reported(seed: int = SEED_DEFAULT) -> dict[str, Any]:
    grammar = run_grammar_campaign(seed)
    byte = run_byte_campaign(seed)
    grammar2 = run_grammar_campaign(seed)
    ok = (
        grammar["generated"] >= 80
        and grammar["semantic_layer_count"] == grammar["generated"]
        and grammar["reach_rate"] >= GRAMMAR_REACH_FLOOR
        and byte["reach_rate"] < grammar["reach_rate"]
        and byte["reach_rate"] <= BYTE_REACH_CEILING
        and grammar["hung"] == 0
        and grammar["crashed"] == 0
        and grammar["fingerprint"] == grammar2["fingerprint"]
        and "reach_rate" in grammar
        and "semantic_layer_count" in grammar
        and "grammar_sha256" in grammar
    )
    return {
        "ok": ok,
        "grammar": {
            k: grammar[k]
            for k in (
                "seed",
                "generated",
                "semantic_layer_count",
                "reach_rate",
                "hung",
                "crashed",
                "grammar_sha256",
                "fingerprint",
            )
        },
        "byte": byte,
        "repro_same_seed": grammar["fingerprint"] == grammar2["fingerprint"],
        "reported": True,
    }


def _deadline(fn, timeout_s: float = HANG_DEADLINE_S) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout_s)
        except Exception as exc:  # noqa: BLE001
            return {
                "accepted": False,
                "codes": [HANG_BOUND_EXCEEDED, type(exc).__name__],
                "elapsed_ms": timeout_s * 1000.0,
                "visits": -1,
                "mode": "timeout",
                "hung": True,
                "crashed": False,
                "typed_rejection": False,
            }


def test_cyclic_subworkflow_is_rejected_not_hung() -> dict[str, Any]:
    doc = cyclic_subworkflow()
    safe = _deadline(lambda: analyze(doc, mode="safe"))
    naive = _deadline(
        lambda: analyze(doc, mode="naive", max_visits=2048, max_nesting=10_000)
    )
    good = _deadline(lambda: analyze(valid_library(), mode="safe"))
    ok = (
        CYCLIC_SUBWORKFLOW in (safe.get("codes") or [])
        and safe.get("typed_rejection") is True
        and safe.get("hung") is False
        and safe.get("crashed") is False
        and INTERNAL_CRASH not in (safe.get("codes") or [])
        and float(safe.get("elapsed_ms") or 9999) < 500.0
        and HANG_BOUND_EXCEEDED in (naive.get("codes") or [])
        and good.get("accepted") is True
        and CYCLIC_SUBWORKFLOW not in (good.get("codes") or [])
    )
    return {"ok": ok, "safe": safe, "naive": naive, "good": good}


def test_zero_producer_barrier_is_rejected() -> dict[str, Any]:
    bad = _deadline(lambda: analyze(zero_producer_barrier(), mode="safe"))
    good = _deadline(lambda: analyze(valid_library(), mode="safe"))
    loop_bad = _deadline(lambda: analyze(loop_no_convergence(), mode="safe"))
    ok = (
        BARRIER_ZERO_PRODUCERS in (bad.get("codes") or [])
        and bad.get("typed_rejection") is True
        and bad.get("hung") is False
        and BARRIER_ZERO_PRODUCERS not in (good.get("codes") or [])
        and good.get("accepted") is True
        and LOOP_NO_CONVERGENCE in (loop_bad.get("codes") or [])
    )
    return {"ok": ok, "bad": bad, "good": good, "loop_no_convergence": loop_bad}
