#!/usr/bin/env python3
"""IMP-0082 probe1: primary cycle detector + publish-time refusal (source).

Exercises the real implementation (tools/marketplace/dependency.py):
self / two-node / four-node cycles reported with exact closed path; acyclic
diamond silent; publish stage refuses; install_order only runs post-gate;
the deliberately-recursive walker is the RecursionError dead control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from marketplace.dependency import (  # noqa: E402
    DependencyCycleError,
    check_at_publish,
    detect_cycles,
    graph_from_document,
    install_order,
    naive_recursive_walk,
    publish_verdict,
)
from marketplace import cycle_cases as CC  # noqa: E402

RESULTS: dict = {"probe": "probe1-publish-cycle-gate", "unit_id": "IMP-0082"}
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILS.append(f"{name}: {detail}")


# 1. Exact closed paths.
g_self = graph_from_document(CC.self_cycle())
got_self = [list(c.path) for c in detect_cycles(g_self)]
check("self-cycle exact path", got_self == CC.EXPECTED_SELF, str(got_self))

g_two = graph_from_document(CC.two_node_cycle())
got_two = [list(c.path) for c in detect_cycles(g_two)]
check("two-node exact path", got_two == CC.EXPECTED_TWO, str(got_two))

g_long = graph_from_document(CC.long_cycle())
got_long = [list(c.path) for c in detect_cycles(g_long)]
check("four-node exact path", got_long == CC.EXPECTED_LONG, str(got_long))

# 2. Acyclic diamond silent.
g_diamond = graph_from_document(CC.diamond())
check("diamond silent", detect_cycles(g_diamond) == [], str(detect_cycles(g_diamond)))

# 3. Publish-stage refusal with exact path in the error.
try:
    check_at_publish(g_two)
    check("publish refuses", False, "no raise")
except DependencyCycleError as exc:
    check("publish refuses", "a -> b -> a" in str(exc) and exc.stage == "publish", str(exc))

# 4. publish_verdict object form.
pv = publish_verdict(g_two)
check("publish_verdict ok=False", pv["ok"] is False and pv["stage"] == "publish", str(pv))
pv_ok = publish_verdict(g_diamond)
check("publish_verdict ok=True diamond", pv_ok["ok"] is True, str(pv_ok))

# 5. install_order works post-gate; raises on cyclic.
order = install_order(g_diamond)
check("install_order diamond", sorted(order) == ["bottom", "left", "right", "top"], str(order))
try:
    install_order(g_two)
    check("install_order raises cyclic", False, "no raise")
except DependencyCycleError as exc:
    check("install_order raises cyclic", exc.stage == "install", str(exc))

# 6. Dead control: naive recursion blows up where the detector does not.
try:
    sys.setrecursionlimit(400)
    naive_recursive_walk(g_two, "a")
    naive_walk_died = False
except RecursionError:
    naive_walk_died = True
finally:
    sys.setrecursionlimit(1000)
check("naive walker RecursionError", naive_walk_died, "walker survived")

# 7. Kind classification carries ranges and is preserved under classify().
doc = {
    "packages": {
        "root": {
            "version": "1.0.0",
            "dependencies": {
                "required": {"lib": "^2.0.0"},
                "optional": {"extras": "~1.1.0"},
                "peer": {"host": ">=3.0.0"},
                "dev": {"pytest": "*"},
            },
        },
        "lib": {"version": "2.1.0", "dependencies": {}},
        "extras": {"version": "1.1.2", "dependencies": {}},
        "host": {"version": "3.2.0", "dependencies": {}},
        "pytest": {"version": "8.0.0", "dependencies": {}},
    }
}
cls = graph_from_document(doc).classify()
check("kind classification",
      cls["required"] == [("root", "lib", "^2.0.0")]
      and cls["optional"] == [("root", "extras", "~1.1.0")]
      and cls["peer"] == [("root", "host", ">=3.0.0")]
      and cls["dev"] == [("root", "pytest", "*")],
      str(cls))

RESULTS.update({
    "cases": {
        "self": got_self, "two": got_two, "long": got_long,
        "diamond_cycles": [], "install_order_diamond": order,
    },
    "naive_walk_died": naive_walk_died,
    "publish_verdict": pv,
    "pass": not FAILS,
    "failures": FAILS,
})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0082-probe1 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0082-probe1 exact cycle paths, publish-stage refusal, install order")
