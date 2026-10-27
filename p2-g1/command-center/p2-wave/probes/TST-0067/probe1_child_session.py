#!/usr/bin/env python3
"""TST-0067 probe1: test_child_process_observes_the_new_value_in_the_same_session.

Session-hit: NEW placed in the child env at spawn is observed by the child
on both independent signals while the parent environment stays unchanged.
Persistent-miss: a NEW written to the persistent store is visible to the
setter's self-read and INVISIBLE to a child spawned from the same session
(the recorded false-green: setter self-agreement is not evidence).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0067.json"


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    constants = receipt.get("constants") or {}
    check("constants-match-receipt",
          harness.ENV_KEY == constants.get("ENV_KEY")
          and harness.OLD == constants.get("OLD")
          and harness.NEW == constants.get("NEW"),
          {"live": [harness.ENV_KEY, harness.OLD, harness.NEW],
           "recorded": [constants.get("ENV_KEY"), constants.get("OLD"),
                        constants.get("NEW")]})

    parent_before = os.environ.get(harness.ENV_KEY)
    child = harness.observe_env_child({harness.ENV_KEY: harness.NEW})
    parent_after = os.environ.get(harness.ENV_KEY)
    check("test_child_process_observes_the_new_value_in_the_same_session",
          child.get("userspace") == harness.NEW
          and child.get("signal_2") == harness.NEW
          and child.get("signals_agree") is True,
          {"pid": child.get("consumer_pid"), "userspace": child.get("userspace"),
           "signal_2": child.get("signal_2"),
           "signals_agree": child.get("signals_agree")})
    check("parent-environment-not-mutated",
          parent_before == parent_after,
          {"before": parent_before, "after": parent_after})

    with tempfile.TemporaryDirectory(prefix="tst0067-") as tmp:
        tmp = Path(tmp)
        store = harness.PersistentStore(tmp / "persistent-store.json")
        store.write(harness.ENV_KEY, harness.NEW)
        setter_self_read = store.self_read(harness.ENV_KEY)
        miss_child = harness.observe_env_child()  # spawned from THIS session
        check("persistent-write-misses-session-child",
              setter_self_read == harness.NEW
              and miss_child.get("userspace") != harness.NEW
              and miss_child.get("signal_2") != harness.NEW,
              {"setter_self_read": setter_self_read,
               "child_userspace": miss_child.get("userspace"),
               "child_signal_2": miss_child.get("signal_2"),
               "child_pid": miss_child.get("consumer_pid")})
        check("setter-self-agreement-false-green-recorded",
              setter_self_read == harness.NEW
              and miss_child.get("userspace") is None,
              "setter sees NEW while the session child sees unset")
        check("two-signals-agree-on-the-miss",
              miss_child.get("signals_agree") is True,
              {"userspace": miss_child.get("userspace"),
               "signal_2": miss_child.get("signal_2")})

    pairs = receipt.get("consumer_observation_pairs") or {}
    check("receipt-session-hit-recorded-shape",
          (pairs.get("session_hit") or {}).get("consumer_userspace") == harness.NEW
          and (pairs.get("session_hit") or {}).get("parent_os_environ_unchanged") is True,
          {k: (pairs.get("session_hit") or {}).get(k)
           for k in ["consumer_userspace", "parent_os_environ_unchanged"]})
    platform = receipt.get("platform") or {}
    check("platform-divergence-disclosed",
          platform.get("system") == "Linux",
          {"receipt_platform": platform.get("system"),
           "this_run": os.name,
           "note": "second signal is /proc environ on the receipt run, "
                   "kernel32 GetEnvironmentVariableW on this Windows re-run"})

    out = {"probe": "probe1-child-session", "unit_id": "TST-0067",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
