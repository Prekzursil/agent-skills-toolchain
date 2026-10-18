#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_sessions_sync.py - repeatable, incremental, zero-loss agent-session vault sync.

Read-only on every source. The vault receives copies; the ONLY mutation ever applied to a
source is the explicitly-configured same-volume MOVE (mode: move) of an already-archived
tree (owner-approved: D:/codex-sessions-archive-20260621), performed as an os.rename so no
bytes are copied and the tree stays intact inside the vault. After the rename the tree is
adopted: every file hashed in place and indexed with src=original path.

Manifest schema (merge-compatible with the 2026-10-18 fixture bootstrap run):
  {alias_of, first_seen, gen, last_synced, mtime_ns, prev, sha256, size, src,
   status, store, tui, vault_path}

Semantics:
  * incremental: size+mtime_ns match on an ok record => keep cached sha256 (no re-read).
  * grown source (session resumed): recopy, gen+1, prev={sha256,size} preserved.
  * vanished source: status="missing", record NEVER dropped.
  * content dedup: identical sha256 across stores = ONE physical vault copy; later files
    get alias_of=<canonical vault_path>. If the canonical later grows, aliases whose own
    recorded hash no longer matches the canonical rematerialize their own copy from their
    own source (zero loss per file). Identity is per-file sha256 only - no file lineage
    is ever assumed (control fact: a prior merge bug dropped 47.1% of the Codex store).
  * every physical copy is hashed during the copy pass (single read).
  * verify: sources re-scanned; <50MB re-hashed vs manifest; >=50MB size+mtime_ns tier
    (owner-specified). Vault-side existence checked for every entry. Live-changed files
    are reported as changed_live (re-run sync to converge), not silently passed.

Usage:
  python agent_sessions_sync.py sync   [--dry-run] [--stores a,b] [--limit-bytes N]
  python agent_sessions_sync.py verify [--stores a,b]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
import time

CHUNK = 4 * 1024 * 1024
LARGE_FILE = 50 * 1024 * 1024          # verification tier boundary (owner-specified)
READ_RETRIES = 3
READ_RETRY_WAIT = 2.0

VAULT_MANIFEST = "manifest.jsonl"
VAULT_STATE = "state"
VAULT_STORES = "stores"
VAULT_LOGS = "logs"

GLOBAL_PRUNE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv",
                     ".mypy_cache", ".pytest_cache", ".ruff_cache"}

_SESSIONISH = ("session", "chat", "conversation", "history", "rollout", "transcript",
               "dialog", "thread", "completion", "prompt")


# ---------------------------------------------------------------- yaml subset
def load_yaml(path):
    """Minimal YAML for our schema: top-level scalars + one list of flat dicts."""
    top = {}
    items = []
    cur = None
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            body = line.strip()
            if body.startswith("- "):
                cur = {}
                items.append(cur)
                body = body[2:]
            if ":" in body:
                key, _, val = body.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if not val and key not in ("prune", "files"):
                    val = ""
                if indent == 0 and cur is None:
                    top[key] = val
                elif cur is not None:
                    cur[key] = val
    top["stores"] = items
    return top


# ---------------------------------------------------------------- accept rule
def storage_type(name: str) -> str:
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


def accepts(name: str) -> bool:
    """Session-file matcher - identical to tss/tsis-deepdive/corpus/build_corpus.py."""
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


# ---------------------------------------------------------------- helpers
def now_iso():
    return _dt.datetime.now().isoformat(timespec="seconds")


def log_line(vault, msg):
    line = f"[{now_iso()}] {msg}"
    print(line, file=sys.stderr, flush=True)
    d = os.path.join(vault, VAULT_LOGS)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sync-current.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def fwd(p):
    """Normalize a Windows path to forward slashes (bootstrap manifest src format)."""
    return p.replace("\\", "/")


def read_chunks_with_retry(path, n_tries=READ_RETRIES):
    """Yield chunks; retry the whole file on transient sharing violations."""
    last = None
    for attempt in range(n_tries):
        try:
            with open(path, "rb", buffering=0) as fh:
                while True:
                    b = fh.read(CHUNK)
                    if not b:
                        return
                    yield b
            return
        except OSError as ex:
            last = ex
            time.sleep(READ_RETRY_WAIT * (attempt + 1))
    raise last


