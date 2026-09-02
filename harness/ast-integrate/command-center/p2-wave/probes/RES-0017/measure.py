"""Measure turn-0 occupancy per capability class with a pinned tokenizer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from account import OCCUPANCY_FIELD, simulate_later_turns
from bpe import RANKS, SEED, TOKENIZER_ID, TOKENIZER_VERSION, load_pinned
from inject import (
    CLASS_ORDER,
    SESSION,
    class_payloads,
    render,
    utf8_len,
    wrapped_block,
)
from live import live_census

HERE = Path(__file__).resolve().parent
STABILITY_TOLERANCE_TOKENS = 0
ABLATION_REL_TOL = 0.15
ABLATION_ABS_TOL = 24
EXTRA_TURN_TOKENS = (400, 180, 90)


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _class_row(name: str, payload: dict, bpe) -> dict:
    injected = payload["injected"]
    tokens = bpe.count(injected)
    bytes_ = utf8_len(injected)
    tree = int(payload.get("tree_bytes") or 0)
    return {
        "class": name,
        "injected_bytes": bytes_,
        "injected_tokens": tokens,
        "tree_bytes": tree,
        "file_size_inference_bytes": tree,
        "file_size_div4_tokens": tree // 4,
        "tokenizer_ne_bytes_div4": tokens != (bytes_ // 4),
        "injected_lt_tree": bytes_ < tree if tree else False,
        "n_files": len(payload.get("files") or []),
        "files": payload.get("files") or [],
        "always_on": payload.get("always_on"),
        "lazy": payload.get("lazy"),
        "schema_files": payload.get("schema_files"),
    }


def _ablation_ok(measured_delta: int, predicted: int) -> bool:
    if measured_delta <= 0 or predicted <= 0:
        return False
    if abs(measured_delta - predicted) <= ABLATION_ABS_TOL:
        return True
    return abs(measured_delta - predicted) / predicted <= ABLATION_REL_TOL


def measure() -> dict:
    bpe = load_pinned()
    payloads = class_payloads(SESSION)
    full = render(payloads)
    occ_tokens = bpe.count(full)
    occ_bytes = utf8_len(full)
    per_class = [_class_row(name, payloads[name], bpe) for name in CLASS_ORDER]
    by_tokens = max(per_class, key=lambda r: r["injected_tokens"])
    by_bytes = max(per_class, key=lambda r: r["injected_bytes"])

    ablate_class = by_tokens["class"]
    without = render(payloads, omit=ablate_class)
    after_tokens = bpe.count(without)
    after_bytes = utf8_len(without)
    delta_tokens = occ_tokens - after_tokens
    delta_bytes = occ_bytes - after_bytes
    block = wrapped_block(ablate_class, payloads)
    predicted_tokens = bpe.count(block)
    predicted_bytes = utf8_len(block)
    confirmed = _ablation_ok(delta_tokens, predicted_tokens) and (
        delta_bytes == predicted_bytes
    )

    full2 = render(payloads)
    stable_tokens = bpe.count(full2)
    stable_bytes = utf8_len(full2)
    stable = (
        abs(stable_tokens - occ_tokens) <= STABILITY_TOLERANCE_TOKENS
        and stable_bytes == occ_bytes
    )

    ledger = simulate_later_turns(occ_tokens, list(EXTRA_TURN_TOKENS))
    tree_sum = sum(int(r["tree_bytes"] or 0) for r in per_class)
    injected_sum_bytes = sum(int(r["injected_bytes"]) for r in per_class)
    bytes_div4 = occ_bytes // 4

    file_size_rejected = tree_sum > occ_bytes
    char_div4_rejected = bytes_div4 != occ_tokens
    cumulative_rejected = ledger[OCCUPANCY_FIELD] != ledger["tokens_cumulative"]

    return {
        "tokenizer": {
            "id": TOKENIZER_ID,
            "version": TOKENIZER_VERSION,
            "seed_path": "command-center/p2-wave/probes/RES-0017/tokenizer_seed.txt",
            "ranks_path": "command-center/p2-wave/probes/RES-0017/bpe_ranks.json",
            "seed_sha256": sha256_file(SEED),
            "ranks_sha256": sha256_file(RANKS),
            "trained_on_session_corpus": False,
        },
        "session_root": "command-center/p2-wave/probes/RES-0017/fixtures/session",
        "occupancy": {
            "numerator_field": OCCUPANCY_FIELD,
            "turn0_injected_tokens": occ_tokens,
            "turn0_injected_bytes": occ_bytes,
            "tokens_cumulative": ledger["tokens_cumulative"],
            "tokens_last_turn": ledger["tokens_last_turn"],
            "cumulative_rejected_as_occupancy": True,
            "cumulative_equals_occupancy": ledger["cumulative_equals_occupancy"],
            "accounting_source": ledger["accounting_source"],
            "ledger": ledger,
        },
        "per_class": per_class,
        "dominates_tokens": by_tokens["class"],
        "dominates_bytes": by_bytes["class"],
        "ablation": {
            "class": ablate_class,
            "predicted_tokens_independent_block": predicted_tokens,
            "measured_occupancy_delta_tokens": delta_tokens,
            "predicted_bytes": predicted_bytes,
            "measured_delta_bytes": delta_bytes,
            "confirmed": confirmed,
            "rel_tol": ABLATION_REL_TOL,
            "abs_tol": ABLATION_ABS_TOL,
            "after_tokens": after_tokens,
            "after_bytes": after_bytes,
        },
        "stability": {
            "remeasure_tokens": stable_tokens,
            "remeasure_bytes": stable_bytes,
            "delta_tokens": stable_tokens - occ_tokens,
            "delta_bytes": stable_bytes - occ_bytes,
            "tolerance_tokens": STABILITY_TOLERANCE_TOKENS,
            "stable": stable,
        },
        "file_size_inference": {
            "tree_bytes_sum": tree_sum,
            "injected_class_bytes_sum": injected_sum_bytes,
            "occupancy_bytes": occ_bytes,
            "tree_gt_occupancy": file_size_rejected,
            "bytes_div4": bytes_div4,
            "tokenizer_tokens": occ_tokens,
            "bytes_div4_equals_tokenizer": not char_div4_rejected,
            "rejected_as_occupancy": True,
        },
        "controls": {
            "file_size_inference_rejected": file_size_rejected,
            "char_div4_rejected": char_div4_rejected,
            "cumulative_rejected_as_occupancy": cumulative_rejected,
            "ablation_confirmed": confirmed,
            "stability_ok": stable,
        },
        "live": live_census(),
        "payloads_meta": {
            name: {
                "injected_bytes": utf8_len(payloads[name]["injected"]),
                "tree_bytes": payloads[name].get("tree_bytes"),
                "always_on": payloads[name].get("always_on"),
                "lazy": payloads[name].get("lazy"),
            }
            for name in CLASS_ORDER
        },
    }


def dumps_measure() -> str:
    return json.dumps(measure(), indent=2, sort_keys=True)
