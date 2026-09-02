#!/usr/bin/env python3
"""Live freeze / refuse / round-trip scenarios for IMP-0477.

Each function builds a disposable workspace, drives migrate_engine, and
returns measured results. Probes and the receipt emitter share this so the
artifact cannot claim a run the probes cannot reproduce.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

import migrate_engine as E  # noqa: E402
from corpus import (  # noqa: E402
    FROZEN_RELS,
    LAUNCHER_REL,
    NOTES_REL,
    SCHEMA_REL,
    build_corpus,
    write_migration,
)


def _tamper_bytes(root: Path, rel: str) -> bytes:
    raw = (root / rel).read_bytes()
    return raw + b"\n# in-place tamper after freeze\n"


def run_freeze_scenario(root: Path) -> dict:
    """Both-states freeze: pre-freeze write ok; post-freeze frozen path refused;
    a path outside the freeze set stays editable.
    """
    build_corpus(root)
    mutated = (root / SCHEMA_REL).read_text(encoding="utf-8").replace(
        '"title": "widget"', '"title": "widget-pre"'
    )
    pre = E.write_bytes(root, SCHEMA_REL, mutated.encode("utf-8"))
    if not pre.get("ok"):
        return {"pass": False, "stage": "pre-freeze-write", "pre": pre}

    # Restore canonical corpus before freeze so round-trip fixtures stay stable.
    build_corpus(root)
    fr = E.freeze(root, FROZEN_RELS, schema_version=1)
    if not fr.get("ok"):
        return {"pass": False, "stage": "freeze", "freeze": fr}

    refused = E.write_bytes(root, SCHEMA_REL, _tamper_bytes(root, SCHEMA_REL))
    launcher_refused = E.write_bytes(
        root, LAUNCHER_REL, _tamper_bytes(root, LAUNCHER_REL)
    )
    notes_ok = E.write_bytes(
        root, NOTES_REL, b"scratch notes; edited after freeze\n"
    )
    noop = E.write_bytes(root, SCHEMA_REL, (root / SCHEMA_REL).read_bytes())

    marker = E.load_marker(root)
    frozen_sha = (marker or {}).get("paths", {}).get(SCHEMA_REL, {}).get("sha256")
    live_sha, _ = E.digest_file(root / SCHEMA_REL)

    ok = (
        pre.get("ok") is True
        and fr.get("ok") is True
        and refused.get("ok") is False
        and refused.get("code") == E.REFUSE_INPLACE
        and launcher_refused.get("ok") is False
        and launcher_refused.get("code") == E.REFUSE_INPLACE
        and notes_ok.get("ok") is True
        and noop.get("ok") is True
        and frozen_sha == live_sha
    )
    return {
        "pass": ok,
        "pre_freeze_edit_accepted": bool(pre.get("ok")),
        "marker_set": bool((marker or {}).get("frozen")),
        "inplace_refused": refused.get("ok") is False,
        "inplace_code": refused.get("code"),
        "launcher_inplace_refused": launcher_refused.get("ok") is False,
        "nonfrozen_editable_after": bool(notes_ok.get("ok")),
        "noop_write_allowed": bool(noop.get("ok")),
        "freeze_hash_unchanged": frozen_sha == live_sha,
        "refusal": {
            "code": refused.get("code"),
            "detail": refused.get("detail"),
            "required_fix": refused.get("required_fix"),
            "path": refused.get("path"),
        },
        "freeze": {"ok": fr.get("ok"), "code": fr.get("code")},
        "schema_rel": SCHEMA_REL,
        "launcher_rel": LAUNCHER_REL,
        "notes_rel": NOTES_REL,
    }


def run_irreversible_scenario(root: Path) -> dict:
    """A numbered migration with no down-step must be refused."""
    build_corpus(root)
    E.freeze(root, FROZEN_RELS, schema_version=1)
    mig = write_migration(root, include_down=False)
    loaded = E.load_migration(mig)
    applied = E.apply_accepted(root, mig)
    ok = (
        loaded.get("ok") is False
        and loaded.get("code") == E.REFUSE_NO_DOWN
        and applied.get("ok") is False
        and applied.get("code") == E.REFUSE_NO_DOWN
        and not (root / "migrations" / "0001_add_description" / "down.py").exists()
    )
    return {
        "pass": ok,
        "refused": loaded.get("ok") is False,
        "code": loaded.get("code"),
        "apply_code": applied.get("code"),
        "required_fix": loaded.get("required_fix"),
        "detail": loaded.get("detail"),
        "migration_dir": str(mig.relative_to(root).as_posix()),
        "down_present": (mig / "down.py").is_file(),
    }


def run_roundtrip_scenario(root: Path) -> dict:
    """Accepted path: freeze, numbered migration, up then down restores bytes."""
    build_corpus(root)
    before = E.snapshot_corpus(root)
    fr = E.freeze(root, FROZEN_RELS, schema_version=1)
    mig = write_migration(root, include_down=True)
    rt = E.round_trip(root, mig)
    after_rt = E.snapshot_corpus(root)
    restored = before == after_rt
    accepted = E.apply_accepted(root, mig)
    marker = E.load_marker(root)
    # After accept, corpus is at v2 and freeze hashes match v2.
    v2 = accepted.get("ok") is True
    mutated = E.write_bytes(root, SCHEMA_REL, _tamper_bytes(root, SCHEMA_REL))
    still_refused = mutated.get("ok") is False and mutated.get("code") == E.REFUSE_INPLACE
    ok = (
        fr.get("ok") is True
        and rt.get("ok") is True
        and restored
        and v2
        and still_refused
        and int((marker or {}).get("schema_version") or 0) == 2
    )
    original = (rt.get("original_sha256") or {}).get(SCHEMA_REL)
    restored_sha = (rt.get("restored_sha256") or {}).get(SCHEMA_REL)
    return {
        "pass": ok,
        "round_trip_ok": bool(rt.get("ok")),
        "round_trip_code": rt.get("code"),
        "files_compared": rt.get("files_compared"),
        "up_executed": bool((rt.get("up") or {}).get("ok")),
        "down_executed": bool((rt.get("down") or {}).get("ok")),
        "byte_identical": restored and original == restored_sha,
        "original_sha256": original,
        "restored_sha256": restored_sha,
        "up_changed": rt.get("up_changed"),
        "accepted_ok": v2,
        "accepted_code": accepted.get("code"),
        "post_migration_schema_version": (marker or {}).get("schema_version"),
        "post_accept_inplace_still_refused": still_refused,
        "migration_id": accepted.get("migration_id") or rt.get("migration_id"),
        "detail": rt.get("detail"),
    }


def run_broken_down_control(root: Path) -> dict:
    """Negative control: a no-op down-step must fail the round-trip."""
    build_corpus(root)
    E.freeze(root, FROZEN_RELS, schema_version=1)
    mig = write_migration(root, include_down=True, broken_down=True)
    rt = E.round_trip(root, mig)
    return {
        "pass": rt.get("ok") is False and rt.get("code") == E.ROUNDTRIP_FAIL,
        "ok": rt.get("ok"),
        "code": rt.get("code"),
        "detail": rt.get("detail"),
    }