def hash_and_copy(src, dst, set_mtime_ns):
    """Single-pass: read src, sha256 it, write dst (tmp+replace). Returns sha256."""
    h = hashlib.sha256()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    with open(tmp, "wb") as out:
        for b in read_chunks_with_retry(src):
            h.update(b)
            out.write(b)
    os.replace(tmp, dst)
    os.utime(dst, ns=(set_mtime_ns, set_mtime_ns))
    return h.hexdigest()


def hash_only(path):
    h = hashlib.sha256()
    for b in read_chunks_with_retry(path):
        h.update(b)
    return h.hexdigest()


def atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


# ---------------------------------------------------------------- walking
def walk_root(root, mode, extra_prune_csv=""):
    """Yield (abs_path, rel_path, size, mtime_ns) per selected file under root."""
    prunes = GLOBAL_PRUNE_DIRS | set(x for x in (extra_prune_csv or "").split(",") if x)
    top_only = mode.endswith("_top")
    top2_only = mode.endswith("_top2")
    use_accept = mode.startswith("accepted")

    if os.path.isfile(root):  # store root IS a single file
        st = os.stat(root)
        yield root, os.path.basename(root), st.st_size, st.st_mtime_ns
        return

    stack = [(root, 0)]
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
                    yield e.path, os.path.relpath(e.path, root).replace("\\", "/"), st.st_size, st.st_mtime_ns
            except OSError:
                continue


def iter_store_files(store):
    mode = store.get("mode", "tree")
    if mode == "files":
        for f in [x.strip() for x in (store.get("files") or "").split("|") if x.strip()]:
            if os.path.isfile(f):
                st = os.stat(f)
                yield f, os.path.basename(f), st.st_size, st.st_mtime_ns
        return
    yield from walk_root(store["path"], mode, store.get("prune", ""))


