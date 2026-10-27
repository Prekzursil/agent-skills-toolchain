"""Shard2-w1 fix 2026-10-24: AUD-0096 copy relevance + robustness (final).

The leak-identity control compares user_keys. Only these filenames can ever
contribute a user_key:
  SKILL.md, plugin.json, mcp.json, .mcp.json, claude_desktop_config.json,
  settings.json, .claude.json, hooks.json, plus files under hooks/ and
  rules/ kind dirs.
Plugin cache internals (media, wheels, bundles) contribute zero keys; on
this host they add ~6000 inert copies per run, and vendored plugin caches
carry dir-symlinks/locked files that shutil.copy2 cannot copy
(PermissionError). This patch:
  1. adds _copy_relevant(rel_path) — the key-bearing filename/kind-dir
     predicate, mirroring classify_file's branches;
  2. filters the tree-copy loop through it;
  3. broadens copy tolerance from FileNotFoundError to OSError;
  4. keeps the skip counter for notes.
Keys-preserving by construction; the leak-identity assertion stays strict.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0096/loadset.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a96f.pyc")


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_copy_relevant" in text:
        print("already-patched")
        return 0

    helper = (
        "\n\n"
        "def _copy_relevant(rel_path: Path) -> bool:\n"
        "    \"\"\"True only for files that can contribute a user_key\n"
        "    (shard2-w1 2026-10-24: copy only key-bearing files; plugin\n"
        "    cache internals contribute zero keys and cannot be copied\n"
        "    reliably on Windows cache dirs).\"\"\"\n"
        "    name = rel_path.name\n"
        "    if name in {\"SKILL.md\", \"plugin.json\", \"mcp.json\", \".mcp.json\",\n"
        "                \"claude_desktop_config.json\", \"settings.json\",\n"
        "                \".claude.json\", \"hooks.json\"}:\n"
        "        return True\n"
        "    lower = rel_path.as_posix().lower()\n"
        "    if \"/hooks/\" in \"/\" + lower or \"/rules/\" in \"/\" + lower:\n"
        "        return True\n"
        "    return False\n"
    )

    anchor_fn = "def copy_user_skills_into(src_home: Path, dest_home: Path) -> int:"
    assert anchor_fn in text, "anchor: copy fn def"
    text = text.replace(anchor_fn, helper + "\n\n" + anchor_fn, 1)

    # Tree-copy loop: relevance filter + OSError tolerance.
    old_loop = (
        "        for path in _walk_files(src):\n"
        "            if _is_secret_name(path.name):\n"
        "                continue\n"
        "            rel_path = path.relative_to(src_home)\n"
        "            dest = dest_home / rel_path\n"
        "            dest.parent.mkdir(parents=True, exist_ok=True)\n"
        "            try:\n"
        "                shutil.copy2(path, dest)\n"
        "            except FileNotFoundError:\n"
        "                # shard2-w1 copy tolerance 2026-10-24: concurrent sessions\n"
        "                # touch the live home; a walked file may vanish before the\n"
        "                # copy. Skip and keep counting instead of crashing.\n"
        "                skipped += 1\n"
        "                continue\n"
        "            copied += 1\n"
        "    return copied"
    )
    new_loop = (
        "        for path in _walk_files(src):\n"
        "            if _is_secret_name(path.name):"
        "            continue\n"
        "            rel_path = path.relative_to(src_home)\n"
        "            if not _copy_relevant(rel_path):\n"
        "                skipped += 1\n"
        "                continue\n"
        "            dest = dest_home / rel_path\n"
        "            dest.parent.mkdir(parents=True, exist_ok=True)\n"
        "            try:\n"
        "                shutil.copy2(path, dest)\n"
        "            except OSError:\n"
        "                skipped += 1\n"
        "                continue\n"
        "            copied += 1\n"
        "    return copied"
    )
    assert old_loop in text, "anchor: tree-copy loop"
    text = text.replace(old_loop, new_loop, 1)

    # Single-file copy: OSError tolerance.
    old_single = (
        "            try:\n"
        "                shutil.copy2(src, dest)\n"
        "            except FileNotFoundError:\n"
        "                skipped += 1\n"
        "                continue\n"
        "            copied += 1\n"
        "            continue"
    )
    new_single = (
        "            try:\n"
        "                shutil.copy2(src, dest)\n"
        "            except OSError:\n"
        "                skipped += 1\n"
        "                continue\n"
        "            copied += 1\n"
        "            continue"
    )
    assert old_single in text, "anchor: single-file copy"
    text = text.replace(old_single, new_single, 1)

    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
