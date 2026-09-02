#!/usr/bin/env python3
"""Probe 2: execute 12 data-only protocols + kernel-required negative control.

Independent of probe 1's printed census: re-derives extra primitives from
structural flags on each record, then:
  * executes EXECUTE_SAMPLE (12) end-to-end
  * asserts P52/P58 refuse (not flattened)
  * asserts a mutant expressible+forks_state is classified needs-kernel-change
  * asserts a brand-new record (P99) executes without editing kernel code
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.plugin import (  # noqa: E402
    EXECUTE_SAMPLE,
    KERNEL_PRIMITIVES,
    NeedsKernelChange,
    classify,
    execute,
    execute_sample,
    extra_primitives,
    load_protocols,
    refuse_kernel_required,
)

# Shadow mapping — must match plugin.STRUCTURAL_TO_PRIMITIVE, kept local so a
# plugin that drops structural detection disagrees with this probe.
SHADOW = {
    "forks_state": "state_fork",
    "nests_councils": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror_runtimes": "multi_runtime_mirror",
    "requires_owner": "human_gate",
}
SHADOW_COMPOSITION = {
    "fork": "state_fork",
    "nested": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror": "multi_runtime_mirror",
    "human_gate": "human_gate",
}


def shadow_extras(record: dict) -> set[str]:
    found: set[str] = set()
    for key, prim in SHADOW.items():
        if record.get(key):
            found.add(prim)
    comp = str(record.get("composition") or "linear")
    if comp in SHADOW_COMPOSITION:
        found.add(SHADOW_COMPOSITION[comp])
    for item in record.get("required_kernel_primitives") or []:
        name = str(item)
        if name and name not in KERNEL_PRIMITIVES:
            found.add(name)
    return found


def main() -> int:
    rows = load_protocols()
    disagreements = []
    for rec in rows:
        plugin_set = set(extra_primitives(rec))
        shadow_set = shadow_extras(rec)
        if plugin_set != shadow_set:
            disagreements.append((rec["id"], sorted(plugin_set), sorted(shadow_set)))
    if disagreements:
        print("FAILED:IMP-0297-probe2 shadow/plugin extra mismatch", disagreements[:5])
        return 1

    sample = execute_sample()
    if sample["n"] != 12 or sample["ids"] != list(EXECUTE_SAMPLE):
        print("FAILED:IMP-0297-probe2 sample roster", sample)
        return 1
    for run in sample["runs"]:
        if run["status"] != "expressible" or int(run["turns"]) < 1:
            print("FAILED:IMP-0297-probe2 sample run", run)
            return 1

    for pid in ("P52", "P58"):
        refusal = refuse_kernel_required(pid)
        if not refusal["refused"] or refusal.get("flattened"):
            print("FAILED:IMP-0297-probe2 silent degradation", pid, refusal)
            return 1
        rec = next(r for r in rows if r["id"] == pid)
        try:
            execute(rec)
            print("FAILED:IMP-0297-probe2 execute did not refuse", pid)
            return 1
        except NeedsKernelChange:
            pass

    mutant = copy.deepcopy(next(r for r in rows if r["id"] == "P02"))
    mutant["forks_state"] = True
    mut_c = classify(mutant)
    if mut_c.status != "needs-kernel-change" or "state_fork" not in mut_c.extra_primitives:
        print("FAILED:IMP-0297-probe2 mutant not caught", mut_c)
        return 1
    try:
        execute(mutant)
        print("FAILED:IMP-0297-probe2 mutant executed (silent degrade)")
        return 1
    except NeedsKernelChange:
        pass

    newbie = {
        "id": "P99",
        "slug": "three-beat-panel",
        "family": "DELIBERATIVE",
        "phases": [
            {
                "id": "open",
                "kind": "round_robin",
                "rounds": 1,
                "speaking_order": "round_robin",
                "obligations": [{"id": "hello", "discharge": "nonempty"}],
                "gates": [{"id": "spoke", "kind": "all_roles_spoke"}],
                "visibility": "all",
                "redact_speaker": False,
                "turn_length": 80,
            }
        ],
        "forks_state": False,
        "nests_councils": False,
        "hidden_parallel": False,
        "mirror_runtimes": False,
        "requires_owner": False,
        "composition": "linear",
        "required_kernel_primitives": [],
        "note": "appended at probe time; kernel.py not edited",
        "provenance": "IMP-0297-probe2",
    }
    if classify(newbie).status != "expressible":
        print("FAILED:IMP-0297-probe2 new record not expressible")
        return 1
    out = execute(newbie)
    if not out["ok"] or out["turns_executed"] < 1 or out["flattened"]:
        print("FAILED:IMP-0297-probe2 new record execute", out)
        return 1

    print(
        f"sample={sample['n']} turns={[r['turns'] for r in sample['runs']]} "
        "P52_refused=True P58_refused=True mutant_caught=True P99_appended=True"
    )
    print("SUCCESS:IMP-0297-probe2 execute-12 negative-control no-flatten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
