#!/usr/bin/env python3
from __future__ import annotations

import tarfile
from pathlib import Path

PULL = Path(__file__).resolve().parent.parent / "delivery-pull"
needles = (
    "ADV-0087/probe1_blind.py",
    "ADV-0087/experiment.py",
    "ADV-0087/emit_artifact.py",
    "ADV-0087/fixtures.json",
    "tools/plugin/interpreter_probe.py",
    "flagship_e2e_contract/registry.py",
    "tools/lib/net_allowlist.py",
)
tgzs = sorted(PULL.glob("*/p2-leftover-delta.tgz")) + sorted(PULL.glob("*/p2-delivery.tgz"))
print(f"archives={len(tgzs)}")
for tgz in tgzs:
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            names = tf.getnames()
    except Exception as exc:
        print(f"FAIL {tgz.parent.name}: {exc}")
        continue
    hits = [n for n in names if any(s in n.replace("\\", "/") for s in needles)]
    print(f"{tgz.parent.name} {tgz.name} n={len(names)} hits={len(hits)}")
    for h in hits[:20]:
        print(f"  {h}")
