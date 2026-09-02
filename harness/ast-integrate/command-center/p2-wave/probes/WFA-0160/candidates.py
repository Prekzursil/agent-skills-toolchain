"""Measurable 284-row candidate array for the floor recount.

The Windows 08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this worktree
(WFA-0007 inspect recorded record_count=284 against that absent file).
This module builds a 284-row array whose family histogram matches
WFA-0042/_inspect_source_out.json json_family_counts, seeds harvested ids
from WFA-0007/WFA-0034, and embeds one in-array renamed copy so the
discount is not a no-op.

Rows are labeled reconstruction vs harvested. This is not a claim the live
284-row registry was present.
"""
from __future__ import annotations

from typing import Any

# Family totals from WFA-0042/_inspect_source_out.json json_family_counts,
# which inspected the live 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json
# (source_sha256 4791c7a6..., 261589 bytes). That file is not on this tree;
# the histogram is. Do not invent a different B/C/D/E split.
FAMILY_TARGETS: dict[str, int] = {
    "A-saved-workflow": 10,
    "B-repo-workflow": 4,
    "C-repo-tool": 25,
    "D-harness-runtime": 6,
    "E-agent": 19,
    "F-plugin": 21,
    "G-skill": 96,
    "H-executed-corpus": 72,
    "I-command": 31,
}

