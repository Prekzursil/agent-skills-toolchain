#!/usr/bin/env python3
"""Emit WFA-0078-candidate-registry-v2.json and the schema-pack subset."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import registry_lib as L  # noqa: E402


def main() -> int:
    artifact = L.emit()
    a = artifact["arithmetic"]
    print(
        f"records={a['v2_count']} v1={a['v1_count']} "
        f"add={a['additions']} col={a['collapses']} "
        f"diffs={len(artifact['field_diff'])} "
        f"kind={artifact['honesty']['worktree_v1_kind']}"
    )
    print(L.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
