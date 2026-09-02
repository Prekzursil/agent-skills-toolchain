"""47 seeded failure classes: reconstructed, with an honest ABSENT-source flag.

The catalog cites _USER-PROMPTS.md:11300-11347. That file is not on this
worktree. These 47 names are reconstructed from catalog tokens and the
four fail-open classes this unit actually exercises. The independent
reviewer MUST NOT certify the enumeration complete against the original
47; the source lines are not here to certify against.
"""
from __future__ import annotations

SEEDED_47: tuple[str, ...] = (
    "detector-failure",
    "overclaim",
    "green-not-live",
    "single-signal-verification",
    "uncontrolled-silence",
    "silent-in-both-states",
    "mutation-survives",
    "stale-evidence",
    "stale-cache",
    "version-skew",
    "spec-drift",
    "docs-code-divergence",
    "capability-loss",
    "data-loss",
    "partial-artifact",
    "provenance-loss",
    "duplicate-control-plane",
    "duplicate-collapse-error",
    "index-corruption",
    "measured-nothing",
    "false-pass",
    "false-coverage",
    "fixture-invalid",
    "environment-drift",
    "platform-gap",
    "supply-chain",
    "secret-in-artifact",
    "signature-bypass",
    "prompt-injection",
    "win-arg-limit",
    "severed-stream",
    "timeout",
    "schema-invalid",
    "use-vs-mention",
    "gameable-metric",
    "unfalsifiable-metric",
    "calibration-failure",
    "irreproducible-claim",
    "scope-drift",
    "packaging-gap",
    "stale-premise",
    "source-unavailable",
    "permission-escalation",
    "sandbox-escape",
    "groupthink",
    "synthesis-distortion",
    "fail-open-control",
)

assert len(SEEDED_47) == 47
assert len(set(SEEDED_47)) == 47

SOURCE_STATUS = "ABSENT"
SOURCE_CITATION = (
    "command-center/WORK-UNIT-CATALOG.json ARC-0047.inputs cites "
    "_USER-PROMPTS.md:11300-11347; that file is not on this worktree"
)
