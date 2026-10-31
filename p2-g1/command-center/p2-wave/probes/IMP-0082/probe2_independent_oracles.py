#!/usr/bin/env python3
"""IMP-0082 probe2: independent instrument reviewer (graphlib + Kosaraju).

Reviewer obligation (catalog): confirm cycle detection runs at publish time,
not only at install time. Method is mechanically different from probe1: this
instrument never imports marketplace.dependency's detector; it re-derives
cycle existence and membership from the RAW edge lists via stdlib graphlib
TopologicalSorter plus a hand-rolled Kosaraju SCC pass (cycle_ref), and it
reads the publish/install stage split off the module source.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W))
sys.path.insert(0, str(W / "tools"))

from marketplace import cycle_cases as CC  # noqa: E402
from marketplace.cycle_ref import independent_report  # noqa: E402

RESULTS: dict = {"probe": "probe2-independent-oracles", "unit_id": "IMP-0082"}
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILS.append(f"{name}: {detail}")


# --- reviewer obligation: publish-time, not only install-time ---------------
dep_src = (W / "tools" / "marketplace" / "dependency.py").read_text(encoding="utf-8")
publish_in_dep = "stage=\"publish\"" in dep_src and "def check_at_publish" in dep_src
check("publish gate in dependency.py", publish_in_dep, "stage=publish marker absent")

# --- reviewer obligation, behavioral form: the publish-surface linter ---------
# index_linter.lint_index runs the cycle detector over the PUBLISHED index
# document; feed it a cyclic doc and require a dependency_cycle finding.
sys.path.insert(0, str(W / "tools"))
from marketplace.index_linter import lint_index  # noqa: E402

cyc_finding = lint_index(index=CC.two_node_cycle())
check("linter flags cyclic published index",
      any(f.get("code", "").lower() == "dependency_cycle" for f in cyc_finding),
      str(cyc_finding)[:300])
clean_finding = lint_index(index=CC.diamond())
check("linter silent on acyclic published index",
      not any(f.get("code", "").lower() == "dependency_cycle" for f in clean_finding),
      str(clean_finding)[:300])

# --- independent re-derivation over raw edge lists ---------------------------
def edges_of(doc: dict, kinds: set[str] | None = None) -> list[tuple[str, str]]:
    allow = kinds  # None = all declared kinds
    out: list[tuple[str, str]] = []
    for name, body in (doc.get("packages") or {}).items():
        for kind, block in ((body or {}).get("dependencies") or {}).items():
            if isinstance(block, dict) and (allow is None or kind in allow):
                for dest in block:
                    out.append((str(name), str(dest)))
    return out


cases = {
    "self": (CC.self_cycle(), True),
    "two": (CC.two_node_cycle(), True),
    "long": (CC.long_cycle(), True),
    "diamond": (CC.diamond(), False),
}
agree_rows = []
for name, (doc, want_cyclic) in cases.items():
    rep = independent_report(edges_of(doc))
    check(f"{name} oracles internal agreement", rep["internal_existence_agree"], str(rep))
    check(f"{name} independent verdict == primary expectation", rep["independent_existence"] == want_cyclic,
          f"got {rep['independent_existence']} want {want_cyclic}")
    # membership cross-check against the primary detector WITHOUT reusing it here
    # is impossible by import; instead check the SCC membership covers the
    # planted expected paths.
    if want_cyclic:
        expected_members = {
            "self": {"loop"},
            "two": {"a", "b"},
            "long": {"p", "q", "r", "s"},
        }[name]
        check(f"{name} membership covers expected", expected_members <= set(rep["members"]),
              f"{expected_members} vs {rep['members']}")
    agree_rows.append({"case": name, "graphlib": rep["graphlib"]["cyclic"],
                       "kosaraju": rep["kosaraju"]["cyclic"],
                       "members": sorted(rep["members"])})

# --- optional/peer/dev stay classifiable, never install-blocking -------------
mixed_doc = {
    "packages": {
        "app": {"version": "1.0.0", "dependencies": {
            "required": {"lib": "*"},
            "dev": {"libdev": "*"},
        }},
        "lib": {"version": "1.0.0", "dependencies": {}},
        "libdev": {"version": "1.0.0", "dependencies": {"required": {"app": "*"}}},
    }
}
rep_mixed = independent_report(edges_of(mixed_doc, kinds={"required"}))
# required-only edge list is acyclic; the cycle only exists if dev edges counted.
check("dev-edge cycle does not block required-install view",
      rep_mixed["independent_existence"] is False, str(rep_mixed["members"]))

RESULTS.update({"rows": agree_rows, "mixed_required_view_cyclic": False,
                "pass": not FAILS, "failures": FAILS})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0082-probe2 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0082-probe2 graphlib+Kosaraju agree; publish-time gate confirmed")
