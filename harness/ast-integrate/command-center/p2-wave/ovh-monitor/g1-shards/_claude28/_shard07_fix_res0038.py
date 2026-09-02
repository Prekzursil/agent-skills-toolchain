#!/usr/bin/env python3
"""Restore RES-0038 tests + reviewer blocks destroyed by the envelope rewrite.

Both blocks are copied verbatim from the unit's own emitter
(command-center/p2-wave/probes/RES-0038/emit_research.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shard07_lib as L

ART = "command-center/research/RES-0038.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0038/probe1_recompute_signal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0038/probe2_signal_table.py"
)

doc = L.load(ART)

doc["tests"] = [
    {
        "id": "T1-recompute-mcpName-and-dns",
        "name": "Recompute npm mcpName from pinned captures; live DNS TXT; both-states mutants",
        "command": P1,
        "result": "PASS",
    },
    {
        "id": "T2-signal-table-split-and-two-rails",
        "name": "Signal table split, two-rail claims, display-only cannot claim recompute",
        "command": P2,
        "result": "PASS",
    },
]

doc["reviewer"] = {
    "reviewer_id": "RES-0038-probe2-signal-table-scope",
    "verdict": "PASS",
    "independent": True,
    "scope_not_agreement": True,
    "method": (
        "probe2 re-reads the artifact, checks the class split, refuses "
        "display-only rows that claim end-to-end recompute, and kills "
        "a confirmed claim reduced to one rail."
    ),
    "note": (
        "Catalog asked for a security reviewer constructing a bypass of "
        "every mitigation. G-1 for this unit is the named probes. A "
        "human bypass review of GitHub OAuth/OIDC is independent of "
        "probe-green and is recorded as NOT-CHECKED below."
    ),
}

L.save(ART, doc)
L.refresh_manifest("RES-0038", [ART])
print("RES-0038 restored tests(2) + original reviewer block")
