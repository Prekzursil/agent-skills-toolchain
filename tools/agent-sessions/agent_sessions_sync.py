#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_sessions_sync.py — repeatable incremental zero-loss sync of AI-agent session
stores into the vault (default D:/agent-sessions-vault).

Owner mandate (2026-10-18): preserve EVERY agent session on C: and D: (all TUIs),
dedup content-identical sessions but lose nothing. Zero-loss proof = every source
file's sha256 is present in the vault manifest, and every manifest sha256 is
verified present in the vault content.

Design
------
* stores.yaml (next to this script, or --stores PATH) is the single registry the
  owner edits when a new TUI appears.
* Incremental: manifest.jsonl (one JSON line per source file) is the state.
  Quick-check = size + mtime_ns; full sha256 only when they drift (or on --verify).
* NEW file            -> sha256; if that content is already materialized in the
                         vault -> ALIAS entry (no second copy; alias_of points at
                         the canonical vault path). Otherwise verified copy.
* GROWN file (jsonl append/resume: size or mtime changed, sha changed)
                     -> prior vault copy rotated to <vault_path>.prev (one
                        generation, prev sha recorded in the manifest), fresh
                        verified copy, gen += 1. Growth NEVER aliases.
* ALIAS healing       -> if a canonical file later grows, its old content may
                         still be needed by alias lines; alias lines whose target
                         drifted (cheap stat check) are re-materialized from their
                         (unchanged) source.
* mode: rename        -> same-drive adoption for the already-archived
                         D:/codex-sessions-archive-20260621 (owner-sanctioned):
                         os.rename the whole tree into the vault (saves ~56G of
                         copying), verify file/byte counts pre/post, then hash-index
                         it in place. Original path recorded in _ADOPTED_FROM.txt.
                         Never executed in --dry-run. (Legacy alias of mode: move.)
* VAULT DIALECT (v1.2.0, 2026-10-18 sessions-repo-wiring lane) — this engine now
  drives the SAME registry + manifest as the vault-build engine
  (tools/sessions-vault/agent_sessions_sync.py on branch sessions-vault), so the
  watchdog runs ONE coherent pipeline:
  * mode: tree         -> whole tree minus GLOBAL_PRUNE_DIRS (+ store `prune` csv).
  * mode: accepted     -> same walk, files filtered by the session-accept rule
                          (storage_type + name rule IDENTICAL to the vault-build
                          engine / tss/tsis-deepdive/corpus/build_corpus.py).
  * mode: accepted_top / accepted_top2 -> accepted, files at depth 0 / <=1 only.
  * mode: files        -> explicit '|'-separated absolute file list (no `path`).
  * mode: move         -> vault-dialect adoption: if the source still exists and
                          the vault dir does not, os.rename it in (dry-run logs
                          only); if the vault dir ALREADY exists the store is
                          adopted-in-place CALMLY (a completed move means the
                          source is intentionally gone — never a WARN loop).
                          Manifest rows stay keyed by the ORIGINAL source path
                          (src + "/" + rel), matching the live vault manifest.
  * VANISHED files     -> after each copy store's walk, manifest rows of that
                          store whose src was not seen flip to status=missing
                          (kept forever, vault copy retained) — same zero-loss
                          semantics as the vault-build engine.
* Copy discipline     -> copy to <dest>.part, hash the .part, compare to the
                         source hash, only then os.replace. Any mismatch = loss
                         risk = nonzero exit.
* Scheduler friendly  -> no console input; UTF-8 with errors=replace; appends to
                         <vault>/logs/sync-YYYYMMDD.log; writes
                         <vault>/state/last-run.json (rc, counts, timestamps) for
                         the watchdog; single-instance lock <vault>/.sync.lock.

Exit codes
----------
  0  clean (or SKIP: another instance holds the lock)
  1  completed with warnings (missing store never seen before, unreadable files)
  2  LOSS-RISK (verify failure, copy failure, manifest corrupt, missing store that
     previously had entries, adopt count mismatch) — inspect the log + last-run.json

Subcommands / flags
-------------------
  (default)          incremental sync
  --dry-run          plan only, write nothing anywhere (not even state)
  --verify           zero-loss proof: re-plan (must be empty) + re-hash every
                     unique vault file against the manifest; nonzero on any drift
  --restore ID --to DIR
                     materialize store ID from the vault (canonicals + aliases)
  --rediscover       scan common roots on C:/D: for session-looking stores not yet
                     in stores.yaml; print YAML snippets to extend the registry
  --only ID          restrict to one store id (repeatable)
  --stores PATH      alternate stores.yaml
  --vault PATH       alternate vault root
  --quiet            suppress per-file lines on stdout
