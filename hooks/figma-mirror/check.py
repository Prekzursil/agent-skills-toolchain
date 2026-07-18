#!/usr/bin/env python
"""figma-mirror hook -- always-mirror-to-Figma, inject-never-block (gem-hunt N.3).

The design surface drifts away from its Figma representation the moment code is edited. This
hook keeps an honest, low-effort MIRROR pipeline warm:

  PostToolUse(Write|Edit|MultiEdit|NotebookEdit)  -> append edited DESIGN/STYLE files to a
                                                     per-session dirty-queue (never injects)
  Stop                                            -> drain the queue (+ an edit-validate
                                                     fallback), hash every candidate, mark
                                                     which surfaces went STALE vs the last real
                                                     mirror in `mirror-manifest.json`, and (in
                                                     ADVISE mode) inject a one-shot pointer to
                                                     the consumer that can re-mirror them.

The actual re-mirror is performed by the AGENT via `mirror_consumer.mjs` (which drives the
Figma MCP `use_figma` in place -- quota-exempt on the Education Full seat -- or DesignSync as a
Figma-free 2nd target). This hook only does the deterministic bookkeeping: it MARKS staleness;
it never claims a sync happened. A code->Figma mirror is LOSSY (structure + tokens survive;
state/routing/logic do not), so the manifest records staleness and lossiness honestly rather
than pretending parity.

HOOK LAW (AGENTS.md 6): external signal (content hash the model cannot fake) -> inject
additionalContext -> exit 0. NEVER blocks. Fail-open: any error exits 0 silently.

SHADOW-FIRST (COUNCIL C5): defaults to `shadow` mode -- it observes, updates the manifest, and
logs a would-have-fired record to a SEPARATE bounded rotating sink, but injects NOTHING. Promote
to `advise` (inject the pointer, still never block) only after burn-in.

Mode:    FIGMA_MIRROR_MODE = off | shadow | advise      (default: shadow)
Opt-out: FIGMA_MIRROR=off in env, or  hooks/figma-mirror/.disabled
Manifest: FIGMA_MIRROR_MANIFEST=<path>  (default: <cwd>/.design/mirror-manifest.json when a
          .design/ dir exists, else ~/.claude/figma-mirror/mirror-manifest.json)

Registration (the 1-line deploy follow-on) is a manifest/settings entry that runs this script on
BOTH PostToolUse (matcher Write|Edit|MultiEdit|NotebookEdit) and Stop. The event is taken from an
explicit arg (`post`/`stop`) when given, else inferred from the payload's hook_event_name.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent

# --- design/style surface heuristic -----------------------------------------
# Markup / styling / token files are mirrored anywhere. Ambiguous component code (.tsx/.jsx/.mjs
# etc.) is mirrored ONLY when it lives under a design-ish directory, so this stays a DESIGN
# mirror and not a whole-codebase mirror.
STYLE_EXT = (".css", ".scss", ".sass", ".less", ".styl", ".pcss",
             ".html", ".htm", ".vue", ".svelte", ".astro")
COMPONENT_EXT = (".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs")
DESIGN_DIR_HINT = ("component", "components", "ui", "design", "styles", "style",
                   "theme", "themes", "widgets", "views", "screens", "layouts")
TOKEN_NAME_HINT = ("tailwind.config", "theme.", "tokens.", "design-tokens",
                   ".tokens.", "designsystem", "design-system")

POST_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

SHADOW_LOG_MAX = int(os.environ.get("FIGMA_MIRROR_SHADOW_MAX", str(256 * 1024)))  # bytes


# --- small helpers -----------------------------------------------------------
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _norm_path(p: str) -> str:
    return str(p or "").replace("\\", "/")


def _sid(data: dict) -> str:
    return str(data.get("session_id") or "default").replace("/", "_").replace("\\", "_")


def _queue_dir() -> Path:
    return Path(tempfile.gettempdir()) / "figma-mirror"


def _dirty_file(sid: str) -> Path:
    return _queue_dir() / f"{sid}.dirty"


def _mode() -> str:
    if (THIS / ".disabled").exists():
        return "off"
    if os.environ.get("FIGMA_MIRROR", "").lower() in ("off", "0", "false"):
        return "off"
    m = os.environ.get("FIGMA_MIRROR_MODE", "shadow").strip().lower()
    return m if m in ("off", "shadow", "advise") else "shadow"


def is_design_file(path: str) -> bool:
    """True when `path` is a design/style surface worth mirroring to Figma."""
    p = _norm_path(path).lower()
    if not p:
        return False
    base = p.rsplit("/", 1)[-1]
    if any(h in base for h in TOKEN_NAME_HINT):
        return True
    _, ext = os.path.splitext(p)
    if ext in STYLE_EXT:
        return True
    if ext in COMPONENT_EXT:
        segs = p.split("/")[:-1]
        return any(seg in DESIGN_DIR_HINT for seg in segs)
    return False


def _sha256(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _manifest_path(cwd: str) -> Path:
    env = os.environ.get("FIGMA_MIRROR_MANIFEST")
    if env:
        return Path(env)
    try:
        design_dir = Path(cwd) / ".design"
        if design_dir.is_dir():
            return design_dir / "mirror-manifest.json"
    except Exception:
        pass
    return Path.home() / ".claude" / "figma-mirror" / "mirror-manifest.json"


def _blank_manifest() -> dict:
    return {"version": 1, "hash_algo": "sha256", "updated_at": None,
            "target_default": "figma", "entries": {}}


def _load_manifest(p: Path) -> dict:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and isinstance(obj.get("entries"), dict):
            obj.setdefault("version", 1)
            obj.setdefault("hash_algo", "sha256")
            obj.setdefault("target_default", "figma")
            return obj
    except Exception:
        pass
    return _blank_manifest()


def _save_manifest(p: Path, obj: dict) -> bool:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        obj["updated_at"] = _now_iso()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def _shadow_log(record: dict) -> None:
    """Append one JSON record to the bounded, auto-rotating shadow sink (COUNCIL C5 iii).

    Never the main ledger. Rotates to `.1` at SHADOW_LOG_MAX bytes (keeps exactly one backup)."""
    try:
        d = _queue_dir()
        d.mkdir(parents=True, exist_ok=True)
        log = d / "shadow.log.jsonl"
        try:
            if log.exists() and log.stat().st_size >= SHADOW_LOG_MAX:
                os.replace(log, d / "shadow.log.jsonl.1")
        except Exception:
            pass
        with log.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _emit(event: str, msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": msg}}))


# --- PostToolUse: capture edited design files into the dirty-queue -----------
def handle_post(data: dict) -> int:
    tool = str(data.get("tool_name") or "")
    if tool not in POST_TOOLS:
        return 0
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp or not is_design_file(str(fp)):
        return 0
    cwd = str(data.get("cwd") or os.getcwd())
    ap = fp if os.path.isabs(str(fp)) else os.path.join(cwd, str(fp))
    try:
        d = _queue_dir()
        d.mkdir(parents=True, exist_ok=True)
        with _dirty_file(_sid(data)).open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(_norm_path(os.path.abspath(ap)) + "\n")
    except Exception:
        pass
    return 0  # PostToolUse never injects here


def _drain_dirty(sid: str) -> list[str]:
    out: list[str] = []
    f = _dirty_file(sid)
    try:
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s:
                    out.append(s)
            f.unlink()  # consume it
    except Exception:
        pass
    return out


def _edit_validate_fallback(sid: str) -> list[str]:
    """Robustness: work even before the PostToolUse leg is registered by reading the
    shared edit-validate edits list and filtering for design surfaces."""
    out: list[str] = []
    try:
        f = Path(tempfile.gettempdir()) / "edit-validate" / f"{sid}.edits"
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s and is_design_file(s):
                    out.append(_norm_path(os.path.abspath(s)))
    except Exception:
        pass
    return out


# --- Stop: mark staleness in the manifest, advise (never block) --------------
def compute_stale(candidates: list[str], manifest: dict):
    """Pure core: return (stale_list, updated_manifest). Marks each existing candidate's current
    hash in the manifest; STALE iff content_hash != last_mirrored_hash (never-mirrored = stale)."""
    entries = manifest.setdefault("entries", {})
    stale: list[dict] = []
    seen: set[str] = set()
    for path in candidates:
        key = _norm_path(os.path.abspath(path))
        if key in seen or not os.path.isfile(key):
            continue
        seen.add(key)
        h = _sha256(key)
        if not h:
            continue
        try:
            size = os.path.getsize(key)
        except Exception:
            size = 0
        e = entries.get(key) or {}
        prior = e.get("last_mirrored_hash")
        is_stale = (h != prior)
        e.update({
            "source": key,
            "content_hash": h,
            "size": size,
            "last_seen_at": _now_iso(),
            "lossy": True,
        })
        e.setdefault("target", None)
        e.setdefault("figma_node_id", None)
        e.setdefault("designsync_path", None)
        e.setdefault("last_mirrored_hash", prior if prior else None)
        e.setdefault("last_mirrored_at", None)
        e["status"] = "stale" if is_stale else "mirrored"
        entries[key] = e
        if is_stale:
            stale.append({"source": key, "content_hash": h,
                          "never_mirrored": prior is None})
    return stale, manifest


def handle_stop(data: dict) -> int:
    if data.get("stop_hook_active"):
        return 0  # anti-loop
    mode = _mode()
    if mode == "off":
        return 0
    sid = _sid(data)
    cwd = str(data.get("cwd") or os.getcwd())
    candidates = _drain_dirty(sid) + _edit_validate_fallback(sid)
    if not candidates:
        return 0
    mpath = _manifest_path(cwd)
    manifest = _load_manifest(mpath)
    stale, manifest = compute_stale(candidates, manifest)
    if stale:
        _save_manifest(mpath, manifest)
    _shadow_log({
        "ts": _now_iso(), "sid": sid, "mode": mode, "cwd": _norm_path(cwd),
        "manifest": _norm_path(str(mpath)),
        "candidates": len(set(candidates)), "stale": len(stale),
        "would_inject": bool(stale) and mode == "advise",
        "stale_files": [os.path.basename(s["source"]) for s in stale[:12]],
    })
    if not stale or mode != "advise":
        return 0  # shadow: observe + log, inject nothing
    shown = ", ".join(sorted({os.path.basename(s["source"]) for s in stale})[:8])
    more = "" if len(stale) <= 8 else f" (+{len(stale) - 8} more)"
    consumer = _norm_path(str(THIS / "mirror_consumer.mjs"))
    msg = (
        f"**[figma-mirror]** {len(stale)} design surface(s) changed this session and are now "
        f"STALE vs their last Figma mirror: {shown}{more}. Nothing was auto-synced -- a "
        f"code->Figma mirror is LOSSY (structure + tokens carry across; state/routing/logic do "
        f"not), so these are only MARKED stale in `{_norm_path(str(mpath))}`. To re-mirror, run "
        f"`node \"{consumer}\" plan` for the exact `use_figma` (or DesignSync) plan, perform the "
        f"writes, then record each one with `mirror_consumer.mjs mark-mirrored`. If you are not "
        f"maintaining a Figma mirror for this project, ignore this -- it never blocks."
    )
    _emit("Stop", msg)
    return 0


def _event(data: dict, argv: list[str]) -> str:
    for a in argv[1:]:
        al = a.strip().lower()
        if al in ("post", "posttooluse", "post-tool-use"):
            return "post"
        if al in ("stop",):
            return "stop"
    ev = str(data.get("hook_event_name") or "").lower()
    if ev == "posttooluse":
        return "post"
    if ev == "stop":
        return "stop"
    # Infer: a tool_name payload is PostToolUse; otherwise treat as Stop.
    return "post" if data.get("tool_name") else "stop"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict):
            return 0
        if _event(data, argv) == "post":
            return handle_post(data)
        return handle_stop(data)
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
