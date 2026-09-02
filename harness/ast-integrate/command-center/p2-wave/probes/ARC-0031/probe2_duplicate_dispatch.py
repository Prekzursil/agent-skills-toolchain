#!/usr/bin/env python3
"""Probe 2: duplicate-dispatch simulation.

Two dispatchers claim the same unit; exactly one must win. The winner is
the CLAIM record (dedupe_key + fencing_token + lease_until_ns) with the
lowest seq under fcntl.LOCK_EX compare-and-append.

Both-states:
  bad  — same unit_id, two threads → winners == 1
  good — two unit_ids → winners == 2
  skip — re-claim after COMPLETE → SKIP, not a second WON
  stale fencing cannot COMPLETE
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger as L  # noqa: E402
import runtime as R  # noqa: E402

DESIGN = REPO / "command-center/phase3/A5/DESIGN.json"


def _claim_pair(led: L.Ledger, unit_id: str) -> list[dict]:
    out: list[dict] = []
    lock = threading.Lock()

    def worker(dispatcher_id: str, substrate: str) -> None:
        result = led.claim(unit_id, dispatcher_id, substrate)
        with lock:
            out.append(result)

    t1 = threading.Thread(target=worker, args=("disp-local-a", "local"))
    t2 = threading.Thread(target=worker, args=("disp-cloud-b", "cloud"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return out


def main() -> int:
    if not R.reducer_identity_ok():
        print("FAILED:ARC-0031-probe2 shared reducer identity failed")
        return 1
    evaluate = R.load_shared_evaluate()
    if evaluate is not R.EVALUATE and evaluate.__code__.co_filename != R.EVALUATE.__code__.co_filename:
        print("FAILED:ARC-0031-probe2 dispatcher reducer is not the shared evaluate")
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0031-ledger-") as td:
        path = Path(td) / "ledger.jsonl"
        led = L.Ledger(path)
        led.enqueue(
            "U-DUP",
            unit_type="skill",
            substrate="local",
            idempotence_key="U-DUP:k",
        )
        pair = _claim_pair(led, "U-DUP")
        wins = [r for r in pair if r.get("result") == "WON"]
        losses = [r for r in pair if r.get("result") == "LOST"]
        print(
            f"same-unit results={[r.get('result') for r in pair]} "
            f"wins={len(wins)} losses={len(losses)}"
        )
        same_ok = len(pair) == 2 and len(wins) == 1 and len(losses) == 1
        if same_ok:
            winner = wins[0]["record"]
            loser = losses[0]["record"]
            same_ok = (
                winner.get("type") == "CLAIM"
                and winner.get("dedupe_key") == "U-DUP"
                and "fencing_token" in winner
                and "lease_until_ns" in winner
                and "claim_id" in winner
                and loser.get("type") == "CLAIM_DENIED"
                and loser.get("winner_seq") == winner.get("seq")
            )

        led.enqueue("U-A", unit_type="skill", substrate="local", idempotence_key="U-A:k")
        led.enqueue("U-B", unit_type="skill", substrate="worktree", idempotence_key="U-B:k")
        ra = led.claim("U-A", "disp-a", "local")
        rb = led.claim("U-B", "disp-b", "worktree")
        distinct_ok = ra.get("result") == "WON" and rb.get("result") == "WON"
        print(f"distinct-units a={ra.get('result')} b={rb.get('result')}")

        claim = wins[0]["record"]
        led.start("U-DUP", claim)
        receipt = {
            "state": "SUCCESS",
            "artifacts": [{"exists": True, "bytes": 256, "path": "x"}],
            "min_bytes_threshold": 128,
            "schema_valid": True,
            "sentinel": "SUCCESS:U-DUP",
            "evidence": [{"anchor": "ledger.jsonl", "claim": "claimed"}],
            "tests": [{"id": "t", "result": "PASS"}],
            "negative_controls": [
                {
                    "id": "nc",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                }
            ],
            "reviewer": {"verdict": "PASS", "independent": True},
            "defects": [],
            "manifest_registration": {"registered": True},
            "downstream_consumers": [
                {"consumer": "probe2", "executed": True, "read_ok": True}
            ],
        }
        verdict = evaluate(receipt)
        if verdict.get("verdict") != "PASS":
            print(f"FAILED:ARC-0031-probe2 reducer {verdict}")
            return 1
        complete = led.complete(
            "U-DUP",
            claim,
            reducer_verdict=verdict["verdict"],
            failing_condition_id=verdict.get("failing-condition-id"),
            artifact_sha256="a" * 64,
        )
        print(f"complete type={complete.get('type')} verdict={complete.get('reducer_verdict')}")
        third = led.claim("U-DUP", "disp-late", "local")
        skip_ok = third.get("result") == "SKIP"
        print(f"reclaim-after-complete result={third.get('result')}")

        stale = dict(claim)
        stale["claim_id"] = "forged"
        denied = led.complete(
            "U-DUP",
            stale,
            reducer_verdict="PASS",
            failing_condition_id=None,
            artifact_sha256="b" * 64,
        )
        stale_ok = denied.get("type") == "CLAIM_DENIED" and denied.get("reason") == "stale-fencing-token"
        print(f"stale-complete type={denied.get('type')} reason={denied.get('reason')}")

        ok_chain, why = led.verify_chain()
        print(f"chain_ok={ok_chain} {why}")

        # Vacuity: a unit that was never claimed must not look like a duplicate win.
        led.enqueue("U-SOLO", unit_type="skill", substrate="cloud", idempotence_key="U-SOLO:k")
        solo = led.claim("U-SOLO", "disp-solo", "cloud")
        vacuity_ok = solo.get("result") == "WON"
        print(f"solo-claim result={solo.get('result')}")

        fired_on_bad = same_ok
        silent_on_good = distinct_ok
        print(
            f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
            f"skip_ok={skip_ok} stale_ok={stale_ok} chain_ok={ok_chain} vacuity_ok={vacuity_ok}"
        )
        if not (
            fired_on_bad
            and silent_on_good
            and skip_ok
            and stale_ok
            and ok_chain
            and vacuity_ok
        ):
            print("FAILED:ARC-0031-probe2 duplicate-dispatch did not discriminate")
            return 1

    if DESIGN.is_file():
        doc = json.loads(DESIGN.read_text(encoding="utf-8"))
        report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
        schema = doc.get("ledger_schema") or report.get("ledger_schema") or {}
        named = " ".join(
            [
                str(schema),
                str(doc.get("delivery_guarantee") or report.get("delivery_guarantee") or {}),
                str(doc.get("claim_mechanism") or report.get("claim_mechanism") or {}),
            ]
        )
        for token in ("claim_id", "fencing_token", "lease_until_ns", "dedupe_key"):
            if token not in named and token not in json.dumps(doc):
                print(f"FAILED:ARC-0031-probe2 DESIGN does not name {token}")
                return 1
        claimed = str(
            (doc.get("delivery_guarantee") or report.get("delivery_guarantee") or {}).get(
                "claimed"
            )
            or ""
        )
        if "at-least-once" not in claimed.lower():
            print("FAILED:ARC-0031-probe2 DESIGN delivery guarantee is not at-least-once")
            return 1

    print("SUCCESS:ARC-0031-probe2 duplicate-dispatch exactly one winner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
