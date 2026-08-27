#!/usr/bin/env python3
"""Cross-AI session catalog indexer.

Walks every AI runtime's session store on this box and writes ONE markdown
catalog of pointers (runtime, date, title, snippet, path) so past sessions are
searchable from basic-memory. It deliberately does NOT ingest transcripts:
full ingestion would bloat the vault and this box is RAM-starved.

Design constraints (from the 2026-08-27 SSOT job):
  * STREAM, never slurp: only the first/last 64 KB of any session file is read.
  * Idempotent: a JSON state file keyed by path+mtime skips unchanged sessions,
    so re-runs only touch new/modified sessions and the catalog is regenerated
    from state each time (safe to re-run on a schedule).
  * Grok sessions are cataloged from DIRECTORY METADATA ONLY (name + mtime) —
    no Grok content is opened (a sibling process owns Grok deep-reads, and the
    store is 22k files / 4 GB).
  * No secrets: snippets pass through a redaction pass and are truncated.
  * Binary content (NUL in head) is skipped.

Usage:
  python index-ai-sessions.py            # incremental index + rewrite catalog
  python index-ai-sessions.py --dry-run  # count what would be indexed, write nothing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STATE_PATH = HOME / ".agents" / "scripts" / "index-ai-sessions.state.json"
# 2026-08-27: catalog moved OUT of the basic-memory vault. Inside the vault the
# 378 KB file became one "oversized entity" (1,482 embedding chunks at
# batch_size=2) whose vector sync stalled the daemon's MCP surface for 25+ min
# per restart -> watchdog kill loop. See .agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md.
DEFAULT_CATALOG = HOME / ".agents" / "session-catalog.md"
FALLBACK_CATALOG = HOME / ".agents" / "SESSION-CATALOG_2026-08-27.md"

HEAD_BYTES = 64 * 1024
TAIL_BYTES = 64 * 1024
SNIPPET_LEN = 200

# Patterns that must never appear in the catalog. Replacement keeps enough
# shape to recognize "there was a token here" without leaking it.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.=]{16,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|token|password|secret)\s*[=:]\s*\S{8,}", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWT
]


def redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def clean_snippet(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = redact(text)
    if len(text) > SNIPPET_LEN:
        text = text[: SNIPPET_LEN - 1] + "\u2026"
    # keep the markdown table intact
    return text.replace("|", "\u00a6")


def extract_text_from_json(obj, budget: int = 400) -> str:
    """Pull the first plausible human-text field out of a session JSON event.

    Handles the shapes seen across Claude/Cursor/Codex JSONL without being
    schema-locked: strings under summary/text/content/message keys win, arrays
    of content blocks are walked, everything else is ignored.
    """
    if isinstance(obj, str):
        s = obj.strip()
        return s if len(s) >= 3 else ""
    if isinstance(obj, dict):
        for key in ("summary", "text", "content", "message", "prompt", "instructions"):
            if key in obj:
                got = extract_text_from_json(obj[key], budget)
                if got:
                    return got
        return ""
    if isinstance(obj, list):
        for item in obj[:8]:
            got = extract_text_from_json(item, budget)
            if got:
                return got
    return ""


def read_head(path: Path) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(HEAD_BYTES)
    except OSError:
        return b""


def read_tail(path: Path) -> bytes:
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
            return fh.read(TAIL_BYTES)
    except OSError:
        return b""


def jsonl_snippets(path: Path) -> tuple[str, str]:
    """(first_snippet, last_snippet) from a JSONL session file, streaming."""
    head = read_head(path)
    if b"\x00" in head[:8000]:
        return ("[binary — skipped]", "")
    first = ""
    for raw in head.split(b"\n"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if not first:
                first = raw[:400].decode("utf-8", "replace")
            break
        got = extract_text_from_json(obj)
        if got:
            first = got
            break
    last = ""
    for raw in reversed(read_tail(path).split(b"\n")):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        got = extract_text_from_json(obj)
        if got:
            last = got
            break
    return (clean_snippet(first), clean_snippet(last))


def mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "?"


def rec(runtime: str, path: Path, title: str, first: str, last: str) -> dict:
    return {
        "runtime": runtime,
        "path": str(path),
        "date": mtime_iso(path),
        "title": clean_snippet(title)[:120],
        "first": first,
        "last": last,
    }


# --------------------------------------------------------------------------
# Per-runtime walkers. Each yields (unit_path, make_record_callable) lazily.
# --------------------------------------------------------------------------

def walk_cursor():
    """Cursor: agent-transcripts/<session-uuid>/ dirs, each holding jsonl
    fragments. The largest jsonl is the representative transcript."""
    root = HOME / ".cursor" / "projects"
    if not root.is_dir():
        return
    for proj in root.iterdir():
        tdir = proj / "agent-transcripts"
        if not tdir.is_dir():
            continue
        for sess in tdir.iterdir():
            if not sess.is_dir():
                if sess.suffix == ".jsonl":  # tolerate flat layouts too
                    yield sess, lambda f=sess: _jsonl_record("cursor", f)
                continue
            files = sorted(sess.rglob("*.jsonl"),
                           key=lambda p: p.stat().st_size, reverse=True)
            if files:
                f = files[0]
                yield f, lambda f=f: _jsonl_record("cursor", f)


def walk_claude():
    root = HOME / ".claude" / "projects"
    if not root.is_dir():
        return
    for proj in root.iterdir():
        if not proj.is_dir():
            continue
        # top-level *.jsonl are the sessions; subdirectories hold subagent /
        # workflow transcripts which recall-workflow-agent already serves.
        for f in proj.glob("*.jsonl"):
            yield f, lambda f=f: _jsonl_record("claude", f)


def walk_codex():
    root = HOME / ".codex" / "sessions"
    if not root.is_dir():
        return
    for f in root.rglob("rollout-*.jsonl"):
        yield f, lambda f=f: _jsonl_record("codex", f)


def walk_goose():
    root = HOME / "AppData" / "Roaming" / "Block" / "goose" / "data" / "sessions"
    if not root.is_dir():
        return
    for f in root.iterdir():
        if f.is_file():
            yield f, lambda f=f: _jsonl_record("goose", f)


def walk_agy():
    """Antigravity: ~/.gemini/history/<project>/ holds shadow-git workspace
    state, not chat transcripts — catalog one metadata row per project."""
    root = HOME / ".gemini" / "history"
    if not root.is_dir():
        return
    for proj in root.iterdir():
        if not proj.is_dir():
            continue
        yield proj, lambda proj=proj: rec(
            "agy", proj, f"workspace history: {proj.name}",
            "[shadow-git workspace state — no transcript content]", "",
        )


def walk_grok():
    """Grok: metadata only. Session = <root>/<url-encoded-cwd>/<uuid>/ dir.
    Content is intentionally never opened here."""
    root = HOME / ".grok" / "sessions"
    if not root.is_dir():
        return
    from urllib.parse import unquote
    for proj in root.iterdir():
        if not proj.is_dir():
            continue
        cwd = unquote(proj.name)
        for sess in proj.iterdir():
            if not sess.is_dir():
                continue
            yield sess, lambda sess=sess, cwd=cwd: rec(
                "grok", sess, f"{sess.name} @ {cwd}",
                "[content not indexed — metadata-only by policy]", "",
            )


def _jsonl_record(runtime: str, f: Path) -> dict:
    first, last = jsonl_snippets(f)
    title = first if first else f.stem
    return rec(runtime, f, title, first, last)


WALKERS = {
    "cursor": walk_cursor,
    "claude": walk_claude,
    "codex": walk_codex,
    "grok": walk_grok,
    "agy": walk_agy,
    "goose": walk_goose,
}


# --------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            with open(STATE_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            print(f"WARN: state file unreadable, re-indexing from scratch: {STATE_PATH}")
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE_PATH.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, str(STATE_PATH))


def read_existing_frontmatter(catalog_path: Path) -> str:
    """basic-memory's sync adds a YAML frontmatter block; keep it stable
    across rewrites so the vault does not see churn on every run."""
    try:
        with open(catalog_path, encoding="utf-8") as fh:
            head = fh.read(2048)
    except OSError:
        return ""
    if head.startswith("---\n"):
        end = head.find("\n---\n", 4)
        if end != -1:
            return head[: end + 5]
    return ""


def write_catalog(state: dict, catalog_path: Path) -> None:
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = read_existing_frontmatter(catalog_path)
    by_runtime: dict[str, list[dict]] = {}
    for entry in state.values():
        by_runtime.setdefault(entry["record"]["runtime"], []).append(entry["record"])
    fd, tmp = tempfile.mkstemp(dir=str(catalog_path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        if frontmatter:
            out.write(frontmatter + "\n")
        out.write("# AI Session Catalog\n\n")
        out.write(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by "
                  f"`~/.agents/scripts/index-ai-sessions.py` (idempotent; re-run any time).\n"
                  "Pointers only — open the path with the runtime's own tooling "
                  "(format-codex-sessions, recall-workflow-agent, etc.). "
                  "Snippets are redacted and truncated; Grok entries are metadata-only.\n\n")
        counts = {rt: len(v) for rt, v in sorted(by_runtime.items())}
        out.write("| runtime | sessions |\n|---|---|\n")
        for rt, n in counts.items():
            out.write(f"| {rt} | {n} |\n")
        out.write("\n")
        for rt in sorted(by_runtime):
            entries = sorted(by_runtime[rt], key=lambda r: r["date"], reverse=True)
            out.write(f"\n## {rt} ({len(entries)})\n\n")
            for r in entries:
                line = f"- **{r['date']}** — {r['title'] or '(untitled)'} — `{r['path']}`"
                if r["last"] and r["last"] != r["first"]:
                    line += f"\n  - last: {r['last']}"
                out.write(line + "\n")
    os.replace(tmp, str(catalog_path))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="count only, write nothing")
    ap.add_argument("--catalog", default=None, help="override catalog output path")
    args = ap.parse_args()

    catalog_path = Path(args.catalog) if args.catalog else (
        DEFAULT_CATALOG if DEFAULT_CATALOG.parent.parent.is_dir() else FALLBACK_CATALOG
    )

    state = load_state()
    stats = {rt: {"seen": 0, "new": 0, "skipped": 0, "errors": 0} for rt in WALKERS}
    seen_keys: dict[str, set] = {rt: set() for rt in WALKERS}
    walker_completed: dict[str, bool] = {}

    for runtime, walker in WALKERS.items():
        try:
            for path, make_record in walker():
                stats[runtime]["seen"] += 1
                key = str(path)
                seen_keys[runtime].add(key)
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    stats[runtime]["errors"] += 1
                    continue
                cached = state.get(key)
                if cached and cached.get("mtime") == mtime:
                    stats[runtime]["skipped"] += 1
                    continue
                if args.dry_run:
                    stats[runtime]["new"] += 1
                    continue
                try:
                    state[key] = {"mtime": mtime, "record": make_record()}
                    stats[runtime]["new"] += 1
                except Exception as exc:  # one bad session must not kill the run
                    stats[runtime]["errors"] += 1
                    print(f"WARN: {runtime} {path}: {exc}")
            walker_completed[runtime] = True
        except Exception as exc:
            walker_completed[runtime] = False
            print(f"WARN: walker {runtime} failed: {exc}")

    # Prune: drop state entries a COMPLETED walker no longer yields (renamed
    # sessions, or walker-strategy changes). Never prune a runtime whose walk
    # crashed — that would turn a transient error into catalog data loss.
    if not args.dry_run:
        stale = [k for k, v in state.items()
                 if walker_completed.get(v["record"]["runtime"], False)
                 and k not in seen_keys[v["record"]["runtime"]]]
        for k in stale:
            del state[k]
        if stale:
            print(f"pruned {len(stale)} stale entries")

    if not args.dry_run:
        save_state(state)
        write_catalog(state, catalog_path)
        print(f"catalog: {catalog_path}")
        print(f"state:   {STATE_PATH}")

    print("runtime   seen    new/updated  skipped  errors")
    for rt, s in stats.items():
        print(f"{rt:<9} {s['seen']:<7} {s['new']:<12} {s['skipped']:<8} {s['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
