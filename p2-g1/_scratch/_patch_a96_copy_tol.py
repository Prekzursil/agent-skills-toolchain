"""Shard2-w1 fix 2026-10-24: AUD-0096 copy tolerance (corrected).

The prior builder's _shard2_w1_loadset.py was written but NEVER applied, and
its init-anchor ("    copied = 0") would have hit the first occurrence in the
file, not necessarily copy_user_skills_into. This patch adds vanish-race
tolerance to BOTH copy sites in copy_user_skills_into, counting skips, and
prints nothing (caller records counts). Concurrent estate sessions may
remove a walked file before it is copied; skipping preserves the measurement
instead of crashing it. The leak-identity assertion stays strict — a vanish
that removes a loadable is an estate event and the probe re-runs cheaply.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0096/loadset.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a96c.pyc")

OLD_TREE = """        for path in _walk_files(src):
            if _is_secret_name(path.name):
                continue
            rel_path = path.relative_to(src_home)
            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied += 1
    return copied"""

NEW_TREE = """        for path in _walk_files(src):
            if _is_secret_name(path.name):
                continue
            rel_path = path.relative_to(src_home)
            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(path, dest)
            except FileNotFoundError:
                # shard2-w1 copy tolerance 2026-10-24: concurrent sessions
                # touch the live home; a walked file may vanish before the
                # copy. Skip and keep counting instead of crashing.
                skipped += 1
                continue
            copied += 1
    return copied"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "shard2-w1 copy tolerance" in text:
        print("already patched")
        return 0
    assert OLD_TREE in text, "pattern miss tree-copy block"

    # 1. tolerance on the tree-copy block (and its trailing return becomes
    #    the function's return with the skip count recorded).
    text = text.replace(OLD_TREE, NEW_TREE, 1)

    # 2. init the counter inside copy_user_skills_into only. The function's
    #    signature line is unique.
    fn_anchor = "def copy_user_skills_into(src_home: Path, dest_home: Path) -> int:\n    \"\"\"Copy documented user-profile load roots (not just SKILL.md). No auth files.\"\"\"\n    copied = 0"
    assert fn_anchor in text, "pattern miss copy fn init"
    text = text.replace(
        fn_anchor,
        fn_anchor + "\n    skipped = 0",
        1,
    )

    # 3. single-file root copy gets the same tolerance.
    old_single = """        if src.is_file():
            if _is_secret_name(src.name):
                continue
            dest = dest_home / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
            continue"""
    new_single = """        if src.is_file():
            if _is_secret_name(src.name):
                continue
            dest = dest_home / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dest)
            except FileNotFoundError:
                skipped += 1
                continue
            copied += 1
            continue"""
    assert old_single in text, "pattern miss single-file copy block"
    text = text.replace(old_single, new_single, 1)

    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
