"""Reconstructed registry join index for WFA-0021.

The 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux
worktree. Membership here is against a reconstructed token index derived
from catalog citations and WFA-0042 inspect of that file (n=284,
sha256 4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a),
never against a live read of the Windows path.

Join key (content-hash trap, named here because a naive join on filename
or a token inside a candidate *name* is the same class of false hit):
  membership is an exact match of a mechanism's declared aliases against
  reconstructed family tokens. Substring hits inside candidate names
  (e.g. "codex" inside wf-saved-codex-auth-research-fanout) are recorded
  as NAME-COLLISION-NOT-MEMBERSHIP and do not count as representation.
"""
from __future__ import annotations

from typing import Any

UPSTREAM_SHA256 = (
    "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
)
UPSTREAM_N = 284
UPSTREAM_PATHS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]

# Family tokens from WFA-0042/_inspect_source_out.json json_family_counts.
# Exact tokens only — "agent" is NOT an alias of "agent-teams".
FAMILIES: list[dict[str, Any]] = [
    {
        "id": "A-saved-workflow",
        "n": 10,
        "tokens": ["saved-workflow", "a-saved-workflow"],
    },
    {
        "id": "B-repo-workflow",
        "n": 4,
        "tokens": ["repo-workflow", "b-repo-workflow"],
    },
    {
        "id": "C-repo-tool",
        "n": 25,
        "tokens": ["repo-tool", "c-repo-tool"],
    },
    {
        "id": "D-harness-runtime",
        "n": 6,
        "tokens": ["harness-runtime", "d-harness-runtime"],
    },
    {
        "id": "E-agent",
        "n": 19,
        "tokens": ["e-agent"],
    },
    {
        "id": "F-plugin",
        "n": 21,
        "tokens": ["plugin", "plugins", "f-plugin"],
    },
    {
        "id": "G-skill",
        "n": 96,
        "tokens": ["skill", "skills", "g-skill"],
    },
    {
        "id": "H-executed-corpus",
        "n": 72,
        "tokens": ["executed-corpus", "h-executed-corpus"],
    },
    {
        "id": "I-command",
        "n": 31,
        "tokens": ["command", "commands", "i-command", "slash-command"],
    },
]

CANDIDATE_NAME_SAMPLES = [
    "wf-saved-agentic-repair-reliability",
    "wf-saved-bc-stage-compendium-enrichment",
    "wf-saved-codex-auth-research-fanout",
    "cmd-start-task",
    "cmd-orchestrate",
    "cmd-multi-workflow",
    "cmd-multi-plan",
    "cmd-multi-execute",
    "cmd-multi-frontend",
    "cmd-multi-backend",
    "cmd-review-design",
]

PROVENANCE = (
    "command-center/p2-wave/probes/WFA-0042/_inspect_source_out.json "
    "plus WORK-UNIT-CATALOG.json citations of G-skill n=96 / F-plugin n=21"
)


def token_set() -> dict[str, str]:
    out: dict[str, str] = {}
    for fam in FAMILIES:
        for tok in fam["tokens"]:
            out[tok] = fam["id"]
    return out


def join_mechanism(aliases: list[str]) -> dict[str, Any]:
    """Exact alias-to-token join. Substring-in-name is a collision, not a hit.

    Content-hash trap: matching the string "codex" or "workflow" inside a
    candidate filename/id is the same failure as hashing a path instead of
    content — the identifier looks related and is not the mechanism.
    """
    tokens = token_set()
    alias_l = [a.lower() for a in aliases]
    hits = []
    for alias in alias_l:
        fam = tokens.get(alias)
        if fam:
            hits.append({"alias": alias, "family": fam})
    collisions = []
    for name in CANDIDATE_NAME_SAMPLES:
        nl = name.lower()
        for alias in alias_l:
            if alias in nl and tokens.get(alias) is None:
                collisions.append({"alias": alias, "candidate_name": name})
    if hits:
        return {
            "membership": "REPRESENTED-IN-RECONSTRUCTED-INDEX",
            "hits": hits,
            "name_collisions": collisions,
            "vs_284_row": "UNDETERMINED-FILE-ABSENT",
        }
    if collisions:
        return {
            "membership": "NAME-COLLISION-NOT-MEMBERSHIP",
            "hits": [],
            "name_collisions": collisions,
            "vs_284_row": "UNDETERMINED-FILE-ABSENT",
        }
    return {
        "membership": "ABSENT-FROM-RECONSTRUCTED-INDEX",
        "hits": [],
        "name_collisions": [],
        "vs_284_row": "UNDETERMINED-FILE-ABSENT",
    }


def upstream_block() -> dict[str, Any]:
    return {
        "present": False,
        "last_known_n": UPSTREAM_N,
        "last_known_sha256": UPSTREAM_SHA256,
        "expected_paths": UPSTREAM_PATHS,
        "reconstruction_provenance": PROVENANCE,
        "note": (
            "The 284-row Windows registry is not on this worktree. "
            "Membership claims are against the reconstructed token index, "
            "not a live 284-row read."
        ),
    }
