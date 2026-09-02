#!/usr/bin/env python3
"""Measure per-MCP-server tool-schema token cost, rank, disable-remeasure, deferred vs eager."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fleet as F  # noqa: E402
import tokenizer as TOK  # noqa: E402


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def account(blob: str) -> dict[str, Any]:
    raw = blob.encode("utf-8")
    tokens = TOK.count_text(blob)
    chars = len(blob)
    return {
        "tokens": tokens,
        "bytes": len(raw),
        "chars": chars,
        "chars_div_4": chars // 4,
        "sha256": sha256_text(blob),
        "tokenizer_ne_chars_div_4": tokens != chars // 4,
    }


def server_row(server: dict[str, Any]) -> dict[str, Any]:
    eager = F.eager_blob(server)
    deferred = F.deferred_blob(server)
    eager_acc = account(eager)
    deferred_acc = account(deferred)
    return {
        "id": server["id"],
        "origin": server.get("origin"),
        "kind": server.get("kind"),
        "title": server.get("title") or server.get("namespace") or server["id"],
        "tool_count": len(server["tools"]),
        "tool_names": [t.get("name") for t in server["tools"]],
        "fixture_path": server.get("_fixture_path"),
        "eager": eager_acc,
        "deferred": deferred_acc,
        "eager_minus_deferred_tokens": eager_acc["tokens"] - deferred_acc["tokens"],
        "eager_minus_deferred_bytes": eager_acc["bytes"] - deferred_acc["bytes"],
    }


def measure() -> dict[str, Any]:
    servers = F.load_fleet()
    rows = [server_row(s) for s in servers]
    ranked = sorted(rows, key=lambda r: (-r["eager"]["tokens"], -r["eager"]["bytes"], r["id"]))
    total_tokens = sum(r["eager"]["tokens"] for r in rows)
    total_bytes = sum(r["eager"]["bytes"] for r in rows)
    deferred_tokens = sum(r["deferred"]["tokens"] for r in rows)
    deferred_bytes = sum(r["deferred"]["bytes"] for r in rows)
    if not ranked:
        raise RuntimeError("empty fleet")
    disabled = ranked[0]
    remaining = [r for r in ranked if r["id"] != disabled["id"]]
    remeasured_tokens = sum(r["eager"]["tokens"] for r in remaining)
    remeasured_bytes = sum(r["eager"]["bytes"] for r in remaining)
    predicted_tokens = disabled["eager"]["tokens"]
    predicted_bytes = disabled["eager"]["bytes"]
    measured_drop_tokens = total_tokens - remeasured_tokens
    measured_drop_bytes = total_bytes - remeasured_bytes
    token_ids = [r["id"] for r in ranked]
    byte_ranked = sorted(rows, key=lambda r: (-r["eager"]["bytes"], -r["eager"]["tokens"], r["id"]))
    byte_ids = [r["id"] for r in byte_ranked]
    dominate = ranked[0]["id"]
    return {
        "tokenizer": TOK.pin_record(),
        "fleet_size": len(rows),
        "ranked_per_server_token_table": [
            {
                "rank": i,
                "id": r["id"],
                "origin": r["origin"],
                "tool_count": r["tool_count"],
                "tokens": r["eager"]["tokens"],
                "bytes": r["eager"]["bytes"],
                "chars_div_4": r["eager"]["chars_div_4"],
                "share_of_eager_tokens": round(r["eager"]["tokens"] / total_tokens, 6)
                if total_tokens
                else 0.0,
                "deferred_tokens": r["deferred"]["tokens"],
                "deferred_bytes": r["deferred"]["bytes"],
                "eager_minus_deferred_tokens": r["eager_minus_deferred_tokens"],
                "tokenizer_ne_chars_div_4": r["eager"]["tokenizer_ne_chars_div_4"],
                "tool_names": r["tool_names"],
                "fixture_path": r["fixture_path"],
            }
            for i, r in enumerate(ranked, 1)
        ],
        "dominating_server": dominate,
        "eager_total": {
            "tokens": total_tokens,
            "bytes": total_bytes,
            "servers": token_ids,
        },
        "deferred_total": {
            "tokens": deferred_tokens,
            "bytes": deferred_bytes,
            "servers": token_ids,
            "mechanism": (
                "Cursor GetDynamicTools catalog analogue: tool name plus description "
                "truncated at 200 characters, inputSchema omitted until first use."
            ),
        },
        "deferred_vs_eager": {
            "eager_tokens": total_tokens,
            "deferred_tokens": deferred_tokens,
            "token_savings": total_tokens - deferred_tokens,
            "eager_bytes": total_bytes,
            "deferred_bytes": deferred_bytes,
            "byte_savings": total_bytes - deferred_bytes,
            "deferred_cheaper_tokens": deferred_tokens < total_tokens,
            "deferred_cheaper_bytes": deferred_bytes < total_bytes,
            "first_use_activation": {
                "note": (
                    "Deferred + one activated full schema vs eager-all. Activating the "
                    "dominating server's full set still costs less than exposing every "
                    "server eagerly iff remaining deferred stubs plus that server's eager "
                    "set stay below the eager total."
                ),
                "activate_id": dominate,
                "deferred_plus_activated_tokens": deferred_tokens
                - disabled["deferred"]["tokens"]
                + disabled["eager"]["tokens"],
                "eager_tokens": total_tokens,
            },
        },
        "disable_and_remeasure": {
            "disabled_server": disabled["id"],
            "predicted_drop_tokens": predicted_tokens,
            "measured_drop_tokens": measured_drop_tokens,
            "tokens_match": predicted_tokens == measured_drop_tokens,
            "predicted_drop_bytes": predicted_bytes,
            "measured_drop_bytes": measured_drop_bytes,
            "bytes_match": predicted_bytes == measured_drop_bytes,
            "remeasured_tokens": remeasured_tokens,
            "remeasured_bytes": remeasured_bytes,
            "baseline_tokens": total_tokens,
            "baseline_bytes": total_bytes,
        },
        "two_signal": {
            "signal_1": "tokenizer tokens (res-0041-gpt2-regex-unigram/v1) over canonical tools/list JSON",
            "signal_2": "UTF-8 byte length of the same canonical JSON (independent field, not a re-run)",
            "token_rank_ids": token_ids,
            "byte_rank_ids": byte_ids,
            "rank_ids_agree": token_ids == byte_ids,
            "dominator_tokens": dominate,
            "dominator_bytes": byte_ids[0],
            "dominator_agrees": dominate == byte_ids[0],
            "every_row_tokenizer_ne_chars_div_4": all(
                r["eager"]["tokenizer_ne_chars_div_4"] for r in rows
            ),
        },
        "home_mcp": F.home_mcp_inventory(),
        "rows": rows,
    }


if __name__ == "__main__":
    import json

    doc = measure()
    slim = {
        "tokenizer": doc["tokenizer"]["pin"],
        "ranked": [
            {"rank": r["rank"], "id": r["id"], "tokens": r["tokens"], "bytes": r["bytes"]}
            for r in doc["ranked_per_server_token_table"]
        ],
        "disable_and_remeasure": doc["disable_and_remeasure"],
        "deferred_vs_eager": {
            k: doc["deferred_vs_eager"][k]
            for k in (
                "eager_tokens",
                "deferred_tokens",
                "token_savings",
                "deferred_cheaper_tokens",
            )
        },
        "two_signal": {
            "rank_ids_agree": doc["two_signal"]["rank_ids_agree"],
            "dominator_agrees": doc["two_signal"]["dominator_agrees"],
        },
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
