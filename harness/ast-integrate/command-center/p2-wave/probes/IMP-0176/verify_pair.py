#!/usr/bin/env python3
"""Independent verifier: planted conflicts fire; look-alike trees stay silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detect as D  # noqa: E402

doc = json.loads((HERE / "fixtures" / "components.json").read_text(encoding="utf-8"))
idx = {c["id"]: c for c in doc["components"]}
conflict = D.detect_pair(idx["stop-unanimity-required"], idx["stop-unanimity-forbidden"])
lookalike = D.detect_pair(
    idx["lookalike-prose-unanimity-egress"], idx["lookalike-prose-forbid-airgap"]
)
print(f"conflict={conflict['conflict']} lookalike={lookalike['conflict']}")
if not conflict["conflict"] or lookalike["conflict"]:
    print("FAILED:IMP-0176-verify-pair")
    raise SystemExit(1)
print("SUCCESS:IMP-0176-verify-pair")