HARVESTED: list[dict[str, Any]] = [
    {
        "id": "wf-saved-agentic-repair-reliability",
        "name": "agentic-repair-reliability.js",
        "family": "A-saved-workflow",
        "does": "agentic repair reliability loop with retries and a stop gate",
        "mechanisms": ["repair-loop", "reliability-gate", "stop-rule"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
        "source_class": "prior-artifacts",
        "classification": "ADOPT-AS-IS",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0007/_inspect_source_out.json:sample[0]",
    },
    {
        "id": "wf-saved-bc-stage-compendium-enrichment",
        "name": "bc-stage-compendium-enrichment.js",
        "family": "A-saved-workflow",
        "does": "enrich a stage compendium from numbered Prompt One corpus files",
        "mechanisms": ["corpus-extract", "stage-enrich", "anchor-verify"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
        "source_class": "prior-artifacts",
        "classification": "DISTILL",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0007/_inspect_source_out.json:sample[1]",
    },
    {
        "id": "wf-saved-codex-auth-research-fanout",
        "name": "codex-auth-research-fanout.mjs",
        "family": "A-saved-workflow",
        "does": "fan out Codex auth research probes across independent vendors",
        "mechanisms": ["fan-out", "vendor-split", "join-barrier"],
        "origin": "harvest:WFA-0007-inspect-sample",
        "row_kind": "harvested",
        "source_class": "prior-artifacts",
        "classification": "ADOPT-WITH-WRAPPER",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0007/_inspect_source_out.json:sample[2]",
    },
    {
        "id": "wf-ext-live-active",
        "name": "live-active-workflow",
        "family": "B-repo-workflow",
        "does": "externally sourced live GitHub workflow used as a maintenance control",
        "mechanisms": ["github-fetch", "maintenance-probe"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "github-code-search",
        "classification": "ADOPT-AS-IS",
        "license": "MIT",
        "runtime": "node",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
    {
        "id": "wf-ext-archived-adopt",
        "name": "archived-upstream",
        "family": "C-repo-tool",
        "does": "archived upstream tool kept as adopt-as-is risk control",
        "mechanisms": ["archive-flag", "adopt-as-is-risk"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "github-code-search",
        "classification": "ADOPT-AS-IS",
        "license": "MIT",
        "runtime": "python",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
    {
        "id": "wf-ext-unreachable",
        "name": "gone-host",
        "family": "G-skill",
        "does": "unreachable external host used as not-checked control",
        "mechanisms": ["not-checked", "no-prose-inference"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "github-code-search",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "license": "UNKNOWN",
        "runtime": "unknown",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
    {
        "id": "wf-ext-stale-api",
        "name": "api-lag",
        "family": "F-plugin",
        "does": "plugin whose API last-push lags git HEAD on purpose",
        "mechanisms": ["api-vs-git-head", "freshness-divergence"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "github-code-search",
        "classification": "ADOPT-WITH-WRAPPER",
        "license": "Apache-2.0",
        "runtime": "node",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
    {
        "id": "wf-ext-prose-archived-wrong",
        "name": "prose-says-archived",
        "family": "E-agent",
        "does": "agent whose prose claims archived while HEAD is live",
        "mechanisms": ["prose-vs-measured", "contradiction-flag"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "github-code-search",
        "classification": "RETIRE",
        "license": "MIT",
        "runtime": "unknown",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
    {
        "id": "wf-local-only",
        "name": "local-only-workflow",
        "family": "A-saved-workflow",
        "does": "local saved workflow with no external origin",
        "mechanisms": ["local-only", "no-github"],
        "origin": "harvest:WFA-0034-fixture",
        "row_kind": "harvested",
        "source_class": "prior-artifacts",
        "classification": "ADOPT-AS-IS",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0034/fixtures/registry.json",
    },
]

# In-array trivial fork of the first harvested row (still inside n=284).
IN_ARRAY_FORK: dict[str, Any] = {
    "id": "wf-saved-agentic-repair-reliability-copy",
    "name": "agentic-repair-reliability copy.js",
    "family": "A-saved-workflow",
    "does": "agentic repair reliability loop with retries and a stop gate",
    "mechanisms": ["repair-loop", "reliability-gate", "stop-rule"],
    "origin": "reconstruction:in-array-trivial-fork",
    "row_kind": "trivial-fork",
    "source_class": "prior-artifacts",
    "classification": "ADOPT-AS-IS",
    "license": "UNKNOWN",
    "runtime": "javascript",
    "provenance": "planted-inside-reconstructed-284",
    "fork_of": "wf-saved-agentic-repair-reliability",
}

PLANT_RENAME_ID = "wf-saved-bc-stage-compendium-enrichment-copy"
PLANT_DISTINCT_ID = "wf-plant-genuinely-distinct-sibling"


def plant_renamed_copy() -> dict[str, Any]:
    """Obvious renamed copy of wf-saved-bc-stage-compendium-enrichment."""
    return {
        "id": PLANT_RENAME_ID,
        "name": "bc-stage-compendium-enrichment copy.js",
        "family": "A-saved-workflow",
        "does": "enrich a stage compendium from numbered Prompt One corpus files",
        "mechanisms": ["corpus-extract", "stage-enrich", "anchor-verify"],
        "origin": "probe-plant:renamed-copy",
        "row_kind": "planted-renamed-copy",
        "source_class": "prior-artifacts",
        "classification": "DISTILL",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0160-probe1",
        "fork_of": "wf-saved-bc-stage-compendium-enrichment",
    }


def plant_distinct() -> dict[str, Any]:
    """Similar naming, different mechanism — must survive discount."""
    return {
        "id": PLANT_DISTINCT_ID,
        "name": "bc-stage-plasma-lattice-scheduler.js",
        "family": "A-saved-workflow",
        "does": "schedule plasma lattice cooldown windows with a quorum barrier",
        "mechanisms": ["plasma-lattice", "cooldown-window", "quorum-barrier"],
        "origin": "probe-plant:genuinely-distinct",
        "row_kind": "planted-distinct",
        "source_class": "prior-artifacts",
        "classification": "DISTILL",
        "license": "UNKNOWN",
        "runtime": "javascript",
        "provenance": "WFA-0160-probe1",
    }


def _fill_row(family: str, seq: int) -> dict[str, Any]:
    slug = family.split("-", 1)[1]
    return {
        "id": f"wf-recon-{slug}-{seq:03d}",
        "name": f"recon-{slug}-{seq:03d}.js",
        "family": family,
        "does": (
            f"reconstructed {family} slot {seq} with unique stage "
            f"sequence {seq} and a distinct stop predicate"
        ),
        "mechanisms": [f"{slug}-core", f"slot-{seq:03d}", "unique-stop"],
        "origin": "reconstruction:family-histogram-fill",
        "row_kind": "reconstruction-fill",
        "source_class": "reconstruction-unattributed",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "license": "UNKNOWN",
        "runtime": "unknown",
        "provenance": "WFA-0160-candidates.build_array",
    }


def build_array() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {k: 0 for k in FAMILY_TARGETS}
    for h in HARVESTED:
        rows.append(dict(h))
        counts[h["family"]] += 1
    # Occupy one A-saved-workflow slot with the in-array fork.
    rows.append(dict(IN_ARRAY_FORK))
    counts[IN_ARRAY_FORK["family"]] += 1
    for family, target in FAMILY_TARGETS.items():
        seq = 1
        while counts[family] < target:
            rows.append(_fill_row(family, seq))
            counts[family] += 1
            seq += 1
    if len(rows) != 284:
        raise RuntimeError(f"reconstructed array length {len(rows)} != 284")
    if sum(FAMILY_TARGETS.values()) != 284:
        raise RuntimeError("FAMILY_TARGETS do not sum to 284")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate ids in reconstructed array")
    return rows


def family_histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[str(r["family"])] = out.get(str(r["family"]), 0) + 1
    return dict(sorted(out.items()))
