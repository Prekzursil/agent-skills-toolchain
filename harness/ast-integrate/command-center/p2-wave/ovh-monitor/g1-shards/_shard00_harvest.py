#!/usr/bin/env python3
"""Find harvest copies of missing shard-00 files."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
PULLS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
WANT = [
    "command-center/p2-wave/probes/ADV-0059/probe1.py",
    "command-center/p2-wave/probes/ADV-0059/probe1_drift.py",
    "command-center/p2-wave/probes/ADV-0059/probe2.py",
    "command-center/p2-wave/probes/ADV-0059/engine.py",
    "command-center/p2-wave/probes/ADV-0059/emit_artifact.py",
    "release/platforms/windows/launch_adapter.py",
    "release/platforms/windows/Launch-Adapter.ps1",
    "tools/marketplace/pr_only_guard.py",
    "tools/marketplace/publishing.py",
    "tools/marketplace/release_mode.py",
    "tools/blueprint_library/compiler.py",
    "tools/blueprint_library/delegate.py",
    "tools/blueprint_library/inventory.py",
    "tools/blueprint_library/registry.py",
    "tools/council/participants/memory.py",
    "tools/selfimprove/writeback.py",
    "tools/lib/completion_reducer.py",
    "command-center/lib/completion_reducer.py",
    "tools/headroom_guard/guard.py",
    "tools/mcp_process_guard/guard.py",
    "tools/package_hygiene.py",
    "tools/council/integrity/dupes.py",
    "tools/agentspec-js/parity/run.py",
    "tools/monitorcore/monitorcore/cockpit.py",
    "command-center/schema/artifact.schema.json",
    "tools/plugin/json_codec.py",
]


def find(rel: str) -> list[str]:
    hits = []
    for root in PULLS:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    hits.append(str(cand))
    return hits


def main() -> None:
    for rel in WANT:
        live = REPO / rel
        hits = find(rel)
        print(
            f"{'Y' if live.is_file() else 'N'} live={live.stat().st_size if live.is_file() else 0:7d} "
            f"harvest={len(hits):2d} {rel}"
        )
        for h in hits[:3]:
            print("   ", h, Path(h).stat().st_size)


if __name__ == "__main__":
    main()
