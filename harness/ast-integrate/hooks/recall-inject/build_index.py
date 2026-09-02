#!/usr/bin/env python3
"""recall-inject/build_index.py — vault note indexer.

Scans the basic-memory vault markdown notes (D:\\basic-memory) and the
global auto-memory MEMORY.md, extracts keywords from front-matter and
content, and builds a trigger→note index cached as JSON.

Cache strategy (content-hash): compute a snapshot hash over all .md file
stat entries (path|size|mtime_ns) via os.scandir — ~3ms for 462 files.
If the hash matches the cached index's vault_hash, return the cache
unchanged. Otherwise rebuild (~100-300ms). This gives a fast (~5ms) hot
path on every prompt invocation.

MEMORY.md summary wins over vault front-matter description for the same
note (the inline MEMORY.md summaries are the most concise one-liners).

Stdlib only — no pyyaml, no numpy, no external deps.
Fail-safe: every function wraps errors silently; the worst case is an
empty notes list, never an exception that would break the hook.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_DIR = THIS / "index"
INDEX_PATH = INDEX_DIR / "recall_index.json"

# ─── stop words: same set as semantic-router for token-overlap consistency ───
_STOP = frozenset(
    (
        "the a an and or to of in on for with is are be this that it as at by from your you i we us our "
        "use using used when whether not no into over under via per any all only just like such than then "
        "do does doing help need needs want wants make makes get gets set sets new add also more most can "
        "could should would may might will must its their them what which who how why where here there about "
        "please thanks thank great works working good nice okay yeah yep cool done now today really very"
    ).split()
)


def _tok(s: str) -> set[str]:
    """Extract significant tokens: 3+ chars, alphanumeric (+ . # - +), stop-word filtered."""
    return {
        w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{2,}", s.lower()) if w not in _STOP
    }


# ─── front-matter parser ──────────────────────────────────────────────────────


def _parse_frontmatter(text: str) -> tuple[str, str, str, list[str]]:
    """Parse YAML front-matter from a note.

    Returns (title, description, permalink, tags+triggers).
    All fields may be empty. Tolerates malformed/missing front-matter.
    Never raises.
    """
    title = description = permalink = ""
    extras: list[str] = []
    try:
        if not text.startswith("---"):
            return title, description, permalink, extras
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
        if not m:
            return title, description, permalink, extras
        fm = m.group(1)

        # title / name (first line only)
        nm = re.search(r"(?mi)^(?:name|title):\s*(.+)$", fm)
        if nm:
            title = nm.group(1).strip().strip("\"'")

        # description (first line; multi-line folded YAML is a non-issue for keywords)
        ds = re.search(r"(?mi)^description:\s*(.+)$", fm)
        if ds:
            description = ds.group(1).strip().strip("\"'")

        # permalink (nested under metadata:)
        pl = re.search(r"(?mi)^\s+permalink:\s*(.+)$", fm)
        if pl:
            permalink = pl.group(1).strip().strip("\"'")

        # tags and triggers — both inline [...] and block (- item) forms
        for field in ("tags", "triggers"):
            inline = re.search(r"(?mi)^" + field + r":\s*\[(.+)\]", fm)
            if inline:
                for t in inline.group(1).split(","):
                    t = t.strip().strip("\"'")
                    if t:
                        extras.append(t)
            else:
                block = re.search(
                    r"(?ms)^" + field + r":\s*\n((?:[ \t]+-[ \t]*.+\n?)*)", fm
                )
                if block:
                    for line in block.group(1).splitlines():
                        t = re.sub(r"^\s*-\s*", "", line).strip().strip("\"'")
                        if t:
                            extras.append(t)
    except Exception:
        pass
    return title, description, permalink, extras


# ─── keyword extraction ───────────────────────────────────────────────────────


def _keywords_for(
    title: str, description: str, extras: list[str], stem: str
) -> list[str]:
    """Build a deduplicated, sorted keyword list for a note.

    Sources (in priority order):
      1. Title tokens (3+ chars, stop-word filtered)
      2. Description tokens
      3. Tags / triggers (each as-is if 2+ chars; also tokenized)
      4. Filename stem: all 2+ char alphanumeric parts (catches 'bc', 'frida', etc.)
    """
    kw: set[str] = set()
    kw.update(_tok(title))
    kw.update(_tok(description))
    for t in extras:
        kw.update(_tok(t))
        t_clean = re.sub(r"[^a-z0-9+#.-]", "", t.strip().lower())
        if len(t_clean) >= 2:
            kw.add(t_clean)
    # Filename stem: split on any non-alphanumeric run → 2+ char parts
    for part in re.findall(r"[a-z0-9]{2,}", stem.lower()):
        kw.add(part)
    return sorted(kw)


# ─── vault note scanner ───────────────────────────────────────────────────────


def _scan_vault_notes(vault_dirs: list[Path]) -> list[dict]:
    """Recursively scan .md files in vault_dirs.

    Skips MEMORY.md files (handled separately by _parse_memory_md).
    Tolerates unreadable/malformed files silently.
    Returns list of note dicts: {path, title, summary, permalink, keywords}.
    """
    notes: list[dict] = []
    for vdir in vault_dirs:
        if not vdir.exists():
            continue
        try:
            md_files = sorted(vdir.rglob("*.md"))
        except Exception:
            continue
        for md_file in md_files:
            if md_file.name.upper() == "MEMORY.MD":
                continue  # handled by _parse_memory_md
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                stem = md_file.stem
                title, description, permalink, extras = _parse_frontmatter(text)
                if not title:
                    # Fallback: stem → title
                    title = re.sub(r"[_\-]+", " ", stem).title()
                summary = description
                if not summary:
                    # First non-empty, non-heading body line
                    in_fm = text.startswith("---")
                    body_text = text
                    if in_fm:
                        m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.DOTALL)
                        if m:
                            body_text = text[m.end() :]
                    for line in body_text.splitlines():
                        line = line.strip()
                        if line and not line.startswith(("#", "---", "```")):
                            summary = line[:200]
                            break
                if not permalink:
                    try:
                        rel = md_file.relative_to(vdir)
                        permalink = str(rel.with_suffix("")).replace("\\", "/")
                    except ValueError:
                        permalink = stem
                kw = _keywords_for(title, summary, extras, stem)
                notes.append(
                    {
                        "path": str(md_file),
                        "title": title,
                        "summary": summary[:200],
                        "permalink": permalink,
                        "keywords": kw,
                    }
                )
            except Exception:
                continue  # skip any unreadable/malformed note
    return notes


