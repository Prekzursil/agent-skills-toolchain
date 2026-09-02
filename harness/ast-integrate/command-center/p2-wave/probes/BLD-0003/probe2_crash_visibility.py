#!/usr/bin/env python3
"""Probe 2: induced enumerator crash fails loudly; independent recount matches."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import enumerator as E  # noqa: E402
import fixture as F  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAIL:BLD-0003-probe2 {msg}")
    return 1


def independent_recount(root: Path) -> dict[str, int]:
    """Second walker: os.walk + same classifier (not pathlib/scandir stack)."""
    rules = E.load_gitignore_rules(root)
    counts = {c: 0 for c in E.CLASSES}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in E.SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            rel = E.safe_relpath(path, root)
            try:
                size = path.stat().st_size
                head = path.read_bytes()[:8192]
            except OSError:
                continue
            tags = E.classify_file(
                rel=rel,
                size=size,
                head=head,
                ignored=E.gitignore_hit(rel, rules),
                abs_len=len(os.path.abspath(os.fspath(path))),
            )
            for tag in tags:
                counts[tag] += 1
    return counts


def main() -> int:
    planted = F.plant()
    root = Path(planted["root"])

    # Crash-visibility: an induced exception must not become a zero census.
    crashed_loudly = False
    zero_census_emitted = False
    try:
        snap = E.census(root, crash_inject=True)
        zero_census_emitted = all(v == 0 for v in (snap.get("counts") or {}).values())
        return _fail("induced exception was swallowed; census returned")
    except ValueError as exc:
        crashed_loudly = "NUL" in str(exc)
        if not crashed_loudly:
            return _fail(f"wrong exception: {exc}")
    except Exception as exc:  # noqa: BLE001
        return _fail(f"unexpected exception type {type(exc).__name__}: {exc}")

    snap = E.census(root)
    other = independent_recount(root)
    if snap["counts"] != other:
        return _fail(f"independent recount mismatch primary={snap['counts']} other={other}")

    out = {
        "probe": "probe2-crash-visibility-and-recount",
        "unit_id": "BLD-0003",
        "induced_crash_failed_loudly": crashed_loudly,
        "zero_census_on_crash": zero_census_emitted,
        "independent_recount_matches": True,
        "counts": snap["counts"],
        "reviewer_substrate": "os.walk recount (PowerShell 7 not required on this Linux worktree)",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"crash_loud=True zero_on_crash=False recount_match=True counts={snap['counts']}"
    )
    print("SUCCESS:BLD-0003-probe2 crash visibility and independent class recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
