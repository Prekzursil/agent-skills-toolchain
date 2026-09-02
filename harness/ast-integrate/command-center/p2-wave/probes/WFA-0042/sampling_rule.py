"""Sampling rule for the 20-record gold set — written before selection.

Rule (frozen as sampling_rule.version=1; later membership edits require a
GOLD_VERSION bump in dimensions.py):

  1. Population is live, non-empty files already on THIS Linux worktree.
     The Windows 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json is an honest
     absent input. Do not invent 284 registry rows.
  2. Cover all 9 catalog families A–I with at least one record each.
  3. n=20 exactly. Remaining slots after the 9-family floor follow the
     inspect histogram order without dropping a family:
       A:3  B:2  C:2  D:1  E:2  F:2  G:4  H:2  I:2
  4. Prefer files that other WFA extractors already cite (ARC-0016 hatch
     catalogs, CNF-0076 fusion pair, WFA-0154 recorded-runs, live skills,
     plugin manifests, slash commands) so the gold set scores extractors
     on the same trees they will read.
  5. Deterministic: the selected path list below is the sample. Runtime
     only checks that each path still exists and is non-empty. No glob
     reshuffle after freeze.
  6. The first five records (A×3, B×2) are the third-reader subset. That
     subset is frozen here, before labelling, not chosen after seeing
     kappa.

This module lists the sample. It does not label.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dimensions import FAMILIES, GOLD_VERSION, N_GOLD

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SAMPLING_RULE_VERSION = 1
SAMPLING_RULE = (
    "Before selection: live worktree files only; cover families A-I; n=20; "
    "quotas A3 B2 C2 D1 E2 F2 G4 H2 I2 matching inspect histogram order; "
    "third-reader n=5 is the first five records; freeze version=1; later "
    "membership edits require GOLD_VERSION bump. 284-row registry is not "
    "invented."
)

# Written after the rule above; membership is frozen with GOLD_VERSION.
SELECTED: tuple[tuple[str, str], ...] = (
    (
        "A-saved-workflow",
        "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/catalogs/workflows.json",
    ),
    (
        "A-saved-workflow",
        "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/catalogs/workflows.json",
    ),
    (
        "A-saved-workflow",
        "command-center/p2-wave/probes/IMP-0196/fixtures/subworkflow_mutual_wait.json",
    ),
    (
        "B-repo-workflow",
        "command-center/p2-wave/probes/CNF-0076/fixtures/fusion/wf.fused-index.json",
    ),
    (
        "B-repo-workflow",
        "command-center/p2-wave/probes/CNF-0076/fixtures/sources/wf.lex-normalize.json",
    ),
    ("C-repo-tool", "tools/marketplace/benchmark_evidence.py"),
    ("C-repo-tool", "tools/marketplace/permission_scan.py"),
    ("D-harness-runtime", "tools/wf-timeout/wf_gate.py"),
    ("E-agent", "AGENTS.md"),
    (
        "E-agent",
        "command-center/p2-wave/probes/WFA-0037/fixtures/corpus/11-COUNCIL-SPECIFICATION.md",
    ),
    ("F-plugin", ".claude-plugin/marketplace.json"),
    (
        "F-plugin",
        "command-center/p2-wave/probes/WFA-0018/fixtures/estate/home/.claude/plugins/"
        "marketplaces/lab/plugins/harness/.claude-plugin/plugin.json",
    ),
    ("G-skill", ".agents/skills/workflow-authoring/SKILL.md"),
    ("G-skill", ".agents/skills/owner-ops-authorization/SKILL.md"),
    ("G-skill", ".agents/skills/codex-orchestrate/SKILL.md"),
    ("G-skill", ".agents/skills/claim-verify-gate/SKILL.md"),
    (
        "H-executed-corpus",
        "command-center/p2-wave/probes/WFA-0154/fixtures/corpus/recorded-runs.json",
    ),
    (
        "H-executed-corpus",
        "command-center/p2-wave/probes/WFA-0154/fixtures/corpus/"
        "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    ),
    ("I-command", "commands/status.md"),
    ("I-command", "commands/prime.md"),
)

QUOTAS = {
    "A-saved-workflow": 3,
    "B-repo-workflow": 2,
    "C-repo-tool": 2,
    "D-harness-runtime": 1,
    "E-agent": 2,
    "F-plugin": 2,
    "G-skill": 4,
    "H-executed-corpus": 2,
    "I-command": 2,
}


def _assert_rule_invariants() -> None:
    if len(SELECTED) != N_GOLD:
        raise RuntimeError(f"sample n={len(SELECTED)} want {N_GOLD}")
    counts: dict[str, int] = {f: 0 for f in FAMILIES}
    seen_paths: set[str] = set()
    for family, rel in SELECTED:
        if family not in counts:
            raise RuntimeError(f"unknown family {family}")
        if rel in seen_paths:
            raise RuntimeError(f"duplicate path {rel}")
        seen_paths.add(rel)
        counts[family] += 1
    if counts != QUOTAS:
        raise RuntimeError(f"quota mismatch {counts} != {QUOTAS}")
    missing = [f for f in FAMILIES if counts[f] < 1]
    if missing:
        raise RuntimeError(f"family coverage missing {missing}")


_assert_rule_invariants()


def selected_rows() -> list[dict[str, Any]]:
    rows = []
    for i, (family, rel) in enumerate(SELECTED):
        rows.append(
            {
                "index": i,
                "family": family,
                "path": rel,
                "third_reader": i < 5,
                "candidate_id": f"{family}:{rel}",
            }
        )
    return rows


def load_selected(repo: Path | None = None) -> list[dict[str, Any]]:
    """Resolve the frozen sample against disk. Fail closed if a path vanished."""
    root = repo or REPO
    rows = []
    for spec in selected_rows():
        path = root / spec["path"]
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(
                f"frozen gold path missing or empty: {spec['path']}"
            )
        rec = dict(spec)
        rec["abs_path"] = path
        rows.append(rec)
    return rows


def sampling_meta() -> dict[str, Any]:
    return {
        "sampling_rule_version": SAMPLING_RULE_VERSION,
        "gold_version": GOLD_VERSION,
        "rule": SAMPLING_RULE,
        "n": N_GOLD,
        "quotas": dict(QUOTAS),
        "written_before_selection": True,
        "registry_284_invented": False,
        "third_reader_is_first_five": True,
    }
