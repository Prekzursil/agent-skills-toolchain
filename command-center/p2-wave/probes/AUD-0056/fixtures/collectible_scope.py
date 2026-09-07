"""Defines the collectible test set for AUD-0056 runtime profiling.

Same largest clean `command-center/` slice as AUD-0052 (0 collection errors),
plus the AUD-0056 deliberately-slow ground-truth fixture. Two salvage/scratch
trees that break collection are ignored; AUD-0052's planted order-dependent
and flaky fixtures are also ignored so nondeterministic outcomes do not
contaminate a wall-clock baseline. tools/, platform/, skills/, and the
ignored trees remain residuals -- not silently dropped.
"""

from __future__ import annotations

TARGET_ARGS: list[str] = [
    "command-center/",
    "--ignore=command-center/ssot/salvaged-at-risk",
    "--ignore=command-center/p2-wave/probes/AUD-0043/fixtures",
    "--ignore=command-center/p2-wave/probes/AUD-0052/fixtures/order_dependent",
    "--ignore=command-center/p2-wave/probes/AUD-0052/fixtures/flaky",
]

REPO_ROOT_COLLECTION_ERRORS = [
    "agent-self/config/hooks/memory-guard/test_scan.py: bare sys.exit(1) at "
    "import time crashes pytest's own collector (INTERNALERROR), not a test result",
    "command-center/ssot/salvaged-at-risk/: ModuleNotFoundError / FileNotFoundError "
    "in salvaged trees (same exclusions as AUD-0052)",
    "command-center/p2-wave/probes/AUD-0043/fixtures/: deliberately broken "
    "scratch packages for AUD-0043 both-states control",
]

IGNORED_FOR_BASELINE_STABILITY = [
    "command-center/p2-wave/probes/AUD-0052/fixtures/order_dependent/: "
    "planted order-dependent pair; FAIL under some collection orders",
    "command-center/p2-wave/probes/AUD-0052/fixtures/flaky/: "
    "planted OS-entropy flaky test; nondeterministic call duration and outcome",
]