# ─── MEMORY.md parser ────────────────────────────────────────────────────────


def _parse_memory_md(path: Path) -> list[dict]:
    """Parse a MEMORY.md bullet-list file.

    Handles format:  - [Title](link.md) — Summary text
    Also handles em-dash (U+2014) and double-hyphen variants.
    Returns list of note dicts.
    """
    entries: list[dict] = []
    if not path.exists():
        return entries
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return entries
    # Pattern: - [Title](link) — summary  (em-dash U+2014, or --)
    _re = re.compile(r"^-\s+\[(.+?)\]\((.+?)\)(?:\s+(?:—|--)\s+(.*))?$")
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue
        try:
            m = _re.match(line)
            if not m:
                continue
            title_raw = m.group(1)
            link = m.group(2) or ""
            summary = (m.group(3) or "").strip()
            # Strip markdown bold/italic from title
            title = re.sub(r"\*\*|__|\*|_|~~", "", title_raw).strip()
            if not title:
                continue
            stem = Path(link).stem if link else re.sub(r"\s+", "_", title.lower())
            # Build a permalink from the link stem
            permalink = stem
            kw = _keywords_for(title, summary, [], stem)
            entries.append(
                {
                    "path": str(path),
                    "title": title,
                    "summary": summary[:200],
                    "permalink": permalink,
                    "keywords": kw,
                }
            )
        except Exception:
            continue
    return entries


# ─── snapshot hash ────────────────────────────────────────────────────────────


def _vault_snapshot_hash(vault_dirs: list[Path], memory_md_paths: list[Path]) -> str:
    """Stable hash over all .md file stat entries (path|size|mtime_ns).

    Uses os.scandir() for speed: ~3ms for 462 files vs ~67ms with Path.stat().
    Sorted before hashing for determinism.
    """
    entries: list[str] = []

    def _walk(directory: str) -> None:
        try:
            with os.scandir(directory) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        # Skip dot-dirs (.hf, .models, .git, .cache, etc.) —
                        # they're either VCS metadata or large model/HF caches
                        # that are irrelevant to the vault and can be huge.
                        if e.name.startswith("."):
                            continue
                        _walk(e.path)
                    elif e.name.endswith(".md"):
                        try:
                            st = e.stat(follow_symlinks=False)
                            entries.append(f"{e.path}|{st.st_size}|{st.st_mtime_ns}")
                        except OSError:
                            pass
        except OSError:
            pass

    for vdir in vault_dirs:
        if vdir.exists():
            _walk(str(vdir))
    for mpath in memory_md_paths:
        try:
            st = mpath.stat()
            entries.append(f"{mpath}|{st.st_size}|{st.st_mtime_ns}")
        except OSError:
            pass
    entries.sort()
    combined = "\n".join(entries)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:24]


# ─── index builder (main API) ────────────────────────────────────────────────


