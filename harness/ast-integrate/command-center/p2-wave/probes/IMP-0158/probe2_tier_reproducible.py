#!/usr/bin/env python3
"""Probe 2: tier assignment is reproducible across two runs with no clock.

Independent of probe 1: re-derives assignments in two subprocesses, injects
two clocks, and AST-checks production functions for wall-clock calls.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from load_lib import ensure_import  # noqa: E402

ensure_import()

CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
from fixtures import load_json, twin_pair
from workflow_foundry.trust_tier import admit_candidate, assign_trust_tier
clock = sys.argv[3]
candidate, unknown, first_party = twin_pair()
rows = {
  "clock": clock,
  "unknown": assign_trust_tier(candidate, unknown, clock=clock).as_dict(),
  "first_party": assign_trust_tier(candidate, first_party, clock=clock).as_dict(),
  "vendor": assign_trust_tier(load_json("candidate-vendor.json"), load_json("evidence-vendor.json"), clock=clock).as_dict(),
  "community": assign_trust_tier(load_json("candidate-community.json"), load_json("evidence-community.json"), clock=clock).as_dict(),
  "contradiction": assign_trust_tier(candidate, load_json("evidence-contradiction.json"), clock=clock).as_dict(),
  "admit_unknown": admit_candidate(candidate, unknown, clock=clock).as_dict(),
  "admit_first_party": admit_candidate(candidate, first_party, clock=clock).as_dict(),
}
print(json.dumps(rows, sort_keys=True, separators=(",", ":")))
"""


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0158-probe2 {msg}")
    return 1


def run_child(clock: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            CHILD,
            str(REPO / "tools"),
            str(HERE),
            clock,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"child rc={proc.returncode} stderr={proc.stderr[-1500:]}"
        )
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def strip_clock(doc: dict) -> dict:
    out = dict(doc)
    out.pop("clock", None)
    return out


def canonical(doc: dict) -> str:
    return json.dumps(strip_clock(doc), sort_keys=True, separators=(",", ":"))


def production_has_wall_clock() -> list[str]:
    src = (REPO / "tools" / "workflow_foundry" / "trust_tier.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    banned = {"now", "utcnow", "today", "time", "monotonic", "time_ns"}
    hits: list[str] = []
    wanted = {"assign_trust_tier", "admit_candidate"}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in wanted:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name) and func.id in banned:
                    hits.append(f"{node.name}:{func.id}()")
                if isinstance(func, ast.Attribute) and func.attr in banned:
                    hits.append(f"{node.name}:*.{func.attr}()")
    return hits


def main() -> int:
    clock_a = "1970-01-01T00:00:00Z"
    clock_b = "2099-12-31T23:59:59Z"
    run1 = run_child(clock_a)
    run2 = run_child(clock_a)
    run3 = run_child(clock_b)

    c1 = canonical(run1)
    c2 = canonical(run2)
    c3 = canonical(run3)
    if c1 != c2:
        return fail("two runs at the same injected clock diverged")
    if c1 != c3:
        return fail("injected clocks changed assignment (clock dependency)")
    if run1.get("clock") == run3.get("clock"):
        return fail("child did not receive distinct injected clocks")

    if run1["unknown"]["tier"] != "unknown":
        return fail("unknown fixture not unknown in subprocess")
    if run1["first_party"]["tier"] != "first-party":
        return fail("first-party fixture not first-party in subprocess")
    if run1["admit_unknown"]["status"] != "REFUSED":
        return fail("unknown not refused in subprocess")
    if run1["admit_first_party"]["status"] != "AUTO_ADOPTED":
        return fail("first-party not auto-adopted in subprocess")
    if "clock" in json.dumps(run1["unknown"]):
        return fail("assignment dict retained a clock field")

    hits = production_has_wall_clock()
    if hits:
        return fail(f"wall-clock calls in production: {hits}")

    digest = hashlib.sha256(c1.encode("utf-8")).hexdigest()
    report = {
        "probe": "probe2-tier-reproducible",
        "unit_id": "IMP-0158",
        "runs": 3,
        "clocks": [clock_a, clock_b],
        "canonical_sha256": digest,
        "same_across_runs": True,
        "clock_independent": True,
        "no_wall_clock_calls": True,
        "unknown_tier": run1["unknown"]["tier"],
        "first_party_tier": run1["first_party"]["tier"],
        "vendor_tier": run1["vendor"]["tier"],
        "community_tier": run1["community"]["tier"],
        "contradiction_tier": run1["contradiction"]["tier"],
        "pass": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"two-run+clock canonical sha256={digest} "
        "unknown=unknown first-party=first-party"
    )
    print("SUCCESS:IMP-0158-probe2 tier assignment reproducible; no clock dependency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
