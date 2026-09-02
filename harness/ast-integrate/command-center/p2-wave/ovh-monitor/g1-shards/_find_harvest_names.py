#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
NAMES = [
    "wf.research.archival.json",
    "license_extract.py",
    "wrong_recipe_gate.py",
    "test_argv_only.py",
    "test_drift_classifier.py",
    "test_deployed_copy_guard.py",
    "blob.py",
    "error-taxonomy.json",
    "test_compat_diagnostics.py",
    "test_exit_codes.py",
    "planted_collisions.json",
    "test_index_schema.py",
    "test_dependency_graph.py",
    "declared-mixed.json",
    "imp0099_matrix.json",
    "test_permission_analysis.py",
    "explain.py",
    "test_workunit_routing.py",
    "replay_log.py",
    "role_extract.py",
    "artifact_cache.py",
    "select_expertise.py",
    "blind_first.py",
    "role_collapse.py",
    "load_semantics.py",
    "nofit.py",
    "presence_gap.py",
    "legal_gate.py",
    "both_states.py",
    "env_allowlist.py",
    "overhead.py",
    "layout-migration.md",
    "quickstart.md",
    "handled-ledger.schema.json",
    "rollback-contract.schema.json",
    "pinned-repo-origin.json",
    "claude_adapter.py",
    "lockfile.schema.json",
    "two_state.py",
]
# Search only a few known harvest boxes, one level of tree/delta then specific dirs.
ROOTS = []
for kind in ("delivery-pull", "missing-pull", "error-pull"):
    p = WAVE / "ovh-monitor" / kind
    if p.is_dir():
        ROOTS.append(p)


def walk_limited(root: Path, name: str, max_hits: int = 5) -> list[str]:
    hits: list[str] = []
    # Prefer exact expected rels first
    for box in root.iterdir():
        if not box.is_dir():
            continue
        for sub in ("tree", "delta", "extracted", "extracted-delta"):
            base = box / sub
            if not base.is_dir():
                continue
            # shallow name match in a few likely folders
            for folder in (
                base,
                base / "tools",
                base / "command-center",
                base / "docs",
                base / "blueprints",
                base / "tools" / "plugin",
                base / "tools" / "plugin" / "tests",
                base / "tools" / "marketplace",
                base / "tools" / "marketplace" / "tests",
                base / "tools" / "marketplace" / "fixtures",
                base / "tools" / "council",
                base / "tools" / "router",
                base / "tools" / "lib",
                base / "tools" / "bench",
                base / "tools" / "agentspec",
                base / "tools" / "workflow_foundry",
                base / "command-center" / "p2-wave" / "probes",
            ):
                if not folder.is_dir():
                    continue
                cand = folder / name
                if cand.is_file():
                    hits.append(str(cand))
                    if len(hits) >= max_hits:
                        return hits
    return hits


def main() -> None:
    for name in NAMES:
        all_hits = []
        for root in ROOTS:
            all_hits.extend(walk_limited(root, name))
        print(f"{name}\t{len(all_hits)}\t{all_hits[:2]}")


if __name__ == "__main__":
    main()
