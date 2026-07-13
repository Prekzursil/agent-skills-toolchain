#!/usr/bin/env python
"""Install + reconcile the shared Claude/Codex lifecycle hook registrations.

This module owns three CLI surfaces:

* ``install.py`` (no flag) writes the freshly-built hook registrations into
  ``~/.claude/settings.json`` and ``~/.codex/hooks.json``, taking an atomic
  timestamped backup and recording a manifest (sha256 + a curated-settings
  snapshot) at ``installed.json``.
* ``install.py --check`` reconciles the live workspace against what the
  installer would produce and emits a STRUCTURED drift report (not just an
  exit code): the hook registrations it OWNS (always managed), plus the
  ``plugins`` / ``enabledPlugins`` / ``tasks`` / ``env`` settings sections and
  the ``~/.claude/skills`` symlink target it OBSERVES. The observed sections
  only assert drift when an optional ``reconcile-baseline.json`` pins an
  expected value; without a baseline they are reported observe-only (the
  shadow-safe default -- report, never fail, until the owner opts in). ``--check``
  is fail-open: an internal error becomes a non-zero drift signal, never a crash.
* ``install.py --bootstrap`` idempotently creates the harness state directories
  and a default ``module-modes.json`` (the SI-2 shadow-ladder mode file), then
  (re)generates the hook registrations. Safe to run repeatedly.

The reconciler is an install-time CLI drift check, NOT a runtime dispatcher
gate: it produces no ``HookResult`` and never injects or blocks a live session,
so it does not route through the SI-2 ``stage()`` shadow-ladder API (that is for
hook modules in ``modules.py``). Its observe-only default and drift-signal exit
code ARE the CLI-equivalent of shadow mode -- consumed by the nightly
self-maintenance routine, never surfaced to the user mid-session.

The ``installed.json`` manifest shape ({installed_at, backup, sha256:{claude,
codex}, settings:{hooks, mcpServers, disabledMcpServers}}) is a load-bearing
contract: modules.py (D5, ConfigChange) compares the live settings against the
``settings`` snapshot to detect config drift, so it is preserved exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness.ledger import default_state_root
    from harness.registration import build_hooks
    from harness.storage import atomic_write_json
else:
    from .ledger import default_state_root
    from .registration import build_hooks
    from .storage import atomic_write_json


HOME = Path.home()
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CODEX_HOOKS = HOME / ".codex" / "hooks.json"
SKILLS_LINK = HOME / ".claude" / "skills"

HERE = Path(__file__).resolve().parent
BACKUPS_DIR = HERE / "backups"
INSTALLED_MANIFEST = HERE / "installed.json"

LIVE_HARNESS_DIR = HOME / ".agents" / "harness"
# Runtime state that must never be copied INTO the live tree (nor backed up):
DEPLOY_EXCLUDE_NAMES = frozenset({
    "installed.json", "backups", "__pycache__", ".pytest_cache", ".ruff_cache",
})
DEPLOY_EXCLUDE_SUFFIXES = (".bak",)
# Optional owner-authored file pinning the EXPECTED value of each observed
# (non-hook) dimension. Its presence promotes those dimensions from
# observe-only to drift-asserting. Absent = the dimensions are reported but
# never fail the check. Shape (all keys optional):
#   {"plugins": {...}, "enabledPlugins": [...], "tasks": {...},
#    "env": {"KEY": "VALUE", ...}, "skills_symlink": {"target": "<abs path>"}}
RECONCILE_BASELINE = HERE / "reconcile-baseline.json"

# The state subdirectories the harness modules expect to exist. Each module
# mkdirs its own leaf lazily, but --bootstrap materializes them up front so a
# brand-new checkout (or a wiped state root) is immediately consistent.
STATE_SUBDIRS = (
    "shadow",           # SI-2 shadow-ladder sampled rotating sink
    "recall-injected",  # SI-5 per-session recall suppression markers
    "session-goals",    # per-session goal isolation (ledger _session_goal_path)
    "anti-degen",       # anti-degeneration sliding windows
    "goal-counters",    # goal re-injection cadence counters
)
MODULE_MODES_NAME = "module-modes.json"

# settings.json sections the reconciler observes for drift beyond the hooks it
# owns. Managed only when the baseline pins them (see RECONCILE_BASELINE).
_SETTINGS_SECTIONS = ("plugins", "enabledPlugins", "tasks", "env")


def _read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def desired_documents(
    claude_settings: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the (claude, codex) documents the installer would write.

    The claude document is the live settings.json with only its ``hooks``
    replaced; the codex document is ``{"hooks": build_hooks("codex")}``. The
    hook set is rebuilt from ``registration.build_hooks`` (and therefore from
    ``registration.EVENTS``), so any events another lane adds compose here for
    free -- no event names are hard-coded in this module.
    """
    target = claude_settings if claude_settings is not None else CLAUDE_SETTINGS
    claude = _read_object(target)
    claude["hooks"] = build_hooks("claude")
    codex = {"hooks": build_hooks("codex")}
    return claude, codex


