"""Defines the "full test suite" (catalog `inputs`) for this pass.

Reuses the exact scope AUD-0052 measured for the same repo state: a bare
repo-root `pytest --collect-only` throws an INTERNALERROR (a stray
`sys.exit(1)` at import time in agent-self/config/hooks/memory-guard/test_scan.py)
and separately raises `ModuleNotFoundError` / `FileNotFoundError` collecting two
non-hermetic salvage trees under command-center/ssot/salvaged-at-risk and the
AUD-0043 scratch-build fixtures (which intentionally break `pip install`, not
pytest collection, but sit under a path pytest still tries to import). Scoping to
`command-center/` with those two paths ignored is the largest slice this pass
collects CLEANLY (0 collection errors) -- 138 tests before this unit's own two
ground-truth fixtures are added (140 with them). The rest of the repo (tools/,
platform/, skills/, etc.) is carried forward as a residual, not silently
dropped -- see this unit's `residual_unknowns`.
"""

from __future__ import annotations

TARGET_ARGS: list[str] = [
    "command-center/",
    "--ignore=command-center/ssot/salvaged-at-risk",
    "--ignore=command-center/p2-wave/probes/AUD-0043/fixtures",
]

REPO_ROOT_COLLECTION_ERRORS = [
    "agent-self/config/hooks/memory-guard/test_scan.py: bare sys.exit(1) at "
    "import time crashes pytest's own collector (INTERNALERROR), not a test result",
    "command-center/ssot/salvaged-at-risk/b5-toolchain/tools/mcp-manager/tests/"
    "test_health.py: ModuleNotFoundError: No module named 'core.models'",
    "command-center/ssot/salvaged-at-risk/wt-salvage-probe/ci/tests/"
    "test_codex_profiles.py: FileNotFoundError on mcp-manifest.json",
    "command-center/p2-wave/probes/AUD-0043/fixtures/scratch_pkg_good/tests/"
    "test_scratch.py: ModuleNotFoundError: No module named 'helper_mod' "
    "(deliberately broken by AUD-0043's own both-states control fixture)",
]
