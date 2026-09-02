#!/usr/bin/env python3
"""IMP-0425 corpus + refuter runner. Importable by named probes and emit."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from fanin_receipt_gate import (  # noqa: E402
    DECISION_ACCEPT,
    DECISION_FAILED,
    ROLE_RECEIPT,
    ROLE_RESULT,
    admit_to_barrier,
    evaluate,
    naive_substring_decide,
)

HISTORICAL = [
    (
        "receipt-1-codex-background",
        HERE / "fixtures/historical/receipt-1-codex-background.txt",
        DECISION_FAILED,
        ROLE_RECEIPT,
    ),
    (
        "receipt-2-codex-job",
        HERE / "fixtures/historical/receipt-2-codex-job.json",
        DECISION_FAILED,
        ROLE_RECEIPT,
    ),
    (
        "receipt-3-job-id",
        HERE / "fixtures/historical/receipt-3-job-id.txt",
        DECISION_FAILED,
        ROLE_RECEIPT,
    ),
]
GENUINE = [
    (
        "genuine-1-discusses-background",
        HERE / "fixtures/genuine/genuine-1-discusses-background.json",
        DECISION_ACCEPT,
        ROLE_RESULT,
    ),
    (
        "genuine-2-quotes-status-phrase",
        HERE / "fixtures/genuine/genuine-2-quotes-status-phrase.md",
        DECISION_ACCEPT,
        ROLE_RESULT,
    ),
    (
        "genuine-3-analysis-of-receipts",
        HERE / "fixtures/genuine/genuine-3-analysis-of-receipts.json",
        DECISION_ACCEPT,
        ROLE_RESULT,
    ),
]
REFUTE_FP = (
    "false-positive-mention",
    HERE / "fixtures/refute/false-positive-mention.md",
    DECISION_ACCEPT,
    ROLE_RESULT,
)
REFUTE_FN = (
    "false-negative-receipt",
    HERE / "fixtures/refute/false-negative-receipt.txt",
    DECISION_FAILED,
    ROLE_RECEIPT,
)

ART = REPO / "command-center/receipts/IMP-0425.json"
SENTINEL = "SENTINEL:IMP-0425:RECEIPT-GATE-ROLE-AWARE"


def load_payload(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(raw)
    return raw


def row_for(cid: str, path: Path, want_decision: str, want_role: str) -> dict[str, Any]:
    payload = load_payload(path)
    decision = evaluate(payload)
    admission = admit_to_barrier(payload)
    naive = naive_substring_decide(payload)
    want_barrier = want_role == ROLE_RESULT
    ok = (
        decision.decision == want_decision
        and decision.role == want_role
        and decision.can_satisfy_barrier is want_barrier
        and admission["barrier_satisfied"] is want_barrier
        and admission["admitted"] is want_barrier
    )
    if want_role == ROLE_RECEIPT:
        ok = ok and admission["state"] == "FAILED"
    rel = path.relative_to(REPO).as_posix()
    return {
        "id": cid,
        "path": rel,
        "want_decision": want_decision,
        "want_role": want_role,
        "got_decision": decision.decision,
        "got_role": decision.role,
        "can_satisfy_barrier": decision.can_satisfy_barrier,
        "admitted": admission["admitted"],
        "barrier_satisfied": admission["barrier_satisfied"],
        "naive_decision": naive,
        "naive_would_fail_use_vs_mention": (
            want_role == ROLE_RESULT and naive == DECISION_FAILED
        ),
        "reason": decision.reason,
        "phrase_hits": [h.__dict__ for h in decision.phrase_hits],
        "ok": ok,
        "structured": decision.structured,
        "opener_is_receipt_speech": decision.opener_is_receipt_speech,
    }


def run_corpus() -> dict[str, Any]:
    historical = [row_for(*item) for item in HISTORICAL]
    genuine = [row_for(*item) for item in GENUINE]
    fp = row_for(*REFUTE_FP)
    fn = row_for(*REFUTE_FN)
    hist_ok = all(r["ok"] for r in historical) and len(historical) >= 3
    gen_ok = all(r["ok"] for r in genuine) and len(genuine) >= 3
    naive_foil = all(r["naive_would_fail_use_vs_mention"] for r in genuine)
    naive_foil = naive_foil and fp["naive_would_fail_use_vs_mention"]
    genuine_rejected = any(r["got_decision"] == DECISION_FAILED for r in genuine)
    use_vs_mention_ok = hist_ok and gen_ok and naive_foil and not genuine_rejected
    receipt_cannot_satisfy = all(
        r["can_satisfy_barrier"] is False and r["barrier_satisfied"] is False
        for r in historical + [fn]
    )
    return {
        "historical": historical,
        "genuine": genuine,
        "refute_false_positive": fp,
        "refute_false_negative": fn,
        "historical_all_rejected": hist_ok,
        "genuine_all_accepted": gen_ok,
        "naive_foil_rejects_genuine": naive_foil,
        "use_vs_mention_ok": use_vs_mention_ok,
        "receipt_cannot_satisfy_barrier": receipt_cannot_satisfy,
        "fp_accepted": fp["ok"] and fp["got_decision"] == DECISION_ACCEPT,
        "fn_rejected": fn["ok"] and fn["got_decision"] == DECISION_FAILED,
        "pass": (
            hist_ok
            and gen_ok
            and naive_foil
            and use_vs_mention_ok
            and receipt_cannot_satisfy
            and fp["ok"]
            and fn["ok"]
        ),
    }


def artifact_ok() -> tuple[bool, str]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return False, "artifact missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"unparseable:{exc}"
    if not isinstance(doc, dict):
        return False, "artifact not an object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{st}"
    if SENTINEL not in text:
        return False, "sentinel-absent"
    return True, "ok"


if __name__ == "__main__":
    report = run_corpus()
    print(f"pass={report['pass']}")
    for r in report["historical"] + report["genuine"]:
        print(f"{r['id']} ok={r['ok']} decision={r['got_decision']} role={r['got_role']}")
    raise SystemExit(0 if report["pass"] else 1)
