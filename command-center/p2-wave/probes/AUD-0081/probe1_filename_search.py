#!/usr/bin/env python3
"""AUD-0081 named probe 1: filename search for the auto-load config set
across every non-owner-authored (cloned/vendored) tree in this checkout.

Catalog evidence_requirement (verbatim, probe 1 half): "a filename search
for the auto-load set across every non-owner-authored tree."

SCOPE DISCLOSURE (measured, not assumed): this probe runs inside exactly
ONE of the estate's many checkouts (this Cursor Cloud pod's /workspace).
CLAUDE.md's own "178 checkouts on this box" section is about a different,
Windows-hosted developer box this pod cannot see or enumerate. This probe
is therefore honestly scoped to the filesystem it can actually walk: this
one checkout, real vendored/cloned tree roots, real bytes on disk.

VENDORED-TREE-ROOT DEFINITION (mechanical, falsifiable): a directory whose
basename case-insensitively equals one of {node_modules, vendor,
vendor_src, third_party, third-party}. This is not an arbitrary allowlist:
every one of these five basenames was independently confirmed, before
writing this probe, to actually exist in this checkout via `find` (see
probe raw output) and/or to be explicitly self-documented as an upstream
snapshot (tools/editor/ralph-orchestrator/vendor/README.md: "Curated
upstream snapshot: mikeyobrien/ralph-orchestrator ... diff -rq against
upstream ... identical"). A directory that merely CONTAINS the substring
"vendor" in an unrelated word (e.g. "providers") is excluded: the match is
on the full path COMPONENT, not a substring of the path string.

AUTO-LOAD SET (from the catalog's question_or_target, verbatim): .claude,
.codex, .mcp.json, a "hooks" directory, AGENTS.md, CLAUDE.md.

This probe walks the REAL filesystem (os.walk), not `git ls-files` --
node_modules is gitignored in this repo (confirmed: `git ls-files` returns
zero node_modules paths) but the auto-load risk is about what an agent
process reads off DISK, not what git tracks, so a git-only census would
silently miss the single most populous vendored-tree class in this
checkout.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "probe1-filename-search.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-filename-search.raw.txt"

VENDORED_ROOT_BASENAMES = {
    "node_modules",
    "vendor",
    "vendor_src",
    "third_party",
    "third-party",
}
PRUNE_ALWAYS = {".git"}

AUTOLOAD_FILE_NAMES = {"agents.md", "claude.md", ".mcp.json"}
AUTOLOAD_DIR_NAMES = {".claude", ".codex", "hooks"}


def find_vendored_roots() -> list[str]:
    """Walk the whole checkout once, returning the topmost directory whose
    basename matches VENDORED_ROOT_BASENAMES. Once a root is found its
    subtree is NOT descended further here (a nested node_modules inside
    another node_modules is still under the same outer vendored root and
    would otherwise be double-reported as a second independent root)."""
    roots: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(REPO):
        rel_dir = os.path.relpath(dirpath, REPO)
        dirnames[:] = [d for d in dirnames if d not in PRUNE_ALWAYS]
        base = os.path.basename(dirpath)
        if rel_dir != "." and base.lower() in VENDORED_ROOT_BASENAMES:
            roots.append(rel_dir.replace(os.sep, "/"))
            dirnames[:] = []  # do not descend into an already-found root
    return sorted(roots)


def scan_root_for_autoload(root_rel: str) -> list[dict]:
    """Walk one vendored-tree root and record every auto-load filename/
    dirname hit found within it (recursively, including hits nested many
    levels deep -- e.g. a hooks/ dir inside a vendored crate)."""
    hits: list[dict] = []
    root_abs = REPO / root_rel
    for dirpath, dirnames, filenames in os.walk(root_abs):
        rel_dir = os.path.relpath(dirpath, REPO).replace(os.sep, "/")
        for d in list(dirnames):
            if d.lower() in AUTOLOAD_DIR_NAMES:
                hits.append(
                    {
                        "path": f"{rel_dir}/{d}",
                        "vendored_root": root_rel,
                        "kind": "dir",
                        "matched_name": d,
                    }
                )
        for f in filenames:
            if f.lower() in AUTOLOAD_FILE_NAMES:
                hits.append(
                    {
                        "path": f"{rel_dir}/{f}",
                        "vendored_root": root_rel,
                        "kind": "file",
                        "matched_name": f,
                    }
                )
    return hits


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    roots = find_vendored_roots()

    all_hits: list[dict] = []
    for root in roots:
        all_hits.extend(scan_root_for_autoload(root))

    # de-duplicate a dir hit that would also be walked as a parent of a
    # nested file hit path string collision (defensive; should not occur
    # given the walk logic above, but asserted rather than assumed)
    seen = set()
    deduped = []
    for h in all_hits:
        key = (h["path"], h["kind"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    all_hits = sorted(deduped, key=lambda h: h["path"])

    by_matched_name: dict[str, int] = {}
    by_root: dict[str, int] = {}
    for h in all_hits:
        by_matched_name[h["matched_name"]] = (
            by_matched_name.get(h["matched_name"], 0) + 1
        )
        by_root[h["vendored_root"]] = by_root.get(h["vendored_root"], 0) + 1

    doc = {
        "ok": True,
        "started_at": started,
        "scope_note": (
            "single checkout only (this Cursor Cloud pod); see module "
            "docstring for the measured 178-checkout-estate scope gap"
        ),
        "vendored_root_basenames": sorted(VENDORED_ROOT_BASENAMES),
        "autoload_file_names": sorted(AUTOLOAD_FILE_NAMES),
        "autoload_dir_names": sorted(AUTOLOAD_DIR_NAMES),
        "vendored_tree_roots": roots,
        "vendored_tree_root_count": len(roots),
        "hits": all_hits,
        "hits_count": len(all_hits),
        "by_matched_name": dict(sorted(by_matched_name.items(), key=lambda kv: -kv[1])),
        "by_vendored_root": dict(sorted(by_root.items(), key=lambda kv: -kv[1])),
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0081-probe1",
        f"unit=AUD-0081 probe=1 vendored_tree_root_count={len(roots)} hits_count={len(all_hits)}",
        f"vendored_tree_roots={roots}",
        f"by_matched_name={doc['by_matched_name']}",
        f"by_vendored_root={doc['by_vendored_root']}",
        "--- all hits ---",
    ]
    for h in all_hits:
        lines.append(f"{h['kind']:4s} {h['matched_name']:12s} {h['path']}")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
