#!/usr/bin/env python3
"""Windows smoke of shard-03 real modules (not official G-1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))


def main() -> int:
    from council.schema.library import write_library

    lib_path = REPO / "tools" / "council" / "schema" / "library.json"
    write_library(lib_path)
    lib = json.loads(lib_path.read_text(encoding="utf-8"))
    print("library protocols", len(lib["protocols"]), "presets", len(lib["presets"]))

    from tools.router.injection_budget import HARD_CEILING_TOKENS, adversarial_k40, budget_inject, naive_inject
    from tools.router.tokenizer import char_quarter_estimate, count_tokens

    caps = adversarial_k40()
    naive = naive_inject(caps)
    budg = budget_inject(caps)
    print(
        "router ceiling", HARD_CEILING_TOKENS,
        "naive", naive.measured_tokens,
        "budgeted", budg.measured_tokens,
        "refused", len(budg.refused),
        "naive_overflow", naive.measured_tokens > HARD_CEILING_TOKENS,
        "neq_len4", naive.measured_tokens != char_quarter_estimate(naive.payload),
        "count_match", count_tokens(naive.payload) == naive.measured_tokens,
    )

    from tools.marketplace.permission_scan import both_states
    bs = both_states()
    print("perm both", {k: bs[k] for k in bs if k != "packages"})

    from tools.marketplace.moderation import run_full_cycle, FULL_CYCLE_EVENT_TYPES, ModerationQueue
    q = ModerationQueue()
    r = run_full_cycle(q)
    print("moderation types", q.cycle_event_types(r["report_id"]), "want", FULL_CYCLE_EVENT_TYPES)

    from tools.bench.gate import decide
    from tools.bench.margin import load_margin_table, PostHocMarginOverrideError
    from tools.bench.paired import paired_from_cases
    from tools.bench.scenarios import improvement_cases, noop_cases, underpowered_cases, secondary_regression_cases

    m = load_margin_table()
    print("keep", decide(paired_from_cases(improvement_cases(24), "c"), m)["outcome"])
    print("noop", decide(paired_from_cases(noop_cases(24), "c"), m)["reason_id"])
    print("under", decide(paired_from_cases(underpowered_cases(4), "c"), m)["outcome"])
    print("reg", decide(paired_from_cases(secondary_regression_cases(24), "c"), m)["reason_id"])
    try:
        load_margin_table(override=0.01)
        print("override NOT refused")
    except PostHocMarginOverrideError:
        print("override refused")

    sys.path.insert(0, str(REPO / "tools" / "workflow_foundry" / "tests"))
    from test_fusion_lineage import run_both_states_suite, run_rehearsal_suite

    rh = run_rehearsal_suite()
    bt = run_both_states_suite()
    print("wfa rehearse pass", rh["pass"], "n", rh["n_fusions"], "ops", rh["operators"])
    print("wfa both pass", bt["pass"], bt["both_states"])

    from tools.council.vote.consent import (
        MODE_CONSENT,
        MODE_VETO,
        OUT_CONSENTED,
        OUT_VETOED,
        RESP_CONSENT,
        RESP_VETO,
        SILENCE_IS_CONSENT,
        LATE_RECORD_AND_IGNORE,
        ConsentSession,
    )
    window = {"opens_at": 1000.0, "closes_at": 2000.0, "timezone": "UTC"}
    seats = [{"id": "alice", "veto_right": True}, {"id": "bob", "veto_right": False}, {"id": "cara", "veto_right": False}]
    veto = ConsentSession("p", MODE_VETO, SILENCE_IS_CONSENT, LATE_RECORD_AND_IGNORE, window, seats, "x")
    veto.respond("alice", RESP_VETO, 1500, "holder veto")
    print("veto", veto.close(2000)["outcome"], "want", OUT_VETOED)
    consent = ConsentSession("p", MODE_CONSENT, SILENCE_IS_CONSENT, LATE_RECORD_AND_IGNORE, window, seats, "x")
    consent.respond("alice", RESP_CONSENT, 1100, "explicit")
    print("consent", consent.close(2000)["outcome"], "want", OUT_CONSENTED)

    return 0


if __name__ == "__main__":
    # CNF extractors live in probe dir; skip if import fails
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("SMOKE-FAIL", type(exc).__name__, exc)
        raise
