"""Anchoring-kind declarations for baseline snapshot fields (TST-0023).

Every top-level field of ``command-center/schema/baseline-snapshot.schema.json``
is either SHA-ANCHORED (recoverable from the git object database at
``pinned_sha``; identical on every recapture at that SHA) or SAMPLED-AT-TIME
(host/worktree state that must carry ``sampled_at``). The two tuples below are
the declaration of record; ``schema_anchoring_gaps`` checks the schema against
them and ``instance_sampled_timestamp_gaps`` checks a captured snapshot.
"""
from __future__ import annotations

import copy
from typing import Any

SHA_ANCHORED = "SHA-ANCHORED"
SAMPLED_AT_TIME = "SAMPLED-AT-TIME"
ANCHORING_KINDS: tuple[str, ...] = (SHA_ANCHORED, SAMPLED_AT_TIME)

# Facts read from git ls-tree / cat-file at pinned_sha. Working-tree bytes are never
# the oracle for these, so an untracked file or an extra branch cannot move them.
ANCHORED_FIELD_NAMES: tuple[str, ...] = (
    "pinned_sha",
    "tree_sha",
    "files",
    "repo",
    "hooks_tree",
    "skills_tree",
    "mcps_tree",
    "plugin_settings_tree",
    "marketplaces_tree",
)

# Facts that cannot be recovered from the commit: quiescence label, wall clock,
# refs, linked worktrees and worktree walks (which see untracked files).
SAMPLED_FIELD_NAMES: tuple[str, ...] = (
    "kind",
    "captured_at",
    "branches",
    "worktrees",
    "live_deployments",
    "caches",
    "plugin_settings_live",
    "marketplaces_live",
    "hooks_live",
    "skills_live",
    "mcps_live",
)

# Sampled scalars: declared SAMPLED-AT-TIME but not count objects, so they carry
# no sampled_at of their own (captured_at is the sample time for both).
SAMPLED_SCALARS: frozenset[str] = frozenset({"kind", "captured_at"})

# Schema keys that may carry the declaration, newest spelling first.
_DECLARATION_KEYS: tuple[str, ...] = ("x-anchoring", "x-anchoring-kind", "anchoring_kind")

__all__ = [
    "SHA_ANCHORED",
    "SAMPLED_AT_TIME",
    "ANCHORING_KINDS",
    "ANCHORED_FIELD_NAMES",
    "SAMPLED_FIELD_NAMES",
    "SAMPLED_SCALARS",
    "declared_kind",
    "expected_kind",
    "schema_anchoring_gaps",
    "instance_sampled_timestamp_gaps",
    "anchored_projection",
    "sampled_projection",
]


def expected_kind(name: str) -> str | None:
    """The anchoring kind this module declares for a top-level field, or None."""
    if name in ANCHORED_FIELD_NAMES:
        return SHA_ANCHORED
    if name in SAMPLED_FIELD_NAMES:
        return SAMPLED_AT_TIME
    return None


def declared_kind(spec: Any) -> str | None:
    """The anchoring kind a schema property declares (``x-anchoring`` or older spellings)."""
    if not isinstance(spec, dict):
        return None
    for key in _DECLARATION_KEYS:
        value = spec.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def schema_anchoring_gaps(schema: dict[str, Any]) -> list[str]:
    """Field names whose schema declaration is missing or disagrees with this module.

    A gap is: a declared field absent from the schema, a schema property with no
    anchoring declaration, a declaration outside ``ANCHORING_KINDS``, or a kind
    that contradicts ``ANCHORED_FIELD_NAMES`` / ``SAMPLED_FIELD_NAMES``.
    """
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return sorted(set(ANCHORED_FIELD_NAMES) | set(SAMPLED_FIELD_NAMES))
    gaps: list[str] = []
    for name in list(ANCHORED_FIELD_NAMES) + list(SAMPLED_FIELD_NAMES):
        spec = props.get(name)
        if not isinstance(spec, dict):
            gaps.append(name)
            continue
        kind = declared_kind(spec)
        if kind != expected_kind(name):
            gaps.append(name)
    for name, spec in props.items():
        if name in gaps or expected_kind(name) is not None:
            continue
        # A schema field this module does not know about must still declare a kind.
        if declared_kind(spec) not in ANCHORING_KINDS:
            gaps.append(str(name))
    return gaps


def instance_sampled_timestamp_gaps(
    snap: dict[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    """Sampled count objects missing ``sampled_at``, plus anchored objects that carry one.

    ``schema`` is accepted for signature stability; the declaration of record is
    this module, so the check does not depend on the schema file being present.
    """
    gaps: list[str] = []
    if not isinstance(snap, dict):
        return sorted(set(SAMPLED_FIELD_NAMES) - SAMPLED_SCALARS)
    for name in SAMPLED_FIELD_NAMES:
        if name in SAMPLED_SCALARS:
            continue
        obj = snap.get(name)
        if not isinstance(obj, dict) or not obj.get("sampled_at"):
            gaps.append(name)
        elif obj.get("anchoring_kind") not in (None, SAMPLED_AT_TIME):
            gaps.append(name)
    for name in ANCHORED_FIELD_NAMES:
        obj = snap.get(name)
        if isinstance(obj, dict) and obj.get("class") is not None and obj.get("sampled_at"):
            # A timestamp on a tree fact would pretend the fact was a sample.
            gaps.append(name)
    return gaps


def anchored_projection(snap: dict[str, Any]) -> dict[str, Any]:
    """The SHA-ANCHORED fields of a snapshot, deep-copied.

    Two captures at the same ``pinned_sha`` must produce equal projections
    whatever the worktree, refs or clock did in between; a capture at a
    different SHA whose tree differs must not.
    """
    return {
        name: copy.deepcopy(snap[name]) for name in ANCHORED_FIELD_NAMES if name in snap
    }


def sampled_projection(snap: dict[str, Any]) -> dict[str, Any]:
    """The SAMPLED-AT-TIME fields of a snapshot, deep-copied (the complement)."""
    return {
        name: copy.deepcopy(snap[name]) for name in SAMPLED_FIELD_NAMES if name in snap
    }
