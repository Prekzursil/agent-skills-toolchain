#!/usr/bin/env python3
"""Probe 1: sandbox egress both-states, by actual network observation.

Enable telemetry (with a sandbox opt-in) and require the observer to see a
TCP/HTTP connection. Disable and require silence. A probe silent in both
states measures nothing. Configuration flags are not the evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import runtime as R  # noqa: E402
from clauses import CONTRACT_REL, EGRESS_RULE, OBSERVATION_RULE, SENTINEL  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0096-probe1 {msg}")
    return 1


def main() -> int:
    if not R.CONTRACT_PATH.is_file():
        return fail(f"contract missing {CONTRACT_REL}")
    text = R.CONTRACT_PATH.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent from contract")
    if EGRESS_RULE not in text:
        return fail("egress rule absent from contract")
    if OBSERVATION_RULE not in text:
        return fail("observation rule absent from contract")

    opt_in = R.load_decision_log(R.FIXTURES / "opt-in.json")
    none = R.load_decision_log(R.FIXTURES / "no-opt-in.json")
    revoked = R.load_decision_log(R.FIXTURES / "revoked.json")
    if R.opt_in_record(opt_in) is None:
        return fail("opt-in fixture did not parse as OPT-IN")
    if R.opt_in_record(none) is not None:
        return fail("empty log parsed as OPT-IN")
    if R.opt_in_record(revoked) is not None:
        return fail("revoked log parsed as OPT-IN")

    observer = R.SandboxObserver()
    counter = R.ConnectCounter()
    observer.start()
    counter.install()
    report: dict = {
        "probe": "probe1-egress",
        "unit_id": "ARC-0096",
        "observation_method": (
            "ThreadingHTTPServer.bind(127.0.0.1:ephemeral) accepted-POST count "
            "plus socket.socket.connect hook in this process. Not a config read."
        ),
        "observer_endpoint": observer.endpoint,
    }
    try:
        event = R.sample_event(probe_id="probe1")
        enabled = R.emit(
            event,
            R.policy(enabled=True, local_recording=False),
            opt_in,
            endpoint=observer.endpoint,
        )
        hits_on = len(observer.hits)
        connects_on = counter.count
        report["enabled"] = {
            "status": enabled.get("status"),
            "bytes_sent": enabled.get("bytes_sent"),
            "observer_hits": hits_on,
            "socket_connects": connects_on,
        }

        event2 = R.sample_event(probe_id="probe1")
        disabled = R.emit(
            event2,
            R.policy(enabled=False, local_recording=False),
            opt_in,
            endpoint=observer.endpoint,
        )
        hits_off = len(observer.hits)
        connects_off = counter.count
        report["disabled"] = {
            "status": disabled.get("status"),
            "bytes_sent": disabled.get("bytes_sent"),
            "observer_hits": hits_off,
            "socket_connects": connects_off,
            "new_hits": hits_off - hits_on,
            "new_connects": connects_off - connects_on,
        }

        event3 = R.sample_event(probe_id="probe1")
        no_opt = R.emit(
            event3,
            R.policy(enabled=True, local_recording=False),
            none,
            endpoint=observer.endpoint,
        )
        hits_no = len(observer.hits)
        connects_no = counter.count
        report["enabled_without_opt_in"] = {
            "status": no_opt.get("status"),
            "bytes_sent": no_opt.get("bytes_sent"),
            "new_hits": hits_no - hits_off,
            "new_connects": connects_no - connects_off,
        }

        event4 = R.sample_event(probe_id="probe1")
        rev = R.emit(
            event4,
            R.policy(enabled=True, local_recording=False),
            revoked,
            endpoint=observer.endpoint,
        )
        hits_rev = len(observer.hits)
        report["enabled_but_revoked"] = {
            "status": rev.get("status"),
            "new_hits": hits_rev - hits_no,
        }
    finally:
        counter.remove()
        observer.stop()

    print(json.dumps(report, indent=2, sort_keys=True))

    silent_both = hits_on == 0 and (hits_off - hits_on) == 0
    if silent_both:
        return fail("probe silent in both states; measures nothing")
    if enabled.get("status") != "EGRESSED":
        return fail(f"enable did not egress status={enabled.get('status')}")
    if hits_on < 1:
        return fail("observer saw no connection while telemetry enabled")
    if connects_on < 1:
        return fail("socket.connect hook silent while telemetry enabled")
    if disabled.get("status") != "DISABLED":
        return fail(f"disable status={disabled.get('status')}")
    if disabled.get("bytes_sent") != 0:
        return fail("disable still sent bytes")
    if (hits_off - hits_on) != 0:
        return fail("observer saw traffic while telemetry disabled")
    if (connects_off - connects_on) != 0:
        return fail("socket.connect fired while telemetry disabled")
    if no_opt.get("status") != "LOCAL-ONLY":
        return fail(f"missing opt-in status={no_opt.get('status')}")
    if (hits_no - hits_off) != 0:
        return fail("observer saw traffic without opt-in")
    if rev.get("status") != "LOCAL-ONLY":
        return fail(f"revoked status={rev.get('status')}")
    if (hits_rev - hits_no) != 0:
        return fail("observer saw traffic after OPT-OUT")
    if any(R.leak_scan(h.get("body") or "") for h in observer.hits):
        return fail("observer body contained a leak")

    print(
        f"enabled_hits={hits_on} disabled_new_hits=0 connects_on={connects_on} "
        f"method=HTTP-accept+socket.connect"
    )
    print("SUCCESS:ARC-0096-probe1 egress both-states by network observation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
