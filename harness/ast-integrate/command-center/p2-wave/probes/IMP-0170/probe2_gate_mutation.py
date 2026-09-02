#!/usr/bin/env python3
"""Probe 2: 20/20 single-gate mutations change the fingerprint.

Mutation of the hasher: drop topology from the fingerprint. Because gates
live on topology, the same 20/20 gate-mutation check must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fingerprint as F  # noqa: E402
import fixtures as X  # noqa: E402


def count_changed(*, include_topology: bool) -> tuple[int, list[dict]]:
    base_fp = F.fingerprint(X.BASE, include_topology=include_topology)
    rows = []
    changed = 0
    for name, mutant in X.gate_mutants():
        fp = F.fingerprint(mutant, include_topology=include_topology)
        diff = fp != base_fp
        changed += int(diff)
        rows.append({"name": name, "changed": diff, "sha256": fp})
    return changed, rows


def main() -> int:
    full_n, full_rows = count_changed(include_topology=True)
    drop_n, drop_rows = count_changed(include_topology=False)
    base_full = F.fingerprint(X.BASE, include_topology=True)
    base_drop = F.fingerprint(X.BASE, include_topology=False)
    gate_test_red_without_topology = drop_n != 20
    payload = {
        "base_sha256_full": base_full,
        "base_sha256_no_topology": base_drop,
        "full_changed": full_n,
        "no_topology_changed": drop_n,
        "gate_mutation_test_red_without_topology": gate_test_red_without_topology,
        "pass": full_n == 20 and gate_test_red_without_topology,
        "probe": "probe2-gate-mutation",
        "total": 20,
        "unit_id": "IMP-0170",
    }
    print(json.dumps(payload, sort_keys=True))
    for r in full_rows:
        print(f"gate {r['name']} changed={r['changed']}")
    print(
        f"topology-drop gate-mutation {drop_n}/20 "
        f"red={gate_test_red_without_topology}"
    )
    if full_n != 20:
        print(f"FAILED:IMP-0170-probe2 gate mutations {full_n}/20")
        return 1
    if not gate_test_red_without_topology:
        print("FAILED:IMP-0170-probe2 dropping topology did not redden gate-mutation")
        return 1
    if drop_n != 0:
        # Honest: gates must not leak into the non-topology components.
        print(f"FAILED:IMP-0170-probe2 gates leaked without topology ({drop_n}/20)")
        return 1
    print("SUCCESS:IMP-0170-probe2 20/20 gate mutations change fingerprint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
