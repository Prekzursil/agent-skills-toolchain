#!/usr/bin/env python3
"""Probe 1: timestamped revocation event vs timestamped denial (catalog signal a).

Looks only at the event log / call sequence clocks. Does not treat the
unit-observed error dict as the pass criterion — that is probe 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0228.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact missing"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0228" not in text:
        return "sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared {st}"
    if doc.get("unit_id") != "TST-0228":
        return f"unit_id {doc.get('unit_id')}"
    return None


def clocks(row: dict) -> dict:
    rev = row.get("revoke_event") or {}
    after = row.get("after") or {}
    before = row.get("before") or {}
    return {
        "t_revoke_ns": rev.get("t_ns"),
        "t_deny_ns": after.get("t_ns"),
        "t_before_ns": before.get("t_ns"),
        "seq_before": before.get("seq"),
        "seq_after": after.get("seq"),
        "revocation_event_id": rev.get("event_id"),
        "deny_call_id": after.get("event_id"),
        "restart_count": row.get("restart_count"),
        "deny_ok": after.get("ok"),
        "deny_code": after.get("code"),
        "ordered": int(after.get("t_ns") or 0) > int(rev.get("t_ns") or 0) > 0,
        "next_seq": int(after.get("seq") or 0) == int(before.get("seq") or 0) + 1,
    }


def main() -> int:
    art_err = check_artifact()
    if art_err:
        print(f"FAILED:TST-0228-probe1 {art_err}")
        return 1

    live = S.evaluate()
    live_row = live["live"]
    control = live["control"]
    start_only = live["start_time_only"]
    live_clocks = clocks(live_row)
    control_clocks = clocks(control)
    start_clocks = clocks(start_only)
    pred = live["live_predicate"]

    summary = {
        "probe": "probe1-revocation-timeline",
        "unit_id": "TST-0228",
        "gate": live_row.get("gate"),
        "live_clocks": live_clocks,
        "control_after_ok": (control.get("after") or {}).get("ok"),
        "control_after_code": (control.get("after") or {}).get("code"),
        "start_time_only_after_ok": (start_only.get("after") or {}).get("ok"),
        "delta_ns": pred.get("delta_ns"),
        "within_one_call": pred.get("within_one_call"),
        "both_states": live["both_states"],
        "negative_control": live["negative_control"],
        "pass": False,
    }
    fails: list[str] = []
    if not live_clocks["ordered"]:
        fails.append(
            f"revoke/deny timestamps not ordered "
            f"revoke={live_clocks['t_revoke_ns']} deny={live_clocks['t_deny_ns']}"
        )
    if not live_clocks["next_seq"]:
        fails.append(
            f"deny seq {live_clocks['seq_after']} is not next call after "
            f"{live_clocks['seq_before']}"
        )
    if live_clocks["deny_ok"]:
        fails.append("event log shows post-revoke Write allowed")
    if live_clocks["deny_code"] != G.CODE_REVOKED:
        fails.append(f"deny event code={live_clocks['deny_code']}")
    rc = live_clocks["restart_count"]
    if rc is None or int(rc) != 0:
        fails.append("restart_count is not 0; denial was not mid-run")
    if not pred.get("within_one_call"):
        fails.append("predicate within_one_call is false")
    if control_clocks["deny_ok"] is not True:
        fails.append("both-states: unreoked Write did not succeed")
    if start_clocks["deny_ok"] is not True:
        fails.append(
            "negative control: start-time-only did not allow the post-revoke call"
        )
    if start_clocks["ordered"] and start_clocks["deny_code"] == G.CODE_REVOKED:
        fails.append("start-time-only unexpectedly denied (test would not discriminate)")
    if not live["both_states"]:
        fails.append("both-states control failed")
    if not live["negative_control"]:
        fails.append("start-time-only negative control failed")
    if not live["mutation_control"]:
        fails.append("one-more-call mutation control failed")

    summary["pass"] = not fails
    print(json.dumps(summary, sort_keys=True))
    if fails:
        print("FAILED:TST-0228-probe1 " + "; ".join(fails))
        return 1
    print(
        f"timeline revoke_ns={live_clocks['t_revoke_ns']} "
        f"deny_ns={live_clocks['t_deny_ns']} delta_ns={pred.get('delta_ns')} "
        f"seq {live_clocks['seq_before']}->{live_clocks['seq_after']} "
        f"restart_count=0"
    )
    print("SUCCESS:TST-0228-probe1 revocation timeline within one call")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
