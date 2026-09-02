#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
WAVE = REPO / "command-center" / "p2-wave"


def is_stub(path: Path) -> bool:
    head = path.read_text(encoding="utf-8", errors="replace")[:900]
    return "g1-surface: generated" in head or "class _NS:" in head


def harvest_real(rel: str) -> list[str]:
    hits = []
    mon = WAVE / "ovh-monitor"
    for kind in ("delivery-pull", "missing-pull", "error-pull"):
        root = mon / kind
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 40:
                    head = cand.read_text(encoding="utf-8", errors="replace")[:200]
                    if "g1-surface: generated" in head or "class _NS:" in head:
                        continue
                    hits.append(f"{kind}/{box.name}/{sub} bytes={cand.stat().st_size}")
    return hits


rels = [
    "tools/plugin/install.py",
    "tools/plugin/payload.py",
    "tools/plugin/placement.py",
    "tools/plugin/errors.py",
    "tools/plugin/rollback_additive.py",
    "tools/marketplace/handoff.py",
    "tools/marketplace/blob_store.py",
    "tools/marketplace/index.py",
    "tools/marketplace/name_linter.py",
    "marketplace/handoff.py",
    "plugin/install.py",
    "plugin/payload.py",
    "workflow_foundry/trust_tier.py",
    "tools/router/index_build.py",
    "tools/router/inject.py",
    "tools/council/stopping/evidence_saturation.py",
    "bench/environment_record.py",
    "tools/bench/ledger.py",
    "council/builder.py",
    "command-center/p2-wave/probes/ADV-0086/probe1_abba.py",
    "command-center/p2-wave/probes/ADV-0086/probe2_host_counters.py",
    "command-center/p2-wave/probes/ADV-0086/probe_timing.py",
    "tools/plugin/payload_allowlist.py",
    "docs/layout-migration.md",
    "tools/marketplace/tests/test_compat_resolution.py",
    "tools/agentspec/tests/test_workunit_routing.py",
]

print("LIVE STUB?")
for rel in rels:
    p = REPO / rel
    if not p.is_file():
        print(f"MISSING {rel}")
        continue
    print(f"{'STUB' if is_stub(p) else 'REAL'} {rel} bytes={p.stat().st_size}")

print("\nHARVEST REAL COPIES")
for rel in rels:
    hits = harvest_real(rel)
    if hits:
        print(rel)
        for h in hits[:5]:
            print("  ", h)
