#!/usr/bin/env python3
"""TST-0175 probe2 -- rollback regression seed (detector control) + user-data preservation.

Regression seed (_USER-PROMPTS.md:11347): a rollback that removes existing
commands or user data is the bug class under test. This probe runs BOTH a
correct rollback and a known-broken rollback over the same fixture and proves
the detector (tree-hash + planted-file assertions) fires on the broken state
and is silent on the correct one.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNIT = "TST-0175"
RUN = HERE / ".run-p2"
sys.path.insert(0, str(HERE))
import ownership as OW  # noqa: E402


def build_root(base: Path) -> Path:
    Cache = OW._cache_cls()
    if base.exists():
        shutil.rmtree(base)
    root = base
    (root / "state/cache").mkdir(parents=True)
    (root / "state/notes").mkdir(parents=True)
    (root / "state/profiles").mkdir(parents=True)
    c = Cache(root / "state/cache")
    c.put(b"rollback-derived-1")
    c.put(b"rollback-derived-2")
    (root / "state/notes/user.json").write_bytes(b'{"note": "persist"}')
    (root / "state/profiles/p.json").write_bytes(b'{"profile": "persist"}')
    (root / "commands.json").write_bytes(
        b'{"commands": ["deploy", "test", "verify"], "installed": true}'
    )
    return root


def main() -> int:
    if RUN.exists():
        shutil.rmtree(RUN)

    # --- correct rollback: derived cleared, user data + commands intact ---
    root = build_root(RUN / "install")
    pre_user = OW.tree_hash(root, OW.USER)
    OW.rollback_correct(root)
    post_user = OW.tree_hash(root, OW.USER)
    user_ok = pre_user == post_user
    commands_ok = b'"deploy"' in (root / "commands.json").read_bytes()
    derived_gone = not any(f for f in (root / "state/cache").rglob("*") if f.is_file())

    # --- known-broken rollback (regression seed): wipes user data; detector must fire ---
    mroot = build_root(RUN / "mutant")
    OW.rollback_buggy(mroot)
    post_mut_user = OW.tree_hash(mroot, OW.USER)
    mutant_user_gone = post_mut_user != pre_user or all(
        v == "<absent>" for v in post_mut_user.values()
    )
    # the broken rollback REMOVED user data -> the probe's equality assertion FAILS there
    detector_fires_on_broken = not (mroot / "state/notes/user.json").exists()

    payload = {
        "probe": "probe2-rollback-seed",
        "unit_id": UNIT,
        "pass": user_ok and commands_ok and derived_gone and detector_fires_on_broken,
        "correct_rollback": {
            "user_data_byte_identical": user_ok,
            "commands_preserved": commands_ok,
            "derived_cache_cleared": derived_gone,
        },
        "regression_seed": {
            "seed": "_USER-PROMPTS.md:11347 rollback removes existing commands or user data",
            "broken_rollback_removed_user_data": mutant_user_gone,
            "detector_fires_on_broken_state": detector_fires_on_broken,
        },
        "signals": {
            "tree_hash_pre_post": {"equal": user_ok},
            "planted_files": {"user": user_ok, "commands": commands_ok},
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 rollback preserves user data; detector fires on seed bug")
        return 0
    print(f"FAILED:{UNIT}-probe2 user={user_ok} commands={commands_ok} derived={derived_gone} det={detector_fires_on_broken}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