def get_or_build_index(
    vault_dirs: list[Path] | None = None,
    memory_md_paths: list[Path] | None = None,
    index_path: Path | None = None,
) -> dict:
    """Return the trigger index dict, building/caching as needed.

    Returned dict schema:
      {
        "vault_hash": str,         # snapshot hash of vault at build time
        "built_at":  float,        # Unix timestamp
        "notes": [
          {
            "path":      str,      # absolute path to source .md file
            "title":     str,
            "summary":   str,      # one-line summary (≤200 chars)
            "permalink": str,      # basic-memory permalink or stem
            "keywords":  [str],    # sorted keyword list
          }, ...
        ]
      }

    On any error (missing vault, corrupt cache, disk full) returns
    {"vault_hash": "", "built_at": 0.0, "notes": []} — never raises.
    """
    if vault_dirs is None:
        vault_dirs = find_vault_dirs()
    if memory_md_paths is None:
        memory_md_paths = find_memory_md_paths()
    if index_path is None:
        index_path = INDEX_PATH

    empty: dict = {"vault_hash": "", "built_at": 0.0, "notes": []}

    try:
        current_hash = _vault_snapshot_hash(vault_dirs, memory_md_paths)
    except Exception:
        return empty

    # Fast path: return cached index if vault unchanged
    if index_path.exists():
        try:
            cached = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("vault_hash") == current_hash:
                return cached
        except Exception:
            pass  # corrupt cache → fall through to rebuild

    # Slow path: rebuild
    try:
        # Scan vault notes first
        notes_by_title: dict[str, dict] = {}
        for note in _scan_vault_notes(vault_dirs):
            key = note["title"].lower().strip()
            notes_by_title[key] = note

        # Merge MEMORY.md entries: prefer their summaries for same-title notes;
        # add new entries that don't exist in the vault.
        for mpath in memory_md_paths:
            for entry in _parse_memory_md(mpath):
                key = entry["title"].lower().strip()
                if key in notes_by_title:
                    # Override summary with the MEMORY.md one-liner if non-empty
                    if entry["summary"]:
                        notes_by_title[key]["summary"] = entry["summary"]
                    # Merge keywords (union)
                    merged_kw = set(notes_by_title[key]["keywords"]) | set(
                        entry["keywords"]
                    )
                    notes_by_title[key]["keywords"] = sorted(merged_kw)
                else:
                    notes_by_title[key] = entry

        index: dict = {
            "vault_hash": current_hash,
            "built_at": time.time(),
            "notes": list(notes_by_title.values()),
        }

        # Persist cache
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(
                json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass  # cache write failure is non-fatal; index is still returned

        return index

    except Exception:
        return empty


# ─── path discovery ───────────────────────────────────────────────────────────


def find_vault_dirs() -> list[Path]:
    """Locate the basic-memory vault root.

    Check order:
      1. BASIC_MEMORY_HOME env var
      2. ~/.basic-memory config (basic-memory's own config file)
      3. Fallback: D:\\basic-memory
    """
    # 1. Env var
    env = os.environ.get("BASIC_MEMORY_HOME", "").strip()
    if env:
        p = Path(env)
        if p.exists():
            return [p]

    # 2. ~/.basic-memory config
    cfg = HOME / ".basic-memory" / "config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            vault_path = data.get("home") or data.get("vault") or data.get("path")
            if vault_path:
                p = Path(vault_path)
                if p.exists():
                    return [p]
        except Exception:
            pass

    # 3. Fallback
    fallback = Path("D:/basic-memory")
    if fallback.exists():
        return [fallback]
    return []


def find_memory_md_paths() -> list[Path]:
    """Locate auto-memory MEMORY.md files to include as bullet-list sources.

    Searches: ~/.claude/projects/*/memory/MEMORY.md
    """
    paths: list[Path] = []
    try:
        for p in sorted((HOME / ".claude" / "projects").glob("*/memory/MEMORY.md")):
            if p.exists():
                paths.append(p)
    except Exception:
        pass
    return paths


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build recall-inject index from the basic-memory vault."
    )
    parser.add_argument(
        "--rebuild", action="store_true", help="Force full rebuild (ignore cache)"
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args()

    if args.rebuild and INDEX_PATH.exists():
        try:
            INDEX_PATH.unlink()
        except Exception:
            pass

    idx = get_or_build_index()
    if not args.quiet:
        print(
            f"Index: {len(idx['notes'])} notes, hash={idx['vault_hash']}, "
            f"built_at={idx['built_at']:.0f}"
        )
        if idx["notes"]:
            print("Sample notes:")
            for n in idx["notes"][:5]:
                print(f"  [{n['title'][:60]}] — {n['summary'][:80]}")
