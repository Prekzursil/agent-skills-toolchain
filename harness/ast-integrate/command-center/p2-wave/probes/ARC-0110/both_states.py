#!/usr/bin/env python3
"""Both-states gate demonstration on a scratch overlay (not a git branch).

Git checkout/stash is forbidden in this delivery. The scratch 'branch' is an
in-memory overlay of file bytes keyed by repo-relative path, applied by the
gate without writing live frozen files.
"""
from __future__ import annotations

from typing import Any

import gate as G
import inventory as I

MUTATION_MARK = b"\n/* ARC-0110-scratch-mutation */\n"


def _pick_frozen(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    for row in rows:
        if row["kind"] == kind:
            return row
    raise RuntimeError(f"no frozen {kind} to mutate")


def valid_migration(rel: str, from_version: int) -> dict[str, Any]:
    return {
        "from_version": from_version,
        "to_version": from_version + 1,
        "paths": [rel],
        "transform": {
            "kind": "additive-annotation",
            "description": "Append a scratch-only marker comment; live tree is untouched.",
        },
        "reversibility": {
            "reversible": True,
            "statement": "Delete the appended marker to recover the frozen bytes.",
        },
        "dry_run_result": {
            "ran": True,
            "ok": True,
            "notes": "Scratch overlay dry-run compared hashes before admit.",
        },
    }


def incomplete_migration(rel: str, from_version: int) -> dict[str, Any]:
    rec = valid_migration(rel, from_version)
    rec["dry_run_result"] = {"ran": False, "ok": False, "notes": "never executed"}
    return rec


def no_bump_migration(rel: str, from_version: int) -> dict[str, Any]:
    rec = valid_migration(rel, from_version)
    rec["to_version"] = from_version
    return rec


def mutate(repo, rel: str) -> bytes:
    return (repo / rel).read_bytes() + MUTATION_MARK


def run(repo) -> dict[str, Any]:
    census = I.census()
    frozen = census["frozen"]
    schema_row = _pick_frozen(frozen, "schema")
    launcher_row = _pick_frozen(frozen, "launcher")
    target = schema_row["path"]
    mutated = mutate(repo, target)
    nf_rel = I.NOT_FROZEN_EXAMPLES[0]
    nf_mutated = mutate(repo, nf_rel)
    frm = int(schema_row["content_version"])

    clean = G.evaluate(repo, frozen, overlay={}, migrations=[])
    unmigrated = G.evaluate(repo, frozen, overlay={target: mutated}, migrations=[])
    migrated = G.evaluate(
        repo,
        frozen,
        overlay={target: mutated},
        migrations=[valid_migration(target, frm)],
    )
    nonfrozen = G.evaluate(
        repo,
        frozen,
        overlay={nf_rel: nf_mutated},
        migrations=[],
    )
    not_checked = G.evaluate(
        repo,
        frozen,
        overlay={target: mutated},
        migrations=[incomplete_migration(target, frm)],
    )
    no_bump = G.evaluate(
        repo,
        frozen,
        overlay={target: mutated},
        migrations=[no_bump_migration(target, frm)],
    )
    launcher_unmigrated = G.evaluate(
        repo,
        frozen,
        overlay={launcher_row["path"]: mutate(repo, launcher_row["path"])},
        migrations=[],
    )

    states = {
        "clean_silent": clean["ok"] is True and clean["verdict"] == "ACCEPT",
        "unmigrated_rejects": (
            unmigrated["ok"] is False
            and unmigrated["verdict"] == "REJECT"
            and any(r["reason"] == "unmigrated-change" for r in unmigrated["rejections"])
        ),
        "migrated_accepts": migrated["ok"] is True and migrated["verdict"] == "ACCEPT",
        "nonfrozen_silent": (
            nonfrozen["ok"] is True
            and nf_rel in nonfrozen["nonfrozen_changes_ignored"]
            and not nonfrozen["rejections"]
        ),
        "not_checked_rejects": (
            not_checked["ok"] is False
            and any("NOT-CHECKED" in r["reason"] for r in not_checked["rejections"])
        ),
        "no_bump_rejects": (
            no_bump["ok"] is False
            and any(r["reason"] == "no-version-bump" for r in no_bump["rejections"])
        ),
        "launcher_unmigrated_rejects": (
            launcher_unmigrated["ok"] is False
            and launcher_unmigrated["verdict"] == "REJECT"
        ),
    }
    both = (
        states["unmigrated_rejects"]
        and states["migrated_accepts"]
        and states["clean_silent"]
        and states["nonfrozen_silent"]
        and states["not_checked_rejects"]
        and states["no_bump_rejects"]
        and states["launcher_unmigrated_rejects"]
    )
    return {
        "scratch_kind": "in-memory-overlay",
        "git_checkout_not_used": True,
        "target_schema": target,
        "target_launcher": launcher_row["path"],
        "not_frozen_edited": nf_rel,
        "states": states,
        "both_states_pass": both,
        "raw": {
            "clean": {k: clean[k] for k in ("ok", "verdict", "reason")},
            "unmigrated": {
                k: unmigrated[k] for k in ("ok", "verdict", "reason", "rejections")
            },
            "migrated": {k: migrated[k] for k in ("ok", "verdict", "reason")},
            "nonfrozen": {
                k: nonfrozen[k]
                for k in ("ok", "verdict", "nonfrozen_changes_ignored")
            },
        },
        "detector_control": {
            "id": "planted-unmigrated-edit-must-reject",
            "fired": states["unmigrated_rejects"],
            "clean_silent": states["clean_silent"],
            "order": "control-before-accept",
            "trusted": states["unmigrated_rejects"] and states["clean_silent"],
        },
    }
