#!/usr/bin/env python3
"""Probe 2: the unit's own observed error (catalog signal b).

Does not treat event-log timestamp order as the pass criterion — that is
probe 1. This probe inspects the CallResult / CapabilityRevoked payload
the running unit observed, plus the Write marker bytes as a filesystem
check that the typed error was not a string-only denial.
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


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0228-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0228" not in text:
        print("FAILED:TST-0228-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:TST-0228-probe2 self-declared", doc.get("state"))
        return 1

    live = S.evaluate()
    live_row = live["live"]
    control = live["control"]
    raised = live["raised"]
    start_only = live["start_time_only"]
    one_more = live["one_more_call"]

    after = live_row.get("after") or {}
    err = after.get("observed_error") or {}
    exc = raised.get("observed_exception") or {}
    control_after = control.get("after") or {}
    start_after = start_only.get("after") or {}
    one_more_after = one_more.get("after") or {}
    rev = live_row.get("revoke_event") or {}

    summary = {
        "probe": "probe2-observed-error",
        "unit_id": "TST-0228",
        "observed_code": err.get("code"),
        "observed_tool": err.get("tool"),
        "observed_revocation_event_id": err.get("revocation_event_id"),
        "exception_type": exc.get("type"),
        "exception_code": exc.get("code"),
        "live_after_wrote": after.get("wrote"),
        "control_after_wrote": control_after.get("wrote"),
        "control_after_ok": control_after.get("ok"),
        "start_time_only_wrote": start_after.get("wrote"),
        "start_time_only_ok": start_after.get("ok"),
        "one_more_after_ok": one_more_after.get("ok"),
        "one_more_after_wrote": one_more_after.get("wrote"),
        "live_marker": live_row.get("marker_sha256"),
        "control_marker": control.get("marker_sha256"),
        "start_marker": start_only.get("marker_sha256"),
        "message_names_code": G.CODE_REVOKED in (after.get("message") or ""),
        "message_names_event": (rev.get("event_id") or "")
        in (after.get("message") or ""),
        "pass": False,
    }
    fails: list[str] = []
    if err.get("code") != G.CODE_REVOKED:
        fails.append(f"observed_error.code={err.get('code')}")
    if err.get("tool") != "Write":
        fails.append(f"observed_error.tool={err.get('tool')}")
    if not err.get("revocation_event_id"):
        fails.append("observed_error missing revocation_event_id")
    if err.get("revocation_event_id") != rev.get("event_id"):
        fails.append("observed_error revocation_event_id != revoke event")
    if G.CODE_REVOKED not in (after.get("message") or ""):
        fails.append("observed message does not name CAPABILITY_REVOKED")
    if (rev.get("event_id") or "") not in (after.get("message") or ""):
        fails.append("observed message does not name the revocation event id")
    if after.get("wrote"):
        fails.append("denied call still wrote the marker")
    if after.get("ok"):
        fails.append("denied call ok=true")

    if control_after.get("ok") is not True or not control_after.get("wrote"):
        fails.append("both-states: unreoked Write did not succeed with a write")
    if control.get("marker_sha256") is None:
        fails.append("both-states: control marker missing")
    if live_row.get("marker_sha256") == control.get("marker_sha256"):
        fails.append("live and control markers are identical; side effect not distinct")

    if start_after.get("ok") is not True or not start_after.get("wrote"):
        fails.append(
            "negative control: start-time-only did not keep writing after revoke"
        )
    if start_after.get("observed_error"):
        fails.append("start-time-only unexpectedly produced observed_error")
    if one_more_after.get("ok") is not True:
        fails.append(
            "mutation control: one-more-call did not allow the extra post-revoke write"
        )

    if exc.get("type") != "CapabilityRevoked":
        fails.append(f"exception type={exc.get('type')}")
    if exc.get("code") != G.CODE_REVOKED:
        fails.append(f"exception code={exc.get('code')}")
    if G.CODE_REVOKED not in (exc.get("message") or ""):
        fails.append("exception message does not name CAPABILITY_REVOKED")

    if not live["both_states"]:
        fails.append("both-states control failed")
    if not live["negative_control"]:
        fails.append("start-time-only negative control failed")
    if not live["mutation_control"]:
        fails.append("one-more-call mutation control failed")

    summary["pass"] = not fails
    print(json.dumps(summary, sort_keys=True))
    if fails:
        print("FAILED:TST-0228-probe2 " + "; ".join(fails))
        return 1
    print(
        f"observed {err.get('code')} event={err.get('revocation_event_id')} "
        f"wrote={after.get('wrote')} exception={exc.get('type')} "
        f"start_time_only_still_writes={start_after.get('wrote')}"
    )
    print("SUCCESS:TST-0228-probe2 unit observed CAPABILITY_REVOKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
