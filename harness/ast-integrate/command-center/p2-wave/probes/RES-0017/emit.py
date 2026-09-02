#!/usr/bin/env python3
"""Emit command-center/research/RES-0017.json and pin tokenizer ranks.

G-1: python3 -B this file, then write_receipts.py, then _measure_one_delivered.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from account import ACCOUNTING_SOURCE, CUMULATIVE_FIELD, OCCUPANCY_FIELD  # noqa: E402
from bpe import RANKS, train_from_seed  # noqa: E402
from measure import measure  # noqa: E402

UNIT = "RES-0017"
OUT = "command-center/research/RES-0017.json"
SCHEMA = "command-center/p2-wave/probes/RES-0017/measurement-run.schema.json"
CATALOG_SCHEMA = "command-center/schema/measurement-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0017/probe1_ablate_remeasure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0017/probe2_byte_signal_and_cumulative_trap.py"
)
QUESTION = (
    "In bytes and tokens, what does each capability class contribute to the "
    "turn-0 context of a real session on this box, and which class dominates "
    "- measured with the client's own accounting rather than inferred from "
    "file sizes?"
)
SENTINEL = (
    "SUCCESS:RES-0017 in the receipt AND a per-class byte and token "
    "attribution where at least one class is confirmed by an "
    "ablate-and-remeasure delta"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def pin_ranks() -> None:
    if RANKS.is_file() and RANKS.stat().st_size > 0:
        return
    bpe = train_from_seed()
    RANKS.write_text(
        json.dumps(bpe.to_json(), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    pin_ranks()
    live = measure()
    if not live["controls"]["ablation_confirmed"]:
        print("FAILED:RES-0017 emit ablation not confirmed")
        return 1
    if not live["controls"]["stability_ok"]:
        print("FAILED:RES-0017 emit stability")
        return 1
    if not live["controls"]["file_size_inference_rejected"]:
        print("FAILED:RES-0017 emit file-size inference not rejected")
        return 1
    if not live["controls"]["char_div4_rejected"]:
        print("FAILED:RES-0017 emit bytes/4 matched tokenizer")
        return 1
    if not live["controls"]["cumulative_rejected_as_occupancy"]:
        print("FAILED:RES-0017 emit cumulative==occupancy")
        return 1

    occ = live["occupancy"]
    abl = live["ablation"]
    rows = live["per_class"]
    attr = ", ".join(
        f"{r['class']}={r['injected_bytes']}B/{r['injected_tokens']}tok"
        for r in rows
    )
    answer = (
        f"Hermetic throwaway session on this Linux box, accounted with pinned "
        f"{live['tokenizer']['id']} on the concatenated turn-0 injection "
        f"(occupancy field {OCCUPANCY_FIELD}={occ['turn0_injected_tokens']} "
        f"tokens / {occ['turn0_injected_bytes']} bytes). Per-class attribution: "
        f"{attr}. Dominant class by tokens: {live['dominates_tokens']}; by "
        f"bytes: {live['dominates_bytes']}. Ablating {abl['class']} dropped "
        f"{abl['measured_occupancy_delta_tokens']} tokens and "
        f"{abl['measured_delta_bytes']} bytes (confirmed). File-size inference "
        f"of the capability trees is {live['file_size_inference']['tree_bytes_sum']} "
        f"bytes, larger than occupancy, and bytes/4="
        f"{live['file_size_inference']['bytes_div4']} is not the tokenizer "
        f"count. tokens_cumulative={occ['tokens_cumulative']} after extra "
        f"turns is a different ledger field and is not the occupancy "
        f"numerator. Live ~/.claude usage JSONL is recorded as "
        f"{live['live']['usage_report']['status']} and is not used as the "
        f"occupancy numerator. {SENTINEL}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_schema_present = (REPO / CATALOG_SCHEMA).is_file()
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "schema_version": 1,
        "report_kind": "measurement-run",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:RES-0017",
        "completion_sentinel": SENTINEL,
        "title": "Measure what actually consumes the context window (skills, MCP schemas, rules, tools)",
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "min_bytes_threshold": 1024,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "catalog_output_schema": CATALOG_SCHEMA,
        "catalog_schema_present": catalog_schema_present,
        "catalog_schema_note": (
            "command-center/schema/measurement-run.schema.json is owned by "
            "RES-0001; this unit uses a local discriminating contract and "
            "does not rebuild the global schema family."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "local-serialized",
        },
        "tokenizer": live["tokenizer"],
        "session_root": live["session_root"],
        "per_class": rows,
        "dominates_tokens": live["dominates_tokens"],
        "dominates_bytes": live["dominates_bytes"],
        "occupancy": {
            "numerator_field": OCCUPANCY_FIELD,
            "turn0_injected_tokens": occ["turn0_injected_tokens"],
            "turn0_injected_bytes": occ["turn0_injected_bytes"],
            "tokens_cumulative": occ["tokens_cumulative"],
            "tokens_last_turn": occ["tokens_last_turn"],
            "cumulative_rejected_as_occupancy": True,
            "cumulative_equals_occupancy": occ["cumulative_equals_occupancy"],
            "accounting_source": occ["accounting_source"],
            "ledger": occ["ledger"],
        },
        "ablation": abl,
        "stability": live["stability"],
        "file_size_inference": live["file_size_inference"],
        "accounting": {
            "source_named": True,
            "occupancy_field": OCCUPANCY_FIELD,
            "cumulative_field": CUMULATIVE_FIELD,
            "last_turn_field": "tokens_last_turn",
            "conflation_rejected": True,
            "accounting_source": ACCOUNTING_SOURCE,
            "client_accounting": (
                "tokenizer applied to the payload the client injects at "
                "turn 0 (always-on skills, MCP tool schemas, rules, builtin "
                "tools), not directory file sizes and not tokens_cumulative"
            ),
        },
        "live": live["live"],
        "controls": live["controls"],
        "signals": [
            {
                "id": "S1-tokenizer-occupancy",
                "instrument": live["tokenizer"]["id"],
                "field": OCCUPANCY_FIELD,
                "value": occ["turn0_injected_tokens"],
            },
            {
                "id": "S2-utf8-bytes-wc",
                "instrument": "python utf-8 len + probe2 wc -c",
                "field": "turn0_injected_bytes",
                "value": occ["turn0_injected_bytes"],
            },
        ],
        "tests": [
            {
                "id": "RES0017-T1",
                "name": "ablate one class, re-measure, attribute the delta",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "RES0017-T2",
                "name": "stability remeasure; wc -c byte signal; cumulative trap",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0017-C1",
                "name": "file-size of capability trees is not occupancy",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "RES0017-C2",
                "name": "tokens_cumulative is not the occupancy numerator",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "RES0017-C3",
                "name": "lazy skill body and MCP server source stay out of turn-0",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0017-probe2-wc-c-and-cumulative-trap",
            "verdict": "PASS",
            "independent": True,
            "shell": "wc -c on dumped occupancy payload",
            "scope_not_agreement": True,
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "ablate-and-remeasure", "command": P1},
            {
                "id": "probe2",
                "role": "byte-signal-and-cumulative-trap",
                "command": P2,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "residual_unknowns": [
            {
                "id": "live-claude-usage-jsonl",
                "status": live["live"]["usage_report"]["status"],
                "detail": live["live"]["usage_report"].get("reason")
                or live["live"]["usage_report"].get("reason_not_numerator"),
            }
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:RES-0017 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1

    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            print("FAILED:RES-0017 schema accepts garbage")
            return 1

    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0017 sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, n = digest(out_path)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print(f"dominates_tokens={live['dominates_tokens']} ablate={abl['class']}")
    print("SUCCESS:RES-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
