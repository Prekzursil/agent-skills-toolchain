#!/usr/bin/env python3
"""Reapply the metaswarm session-start latency gate after a plugin update.

The plugin cache (~/.claude/plugins/cache/metaswarm-marketplace/metaswarm/<ver>/)
is overwritten on plugin updates, which silently reverts the patch. This script
re-applies it idempotently:

  * marker present  -> "already-patched", skipped
  * anchors present -> backup <file>.bak-pre-latencygate-<date>, then patch
  * anchors moved   -> FAILED for that file, exit 2 (never guess — upstream
                       changed the script; re-derive the patch by hand)

Fix receipt: harness-patches/metaswarm-sessionstart/README.md (2026-09-19).
Pure stdlib. Read reapply.py --help for options.
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys
from pathlib import Path

MARKER = "METASWARM-PATCH: sessionstart-latency-gate"

# Anchors are exact substrings of metaswarm 0.12.0 hooks/session-start.sh.
# Any drift here means upstream changed the script -> fail loudly.
A1_OLD = (
    'beads_standalone=false\n'
    'beads_plugin_caches=("${HOME}/.claude/plugins/cache" '
    '"${CODEX_HOME:-${HOME}/.codex}/plugins/cache")\n'
)
A1_NEW = (
    'beads_standalone=false\n'
    '# METASWARM-PATCH: sessionstart-latency-gate v1 (2026-09-19, estate) — receipt in\n'
    '# agent-skills-toolchain harness-patches/metaswarm-sessionstart/. beads_standalone is\n'
    '# only read by the `bd prime` branch (Phase 4), which requires new_project=false, but\n'
    '# this scan runs unconditionally first: find over two plugin caches + one jq spawn per\n'
    '# plugin.json (529 files on this box) cost 140s of SessionStart wall-clock in cwds where\n'
    '# the result is never consumed. Gate it on the same project check Phase 2 uses; behavior\n'
    '# is unchanged wherever the scan still runs.\n'
    'if [ -f ".metaswarm/project-profile.json" ]; then\n'
    'beads_plugin_caches=("${HOME}/.claude/plugins/cache" '
    '"${CODEX_HOME:-${HOME}/.codex}/plugins/cache")\n'
)
A2_OLD = '  [ "$beads_standalone" = true ] && break\ndone\n'
A2_NEW = '  [ "$beads_standalone" = true ] && break\ndone\nfi  # METASWARM-PATCH: sessionstart-latency-gate v1\n'

DEFAULT_GLOB = (
    Path.home() / ".claude" / "plugins" / "cache"
    / "metaswarm-marketplace" / "metaswarm" / "*" / "hooks" / "session-start.sh"
)


def default_targets() -> list[Path]:
    return sorted(Path.home().glob(
        ".claude/plugins/cache/metaswarm-marketplace/metaswarm/*/hooks/session-start.sh"
    ))


def process(path: Path, dry_run: bool) -> str:
    """Patch one file. Returns 'patched' | 'skipped' | 'anchors-missing'."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAILED: unreadable {path}: {exc}")
        return "anchors-missing"

    if MARKER in text:
        print(f"already-patched, skipped: {path}")
        return "skipped"

    if A1_OLD not in text or A2_OLD not in text:
        print(
            f"FAILED: anchors not found in {path} — upstream changed the script. "
            "Re-derive the patch from harness-patches/metaswarm-sessionstart/README.md; "
            "do not guess."
        )
        return "anchors-missing"

    if text.count(A1_OLD) != 1 or text.count(A2_OLD) != 1:
        print(f"FAILED: anchor not unique in {path} — manual review required.")
        return "anchors-missing"

    if dry_run:
        print(f"would patch: {path}")
        return "patched"

    stamp = datetime.date.today().strftime("%Y%m%d")
    backup = path.with_name(path.name + f".bak-pre-latencygate-{stamp}")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(A1_OLD, A1_NEW).replace(A2_OLD, A2_NEW), encoding="utf-8")
    print(f"patched: {path} (backup: {backup.name})")
    return "patched"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", action="append", type=Path, default=None,
                    help="explicit script path(s) to patch (repeatable; default: "
                         "all metaswarm marketplace cache versions)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen without writing")
    args = ap.parse_args(argv)

    targets = args.target or default_targets()
    if not targets:
        print(f"No session-start.sh found under {DEFAULT_GLOB.parent} — nothing to do.")
        return 0

    statuses = [process(t, args.dry_run) for t in targets]
    if any(s == "anchors-missing" for s in statuses):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
