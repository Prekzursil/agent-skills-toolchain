#!/usr/bin/env python3
"""IMP-0107 probe 2: conflict persists across restart; no silent preference.

Independent of probe 1: new store, new process-equivalent policy object.
Also confirms matching-digest install still works after a restart, and that
prefer_upstream / authoritative config is refused.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from mirror_conflict import (  # noqa: E402
    FORBIDDEN_PREFER_KEYS,
    MirrorConflictPolicy,
    SilentPreferenceRefused,
    UnresolvedMirrorConflict,
    census,
    sha256_digest,
)

SRC = REPO / "tools" / "marketplace" / "mirror_conflict.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0107-probe2 {msg}")
    return 1


def source_has_silent_prefer(path: Path) -> list[str]:
    """AST scan: assignments that would pick a winner from config."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    banned = {
        "prefer_upstream",
        "prefer_mirror",
        "preferred_source",
        "authoritative_side",
        "winner",
        "auto_resolve",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in banned:
                    hits.append(target.id)
                if isinstance(target, ast.Attribute) and target.attr in banned:
                    hits.append(target.attr)
    return hits


def main() -> int:
    hits = source_has_silent_prefer(SRC)
    if hits:
        return fail(f"source assigns silent-prefer fields: {hits}")
    src_text = SRC.read_text(encoding="utf-8")
    for key in sorted(FORBIDDEN_PREFER_KEYS):
        if key not in src_text:
            return fail(f"forbidden key {key} not listed in FORBIDDEN_PREFER_KEYS body")

    with tempfile.TemporaryDirectory(prefix="imp0107-p2-") as tmp:
        tmp_path = Path(tmp)
        store = tmp_path / "conflicts.json"
        dest = tmp_path / "install-root"

        try:
            MirrorConflictPolicy(store, config={"prefer_upstream": True})
            return fail("prefer_upstream was accepted")
        except SilentPreferenceRefused:
            prefer_refused = True
        try:
            MirrorConflictPolicy(store, config={"authoritative": "mirror"})
            return fail("authoritative was accepted")
        except SilentPreferenceRefused:
            authoritative_refused = True

        first = MirrorConflictPolicy(store)
        up_d = sha256_digest(b"restart-upstream")
        mir_d = sha256_digest(b"restart-mirror")
        first.compare_and_record(
            "persist-pkg",
            "9.9.9",
            upstream_url="https://upstream.example/persist-pkg/9.9.9",
            upstream_digest=up_d,
            mirror_url="file:///private-mirror/persist-pkg/9.9.9",
            mirror_digest=mir_d,
        )
        store_bytes = store.read_bytes()
        del first

        restarted = MirrorConflictPolicy(store)
        rec = restarted.unresolved("persist-pkg", "9.9.9")
        if rec is None or rec.get("status") != "unresolved":
            return fail("conflict did not survive restart")
        if store.read_bytes() != store_bytes:
            return fail("restart mutated the conflict store")
        try:
            restarted.chosen_digest("persist-pkg", "9.9.9")
            return fail("chosen_digest picked a side after restart")
        except UnresolvedMirrorConflict:
            no_chosen = True

        dest.mkdir(parents=True)
        before = census(dest)
        refused = restarted.install("persist-pkg", "9.9.9", dest, b"restart-mirror")
        after = census(dest)
        if refused.ok or before != after:
            return fail(f"post-restart install not fail-closed ok={refused.ok}")

        # Matching later fetch must NOT auto-clear the security event.
        still = restarted.compare_and_record(
            "persist-pkg",
            "9.9.9",
            upstream_url="https://upstream.example/persist-pkg/9.9.9",
            upstream_digest=up_d,
            mirror_url="file:///private-mirror/persist-pkg/9.9.9",
            mirror_digest=up_d,
        )
        if still is None or still.get("status") != "unresolved":
            return fail("later matching compare silently cleared the conflict")
        still_refused = restarted.install("persist-pkg", "9.9.9", dest, b"restart-upstream")
        if still_refused.ok:
            return fail("install allowed before explicit resolve")

        resolved = restarted.resolve(
            "persist-pkg",
            "9.9.9",
            actor="security-reviewer",
            note="human resolution after both digests inspected; no silent prefer",
        )
        if resolved.get("status") != "resolved":
            return fail("resolve did not mark resolved")
        if restarted.unresolved("persist-pkg", "9.9.9") is not None:
            return fail("unresolved() still set after resolve")

        allowed = restarted.install("persist-pkg", "9.9.9", dest, b"restart-upstream")
        walked = census(dest)
        if not allowed.ok or "persist-pkg/9.9.9/payload.bin" not in walked:
            return fail("explicit resolve did not allow a subsequent install")

        # Matching-digest package in the restarted process still installs.
        good = b"post-restart-match"
        gd = sha256_digest(good)
        none = restarted.compare_and_record(
            "ok-pkg",
            "1.0.0",
            upstream_url="https://upstream.example/ok-pkg/1.0.0",
            upstream_digest=gd,
            mirror_url="file:///private-mirror/ok-pkg/1.0.0",
            mirror_digest=gd,
        )
        if none is not None:
            return fail("matching digests conflicted after restart")
        ok_install = restarted.install("ok-pkg", "1.0.0", dest, good)
        if not ok_install.ok:
            return fail("matching digest install failed after restart")

        out = {
            "probe": "probe2-persist-negative",
            "unit_id": "IMP-0107",
            "persist_across_restart": True,
            "no_auto_clear_on_later_match": True,
            "explicit_resolve_then_install": True,
            "prefer_upstream_refused": prefer_refused,
            "authoritative_refused": authoritative_refused,
            "chosen_digest_raises": no_chosen,
            "source_silent_prefer_assigns": hits,
            "matching_after_restart": True,
            "pass": True,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            "persist=True no_silent_prefer=True later_match_does_not_clear=True "
            "explicit_resolve_installs=True"
        )
        print("SUCCESS:IMP-0107-probe2 persist across restart and no silent prefer")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
