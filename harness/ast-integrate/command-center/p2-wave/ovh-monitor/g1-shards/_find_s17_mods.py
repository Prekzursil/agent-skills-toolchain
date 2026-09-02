#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # ovh-monitor
NAMES = {
    "content_gate.py",
    "select_random.py",
    "operator_surface.py",
    "test_entry_parity.py",
    "malicious_plugin.py",
    "local_repo.py",
    "exclusion_set.json",
}
# also look under tools trees
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    if p.name not in NAMES and p.name not in {"store.py", "targets.py"}:
        continue
    if p.name in {"store.py", "targets.py"}:
        parent = p.parent.name
        if parent not in {"artifact_cache", "evidence_snapshot"}:
            continue
    sz = p.stat().st_size
    if sz < 200:
        continue
    print(sz, p)