# ---------------------------------------------------------------- engine
class Engine:
    def __init__(self, cfg):
        self.vault = cfg["vault"]
        self.reserve = float(cfg.get("reserve_gb", 20)) * 1e9
        self.stores = cfg["stores"]
        os.makedirs(os.path.join(self.vault, VAULT_STORES), exist_ok=True)
        os.makedirs(os.path.join(self.vault, VAULT_STATE), exist_ok=True)
        os.makedirs(os.path.join(self.vault, VAULT_LOGS), exist_ok=True)
        self.state_path = os.path.join(self.vault, VAULT_STATE, "state.json")
        self.state = {"files": {}}
        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8") as fh:
                self.state = json.load(fh)
        elif os.path.exists(os.path.join(self.vault, VAULT_MANIFEST)):
            # bootstrap continuity: import an existing manifest written by the
            # 2026-10-18 fixture engine (merge, never overwrite/drop)
            with open(os.path.join(self.vault, VAULT_MANIFEST), "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    self.state["files"][r["src"]] = r
            log_line(self.vault, f"STATE imported {len(self.state['files'])} entries "
                                 f"from existing {VAULT_MANIFEST}")
        self.canon = {}
        for src, rec in self.state["files"].items():
            if (rec.get("status") == "ok" and rec.get("alias_of") is None
                    and rec.get("sha256")):
                self.canon.setdefault(rec["sha256"], rec["vault_path"])
        removed = 0
        for r, _, files in os.walk(os.path.join(self.vault, VAULT_STORES)):
            for f in files:
                if f.endswith(".part"):
                    try:
                        os.remove(os.path.join(r, f)); removed += 1
                    except OSError:
                        pass
        if removed:
            log_line(self.vault, f"CLEAN removed {removed} stale .part files")

    def save_state(self):
        atomic_write_json(self.state_path, self.state)

    def write_manifest(self):
        lines = []
        for src in sorted(self.state["files"]):
            r = self.state["files"][src]
            lines.append(json.dumps({
                "alias_of": r.get("alias_of"),
                "first_seen": r.get("first_seen"),
                "gen": r.get("gen", 0),
                "last_synced": r.get("last_synced"),
                "mtime_ns": r.get("mtime_ns"),
                "prev": r.get("prev"),
                "sha256": r.get("sha256"),
                "size": r.get("size"),
                "src": src,
                "status": r.get("status"),
                "store": r.get("store"),
                "tui": r.get("tui"),
                "vault_path": r.get("vault_path"),
            }, sort_keys=True))
        tmp = os.path.join(self.vault, VAULT_MANIFEST) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        os.replace(tmp, os.path.join(self.vault, VAULT_MANIFEST))

    # ---------------- move + adopt
    def adopt_moved(self, store, dry):
        """Rename src into vault/stores/<id> (same volume), then index every file.

        src recorded as ORIGINAL path / rel. Hashing happens on the moved file,
        which by rename semantics is byte-identical to the original.
        """
        sid = store["id"]
        src = store["path"]
        dst = os.path.join(self.vault, VAULT_STORES, sid)
        stats = dict(adopted_files=0, bytes_saved_by_rename=0, unreadable=0)
        if not os.path.exists(dst):
            if not os.path.exists(src):
                log_line(self.vault, f"ADOPT-FAIL {sid}: neither {src} nor {dst} exists")
                return stats
            if dry:
                log_line(self.vault, f"MOVE(dry) {src} -> {dst}")
                return stats
            log_line(self.vault, f"MOVE {src} -> {dst} (same-volume rename; tree intact)")
            os.rename(src, dst)
        else:
            log_line(self.vault, f"ADOPT {sid}: vault dir exists, adopting in place")
        stats["bytes_saved_by_rename"] = self._tree_size(dst)
        walk_mode = store.get("walk", "tree")
        t0 = time.time()
        n = b = 0
        for p, rel, sz, mt in walk_root(dst, walk_mode):
            n += 1
            b += sz
            orig_src = fwd(src) + "/" + rel
            rec = self.state["files"].get(orig_src)
            if rec and rec.get("status") == "ok" and rec.get("size") == sz \
                    and rec.get("mtime_ns") == mt:
                rec["last_synced"] = now_iso()
                continue
            try:
                sha = hash_only(p)
            except OSError as ex:
                log_line(self.vault, f"ADOPT-UNREADABLE {p}: {ex}")
                self.state["files"][orig_src] = {
                    "alias_of": None, "first_seen": now_iso(), "gen": 0,
                    "last_synced": now_iso(), "mtime_ns": mt, "prev": None,
                    "sha256": None, "size": sz, "src": orig_src, "status": "unreadable",
                    "store": sid, "tui": store.get("tui", sid),
                    "vault_path": f"{VAULT_STORES}/{sid}/{rel}"}
                stats["unreadable"] += 1
                continue
            first = (rec or {}).get("first_seen", now_iso())
            gen = (rec or {}).get("gen", 0)
            prev = None
            if rec and rec.get("status") == "ok":
                prev = {"sha256": rec.get("sha256"), "size": rec.get("size")}
                gen += 1
            canon_vp = self.canon.get(sha)
            vp = f"{VAULT_STORES}/{sid}/{rel}"
            if canon_vp and canon_vp != vp:
                self.state["files"][orig_src] = {
                    "alias_of": canon_vp, "first_seen": first, "gen": gen,
                    "last_synced": now_iso(), "mtime_ns": mt, "prev": prev,
                    "sha256": sha, "size": sz, "src": orig_src, "status": "ok",
                    "store": sid, "tui": store.get("tui", sid), "vault_path": vp}
            else:
                self.state["files"][orig_src] = {
                    "alias_of": None, "first_seen": first, "gen": gen,
                    "last_synced": now_iso(), "mtime_ns": mt, "prev": prev,
                    "sha256": sha, "size": sz, "src": orig_src, "status": "ok",
                    "store": sid, "tui": store.get("tui", sid), "vault_path": vp}
                self.canon[sha] = vp
            stats["adopted_files"] += 1
            if n % 500 == 0:
                log_line(self.vault, f"  adopt {sid}: {n} files {b/1e9:.2f}GB ({time.time()-t0:.0f}s)")
        log_line(self.vault, f"ADOPT-DONE {sid}: {n} files {b/1e9:.2f}GB in {time.time()-t0:.0f}s")
        return stats

    # ---------------- sync
    def sync(self, dry=False, only=None, limit_bytes=None):
        stats = dict(new=0, unchanged=0, grown=0, new_alias=0, rematerialized=0,
                     adopted_files=0, unreadable=0, missing_stores=0,
                     bytes_copied=0, bytes_saved_by_alias=0, bytes_saved_by_rename=0)
        picked = [s for s in self.stores if (not only or s["id"] in only)]
        # ---- preflight space (worst case: no dedup savings assumed)
        need = 0
        for store in picked:
            if store.get("mode") == "move":
                continue
            spath = store.get("path")
            if spath is None:
                pass  # files-mode: list may still exist
            elif not os.path.exists(spath):
                stats["missing_stores"] += 1
                log_line(self.vault, f"WARN store path missing: {spath}")
                continue
            for p, rel, sz, mt in iter_store_files(store):
                rec = self.state["files"].get(fwd(p))
                if (rec and rec.get("size") == sz and rec.get("mtime_ns") == mt
                        and rec.get("status") == "ok"):
                    continue
                vabs = os.path.join(self.vault, VAULT_STORES, store["id"], rel)
                try:
                    if os.path.getsize(vabs) == sz:
                        continue
                except OSError:
                    pass
                need += sz
        if not dry:
            free = shutil.disk_usage(self.vault).free
            projected = free - need
            log_line(self.vault, f"PREFLIGHT need={need/1e9:.2f}GB free={free/1e9:.2f}GB "
                                 f"projected-free={projected/1e9:.2f}GB reserve={self.reserve/1e9:.0f}GB")
            if projected < self.reserve:
                msg = (f"ABORT: projected free {projected/1e9:.1f}GB < reserve "
                       f"{self.reserve/1e9:.0f}GB (need {need/1e9:.1f}GB). "
                       f"Re-run with --stores subset to phase the run.")
                log_line(self.vault, msg)
                raise SystemExit(2)

        for store in picked:
            sid, tui = store["id"], store.get("tui", store["id"])
            mode = store.get("mode", "tree")
            if mode == "move":
                a = self.adopt_moved(store, dry)
                stats["adopted_files"] += a["adopted_files"]
                stats["bytes_saved_by_rename"] += a["bytes_saved_by_rename"]
                stats["unreadable"] += a["unreadable"]
                continue
            if store.get("path") is None and mode != "files":
                log_line(self.vault, f"WARN store {sid} has no path; skipped")
                continue
            t0 = time.time()
            n = b = 0
            for p, rel, sz, mt in iter_store_files(store):
                n += 1
                b += sz
                key = fwd(p)
                rec = self.state["files"].get(key)
                if (rec and rec.get("status") == "ok"
                        and rec.get("size") == sz and rec.get("mtime_ns") == mt
                        and (rec.get("alias_of") or os.path.exists(
                            os.path.join(self.vault, rec.get("vault_path", "__none__"))))):
                    rec["last_synced"] = now_iso()
                    stats["unchanged"] += 1
                    continue
                vp = f"{VAULT_STORES}/{sid}/{rel}"
                vabs = os.path.join(self.vault, vp)
                grown = rec is not None and rec.get("status") == "ok"
                if dry:
                    log_line(self.vault, f"WOULD-COPY {p} ({sz} bytes)")
                    continue
                adopted = False
                sha = None
                try:
                    if not grown and os.path.getsize(vabs) == sz:
                        sha_v = hash_only(vabs)
                        if sz < LARGE_FILE:
                            if hash_only(p) == sha_v:
                                sha = sha_v
                                adopted = True
                        else:
                            sha = sha_v
                            adopted = True
                except OSError:
                    adopted = False
                if not adopted:
                    try:
                        sha = hash_and_copy(p, vabs, mt)
                    except OSError as ex:
                        log_line(self.vault, f"UNREADABLE {p}: {ex}")
                        self.state["files"][key] = {
                            "alias_of": None,
                            "first_seen": (rec or {}).get("first_seen", now_iso()),
                            "gen": (rec or {}).get("gen", 0), "last_synced": now_iso(),
                            "mtime_ns": mt, "prev": (rec or {}).get("prev"),
                            "sha256": None, "size": sz, "src": key, "status": "unreadable",
                            "store": sid, "tui": tui, "vault_path": None}
                        stats["unreadable"] += 1
                        continue
                prev = None
                gen = 0
                first = now_iso()
                if rec is not None:
                    first = rec.get("first_seen", first)
                    gen = rec.get("gen", 0)
                    if grown:
                        prev = {"sha256": rec.get("sha256"), "size": rec.get("size")}
                        gen += 1
                        stats["grown"] += 1
                canon_vp = self.canon.get(sha)
                if canon_vp and canon_vp != vp:
                    if os.path.exists(vabs):
                        os.remove(vabs)  # our fresh duplicate - canonical already holds it
                    self.state["files"][key] = {
                        "alias_of": canon_vp, "first_seen": first, "gen": gen,
                        "last_synced": now_iso(), "mtime_ns": mt, "prev": prev,
                        "sha256": sha, "size": sz, "src": key, "status": "ok",
                        "store": sid, "tui": tui, "vault_path": vp}
                    stats["new_alias"] += 1
                    stats["bytes_saved_by_alias"] += sz
                else:
                    self.state["files"][key] = {
                        "alias_of": None, "first_seen": first, "gen": gen,
                        "last_synced": now_iso(), "mtime_ns": mt, "prev": prev,
                        "sha256": sha, "size": sz, "src": key, "status": "ok",
                        "store": sid, "tui": tui, "vault_path": vp}
                    self.canon[sha] = vp
                    stats["new"] += 1
                    if adopted:
                        stats["adopted_files"] += 1
                    else:
                        stats["bytes_copied"] += sz
                    if grown:
                        self._rematerialize_drifted_aliases(vp, sha)
                if n % 500 == 0:
                    log_line(self.vault, f"  {sid}: {n} files {b/1e9:.2f}GB "
                                         f"({time.time()-t0:.0f}s) new={stats['new']} alias={stats['new_alias']}")
            log_line(self.vault, f"STORE-DONE {sid}: {n} files {b/1e9:.2f}GB in {time.time()-t0:.0f}s")
        # ---- mark vanished (record kept, status flipped)
        live_paths = set()
        for store in picked:
            if store.get("mode") == "move":
                continue
            if store.get("path") is not None and not os.path.exists(store["path"]):
                continue
            for p, _, _, _ in iter_store_files(store):
                live_paths.add(fwd(p))
        for p, rec in self.state["files"].items():
            if p not in live_paths and rec.get("status") in ("ok", "unreadable"):
                sid = rec.get("store")
                if only and sid not in only:
                    continue
                # only mark missing if the store's source tree still exists;
                # move stores live in the vault now and are never "vanished"
                srcdef = next((x for x in self.stores if x.get("id") == sid), None)
                if srcdef is None or srcdef.get("mode") == "move":
                    continue
                if srcdef.get("path") is None or not os.path.exists(srcdef["path"]):
                    continue
                rec["status"] = "missing"
                rec["last_synced"] = now_iso()
        if not dry:
            self.save_state()
            self.write_manifest()
            atomic_write_json(os.path.join(self.vault, VAULT_STATE, "last-run.json"), {
                "finished": now_iso(), "phase": "done", "rc": 0, "stats": stats,
                "version": "1.1.0"})
        log_line(self.vault, f"RUN COMPLETE dry={dry} stats={json.dumps(stats)}")
        return stats

    def _tree_size(self, root):
        tot = 0
        for r, _, files in os.walk(root):
            for f in files:
                try:
                    tot += os.path.getsize(os.path.join(r, f))
                except OSError:
                    pass
        return tot

    def _rematerialize_drifted_aliases(self, vp, new_sha):
        """Canonical at vp grew to new_sha: aliases whose recorded hash no longer
        matches the physical target must get their own copy from their own source."""
        for p, rec in self.state["files"].items():
            if rec.get("alias_of") == vp and rec.get("sha256") != new_sha:
                if not os.path.exists(p):
                    continue  # vanished sources keep their record; nothing to copy
                try:
                    vabs = os.path.join(self.vault, rec["vault_path"])
                    got = hash_and_copy(p, vabs, os.stat(p).st_mtime_ns)
                    rec["alias_of"] = None
                    rec["sha256"] = got
                    rec["gen"] = rec.get("gen", 0) + 1
                    rec["last_synced"] = now_iso()
                    log_line(self.vault, f"REMAT {p}: alias target drifted; own copy materialized")
                except OSError:
                    pass

    # ---------------- verify (zero-loss proof)
    def verify(self, only=None):
        res = dict(passed=0, hash_verified=0, stat_verified=0, changed_live=0,
                   missing_in_manifest=0, vault_missing=0, unreadable=0, failures=0)
        picked = [s for s in self.stores if (not only or s["id"] in only)]
        by_src = self.state["files"]
        for store in picked:
            sid = store["id"]
            t0 = time.time()
            n = 0
            if store.get("mode") == "move":
                vroot = os.path.join(self.vault, VAULT_STORES, sid)
                if not os.path.exists(vroot):
                    log_line(self.vault, f"VERIFY-FAIL move store {sid}: vault dir absent")
                    res["failures"] += 1
                    continue
                for p, rel, sz, mt in walk_root(vroot, store.get("walk", "tree")):
                    n += 1
                    orig_src = fwd(store["path"]) + "/" + rel
                    rec = by_src.get(orig_src)
                    if rec is None or rec.get("status") != "ok":
                        res["missing_in_manifest"] += 1
                        res["failures"] += 1
                        log_line(self.vault, f"VERIFY-FAIL moved file not indexed: {orig_src}")
                        continue
                    if sz < LARGE_FILE:
                        try:
                            okv = hash_only(p) == rec.get("sha256")
                        except OSError:
                            okv = None
                            res["unreadable"] += 1
                        if okv:
                            res["hash_verified"] += 1
                            res["passed"] += 1
                        elif okv is None:
                            pass
                        else:
                            res["failures"] += 1
                            log_line(self.vault, f"VERIFY-FAIL moved hash mismatch: {p}")
                    else:
                        res["stat_verified"] += 1
                        res["passed"] += 1
                    if n % 1000 == 0:
                        log_line(self.vault, f"  VERIFY(move) {sid}: {n} ({time.time()-t0:.0f}s)")
                log_line(self.vault, f"VERIFY-STORE-DONE(move) {sid}: {n} files in {time.time()-t0:.0f}s")
                continue
            if store.get("path") is not None and not os.path.exists(store["path"]):
                continue
            for p, rel, sz, mt in iter_store_files(store):
                n += 1
                rec = by_src.get(fwd(p))
                if rec is None or rec.get("status") != "ok":
                    res["missing_in_manifest"] += 1
                    res["failures"] += 1
                    log_line(self.vault, f"VERIFY-FAIL no ok-manifest entry: {p}")
                    continue
                if sz != rec.get("size") or mt != rec.get("mtime_ns"):
                    try:
                        sha_now = hash_only(p) if sz < LARGE_FILE else None
                    except OSError:
                        sha_now = None
                        res["unreadable"] += 1
                    if sha_now and sha_now == rec.get("sha256"):
                        res["passed"] += 1   # timestamp-only drift; content identical
                        continue
                    res["changed_live"] += 1
                    log_line(self.vault, f"VERIFY-CHANGED-LIVE {p} (re-sync to converge)")
                    continue
                if rec.get("alias_of"):
                    tgt = os.path.join(self.vault, rec["alias_of"])
                    if not os.path.exists(tgt):
                        res["vault_missing"] += 1
                        res["failures"] += 1
                        log_line(self.vault, f"VERIFY-FAIL alias target absent: {rec['alias_of']}")
                        continue
                else:
                    vabs = os.path.join(self.vault, rec["vault_path"])
                    if not os.path.exists(vabs):
                        res["vault_missing"] += 1
                        res["failures"] += 1
                        log_line(self.vault, f"VERIFY-FAIL vault copy absent: {rec['vault_path']}")
                        continue
                if sz < LARGE_FILE:
                    try:
                        if hash_only(p) == rec.get("sha256"):
                            res["hash_verified"] += 1
                            res["passed"] += 1
                        else:
                            res["failures"] += 1
                            log_line(self.vault, f"VERIFY-FAIL hash mismatch: {p}")
                    except OSError as ex:
                        res["unreadable"] += 1
                        log_line(self.vault, f"VERIFY-UNREADABLE {p}: {ex}")
                else:
                    res["stat_verified"] += 1
                    res["passed"] += 1
                if n % 1000 == 0:
                    log_line(self.vault, f"  VERIFY {sid}: {n} ({time.time()-t0:.0f}s)")
            log_line(self.vault, f"VERIFY-STORE-DONE {sid}: {n} files in {time.time()-t0:.0f}s")
        log_line(self.vault, f"VERIFY COMPLETE {json.dumps(res)}")
        return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sync", "verify"])
    ap.add_argument("--config",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "stores.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stores", help="comma-separated store ids")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    eng = Engine(cfg)
    only = set(args.stores.split(",")) if args.stores else None
    if args.cmd == "sync":
        eng.sync(dry=args.dry_run, only=only)
    else:
        eng.verify(only=only)


if __name__ == "__main__":
    main()
