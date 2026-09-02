#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
PULLS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "scw-pull",
]
NEED = [
    "tools/plugin/mcp_activation.py",
    "tools/plugin/tests/test_eol_policy.py",
    "tools/plugin/eol_assert.py",
    "tools/agentspec/agentspec/source_policy.py",
    "tools/agentspec/agentspec/strict_parse.py",
    "tools/agentspec/agentspec/artifact_cache.py",
    "tools/agentspec/agentspec/research.py",
    "tools/agentspec/agentspec/import_generic_dag.py",
    "tools/workflow/fusion_rollback.py",
    "tools/council/determinism.py",
    "tools/council/topology/tournament.py",
    "tools/council/stopping/deadlock.py",
    "tools/council/decompose.py",
    "tools/council/protocol/ngt.py",
    "synthesis/report_writer.py",
    "detector_control/enumerate.py",
    "detector_control/gate.py",
    "tools/lib/owner_approval.py",
    "command-center/adapters/codex.py",
    "adapters/codex.py",
    "tools/marketplace/tests/fixtures/declared-mixed.json",
    "command-center/p2-wave/probes/ADV-0013/probe1_old_token_occurrences.py",
    "command-center/p2-wave/probes/ADV-0013/probe2_rename_commit_differential.py",
    "command-center/p2-wave/probes/ADV-0013/identifier_drift_detector.py",
    "command-center/p2-wave/probes/ADV-0065/probe1_chain_effective.py",
    "command-center/p2-wave/probes/ADV-0065/probe2_install_disclosure.py",
    "command-center/p2-wave/probes/ADV-0065/probe1_effective_permissions.py",
]


def is_stub(text: str) -> bool:
    return "# g1-surface: generated" in text or "# g1-mod: real-surface" in text or "class _NS:" in text[:2000]


def main() -> None:
    hits = 0
    for rel in NEED:
        found = []
        for root in PULLS:
            if not root.is_dir():
                continue
            for box in root.iterdir():
                if not box.is_dir():
                    continue
                for sub in ("delta", "tree"):
                    cand = box / sub / rel
                    if cand.is_file() and cand.stat().st_size > 0:
                        text = cand.read_text(encoding="utf-8", errors="replace")[:4000]
                        stub = is_stub(text)
                        found.append((cand.stat().st_size, stub, f"{root.name}/{box.name}/{sub}"))
        live = REPO / rel
        live_sz = live.stat().st_size if live.is_file() else 0
        live_stub = is_stub(live.read_text(encoding="utf-8", errors="replace")[:4000]) if live.is_file() else True
        if found:
            found.sort(reverse=True)
            print(f"HIT {rel} live={live_sz} stub={live_stub} harvest={found[:3]}")
            hits += 1
        else:
            print(f"MISS {rel} live={live_sz} stub={live_stub}")
    print("hits", hits)


if __name__ == "__main__":
    main()