# --------------------------------------------------------------------------- #
# Structured drift reconciliation (--check)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DriftItem:
    """One reconciled dimension of the workspace.

    ``managed`` items contribute to the exit code (a drift/error there fails
    the check); observe-only items report their current state without ever
    failing it.
    """

    section: str
    status: str  # "ok" | "drift" | "unmanaged" | "error"
    managed: bool
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def is_drift(self) -> bool:
        return self.managed and self.status in {"drift", "error"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "status": self.status,
            "managed": self.managed,
            "detail": self.detail,
        }


def _norm_path(value: Any) -> str:
    """Case/separator-insensitive path key for a robust Windows compare.

    ``os.readlink`` on Windows prepends the extended-length ``\\\\?\\`` prefix
    to an absolute symlink target, so it is stripped here to compare equal to a
    plain baseline path.
    """
    if not value:
        return ""
    text = str(value)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return os.path.normcase(os.path.normpath(text))


def _structured_diff(expected: Any, actual: Any) -> dict[str, Any]:
    """Describe how ``actual`` differs from ``expected`` ({} when equal).

    For two dicts this reports added/removed/changed KEY NAMES only (never
    values -- so env token values can never leak into the printed report). For
    anything else it reports the expected/actual pair. Purely descriptive: no
    mutation, no I/O.
    """
    if expected == actual:
        return {}
    if isinstance(expected, dict) and isinstance(actual, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        diff: dict[str, Any] = {}
        added = sorted(str(k) for k in actual_keys - expected_keys)
        removed = sorted(str(k) for k in expected_keys - actual_keys)
        changed = sorted(
            str(k) for k in (expected_keys & actual_keys) if expected[k] != actual[k]
        )
        if added:
            diff["added"] = added
        if removed:
            diff["removed"] = removed
        if changed:
            diff["changed"] = changed
        return diff
    return {"expected": expected, "actual": actual}


def _summarize(value: Any) -> Any:
    """Value-free summary for observe-only reporting (never leaks env values)."""
    if isinstance(value, dict):
        return {"keys": sorted(str(k) for k in value)}
    if isinstance(value, list):
        return {"count": len(value)}
    if value is None:
        return None
    return {"type": type(value).__name__}


def _reconcile_hooks(
    current_claude: dict[str, Any],
    desired_claude: dict[str, Any],
    current_codex: dict[str, Any],
    desired_codex: dict[str, Any],
) -> list[DriftItem]:
    """The hooks the installer OWNS -- always managed.

    A claude/codex ``hooks`` diff reports which event names drifted. The codex
    document may additionally carry unexpected top-level keys (the claude
    document is derived from the live file so it never can); those are folded in
    so ``ok`` here is exactly equivalent to the original whole-document match.
    """
    items: list[DriftItem] = []
    for name, current, desired in (
        ("hooks.claude", current_claude, desired_claude),
        ("hooks.codex", current_codex, desired_codex),
    ):
        detail = _structured_diff(desired.get("hooks"), current.get("hooks"))
        unexpected = sorted(str(k) for k in set(current) - set(desired))
        if unexpected:
            detail = {**detail, "unexpected_keys": unexpected}
        items.append(
            DriftItem(
                section=name,
                status="drift" if detail else "ok",
                managed=True,
                detail=detail,
            )
        )
    return items


def _reconcile_settings_sections(
    current_claude: dict[str, Any], baseline: dict[str, Any] | None
) -> list[DriftItem]:
    """plugins / enabledPlugins / tasks / env -- managed only when pinned."""
    items: list[DriftItem] = []
    for section in _SETTINGS_SECTIONS:
        actual = current_claude.get(section)
        if baseline is None or section not in baseline:
            items.append(
                DriftItem(
                    section=section,
                    status="unmanaged",
                    managed=False,
                    detail={"observed": _summarize(actual)},
                )
            )
            continue
        detail = _structured_diff(baseline.get(section), actual)
        items.append(
            DriftItem(
                section=section,
                status="drift" if detail else "ok",
                managed=True,
                detail=detail,
            )
        )
    return items


def _observe_symlink(link: Path) -> dict[str, Any]:
    if link.is_symlink():
        return {"is_symlink": True, "target": os.readlink(link)}
    if link.exists():
        return {"is_symlink": False, "target": None, "exists": True}
    return {"is_symlink": False, "target": None, "exists": False}


def _reconcile_skills_symlink(
    link: Path, baseline: dict[str, Any] | None
) -> DriftItem:
    """The ~/.claude/skills symlink target -- managed only when pinned."""
    managed = bool(baseline) and "skills_symlink" in baseline
    try:
        observed = _observe_symlink(link)
    except OSError as exc:
        return DriftItem(
            section="skills_symlink",
            status="error",
            managed=managed,
            detail={"message": type(exc).__name__},
        )
    if not managed:
        return DriftItem(
            section="skills_symlink",
            status="unmanaged",
            managed=False,
            detail={"observed": observed},
        )
    expected = baseline.get("skills_symlink") or {}
    expected_target = expected.get("target") if isinstance(expected, dict) else None
    if expected_target is None:
        # Pinned without a target -> only require that it BE a symlink.
        if observed.get("is_symlink"):
            return DriftItem("skills_symlink", "ok", True, {})
        return DriftItem(
            "skills_symlink",
            "drift",
            True,
            {"observed": observed, "message": "expected a symlink"},
        )
    if _norm_path(observed.get("target")) == _norm_path(expected_target):
        return DriftItem("skills_symlink", "ok", True, {})
    return DriftItem(
        "skills_symlink",
        "drift",
        True,
        {"expected": expected_target, "actual": observed.get("target")},
    )


def _read_baseline(baseline_path: Path | None = None) -> dict[str, Any] | None:
    target = baseline_path if baseline_path is not None else RECONCILE_BASELINE
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def build_reconcile_report(
    *,
    claude_settings: Path | None = None,
    codex_hooks: Path | None = None,
    skills_link: Path | None = None,
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    """Reconcile the live workspace and return a structured drift report.

    Fail-open by construction: every read is wrapped so a missing/invalid file
    becomes a drift-signalling item rather than an exception.
    """
    claude_path = claude_settings if claude_settings is not None else CLAUDE_SETTINGS
    codex_path = codex_hooks if codex_hooks is not None else CODEX_HOOKS
    link = skills_link if skills_link is not None else SKILLS_LINK

    items: list[DriftItem] = []

    current_claude: dict[str, Any] = {}
    try:
        desired_claude, desired_codex = desired_documents(claude_path)
        current_claude = _read_object(claude_path)
        current_codex = _read_object(codex_path) if codex_path.exists() else {}
        items.extend(
            _reconcile_hooks(
                current_claude, desired_claude, current_codex, desired_codex
            )
        )
    except (OSError, ValueError) as exc:
        items.append(
            DriftItem(
                section="hooks",
                status="error",
                managed=True,
                detail={"message": type(exc).__name__},
            )
        )

    baseline = _read_baseline(baseline_path)
    items.extend(_reconcile_settings_sections(current_claude, baseline))
    items.append(_reconcile_skills_symlink(link, baseline))

    drift = any(item.is_drift for item in items)
    summary: dict[str, int] = {}
    for item in items:
        summary[item.status] = summary.get(item.status, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "drift": drift,
        "baseline": str(RECONCILE_BASELINE if baseline_path is None else baseline_path)
        if baseline is not None
        else None,
        "summary": summary,
        "items": [item.to_dict() for item in items],
    }


def _run_check() -> int:
    try:
        report = build_reconcile_report()
        drift = bool(report.get("drift"))
    except Exception:
        # Fail-open: a --check may never crash. An unexpected failure is itself
        # a non-zero drift signal for the caller (e.g. the nightly routine).
        report = {"drift": True, "error": "reconcile_failed", "items": []}
        drift = True
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 1 if drift else 0


# --------------------------------------------------------------------------- #
# Bootstrap (--bootstrap)
# --------------------------------------------------------------------------- #


def _ensure_state_dirs(state_root: Path | None = None) -> list[Path]:
    """Idempotently create the harness state subdirectories."""
    root = Path(state_root) if state_root is not None else default_state_root()
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for name in STATE_SUBDIRS:
        target = root / name
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)
    return created


def _ensure_module_modes(state_root: Path | None = None) -> Path:
    """Idempotently write a default SI-2 module-modes.json.

    The default is an empty object: every gate then resolves to its tier
    default (heuristic -> shadow) via ``resolve_mode``; per-gate overrides are
    the owner's to add. An existing file is PRESERVED (never clobbered) so a
    manual promotion survives re-running --bootstrap.
    """
    root = Path(state_root) if state_root is not None else default_state_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / MODULE_MODES_NAME
    if not path.exists():
        atomic_write_json(path, {})
    return path


def bootstrap(*, state_root: Path | None = None, do_install: bool = True) -> int:
    """Idempotently prepare state dirs + module-modes, then install hooks."""
    _ensure_state_dirs(state_root)
    _ensure_module_modes(state_root)
    if do_install:
        return install(check=False)
    return 0


# --------------------------------------------------------------------------- #
# Install (default) + CLI
# --------------------------------------------------------------------------- #


def install(*, check: bool = False) -> int:
    if check:
        return _run_check()

    claude, codex = desired_documents()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = BACKUPS_DIR / stamp
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(CLAUDE_SETTINGS, backup / "claude-settings.json")
    if CODEX_HOOKS.exists():
        shutil.copy2(CODEX_HOOKS, backup / "codex-hooks.json")

    atomic_write_json(CLAUDE_SETTINGS, claude)
    atomic_write_json(CODEX_HOOKS, codex)
    manifest = {
        "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backup": str(backup),
        "sha256": {
            "claude": hashlib.sha256(CLAUDE_SETTINGS.read_bytes()).hexdigest(),
            "codex": hashlib.sha256(CODEX_HOOKS.read_bytes()).hexdigest(),
        },
        # Snapshot the curated sections the ConfigChange gate (modules.py
        # _config_drift, D5) compares the live settings against. Stored as real
        # values (None when a section is absent) so the baseline carries the
        # installed hooks/MCP state itself, not just a hash of it. `claude` is
        # the desired settings dict just written to CLAUDE_SETTINGS, so its
        # "hooks" is the freshly-built block and mcp* mirror the live file.
        "settings": {
            key: claude.get(key)
            for key in ("hooks", "mcpServers", "disabledMcpServers")
        },
    }
    atomic_write_json(INSTALLED_MANIFEST, manifest)
    return 0


# --------------------------------------------------------------------------- #
# Deploy (--deploy): repo harness (ci/harness) -> live ~/.agents/harness
# --------------------------------------------------------------------------- #


def _deploy_ignore(dir_path: str, names: list[str]) -> set[str]:
    """shutil.copytree/ignore-compatible predicate: drop runtime-state names + *.bak."""
    return {
        n for n in names
        if n in DEPLOY_EXCLUDE_NAMES or n.endswith(DEPLOY_EXCLUDE_SUFFIXES)
    }


def deploy(*, source_dir: Path | None = None, live_dir: Path | None = None) -> int:
    """Copy the repo harness (ci/harness) -> the live ~/.agents/harness, EXCLUDING
    runtime state (installed.json, backups/, __pycache__, .pytest_cache, .ruff_cache,
    *.bak). Backs the live tree up first (like install()); idempotent; prints copied files."""
    src = (source_dir or HERE).resolve()
    dst = (live_dir or LIVE_HARNESS_DIR)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # 1. Back up the existing live tree (same runtime-state exclusions -> the backup
    #    is source-clean too). Skip when there is nothing live yet.
    if dst.exists():
        backup = BACKUPS_DIR / f"deploy-{stamp}" / "harness"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dst, backup, ignore=_deploy_ignore, dirs_exist_ok=False)

    # 2. Deterministic walk + copy (so we can PRINT exactly what we copied, and prune
    #    excluded DIRS in-place so we never descend into __pycache__/backups).
    copied: list[str] = []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in DEPLOY_EXCLUDE_NAMES)
        rel_root = os.path.relpath(root, src)
        for name in sorted(files):
            if name in DEPLOY_EXCLUDE_NAMES or name.endswith(DEPLOY_EXCLUDE_SUFFIXES):
                continue
            rel = os.path.normpath(os.path.join(rel_root, name))
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(os.path.join(root, name), target)
            copied.append(rel)

    sys.stdout.write(
        json.dumps({"deployed_to": str(dst), "source": str(src),
                    "count": len(copied), "copied": copied}, ensure_ascii=False, indent=2) + "\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install + reconcile shared lifecycle hook registrations"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="reconcile the workspace and print a structured drift report "
        "(exit non-zero on managed drift; fail-open, never crashes)",
    )
    group.add_argument(
        "--bootstrap",
        action="store_true",
        help="idempotently create state dirs + default module-modes.json, "
        "then (re)generate the hook registrations",
    )
    group.add_argument(
        "--deploy",
        action="store_true",
        help="copy the repo harness (ci/harness) into the live ~/.agents/harness, "
        "excluding runtime state; backs the live tree up first; idempotent",
    )
    args = parser.parse_args(argv)
    if args.bootstrap:
        return bootstrap()
    if args.deploy:
        return deploy()
    return install(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
