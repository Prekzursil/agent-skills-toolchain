#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
cands = [
    "marketplace/installer.py",
    "marketplace/permission_catalog.py",
    "marketplace/permission_surface.py",
    "marketplace/evidence_lint.py",
    "plugin/permission_enforcement.py",
    "tools/agentspec/agentspec/research.py",
    "tools/agentspec/agentspec/source_policy.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/import_generic_dag.py",
    "tools/agentspec/agentspec/strict_parse.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/workflow/fusion_rollback.py",
    "tools/council/determinism.py",
    "tools/council/topology/tournament.py",
    "tools/council/stopping/deadlock.py",
    "tools/council/protocol.py",
    "tools/council/protocol/ngt.py",
    "tools/router/embed_model.py",
    "tools/router/lexical.py",
    "tools/router/semantic_matcher.py",
    "adapters/codex.py",
    "detector_control/enumerate.py",
    "detector_control/gate.py",
    "synthesis/report_writer.py",
    "council/determinism.py",
    "council/protocol.py",
    "council/protocol/ngt.py",
    "council/simulate.py",
    "plugin/__init__.py",
    "marketplace/__init__.py",
    "router/embed_model.py",
    "router/lexical.py",
    "router/semantic_matcher.py",
    "adapters/__init__.py",
    "platform/marketplace/mkt/install.py",
]
print("REPO", REPO)
for rel in cands:
    p = REPO / rel
    print(f"{'Y' if p.is_file() else 'N'} {rel}")
# also package dirs
for d in [
    "marketplace",
    "plugin",
    "router",
    "adapters",
    "council",
    "detector_control",
    "synthesis",
    "tools/agentspec/agentspec",
    "tools/council",
    "tools/workflow",
    "tools/router",
    "tools/lib",
    "platform/marketplace",
]:
    p = REPO / d
    print(f"DIR {'Y' if p.is_dir() else 'N'} {d}")
    if p.is_dir():
        names = sorted(x.name for x in p.iterdir())[:30]
        print("  ", names)