"""

import argparse
import fnmatch
import hashlib
import io
import json
import os
import shutil
import sys
import time
import traceback

VERSION = "1.2.0"
STAMP_FMT = "%Y-%m-%dT%H:%M:%S"

DEFAULT_STORES_YAML = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "stores.yaml"
)
DEFAULT_VAULT = "D:/agent-sessions-vault"

CHUNK = 1024 * 1024
LOCK_MAX_AGE_S = 12 * 3600  # stale lock takeover
DEFAULT_EXCLUDES = ["*.part", "*.tmp", "*.swp", "desktop.ini", "thumbs.db", ".ds_store"]

# ---- vault dialect (mode: tree / accepted* / files / move) ------------------
# Walk + accept rule byte-compatible with the vault-build engine
# (tools/sessions-vault/agent_sessions_sync.py, branch sessions-vault), which is
# identical to tss/tsis-deepdive/corpus/build_corpus.py::file_accepts. Keeping
# the rule identical means this engine re-walks the live registry EXACTLY as the
# build engine did — no under-copying (loss) and no idle re-copying.
VAULT_WALK_MODES = {"tree", "accepted", "accepted_top", "accepted_top2"}

GLOBAL_PRUNE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

_SESSIONISH = (
    "session",
    "chat",
    "conversation",
    "history",
    "rollout",
    "transcript",
    "dialog",
    "thread",
    "completion",
    "prompt",
)


def storage_type(name):
    n = name.lower()
    if n.endswith(".jsonl.zst"):
        return "zst"
    if n.endswith(".jsonl.gz") or n.endswith(".json.gz"):
        return "gz"
    if n.endswith(".jsonl"):
        return "jsonl"
    if n.endswith(".json"):
        return "json"
    if n.endswith((".sqlite", ".sqlite3", ".db", ".vscdb")):
        return "sqlite"
    return "other"


def accepts(name):
    """Session-file matcher - identical to the vault-build engine + corpus rule."""
    n = name.lower()
    st = storage_type(n)
    if st in ("jsonl", "zst", "gz"):
        return True
    if st == "sqlite":
        if n.endswith(("-shm", "-wal", "-journal")):
            return False
        return True
    if st == "json":
        base = os.path.basename(n)
        if base == "conversations.json" or base.startswith("conversations-"):
            return True
        if base in ("codex.json", "transcript.json", "updates.json", "summary.json"):
            return True
        if any(k in base for k in _SESSIONISH):
            return True
        if base.startswith("local_") or base == "meta.json":
            return True
    return False


def _walk_vault(root, mode, extra_prune_csv=""):
    """Vault-dialect walk: (abs, rel_posix, size, mtime_ns) under root.

    Depth/accept semantics copied from the vault-build engine's walk_root so the
    same registry produces the same file set under either engine.
    """
    prunes = GLOBAL_PRUNE_DIRS | set(x for x in (extra_prune_csv or "").split(",") if x)
    top_only = mode.endswith("_top") and not mode.endswith("_top2")
    top2_only = mode.endswith("_top2")
    use_accept = mode.startswith("accepted")

    if os.path.isfile(lp(root)):  # store root IS a single file
        st = os.stat(lp(root))
        yield up(root), os.path.basename(root), st.st_size, st.st_mtime_ns
        return

    stack = [(lp(root), 0)]
    while stack:
        d, dep = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name in prunes:
                        continue
                    if top_only:
                        continue
                    if top2_only and dep >= 1:
                        continue
                    stack.append((e.path, dep + 1))
                elif e.is_file(follow_symlinks=False):
                    if use_accept and not accepts(e.name):
                        continue
                    st = e.stat(follow_symlinks=False)
                    yield (
                        up(e.path),
                        os.path.relpath(e.path, lp(root)).replace("\\", "/"),
                        st.st_size,
                        st.st_mtime_ns,
                    )
            except OSError:
                continue


# ----------------------------------------------------------------------------
# small utilities
# ----------------------------------------------------------------------------


def lp(path):
    """Normalize to an absolute long path (\\\\?\\-prefixed on Windows)."""
    p = os.path.abspath(path)
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + os.path.normpath(p)
    return p


def up(path):
    """Display/portable form: absolute, forward slashes, no long-path prefix."""
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        p = p[4:]
    return p.replace("\\", "/")


def now_iso():
    return time.strftime(STAMP_FMT)


class Log:
    def __init__(self, vault_root, quiet, dry_run, enabled=True):
        self.quiet = quiet
        self.lines = []
        self.path = None
        if enabled and not dry_run and vault_root:
            d = os.path.join(vault_root, "logs")
            try:
                os.makedirs(d, exist_ok=True)
                self.path = os.path.join(d, "sync-%s.log" % time.strftime("%Y%m%d"))
                # append-open once; keep handle
                self._fh = io.open(
                    lp(self.path), "a", encoding="utf-8", errors="replace"
                )
            except OSError:
                self.path = None
                self._fh = None
        else:
            self._fh = None

    def _emit(self, level, msg):
        line = "%s %s %s" % (now_iso(), level, msg)
        self.lines.append(line)
        if self._fh:
            try:
                self._fh.write(line + "\n")
                self._fh.flush()
            except OSError:
                pass
        if not self.quiet:
            try:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            except OSError:
                pass

    def info(self, msg):
        self._emit("INFO", msg)

    def warn(self, msg):
        self._emit("WARN", msg)

    def err(self, msg):
        self._emit("ERROR", msg)

    def close(self):
        if self._fh:
            try:
                self._fh.close()
            except OSError:
                pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ----------------------------------------------------------------------------
# stores.yaml loading (PyYAML preferred, minimal fallback parser otherwise)
# ----------------------------------------------------------------------------


def _join_flow_lines(text):
    """Join multi-line YAML flow lists (include: ["a",\n  "b"]) into one logical
    line so the line-oriented fallback parser below can handle them."""
    out = []
    buf = None
    for raw in text.splitlines():
        if buf is None:
            s = raw.strip()
            if s.count("[") > s.count("]"):
                buf = raw
            else:
                out.append(raw)
        else:
            buf = buf.rstrip() + " " + raw.strip()
            if buf.strip().count("[") <= buf.strip().count("]"):
                out.append(buf)
                buf = None
    if buf is not None:
        out.append(buf)
    return "\n".join(out)


def _strip_comment(v):
    """Remove a trailing YAML comment from a scalar value, quote-aware."""
    if v and v[0] in "\"'":
        end = v.find(v[0], 1)
        return v if end == -1 else v[: end + 1]
    i = 0
    while True:
        i = v.find("#", i)
        if i == -1:
            return v
        if i == 0 or v[i - 1] in " \t":
            return v[:i].strip()
        i += 1


def _mini_yaml_load(text):
    """Parse the exact stores.yaml subset: top-level scalars + one list of flat
    mappings with scalar values and inline [a, b] lists. Fails loudly on anything
    else so nobody silently gets a mis-parsed registry."""
    text = _join_flow_lines(text)
    root = {}
    current = None  # dict being filled inside the stores list
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            current = None
            if ":" not in line:
                raise ValueError("unparseable line (fallback parser): %r" % raw)
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "":
                if k == "stores":
                    root[k] = []
                else:
                    root[k] = {}
            else:
                root[k] = _scalar(_strip_comment(v))
        else:
            if line.startswith("- "):
                if not isinstance(root.get("stores"), list):
                    raise ValueError("list item outside stores: %r" % raw)
                current = {}
                root["stores"].append(current)
                line = line[2:].strip()
                if ":" not in line:
                    raise ValueError("unparseable list line: %r" % raw)
                k, v = line.split(":", 1)
                current[k.strip()] = _scalar(_strip_comment(v.strip()))
            else:
                if current is None or ":" not in line:
                    raise ValueError("unparseable line (fallback parser): %r" % raw)
                k, v = line.split(":", 1)
                current[k.strip()] = _scalar(_strip_comment(v.strip()))
    return root


def _scalar(v):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_scalar(x.strip()) for x in inner.split(",")]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return v


def load_stores(path):
    with io.open(lp(path), "r", encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ImportError:
        data = _mini_yaml_load(text)
    if not isinstance(data, dict):
        raise ValueError("stores.yaml must be a mapping")
    stores = data.get("stores") or []
    seen = set()
    for s in stores:
        sid = s.get("id")
        if not sid:
            raise ValueError("store entry without id: %r" % (s,))
        if sid in seen:
            raise ValueError("duplicate store id: %s" % sid)
        seen.add(sid)
        if not s.get("path"):
            mode = (s.get("mode") or "").lower()
            if mode != "files" or not s.get("files"):
                raise ValueError("store %s has no path" % sid)
    return data


# ----------------------------------------------------------------------------
# manifest
# ----------------------------------------------------------------------------


class Manifest:
    """manifest.jsonl — one JSON object per source file (keyed by 'src')."""

    def __init__(self, vault_root):
        self.vault_root = vault_root
        self.path = os.path.join(vault_root, "manifest.jsonl")
        self.entries = {}  # src(up) -> dict

    def load(self):
        if not os.path.exists(lp(self.path)):
            return
        bad = 0
        with io.open(lp(self.path), "r", encoding="utf-8") as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if isinstance(obj, dict) and obj.get("src"):
                    self.entries[obj["src"]] = obj
        if bad:
            raise RuntimeError(
                "manifest.jsonl has %d corrupt lines (vault state unsafe) - "
                "restore from manifest.jsonl.bak or rebuild deliberately" % bad
            )

    def sha_index(self):
        """sha256 -> sorted list of vault-relative paths materialized with that sha."""
        idx = {}
        for e in self.entries.values():
            if e.get("vault_path") and e.get("sha256") and e.get("status") == "ok":
                idx.setdefault(e["sha256"], []).append(e["vault_path"])
        for v in idx.values():
            v.sort()
        return idx

    def save_atomic(self):
        tmp = self.path + ".tmp"
        d = os.path.dirname(lp(self.path))
        os.makedirs(d, exist_ok=True)
        with io.open(lp(tmp), "w", encoding="utf-8") as f:
            for src in sorted(self.entries):
                f.write(json.dumps(self.entries[src], sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        # keep one backup generation of the manifest itself
        if os.path.exists(lp(self.path)):
            shutil.copyfile(lp(self.path), lp(self.path + ".bak"))
        os.replace(lp(tmp), lp(self.path))


# ----------------------------------------------------------------------------
# walking / classification
# ----------------------------------------------------------------------------


def _match_any(rel_posix, patterns):
    low = rel_posix.lower()
    for p in patterns or []:
        if fnmatch.fnmatch(low, p.lower()):
            return True
    return False


def _top_segments(patterns):
    segs = set()
    for p in patterns or []:
        first = p.split("/")[0].lower()
        if any(ch in first for ch in "*?["):
            return None  # wildcarded first segment -> cannot prune safely
        segs.add(first)
    return segs or None


def iter_store_files(store, log):
    """Yield (abs_path, rel_posix, size, mtime_ns) for files under store path,
    honoring include/exclude globs (posix-style, case-insensitive)."""
    # ---- vault dialect first (mode: files / tree / accepted*) ----
    vmode = (store.get("mode") or "").lower()
    if vmode == "files":
        for f in [
            x.strip() for x in (store.get("files") or "").split("|") if x.strip()
        ]:
            if os.path.isfile(lp(f)):
                st = os.stat(lp(f))
                yield up(f), os.path.basename(f), st.st_size, st.st_mtime_ns
        return
    if vmode in VAULT_WALK_MODES:
        yield from _walk_vault(store["path"], vmode, store.get("prune", ""))
        return
    # ---- legacy include/exclude dialect (mode copy/rename or absent) ----
    root = store["path"]
    include = store.get("include") or []
    exclude = list(DEFAULT_EXCLUDES) + list(store.get("exclude") or [])
    top = _top_segments(include) if include else None
    for dirpath, dirnames, filenames in os.walk(lp(root), followlinks=False):
        dirnames.sort()
        filenames.sort()
        rel_dir = os.path.relpath(dirpath, lp(root)).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        # prune excluded / non-includable dirs
        keep = []
        for dn in dirnames:
            rdir = (rel_dir + "/" + dn) if rel_dir else dn
            if _match_any(rdir, exclude) or _match_any(rdir + "/**", exclude):
                continue
            if top is not None and (rel_dir == "" and dn.lower() not in top):
                continue
            keep.append(dn)
        dirnames[:] = keep
        for fn in filenames:
            rel = (rel_dir + "/" + fn) if rel_dir else fn
            if _match_any(rel, exclude):
                continue
            if include and not _match_any(rel, include):
                continue
            ap = os.path.join(dirpath, fn)
            try:
                st = os.stat(lp(ap))
            except OSError as e:
                log.warn("stat failed %s: %s" % (up(ap), e))
                continue
            if not os.path.isfile(lp(ap)):
                continue
            yield up(ap), rel, st.st_size, st.st_mtime_ns


def walk_counts(root):
    files = 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(lp(root), followlinks=False):
        dirnames.sort()
        for fn in sorted(filenames):
            try:
                st = os.stat(lp(os.path.join(dirpath, fn)))
                files += 1
                total += st.st_size
            except OSError:
                files += 1  # count it, size unknown — count integrity is the gate
    return files, total


# ----------------------------------------------------------------------------
# sync engine
# ----------------------------------------------------------------------------


class Syncer:
    def __init__(self, args):
        self.args = args
        self.vault = args.vault
        self.dry = args.dry_run
        self.log = Log(self.vault, args.quiet, self.dry)
        self.man = Manifest(self.vault)
        self.warnings = 0
        self.lossrisk = 0
        self.stats = {
            "new": 0,
            "new_alias": 0,
            "grown": 0,
            "rematerialized": 0,
            "unchanged": 0,
            "adopted_files": 0,
            "bytes_copied": 0,
            "bytes_saved_by_alias": 0,
            "bytes_saved_by_rename": 0,
            "unreadable": 0,
            "missing_stores": 0,
        }

    # ---- helpers ----

    def vault_rel(self, store_id, rel):
        return "stores/%s/%s" % (store_id, rel)

    def vault_abs(self, vrel):
        return os.path.join(self.vault, vrel.replace("/", os.sep))

    def note_warn(self, msg):
        self.warnings += 1
        self.log.warn(msg)

    def note_loss(self, msg):
        self.lossrisk += 1
        self.log.err(msg)

    # ---- lock ----

    def acquire_lock(self):
        if self.dry:
            return True
        lock = os.path.join(self.vault, ".sync.lock")
        os.makedirs(lp(self.vault), exist_ok=True)
        try:
            fd = os.open(lp(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                st = os.stat(lp(lock))
                age = time.time() - st.st_mtime
            except OSError:
                age = 0
            if age > LOCK_MAX_AGE_S:
                try:
                    os.remove(lp(lock))
                    self.log.warn("removed stale lock (age %.1fh)" % (age / 3600.0))
                    fd = os.open(lp(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except OSError as e:
                    self.note_loss("cannot take over stale lock: %s" % e)
                    return False
            else:
                # concurrent instance: skip cleanly (watchdog pattern), not a loss
                self.log.info(
                    "SKIP another sync instance holds the lock (%s)" % up(lock)
                )
                return False
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"pid": os.getpid(), "started": now_iso()}))
        self._lock_path = lock
        return True

    def release_lock(self):
        p = getattr(self, "_lock_path", None)
        if p:
            try:
                os.remove(lp(p))
            except OSError:
                pass

    # ---- core copy ----

    def verified_copy(self, src_abs, dst_abs, src_sha=None):
        """Copy src -> dst via .part + hash verify. Returns sha or None on failure."""
        ddir = os.path.dirname(lp(dst_abs))
        os.makedirs(ddir, exist_ok=True)
        tmp = lp(dst_abs) + ".part"
        try:
            if src_sha is None:
                src_sha = sha256_file(src_abs)
            shutil.copyfile(lp(src_abs), tmp)
            got = sha256_file(tmp)
            if got != src_sha:
                self.note_loss(
                    "VERIFY-FAIL copy %s -> %s (sha mismatch)"
                    % (up(src_abs), up(dst_abs))
                )
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                return None
            os.replace(tmp, lp(dst_abs))
            self.stats["bytes_copied"] += os.stat(lp(dst_abs)).st_size
            return src_sha
        except OSError as e:
            self.note_loss("copy failed %s -> %s: %s" % (up(src_abs), up(dst_abs), e))
            try:
                os.remove(tmp)
            except OSError:
                pass
            return None

    # ---- adopt (rename) mode ----

    def adopt_move(self, store, sid, sha_idx):
        """Vault-dialect adoption (mode: move; legacy alias: mode: rename).

        - src present, vault dir absent  -> os.rename into the vault (never in
          --dry-run), file/byte counts verified pre/post, _ADOPTED_FROM.txt.
        - vault dir present, src absent  -> CALM adopt-in-place: a completed
          move means the source is intentionally gone (steady state for
          D:/codex-sessions-archive-20260621 since 2026-10-18 09:11).
        - both present                   -> conflict = loss-risk (never overwrite).
        - neither                       -> "missing" (caller flags the store).

        Indexing is hash-only (no copying) and keys manifest rows by the
        ORIGINAL source path (src + "/" + rel) — byte-compatible with the
        vault-build engine's adopt_moved, so both engines share one manifest
        without duplicating rows for the same physical files.
        """
        src = up(store["path"])
        dest = self.vault_abs("stores/" + sid)
        walk_mode = store.get("walk", "tree")
        if not os.path.exists(lp(dest)):
            if not os.path.exists(lp(src)):
                return "missing"
            if self.dry:
                files, total = walk_counts(src)
                self.stats["bytes_saved_by_rename"] += total
                self.log.info(
                    "[dry-run] MOVE %s: %s -> %s (%d files, %d bytes)"
                    % (sid, src, up(dest), files, total)
                )
                return "planned"
            files_pre, total_pre = walk_counts(src)
            # same-drive rename (os.rename across drives fails; message via OSError)
            try:
                os.rename(lp(src), lp(dest))
            except OSError as e:
                self.note_loss("move %s failed: %s" % (sid, e))
                return "failed"
            files_post, total_post = walk_counts(dest)
            if files_post != files_pre or total_post != total_pre:
                self.note_loss(
                    "move %s COUNT MISMATCH pre=%d/%d post=%d/%d "
                    "- inspect immediately"
                    % (sid, files_pre, total_pre, files_post, total_post)
                )
                return "mismatch"
            with io.open(
                lp(os.path.join(lp(dest), "_ADOPTED_FROM.txt")), "w", encoding="utf-8"
            ) as f:
                f.write(
                    "adopted_by_move_from: %s\nadopted_at: %s\n"
                    "files: %d\nbytes: %d\n" % (src, now_iso(), files_post, total_post)
                )
            self.stats["bytes_saved_by_rename"] += total_pre
            self.log.info(
                "MOVE %s: renamed %s into vault (%d files, %d bytes, "
                "0 bytes copied)" % (sid, src, files_post, total_post)
            )
        else:
            if os.path.exists(lp(src)):
                self.note_loss(
                    "move %s: BOTH source and vault dir exist "
                    "(%s / %s) - refusing to touch either" % (sid, src, up(dest))
                )
                return "conflict"
            self.log.info(
                "ADOPT %s: vault dir present (move already complete) - "
                "re-indexing in place, rows keyed by original source "
                "path" % sid
            )
        # index in place: hash-only, no copying; rows keyed by ORIGINAL src path
        adopted = 0
        for ap, rel, size, mns in iter_store_files(
            dict(store, path=up(dest), mode=walk_mode), self.log
        ):
            if rel == "_ADOPTED_FROM.txt":
                continue
            orig_src = src + "/" + rel
            e = self.man.entries.get(orig_src)
            if (
                e
                and e.get("status") == "ok"
                and e.get("size") == size
                and e.get("mtime_ns") == mns
            ):
                e["last_synced"] = now_iso()
                self.stats["unchanged"] += 1
                continue
            try:
                sha = sha256_file(ap)
            except OSError as ex:
                self.note_warn("unreadable adopted file %s: %s" % (up(ap), ex))
                self.stats["unreadable"] += 1
                self.man.entries[orig_src] = {
                    "src": orig_src,
                    "store": sid,
                    "tui": store.get("tui", sid),
                    "vault_path": self.vault_rel(sid, rel),
                    "alias_of": None,
                    "sha256": None,
                    "size": size,
                    "mtime_ns": mns,
                    "gen": 0,
                    "prev": None,
                    "first_seen": e["first_seen"] if e else now_iso(),
                    "last_synced": now_iso(),
                    "status": "unreadable",
                }
                continue
            first = now_iso()
            gen = 0
            prev = None
            if e:
                first = e.get("first_seen", first)
                if e.get("status") == "ok":
                    prev = {"sha256": e.get("sha256"), "size": e.get("size")}
                    gen = e.get("gen", 0) + 1
            vrel = self.vault_rel(sid, rel)
            alias_of = None
            targets = sha_idx.get(sha) if sha_idx else None
            if targets:
                alias_of = targets[0]
            self.man.entries[orig_src] = {
                "src": orig_src,
                "store": sid,
                "tui": store.get("tui", sid),
                "vault_path": vrel,
                "alias_of": alias_of,
                "sha256": sha,
                "size": size,
                "mtime_ns": mns,
                "gen": gen,
                "prev": prev,
                "first_seen": first,
                "last_synced": now_iso(),
                "status": "ok",
            }
            # the physical file lives at vrel (renamed-in tree) — a valid
            # canonical target for later stores
            if not alias_of:
                sha_idx.setdefault(sha, []).append(vrel)
                sha_idx[sha].sort()
            adopted += 1
            if adopted % 500 == 0:
                self.log.info("  adopt %s: %d files re-indexed" % (sid, adopted))
        self.stats["adopted_files"] += adopted
        self.log.info("ADOPT-DONE %s: %d file(s) indexed in place" % (sid, adopted))
        return "adopted"

    # ---- main sync ----

    def run(self):
        data = load_stores(self.args.stores)
        stores = data.get("stores") or []
        only = set(self.args.only or [])
        if not self.dry:
            os.makedirs(lp(self.vault), exist_ok=True)
        if not self.acquire_lock():
            self.write_state(0, "skip-lock")
            return 0
        try:
            self.man.load()
            sha_idx = self.man.sha_index()
            for store in stores:
                sid = store["id"]
                if only and sid not in only:
                    continue
                mode = (store.get("mode") or "copy").lower()
                if mode in ("move", "rename", "adopt-rename"):
                    res = self.adopt_move(store, sid, sha_idx)
                    if res == "missing":
                        self.handle_missing_store(store)
                    continue
                self.sync_copy_store(store, sha_idx)
            if not self.dry:
                self.man.save_atomic()
                self.write_summary()
            rc = 2 if self.lossrisk else (1 if self.warnings else 0)
            self.log.info(
                "RUN COMPLETE rc=%d stats=%s"
                % (rc, json.dumps(self.stats, sort_keys=True))
            )
            self.write_state(rc, "done")
            return rc
        finally:
            self.release_lock()
            self.log.close()

    def handle_missing_store(self, store):
        sid = store["id"]
        self.stats["missing_stores"] += 1
        n = sum(1 for e in self.man.entries.values() if e.get("store") == sid)
        if n:
            self.note_loss(
                "store %s MISSING but has %d manifest entries - "
                "possible source loss" % (sid, n)
            )
        else:
            self.note_warn(
                "store %s path missing (never synced): %s"
                % (sid, store.get("path") or store.get("files"))
            )

    def sync_copy_store(self, store, sha_idx):
        sid = store["id"]
        if store.get("path"):
            root = up(store["path"])
            if not (os.path.isdir(lp(root)) or os.path.isfile(lp(root))):
                self.handle_missing_store(store)
                return
        elif not store.get("files"):
            # neither path nor files list — unusable entry
            self.handle_missing_store(store)
            return
        seen_srcs = set()
        for ap, rel, size, mns in iter_store_files(store, self.log):
            seen_srcs.add(ap)
            e = self.man.entries.get(ap)
            vrel = self.vault_rel(sid, rel)
            vabs = self.vault_abs(vrel)
            if (
                e
                and e.get("status") == "ok"
                and e.get("size") == size
                and e.get("mtime_ns") == mns
            ):
                # quick-check unchanged — but heal aliases whose target drifted
                if e.get("alias_of"):
                    tgt = self.vault_abs(e["alias_of"])
                    ok = True
                    try:
                        tsz = os.stat(lp(tgt)).st_size
                    except OSError:
                        ok = False
                    else:
                        ok = tsz == e.get("size")
                    if not ok:
                        self.log.info(
                            "REMAT %s: alias target drifted; "
                            "materializing own copy" % ap
                        )
                        sha = self.verified_copy(ap, vabs)
                        if sha:
                            e.update(
                                {
                                    "vault_path": vrel,
                                    "alias_of": None,
                                    "sha256": sha,
                                    "size": size,
                                    "mtime_ns": mns,
                                    "last_synced": now_iso(),
                                }
                            )
                            self.stats["rematerialized"] += 1
                        continue
                self.stats["unchanged"] += 1
                continue
            # drifted or new: need the source hash (dry-run stays fast for new)
            if self.dry and e is None:
                self.log.info("[dry-run] NEW %s (%d bytes)" % (ap, size))
                self.stats["new"] += 1
                continue
            try:
                sha = sha256_file(ap)
            except OSError as ex:
                self.note_warn("unreadable %s: %s" % (ap, ex))
                self.stats["unreadable"] += 1
                self.man.entries[ap] = {
                    "src": ap,
                    "store": sid,
                    "tui": store.get("tui", sid),
                    "vault_path": None,
                    "alias_of": None,
                    "sha256": None,
                    "size": size,
                    "mtime_ns": mns,
                    "gen": 0,
                    "prev": None,
                    "first_seen": e["first_seen"] if e else now_iso(),
                    "last_synced": now_iso(),
                    "status": "unreadable",
                }
                continue
            if e and e.get("status") == "ok" and e.get("sha256") == sha:
                # mtime-only churn: content identical
                e.update({"size": size, "mtime_ns": mns, "last_synced": now_iso()})
                self.stats["unchanged"] += 1
                continue
            if e and e.get("status") == "ok":
                # GROWN (or truncated): rotate .prev, re-copy, never alias
                self.log.info(
                    "GROWN %s (gen %s -> %s)"
                    % (ap, e.get("gen", 0), e.get("gen", 0) + 1)
                )
                if self.dry:
                    self.stats["grown"] += 1
                    continue
                prev_sha = e.get("sha256")
                prev_size = e.get("size")
                old_vabs = (
                    self.vault_abs(e["vault_path"]) if e.get("vault_path") else None
                )
                if old_vabs and os.path.exists(lp(old_vabs)):
                    prevp = lp(old_vabs) + ".prev"
                    try:
                        if os.path.exists(prevp):
                            os.remove(prevp)  # keep exactly one generation
                        os.replace(lp(old_vabs), prevp)
                    except OSError as ex:
                        self.note_loss(
                            "prev-rotation failed %s: %s" % (up(old_vabs), ex)
                        )
                got = self.verified_copy(ap, vabs, src_sha=sha)
                if got:
                    e.update(
                        {
                            "vault_path": vrel,
                            "alias_of": None,
                            "sha256": sha,
                            "size": size,
                            "mtime_ns": mns,
                            "gen": e.get("gen", 0) + 1,
                            "prev": {"sha256": prev_sha, "size": prev_size},
                            "last_synced": now_iso(),
                        }
                    )
                    self.stats["grown"] += 1
                continue
            # NEW (or recovering from unreadable): dedup by content
            targets = sha_idx.get(sha) if sha_idx else None
            if targets:
                tgt = targets[0]
                if self.dry:
                    self.stats["new_alias"] += 1
                    self.log.info("[dry-run] NEW-ALIAS %s == %s" % (ap, tgt))
                    continue
                self.man.entries[ap] = {
                    "src": ap,
                    "store": sid,
                    "tui": store.get("tui", sid),
                    "vault_path": None,
                    "alias_of": tgt,
                    "sha256": sha,
                    "size": size,
                    "mtime_ns": mns,
                    "gen": 0,
                    "prev": None,
                    "first_seen": e["first_seen"] if e else now_iso(),
                    "last_synced": now_iso(),
                    "status": "ok",
                }
                self.stats["new_alias"] += 1
                self.stats["bytes_saved_by_alias"] += size
                self.log.info(
                    "ALIAS %s == %s (dedup, %d bytes saved)" % (ap, tgt, size)
                )
                continue
            if self.dry:
                self.log.info("[dry-run] NEW %s (%d bytes)" % (ap, size))
                self.stats["new"] += 1
                continue
            got = self.verified_copy(ap, vabs, src_sha=sha)
            if got:
                self.man.entries[ap] = {
                    "src": ap,
                    "store": sid,
                    "tui": store.get("tui", sid),
                    "vault_path": vrel,
                    "alias_of": None,
                    "sha256": sha,
                    "size": size,
                    "mtime_ns": mns,
                    "gen": 0,
                    "prev": None,
                    "first_seen": e["first_seen"] if e else now_iso(),
                    "last_synced": now_iso(),
                    "status": "ok",
                }
                sha_idx.setdefault(sha, []).append(vrel)
                sha_idx[sha].sort()
                self.stats["new"] += 1
                self.log.info("NEW %s (%d bytes) sha=%s" % (ap, size, sha[:12]))

        # VANISHED: rows of this store whose src was NOT seen this walk flip to
        # status=missing — kept forever, vault copies retained (zero-loss: the
        # manifest records the source's history instead of lying with ok).
        # Move stores are exempt: their rows are keyed by the ORIGINAL source
        # path and are reconciled inside adopt_move instead.
        vanished = 0
        for src_key, e in self.man.entries.items():
            if (
                e.get("store") == sid
                and e.get("status") == "ok"
                and src_key not in seen_srcs
            ):
                e["status"] = "missing"
                vanished += 1
        if vanished:
            self.log.info(
                "VANISHED %s: %d file(s) gone from source - rows kept "
                "as status=missing (vault copies retained)" % (sid, vanished)
            )

    # ---- state / summary ----

    def write_state(self, rc, phase):
        if self.dry:
            return
        try:
            d = os.path.join(self.vault, "state")
            os.makedirs(d, exist_ok=True)
            with io.open(
                lp(os.path.join(d, "last-run.json")), "w", encoding="utf-8"
            ) as f:
                json.dump(
                    {
                        "rc": rc,
                        "phase": phase,
                        "finished": now_iso(),
                        "version": VERSION,
                        "stats": self.stats,
                        "warnings": self.warnings,
                        "lossrisk": self.lossrisk,
                    },
                    f,
                    indent=1,
                    sort_keys=True,
                )
        except OSError as e:
            sys.stderr.write("FATAL cannot write state: %s\n" % e)
            sys.exit(2)

    def write_summary(self):
        per = {}
        for e in self.man.entries.values():
            s = per.setdefault(
                e.get("store", "?"),
                {"files": 0, "aliases": 0, "bytes": 0, "unreadable": 0},
            )
            if e.get("status") == "ok":
                s["files"] += 1
                s["bytes"] += e.get("size") or 0
                if e.get("alias_of"):
                    s["aliases"] += 1
            else:
                s["unreadable"] += 1
        out = {
            "generated": now_iso(),
            "version": VERSION,
            "total_entries": len(self.man.entries),
            "stores": per,
        }
        p = os.path.join(self.vault, "manifest-summary.json")
        tmp = p + ".tmp"
        with io.open(lp(tmp), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, sort_keys=True)
        os.replace(lp(tmp), lp(p))


# ----------------------------------------------------------------------------
# --verify : zero-loss proof
# ----------------------------------------------------------------------------


def cmd_verify(args):
    man = Manifest(args.vault)
    man.load()
    syncer = Syncer(args)  # for logging only
    log = syncer.log
    # pass 1: hash every unique materialized vault file once
    unique = {}
    for e in man.entries.values():
        vp = e.get("vault_path")
        sha = e.get("sha256")
        if vp and sha and vp not in unique:
            unique[vp] = sha
    bad = 0
    hashed = 0
    for vp, sha in sorted(unique.items()):
        ap = os.path.join(args.vault, vp.replace("/", os.sep))
        try:
            got = sha256_file(ap)
        except OSError as ex:
            log.err("MISSING vault file %s: %s" % (vp, ex))
            bad += 1
            continue
        hashed += 1
        if got != sha:
            log.err("HASH DRIFT %s manifest=%s actual=%s" % (vp, sha, got))
            bad += 1
    # pass 2: every manifest line must be provable
    ok_lines = 0
    alias_broken = 0
    for src, e in sorted(man.entries.items()):
        if e.get("status") != "ok":
            continue
        sha = e.get("sha256")
        if e.get("alias_of"):
            tgt = e["alias_of"]
            if unique.get(tgt) == sha:
                ok_lines += 1
            else:
                alias_broken += 1
                log.err(
                    "BROKEN ALIAS %s -> %s (target drifted; re-run sync "
                    "to rematerialize)" % (src, tgt)
                )
        else:
            if unique.get(e.get("vault_path")) == sha:
                ok_lines += 1
            else:
                bad += 1
    # pass 3: sources must be current (no pending new/grown) — reuse dry-run plan
    pending = plan_pending(args, man)
    log.info(
        "VERIFY unique-vault-files=%d hashed=%d ok-manifest-lines=%d "
        "alias-broken=%d bad=%d pending-at-source=%d"
        % (len(unique), hashed, ok_lines, alias_broken, bad, pending)
    )
    verdict_ok = bad == 0 and alias_broken == 0 and pending == 0
    log.info(
        "ZERO-LOSS PROOF: %s"
        % (
            "PASS — every source file's sha256 is present & verified in the "
            "vault, and no source changes are pending"
            if verdict_ok
            else "FAIL — see ERROR lines above (vault incomplete or stale)"
        )
    )
    syncer.log.close()
    return 0 if verdict_ok else 2


def plan_pending(args, man):
    """Count source files that would need action (new/grown). Read-only."""
    args.quiet = True
    s = Syncer(args)
    data = load_stores(args.stores)
    for store in data.get("stores") or []:
        mode = (store.get("mode") or "copy").lower()
        if mode in ("move", "rename", "adopt-rename"):
            src = up(store["path"])
            dest = os.path.join(args.vault, "stores", store["id"])
            if os.path.exists(lp(src)) and not os.path.exists(lp(dest)):
                s.stats["new"] += 1
            elif (
                not os.path.exists(lp(src))
                and not os.path.exists(lp(dest))
                and any(e.get("store") == store["id"] for e in man.entries.values())
            ):
                s.stats["missing_stores"] += 1
            # vault dir present (with or without src) = adopted/calm -> not pending
            continue
        if mode == "files":
            for f in [
                x.strip() for x in (store.get("files") or "").split("|") if x.strip()
            ]:
                if not os.path.isfile(lp(f)):
                    continue
                st = os.stat(lp(f))
                e = man.entries.get(up(f))
                if (
                    e
                    and e.get("status") == "ok"
                    and e.get("size") == st.st_size
                    and e.get("mtime_ns") == st.st_mtime_ns
                ):
                    continue
                if e and e.get("status") == "ok":
                    s.stats["grown"] += 1
                else:
                    s.stats["new"] += 1
            continue
        root = up(store["path"])
        if not (os.path.isdir(lp(root)) or os.path.isfile(lp(root))):
            if any(e.get("store") == store["id"] for e in man.entries.values()):
                s.stats["missing_stores"] += 1
            continue
        for ap, rel, size, mns in iter_store_files(store, s.log):
            e = man.entries.get(ap)
            if (
                e
                and e.get("status") == "ok"
                and e.get("size") == size
                and e.get("mtime_ns") == mns
            ):
                continue
            if e and e.get("status") == "ok":
                s.stats["grown"] += 1
            else:
                s.stats["new"] += 1
    return s.stats["new"] + s.stats["grown"] + s.stats["missing_stores"]


# ----------------------------------------------------------------------------
# --restore
# ----------------------------------------------------------------------------


def cmd_restore(args):
    if not args.to:
        sys.stderr.write("--restore requires --to DIR\n")
        return 2
    man = Manifest(args.vault)
    man.load()
    data = load_stores(args.stores)
    store = None
    for s in data.get("stores") or []:
        if s["id"] == args.restore:
            store = s
            break
    if store is None:
        sys.stderr.write("unknown store id: %s\n" % args.restore)
        return 2
    dest_root = up(args.to)
    log = Log(args.vault, args.quiet, False)
    n = fail = 0
    for src in sorted(man.entries):
        e = man.entries[src]
        if e.get("store") != args.restore or e.get("status") != "ok":
            continue
        rel = e["src"]
        pref = up(store["path"]).rstrip("/") + "/"
        if rel.startswith(pref):
            rel = rel[len(pref) :]
        dst = os.path.join(dest_root, rel.replace("/", os.sep))
        src_vault = e.get("alias_of") or e.get("vault_path")
        if not src_vault:
            continue
        sp = os.path.join(args.vault, src_vault.replace("/", os.sep))
        try:
            os.makedirs(os.path.dirname(lp(dst)), exist_ok=True)
            shutil.copyfile(lp(sp), lp(dst))
            if sha256_file(dst) != e["sha256"]:
                log.err("restore hash mismatch %s" % dst)
                fail += 1
                continue
            n += 1
        except OSError as ex:
            log.err("restore failed %s: %s" % (dst, ex))
            fail += 1
    log.info(
        "RESTORE %s -> %s: %d files ok, %d failed" % (args.restore, dest_root, n, fail)
    )
    log.close()
    return 0 if fail == 0 else 2


# ----------------------------------------------------------------------------
# --rediscover
# ----------------------------------------------------------------------------

REDISCOVER_ROOTS = [
    "C:/Users/Prekzursil",
    "C:/Users/Prekzursil/AppData/Roaming",
    "C:/Users/Prekzursil/AppData/Local",
    "C:/Users/Prekzursil/Documents",
    "C:/Users/Prekzursil/Cowork",
    "D:/",
]
SESSION_HINTS = ("session", "transcript", "chat", "rollout", "conversations", "history")
FILE_HINTS = (".jsonl", ".jsonl.zst", ".zst", ".db")


def cmd_rediscover(args):
    data = load_stores(args.stores)
    known = set()
    for s in data.get("stores") or []:
        known.add(up(s["path"]).lower().rstrip("/"))
    print(
        "# rediscover %s — candidate session stores NOT yet in stores.yaml" % now_iso()
    )
    print(
        "# review each, then paste accepted entries into stores.yaml "
        "(the registry is the single source of truth)"
    )
    found = 0
    for root in REDISCOVER_ROOTS:
        try:
            entries = sorted(os.listdir(lp(root)))
        except OSError:
            continue
        for name in entries:
            cand = os.path.join(root, name)
            if not os.path.isdir(lp(cand)):
                continue
            if up(cand).lower().rstrip("/") in known:
                continue
            score = 0
            n_checked = 0
            for dp, dns, fns in os.walk(lp(cand), followlinks=False):
                dns[:] = [
                    d
                    for d in dns
                    if d.lower() not in ("node_modules", ".git", "__pycache__")
                ]
                low = dp.lower()
                if any(h in low for h in SESSION_HINTS):
                    score += 2
                for fn in fns:
                    if fn.lower().endswith(FILE_HINTS):
                        score += 1
                        if fn.lower().endswith(".jsonl"):
                            score += 1
                n_checked += 1
                if n_checked > 400 or score > 12:
                    dns[:] = []
            if score >= 4:
                found += 1
                print(
                    '  - id: CHANGEME-%d\n    tui: "%s"\n    path: "%s"'
                    % (found, name, up(cand))
                )
    if found == 0:
        print("  # (no new candidates above threshold)")
    print("# end rediscover (%d candidates)" % found)
    return 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------


def main(argv=None):
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        description="Incremental zero-loss sync of AI-agent session stores "
        "into the vault"
    )
    ap.add_argument(
        "--stores",
        default=DEFAULT_STORES_YAML,
        help="path to stores.yaml (default: %(default)s)",
    )
    ap.add_argument(
        "--vault", default=DEFAULT_VAULT, help="vault root (default: %(default)s)"
    )
    ap.add_argument(
        "--only",
        action="append",
        metavar="ID",
        help="restrict to this store id (repeatable)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only; write nothing (no state, no manifest)",
    )
    ap.add_argument(
        "--verify",
        action="store_true",
        help="zero-loss proof: re-hash the vault vs the manifest",
    )
    ap.add_argument(
        "--restore",
        metavar="ID",
        help="materialize store ID from the vault (needs --to)",
    )
    ap.add_argument("--to", metavar="DIR", help="restore destination")
    ap.add_argument(
        "--rediscover",
        action="store_true",
        help="suggest stores.yaml additions from a bounded scan",
    )
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument(
        "--version", action="version", version="agent_sessions_sync.py " + VERSION
    )
    args = ap.parse_args(argv)

    try:
        if args.rediscover:
            return cmd_rediscover(args)
        if args.restore:
            return cmd_restore(args)
        if args.verify:
            return cmd_verify(args)
        return Syncer(args).run()
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 2
    except Exception as e:
        sys.stderr.write("FATAL %s\n%s\n" % (e, traceback.format_exc()))
        return 2


if __name__ == "__main__":
    sys.exit(main())
