"""Canonical closed mechanism vocabulary for WFA-0058.

Ids use MX-NNNN so they cannot collide with wf-* candidates, BP-*
blueprints, or M-NN option tokens (the measured M-NN clash class).
NEW-MECHANISM is the gap token, not a vocabulary id.
"""
from __future__ import annotations

from typing import Any

GAP = "NEW-MECHANISM"
VERSION = "1.0.0"
VOCABULARY_ID = "wfa-mechanism-vocabulary"
ID_PATTERN = r"^MX-[0-9]{4}$"
DISCRIMINATION_FLOOR = 0.90  # 18 of 20
ID_NAMESPACE = "MX-NNNN"

# Distinctive tokens used by the mapper; not shown to the blind reader.
MECHANISMS: tuple[dict[str, Any], ...] = (
    {
        "id": "MX-0001",
        "definition": (
            "A fail-closed completeness gate: an empty or deleted guarded "
            "block is a failure, never a vacuous pass."
        ),
        "discriminating_example": (
            "Deleting the entire defaults block of a catalog while "
            "require_complete defaults false and CI passes no flag: the "
            "gate must go red, unlike a completeness check that is silent "
            "when zero rows remain."
        ),
        "keys": (
            "fail-closed",
            "vacuous",
            "guarded",
            "deleted",
            "empty",
            "completeness",
        ),
        "aliases": (
            "fail-closed completeness gate",
            "empty guarded block is a failure not a pass",
            "deletion of the guarded defaults must turn CI red",
        ),
    },
    {
        "id": "MX-0002",
        "definition": (
            "Provenance hashing of committed git blobs so a CRLF working "
            "copy cannot change a digest verdict."
        ),
        "discriminating_example": (
            "git cat-file -p HEAD:path returns LF bytes on Windows and "
            "Linux; hashing the working tree under core.autocrlf=true does not."
        ),
        "keys": (
            "cat-file",
            "crlf",
            "autocrlf",
            "blob",
            "digest",
            "committed",
        ),
        "aliases": (
            "committed-blob provenance hashing",
            "git cat-file digest independent of autocrlf",
            "CRLF working copy must not change the blob hash",
        ),
    },
    {
        "id": "MX-0003",
        "definition": (
            "Closed identifier namespace: every cited token resolves to "
            "exactly one record in one vocabulary."
        ),
        "discriminating_example": (
            "The M-NN option-id collision versus MECH-NN architecture "
            "cards: one literal token, two records."
        ),
        "keys": (
            "namespace",
            "collision",
            "token",
            "identifier",
            "resolves",
            "m-nn",
        ),
        "aliases": (
            "closed identifier namespace",
            "one token must not name two records",
            "M-NN option versus architecture-card collision",
        ),
    },
    {
        "id": "MX-0004",
        "definition": (
            "Blind independent first pass: each reader scores from a "
            "private source partition and must not see the other reader's "
            "notes or warrants."
        ),
        "discriminating_example": (
            "Two reviewers receive disjoint file partitions and are "
            "forbidden from reading each other's transcripts before scoring."
        ),
        "keys": (
            "blind",
            "independent",
            "partition",
            "private",
            "first-pass",
            "disjoint",
        ),
        "aliases": (
            "blind independent first pass",
            "disjoint private partitions with no shared notes",
            "independent first pass without shared context",
        ),
    },
    {
        "id": "MX-0005",
        "definition": (
            "Shared-context deliberation: later judges read earlier "
            "judges' transcripts or a common channel before scoring, so "
            "agreement can be echo rather than independent evidence."
        ),
        "discriminating_example": (
            "The second judge is handed the first judge's full transcript "
            "before scoring the same item."
        ),
        "keys": (
            "shared-context",
            "deliberation",
            "transcript",
            "echo",
            "joint",
            "channel",
        ),
        "aliases": (
            "shared-context deliberation",
            "second judge reads the first judge's notes",
            "joint scoring over a common transcript",
        ),
    },
    {
        "id": "MX-0006",
        "definition": (
            "Deterministic replay: the same inputs plus a recorded seed "
            "must emit byte-identical artifacts on a second machine."
        ),
        "discriminating_example": (
            "Re-running the adapter with the recorded seed produces the "
            "same artifact bytes; any drift is a replay failure."
        ),
        "keys": (
            "deterministic",
            "replay",
            "seed",
            "byte-identical",
            "identical",
            "re-run",
        ),
        "aliases": (
            "deterministic replay",
            "same seed yields byte-identical artifacts",
            "recorded-seed replay on a second machine",
        ),
    },
    {
        "id": "MX-0007",
        "definition": (
            "Non-deterministic sampling: draws from a distribution "
            "(temperature, nucleus, or explicit RNG) so identical prompts "
            "need not yield identical completions."
        ),
        "discriminating_example": (
            "Raising temperature above zero yields different completions "
            "for one prompt across draws."
        ),
        "keys": (
            "sampling",
            "temperature",
            "stochastic",
            "distribution",
            "draw",
            "nucleus",
        ),
        "aliases": (
            "non-deterministic sampling",
            "temperature-above-zero diverse completions",
            "stochastic draws from a token distribution",
        ),
    },
    {
        "id": "MX-0008",
        "definition": (
            "Fire-and-forget dispatch: the parent spawns work and "
            "continues without joining; a background receipt is not a "
            "completion proof."
        ),
        "discriminating_example": (
            "The parent writes a background receipt and never waits for "
            "the child artifact; the join is discarded."
        ),
        "keys": (
            "fire-and-forget",
            "dispatch",
            "background",
            "spawn",
            "no-wait",
            "never-join",
        ),
        "aliases": (
            "fire-and-forget dispatch",
            "spawn workers and continue without joining",
            "background receipt without a join",
        ),
    },
    {
        "id": "MX-0009",
        "definition": (
            "Blocking fan-in barrier: the parent waits until every worker "
            "artifact exists and a shared reducer has judged the set."
        ),
        "discriminating_example": (
            "The parent blocks at a join until every worker file exists "
            "and the reducer runs; a missing artifact keeps the barrier red."
        ),
        "keys": (
            "fan-in",
            "barrier",
            "join",
            "blocking",
            "reducer",
            "wait",
        ),
        "aliases": (
            "blocking fan-in barrier",
            "parent waits for every worker artifact",
            "join barrier before the shared reducer",
        ),
    },
    {
        "id": "MX-0010",
        "definition": (
            "Use-versus-mention: an artifact that documents a mechanism "
            "is not credited with implementing it."
        ),
        "discriminating_example": (
            "A handbook that describes fan-in barriers is not an "
            "implementation of a barrier."
        ),
        "keys": (
            "mention",
            "documents",
            "credited",
            "implements",
            "handbook",
            "use-versus-mention",
        ),
        "aliases": (
            "use-versus-mention control",
            "documenting a mechanism is not implementing it",
            "handbook mention must not receive implementation credit",
        ),
    },
    {
        "id": "MX-0011",
        "definition": (
            "Source-anchor carriage: every IR node keeps its source "
            "anchor and licence class through translation, fusion, and "
            "rendering; an empty-string anchor is rejected as firmly as "
            "a missing one."
        ),
        "discriminating_example": (
            "Licence class stays attached to the IR node after fusion "
            "rewrites the tree; dropping the file:line anchor is a loss."
        ),
        "keys": (
            "anchor",
            "licence",
            "fusion",
            "translation",
            "rendering",
            "file:line",
        ),
        "aliases": (
            "source-anchor carriage through fusion",
            "licence class travels with the IR node",
            "empty-string source anchor is rejected",
        ),
    },
    {
        "id": "MX-0012",
        "definition": (
            "Mechanism-level exact-set deduplication: two artifacts with "
            "the same canonical id set are the same mechanism set; "
            "prose similarity is not the operation."
        ),
        "discriminating_example": (
            "Two candidates with identical MX id sets collapse even when "
            "their free-text descriptions are rewritten."
        ),
        "keys": (
            "exact-set",
            "deduplication",
            "vocabulary-id",
            "collapse",
            "canonical",
            "set-operation",
        ),
        "aliases": (
            "mechanism-level exact-set deduplication",
            "same MX id set collapses regardless of prose",
            "dedup is an exact set operation on vocabulary ids",
        ),
    },
)


def by_id() -> dict[str, dict[str, Any]]:
    return {str(m["id"]): m for m in MECHANISMS}


def vocab_ids() -> tuple[str, ...]:
    return tuple(str(m["id"]) for m in MECHANISMS)


def public_entries() -> list[dict[str, str]]:
    """Gate shape: id + definition + discriminating_example only."""
    rows = []
    for mech in MECHANISMS:
        rows.append(
            {
                "id": str(mech["id"]),
                "definition": str(mech["definition"]),
                "discriminating_example": str(mech["discriminating_example"]),
            }
        )
    return rows


def alias_index() -> dict[str, str]:
    out: dict[str, str] = {}
    for mech in MECHANISMS:
        mid = str(mech["id"])
        for alias in mech["aliases"]:
            key = " ".join(str(alias).lower().split())
            if key in out and out[key] != mid:
                raise RuntimeError(f"alias collision {alias!r}")
            out[key] = mid
    return out
