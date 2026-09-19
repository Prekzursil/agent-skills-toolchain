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
* ``install.py --deploy [--target harness|skills|hooks]`` CAS-lite deploys ONE
  repo tree into its live target: a staged/atomic per-file copy guarded by a
  single-writer lock, a plan-time content hash, a plan-time compile check of the
  candidate on the python import surfaces (byte parity proves the copy, never
  that the copy is loadable), a pre-write compare-and-swap (abort if live changed
  since PLAN), and a fail-closed post-write parity check that restores the
  pre-deploy backup on any mismatch, then writes a receipt.
  See the "Deploy" section banner for the full phase composition.
* ``install.py --reconcile-skills`` performs the read-only D-001 prerequisite:
  inventory canonical, projection, provider-only, and both live skill surfaces;
  preserve their union; and route one-sided or conflicting copies without
  choosing a winner. A skills deploy runs this same check before its first write.

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
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness.ledger import default_state_root
    from harness.registration import build_hooks
    from harness.storage import atomic_write_json, read_json
    from harness.surface_reconciler import (
        DEPLOY_STAGE_PREFIX,
        LIVE_DAILY,
        LIVE_VAULT,
        REPO_CANONICAL,
        REPO_PROJECTION,
        comparison_hash,
        is_deploy_excluded,
        reconcile_paths,
    )
else:
    from .ledger import default_state_root
    from .registration import build_hooks
    from .storage import atomic_write_json, read_json
    from .surface_reconciler import (
        DEPLOY_STAGE_PREFIX,
        LIVE_DAILY,
        LIVE_VAULT,
        REPO_CANONICAL,
        REPO_PROJECTION,
        comparison_hash,
        is_deploy_excluded,
        reconcile_paths,
    )


HOME = Path.home()
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CODEX_HOOKS = HOME / ".codex" / "hooks.json"
SKILLS_LINK = HOME / ".claude" / "skills"

HERE = Path(__file__).resolve().parent
BACKUPS_DIR = HERE / "backups"
INSTALLED_MANIFEST = HERE / "installed.json"

LIVE_HARNESS_DIR = HOME / ".agents" / "harness"
# Runtime state that must never be copied INTO the live tree (nor backed up):
# installed.json is the deploy RECEIPT (written per-deploy, never copied FROM
# source); backups/, __pycache__/, .venv/ are generated trees; .deploy.lock is
# the single-writer lock; .deploy-stage-* are the atomic staging temp dirs.
# The CAS-lite deploy machinery (ONE target per call).
DEPLOY_TARGETS = ("harness", "skills", "hooks", "command-center")
# Targets whose repo tree is NOT a clean managed tree, mapped to the EXACT set of
# relative paths that may deploy. Absent from this map = deploy the whole tree
# (the harness/skills/hooks contract, unchanged).
#
# "command-center" needs one because, unlike the other three, its repo directory
# is a live working surface that concurrent agents write scratch into -- measured
# 2026-08-09, 10 untracked files totalling ~1.4 MB, the largest a 1.37 MB
# `_baseline_probe_out.json`. A whole-tree copy would ship that scratch to the box.
#
# The allowlist is exactly what a LIVE consumer READS, and nothing else:
# `WORK-UNIT-CATALOG.json` is loaded by modules.RegisterGateModule._load_catalog,
# whose candidate list names `~/.agents/command-center/WORK-UNIT-CATALOG.json` and
# `~/.claude/command-center/WORK-UNIT-CATALOG.json`. The register's other files
# (STATUS.md, OWNER-DECISIONS.md, the sources/ tree, ...) are repo-side
# documentation and generated views -- no live code opens them, so copying them
# would be cargo-cult. Add a path here only when a live consumer reads it.
#
# DIRECTIONALITY, disclosed rather than hidden: this is a one-way repo -> live
# snapshot of a MUTABLE file. `tools/command-center/close.py` writes the REPO
# copy; the deployed copy is read-only state that goes stale between deploys, so
# an item closed after the last deploy keeps resurfacing until the next one.
# Re-deploy after a close, and never hand-edit the live copy (invisible to git,
# overwritten by the next deploy).
DEPLOY_INCLUDE: dict[str, frozenset[str]] = {
    "command-center": frozenset({"WORK-UNIT-CATALOG.json"}),
}
# Targets whose managed .py files are PYTHON IMPORT SURFACES, so a candidate that
# does not even compile must never reach the live tree: "harness" is imported as a
# package by every consumer, and each hooks/<name>/*.py is imported in-process by
# hooks/_dispatch/dispatch.py. "skills" is deliberately EXCLUDED: it is a document
# vault, and skills/codex-databricks-fanout/scripts/batch_runner.py is a
# `# Databricks notebook source` file whose widget cell legitimately precedes its
# `from __future__` import, so CPython cannot compile it -- gating skills would
# fail-closed on a file that is correct for its runtime. Measured 2026-07-29:
# harness 33/33 and hooks 193/193 managed .py compile; skills 214/215.
COMPILE_GATED_TARGETS = ("harness", "hooks")
DEPLOY_LOCK_NAME = ".deploy.lock"
# A lock older than this (seconds) is treated as stale (crashed writer) and stolen.
DEPLOY_LOCK_STALE_SECONDS = 600.0
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
    "shadow",  # SI-2 shadow-ladder sampled rotating sink
    "recall-injected",  # SI-5 per-session recall suppression markers
    "session-goals",  # per-session goal isolation (ledger _session_goal_path)
    "anti-degen",  # anti-degeneration sliding windows
    "goal-counters",  # goal re-injection cadence counters
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


def _reconcile_skills_symlink(link: Path, baseline: dict[str, Any] | None) -> DriftItem:
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
    expected = (baseline or {}).get("skills_symlink") or {}
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
# Deploy (--deploy): repo tree (harness | skills | hooks | command-center) -> live.
#
# CAS-LITE deploy: a right-sized, staged/atomic copy with optimistic-concurrency
# integrity (NOT an 11-state journal, a compensating-transaction engine, or a
# content-addressed bundle store). One target per call. The phases compose as:
#
#   LOCK      single-writer ~/.agents/harness/.deploy.lock (pid+ts, stale-steal)
#   PLAN      sha256 every managed LIVE file (current) AND every candidate file
#   VALIDITY  on a python import surface (COMPILE_GATED_TARGETS) compile() every
#             candidate .py; a candidate that cannot compile ABORTS here, before
#             any backup/stage/write -- byte parity proves the copy, not the code
#   BACKUP    pre-deploy copy of the live tree (last-known-good, runtime-clean)
#   STAGE     copy candidates into a temp dir on the SAME filesystem as the target
#   CAS       re-hash each live file immediately before the write phase; if it !=
#             the plan-time hash, ABORT the whole deploy (live changed since PLAN)
#   WRITE     per-file os.replace (atomic; never a partial file)
#   PARITY    re-hash live vs candidate; on ANY mismatch RESTORE the backup + FAIL
#   RECEIPT   write/extend <target>/installed.json (deployed_at, source_commit,
#             target, per-file sha256, backup_path)
#
# Only the PARITY hashes must be content-based; timestamps in the receipt are
# ordinary datetime.now() metadata.
# --------------------------------------------------------------------------- #


class DeployLockError(RuntimeError):
    """The single-writer deploy lock is held by a live (non-stale) writer."""

    def __init__(self, held: dict[str, Any]) -> None:
        super().__init__("deploy lock is held")
        self.held = held


class DeployCASConflict(RuntimeError):
    """A managed live file changed between PLAN and the pre-write re-hash."""

    def __init__(self, rel: str, expected: str | None, actual: str | None) -> None:
        super().__init__(f"CAS conflict on {rel}")
        self.rel = rel
        self.expected = expected
        self.actual = actual


def _is_excluded_name(name: str) -> bool:
    """True when a file/dir basename is runtime state that never deploys/backs up."""
    return is_deploy_excluded(name)


def _deploy_ignore(dir_path: str, names: list[str]) -> set[str]:
    """shutil.copytree/ignore-compatible predicate: drop all runtime-state names."""
    return {n for n in names if _is_excluded_name(n)}


def _hash_file(path: Path) -> str:
    """Content hash (sha256 of raw bytes) of a single file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _managed_files(
    root: Path, include: frozenset[str] | None = None
) -> dict[str, Path]:
    """The deterministic managed-file set under ``root`` -> {relpath: abspath}.

    Excludes runtime state (installed.json, backups/, __pycache__, .venv,
    .deploy.lock, *.bak/*.bak-*, staging dirs). Deterministic: dirs and files are
    walked sorted so ``copied`` order is stable across runs.

    ``include`` (DEPLOY_INCLUDE for the target, None for a whole-tree target)
    narrows the result to an exact relative-path allowlist. It must be applied
    IDENTICALLY to the candidate scan and the live scans, or the pre-write CAS
    would compare an allowlisted plan against an unfiltered live tree and abort
    every second deploy on a file it was never asked to manage."""
    result: dict[str, Path] = {}
    if not root.exists():
        return result

    def raise_walk_error(exc: OSError) -> None:
        raise exc

    for dirpath, dirs, files in os.walk(root, onerror=raise_walk_error):
        dirs[:] = sorted(d for d in dirs if not _is_excluded_name(d))
        rel_root = os.path.relpath(dirpath, root)
        for name in sorted(files):
            if _is_excluded_name(name):
                continue
            rel = os.path.normpath(os.path.join(rel_root, name))
            if include is not None and rel not in include:
                continue
            result[rel] = Path(dirpath) / name
    return result


def _managed_hashes(
    root: Path, include: frozenset[str] | None = None
) -> dict[str, str]:
    """Plan-time content hashes of every managed file currently under ``root``."""
    return {
        rel: _hash_file(path) for rel, path in _managed_files(root, include).items()
    }


def _uncompilable_python(candidate: dict[str, Path]) -> list[dict[str, str]]:
    """Managed candidate ``.py`` files whose bytes do not compile -> diagnostics.

    Byte parity proves the deploy COPIED exactly what it planned; it cannot prove
    the copy is loadable. A candidate whose ``__init__.py`` was a SyntaxError used
    to deploy green with a receipt while no consumer could ``import harness`` at
    all -- byte-identical to a broken source is still broken.

    Scope, stated narrowly on purpose: this is a SYNTAX/compile check only. It
    deliberately does NOT import the module, because importing would execute
    arbitrary candidate code inside the deployer. Residual gap, disclosed rather
    than hidden: a file that compiles but raises at import time (bad relative
    import, missing dependency) still deploys green; settling that needs an
    out-of-process import smoke of the LIVE tree after the write, which is a
    separate change with its own sandboxing decision.

    ``compile`` reads raw bytes so PEP 263 encoding declarations and a UTF-8 BOM
    are honored exactly as the interpreter would. ``OSError`` is intentionally NOT
    caught here -- the caller runs this inside the PLAN scan whose ``except
    OSError`` already reports ``managed_file_scan_failed``."""
    problems: list[dict[str, str]] = []
    for rel in sorted(candidate):
        if not rel.endswith(".py"):
            continue
        try:
            compile(candidate[rel].read_bytes(), rel, "exec")
        except (SyntaxError, ValueError) as exc:
            problems.append({"file": rel, "problem": f"{type(exc).__name__}: {exc}"})
    return problems


def _default_source(target: str) -> Path:
    """Repo-side source tree for a deploy target (module globals => monkeypatchable).

    Every non-harness target names its repo directory EXPLICITLY. The previous
    `"skills" if target == "skills" else "hooks"` form made "hooks" the silent
    default for anything unrecognized, so a target added to DEPLOY_TARGETS without
    a row here would have deployed the hooks tree under another target's name."""
    if target == "harness":
        return HERE
    repo_root = HERE.resolve().parents[1]  # agent-self/harness -> agent-self -> <repo>
    subdir = {"skills": "skills", "hooks": "hooks", "command-center": "command-center"}
    return repo_root / subdir[target]


def _default_live(target: str) -> Path:
    """Live target dir. Honors the HARNESS_LIVE_* env overrides (tests), else the
    module globals (so an existing LIVE_HARNESS_DIR monkeypatch keeps working).

    `command-center` sits beside harness/ and skills/ under ~/.agents because that
    is one of the two deployed layouts modules.RegisterGateModule already probes
    for WORK-UNIT-CATALOG.json; the other (~/.claude/command-center) is left as a
    read fallback so an operator may place the file there by hand."""
    if target == "harness":
        env = os.environ.get("HARNESS_LIVE_AGENTS_DIR")
        return (Path(env) / "harness") if env else LIVE_HARNESS_DIR
    if target in {"skills", "command-center"}:
        agents = os.environ.get("HARNESS_LIVE_AGENTS_DIR") or str(HOME / ".agents")
        return Path(agents) / target
    return Path(
        os.environ.get("HARNESS_LIVE_HOOKS_DIR") or (HOME / ".claude" / "hooks")
    )


def _default_skill_surface_roots(
    projection: Path | None = None, live_vault: Path | None = None
) -> dict[str, Path]:
    """Every D-001 skill surface, with source/target seams overridable by deploy."""
    repo_root = HERE.resolve().parents[1]
    return {
        REPO_CANONICAL: repo_root / ".agents" / "skills",
        REPO_PROJECTION: projection or repo_root / "skills",
        LIVE_VAULT: live_vault or _default_live("skills"),
        LIVE_DAILY: SKILLS_LINK,
    }


def reconcile_skills(
    roots: dict[str, Path] | None = None, *, emit: bool = True
) -> tuple[int, dict[str, Any]]:
    """Run the read-only surface pass; ROUTE/FAILED is non-zero for callers."""
    report = reconcile_paths(roots or _default_skill_surface_roots())
    if emit:
        _emit(report)
    return (0 if report["verdict"] == "CLEAN" else 1), report


def _acquire_deploy_lock(live_dir: Path, stale_seconds: float) -> Path:
    """Take the single-writer lock; raise DeployLockError if a live writer holds it.

    A lock whose timestamp is older than ``stale_seconds`` (a crashed writer) is
    stolen. Records {pid, timestamp, iso} for diagnostics."""
    live_dir.mkdir(parents=True, exist_ok=True)
    lock = live_dir / DEPLOY_LOCK_NAME
    now = time.time()
    if lock.exists():
        info = read_json(lock, {})
        info = info if isinstance(info, dict) else {}
        ts = info.get("timestamp")
        if isinstance(ts, (int, float)) and (now - ts) <= stale_seconds:
            raise DeployLockError(held={"pid": info.get("pid"), "timestamp": ts})
        # else: stale / unreadable -> steal it.
    atomic_write_json(
        lock,
        {
            "pid": os.getpid(),
            "timestamp": now,
            "iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    return lock


def _release_deploy_lock(lock: Path) -> None:
    """Always-safe lock release (used in a finally); never raises."""
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        pass


def _restore_tree(backup: Path, dst: Path) -> None:
    """Restore last-known-good: copy every backed-up managed file back over dst."""
    for rel, path in _managed_files(backup).items():
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _source_commit(src: Path) -> str | None:
    """git rev-parse HEAD for the source tree, or None (fail-open, never raises)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(src),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _write_receipt(
    dst: Path, src: Path, target: str, file_hashes: dict[str, str], backup: Path | None
) -> dict[str, Any]:
    """Write/EXTEND <target>/installed.json with the deploy receipt (merge-preserve
    any pre-existing keys). Timestamp = datetime.now (ordinary metadata); the
    integrity fields (per-file sha256) are content-based."""
    receipt_path = dst / "installed.json"
    existing = read_json(receipt_path, {})
    base = existing if isinstance(existing, dict) else {}
    receipt = {
        **base,
        "deployed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_commit": _source_commit(src),
        "target": target,
        "files": {rel: file_hashes[rel] for rel in sorted(file_hashes)},
        "backup_path": str(backup) if backup is not None else None,
    }
    atomic_write_json(receipt_path, receipt)
    return receipt


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def deploy(
    *,
    source_dir: Path | None = None,
    live_dir: Path | None = None,
    target: str = "harness",
    lock_stale_seconds: float = DEPLOY_LOCK_STALE_SECONDS,
    skill_surface_roots: dict[str, Path] | None = None,
    _after_reconcile: Callable[[], None] | None = None,
    _after_stage: Callable[[], None] | None = None,
    _after_write: Callable[[], None] | None = None,
) -> int:
    """CAS-lite deploy of one repo tree -> its live target (see the section banner).

    Returns 0 on success; 1 on any integrity/contention failure (lock held, CAS
    conflict, or a post-write parity mismatch -- fail-CLOSED, restoring the backup).
    ``target`` selects the tree (harness | skills | hooks | command-center); deploy
    ONE per call. A target listed in DEPLOY_INCLUDE deploys only its allowlisted
    relative paths instead of its whole tree.
    ``_after_reconcile`` / ``_after_stage`` / ``_after_write`` are internal
    lifecycle probes (default None) used by tests to inject a concurrent live
    change at the reconciliation / CAS / parity seams; production callers leave
    them unset."""
    if target not in DEPLOY_TARGETS:
        raise ValueError(f"unsupported deploy target: {target!r}")
    src = (source_dir or _default_source(target)).absolute()
    dst = live_dir or _default_live(target)
    # One filter, threaded through EVERY scan (candidate, live-plan, stage,
    # pre-write CAS). Splitting it across the plan and the CAS is the bug this
    # single binding exists to make impossible.
    include = DEPLOY_INCLUDE.get(target)

    # Pre-bound for definite assignment. Each is read only on the
    # ``target == "skills"`` path, where it is reassigned before use, but the
    # reads live under SEPARATE ``if target == "skills"`` guards the type checker
    # cannot correlate with the assignment guard -- so bind harmless defaults the
    # non-skills path never reads.
    roots: dict[str, Path] = {}
    reconciliation: dict[str, Any] = {}
    revalidation: dict[str, Any] = {}

    # D-001 read-only reconciliation FIRST. This precedes even lock acquisition:
    # _acquire_deploy_lock mkdirs the live root and writes .deploy.lock. Overlay
    # the actual candidate/target so a caller cannot reconcile different paths
    # from the ones it asks this function to mutate.
    if target == "skills":
        roots = dict(skill_surface_roots or _default_skill_surface_roots(src, dst))
        roots[REPO_PROJECTION] = src
        roots[LIVE_VAULT] = dst
        reconcile_code, reconciliation = reconcile_skills(roots, emit=False)
        if reconcile_code != 0:
            _emit(
                {
                    "status": "failed",
                    "target": target,
                    "reason": "surface_reconciliation_required",
                    "reconciliation": reconciliation,
                }
            )
            return 1
        if _after_reconcile is not None:
            _after_reconcile()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Capture pre-existence BEFORE the lock mkdirs the target (governs backup).
    live_pre_existed = dst.exists()

    lock_path: Path | None = None
    try:
        try:
            lock_path = _acquire_deploy_lock(dst, lock_stale_seconds)
        except DeployLockError as exc:
            _emit(
                {
                    "status": "failed",
                    "target": target,
                    "reason": "lock_contention",
                    "held_by": exc.held,
                }
            )
            return 1

        # PLAN: content hashes for the current live tree AND the candidate tree.
        # Enumeration errors are fatal; an incomplete plan cannot authorize a
        # zero-file or partial deployment.
        try:
            candidate = _managed_files(src, include)
            candidate_hashes = {
                rel: _hash_file(path) for rel, path in candidate.items()
            }
            live_plan_hashes = _managed_hashes(dst, include)
            receipt_paths = sorted(candidate)
            # VALIDITY (fail-CLOSED, before ANY write): on a Python import surface
            # a candidate that does not compile must not be deployed. Byte parity
            # alone would have called it "deployed".
            uncompilable = (
                _uncompilable_python(candidate)
                if target in COMPILE_GATED_TARGETS
                else []
            )
        except OSError as exc:
            _emit(
                {
                    "status": "failed",
                    "target": target,
                    "reason": "managed_file_scan_failed",
                    "problem": type(exc).__name__,
                }
            )
            return 1

        # Abort at PLAN: no backup, no staging, no live write, no receipt.
        if uncompilable:
            _emit(
                {
                    "status": "failed",
                    "target": target,
                    "reason": "candidate_syntax_invalid",
                    "invalid": uncompilable,
                }
            )
            return 1

        # Bind the write plan to the read-only result. PLAN comes first so the
        # existing pre-write CAS catches changes after this revalidation; the
        # snapshot comparison catches changes between the first pass and PLAN.
        if target == "skills":
            revalidate_code, revalidation = reconcile_skills(roots, emit=False)
            snapshots_changed = (
                revalidation["snapshots"] != reconciliation["snapshots"]
                or revalidation["root_aliases"] != reconciliation["root_aliases"]
                or revalidation["root_resolutions"]
                != reconciliation["root_resolutions"]
            )
            if revalidate_code != 0 or snapshots_changed:
                _emit(
                    {
                        "status": "failed",
                        "target": target,
                        "reason": "surface_changed_after_reconciliation",
                        "snapshots_changed": snapshots_changed,
                        "reconciliation": reconciliation,
                        "revalidation": revalidation,
                    }
                )
                return 1

        # The comparison contract treats text LF/CRLF as equal and explicitly
        # never copies an EOL-only file. Reconciliation has already proved these
        # are the only possible content-equivalent raw differences, so omit them
        # from the write set while preserving them in the eventual live receipt.
        eol_skipped: list[str] = []
        if target == "skills":
            raw_differences = sorted(
                rel
                for rel, digest in candidate_hashes.items()
                if live_plan_hashes.get(rel) not in {None, digest}
            )
            try:
                eol_skipped = [
                    rel
                    for rel in raw_differences
                    if comparison_hash(candidate[rel]) == comparison_hash(dst / rel)
                ]
            except OSError as exc:
                _emit(
                    {
                        "status": "failed",
                        "target": target,
                        "reason": "managed_file_scan_failed",
                        "problem": type(exc).__name__,
                    }
                )
                return 1
            if eol_skipped != raw_differences:
                _emit(
                    {
                        "status": "failed",
                        "target": target,
                        "reason": "raw_plan_not_reconciled",
                    }
                )
                return 1
            candidate = {
                rel: path for rel, path in candidate.items() if rel not in eol_skipped
            }
            candidate_hashes = {
                rel: digest
                for rel, digest in candidate_hashes.items()
                if rel not in eol_skipped
            }

        # BACKUP the pre-deploy live tree (last-known-good), runtime-clean. Only
        # when the target pre-existed -- a brand-new target has nothing to save.
        backup: Path | None = None
        if live_pre_existed:
            backup = BACKUPS_DIR / f"deploy-{stamp}" / target
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(dst, backup, ignore=_deploy_ignore, dirs_exist_ok=False)

        # STAGE every candidate into a temp dir on the SAME filesystem as dst, so
        # the WRITE phase is a same-fs os.replace (atomic, never a partial file).
        with tempfile.TemporaryDirectory(
            prefix=DEPLOY_STAGE_PREFIX, dir=str(dst)
        ) as stage_root:
            stage = Path(stage_root)
            for rel, srcp in candidate.items():
                staged = stage / rel
                staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(srcp, staged)

            if _after_stage is not None:
                _after_stage()  # test seam: simulate a concurrent live change

            # The source can change after PLAN. Verify the completed stage against
            # the approved raw-byte plan before the first live write.
            staged_hashes = _managed_hashes(stage, include)
            if staged_hashes != candidate_hashes:
                _emit(
                    {
                        "status": "failed",
                        "target": target,
                        "reason": "staged_candidate_changed",
                    }
                )
                return 1

            # Reconcile all five surfaces once more at the last safe point before
            # live writes. This binds provider/canonical roots and symlinked parent
            # resolution too; the raw live-tree CAS below covers the write target.
            if target == "skills":
                final_code, final_reconciliation = reconcile_skills(roots, emit=False)
                final_changed = (
                    final_reconciliation["snapshots"] != revalidation["snapshots"]
                    or final_reconciliation["root_aliases"]
                    != revalidation["root_aliases"]
                    or final_reconciliation["root_resolutions"]
                    != revalidation["root_resolutions"]
                )
                if final_code != 0 or final_changed:
                    _emit(
                        {
                            "status": "failed",
                            "target": target,
                            "reason": "surface_changed_before_write",
                            "snapshots_changed": final_changed,
                            "revalidation": revalidation,
                            "final_reconciliation": final_reconciliation,
                        }
                    )
                    return 1

            # PRE-WRITE CAS: re-hash each managed live file immediately before the
            # write phase; a divergence from the plan-time hash means live changed
            # since PLAN -> abort the WHOLE deploy with NO writes (optimistic
            # concurrency). The full-map check catches new live-only paths too;
            # per-file replacement is not a tree-atomic transaction.
            current_live_hashes = _managed_hashes(dst, include)
            if current_live_hashes != live_plan_hashes:
                changed = sorted(set(current_live_hashes) | set(live_plan_hashes))
                rel = next(
                    path
                    for path in changed
                    if current_live_hashes.get(path) != live_plan_hashes.get(path)
                )
                raise DeployCASConflict(
                    rel, live_plan_hashes.get(rel), current_live_hashes.get(rel)
                )

            # WRITE: per-file atomic replace out of the stage into live.
            copied: list[str] = []
            for rel in sorted(candidate):
                live_target = dst / rel
                live_target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / rel, live_target)
                copied.append(rel)

        if _after_write is not None:
            _after_write()  # test seam: simulate post-write corruption

        # POST-WRITE PARITY (fail-CLOSED): live must byte-match the candidate. Any
        # mismatch -> restore the last-known-good backup and FAIL (never pass).
        mismatches = [
            rel for rel in candidate if _hash_file(dst / rel) != candidate_hashes[rel]
        ]
        if mismatches:
            if backup is not None:
                _restore_tree(backup, dst)
            _emit(
                {
                    "status": "failed",
                    "target": target,
                    "reason": "parity_mismatch",
                    "mismatches": sorted(mismatches),
                    "restored_from": str(backup) if backup is not None else None,
                }
            )
            return 1

        # RECEIPT: write/extend <target>/installed.json.
        receipt_hashes = {rel: _hash_file(dst / rel) for rel in receipt_paths}
        receipt = _write_receipt(dst, src, target, receipt_hashes, backup)
        _emit(
            {
                "status": "deployed",
                "target": target,
                "deployed_to": str(dst),
                "source": str(src),
                "count": len(copied),
                "copied": copied,
                "surface_reconciled": target == "skills",
                "eol_skipped": eol_skipped,
                "backup": str(backup) if backup is not None else None,
                "receipt": receipt,
            }
        )
        return 0
    except DeployCASConflict as exc:
        _emit(
            {
                "status": "failed",
                "target": target,
                "reason": "cas_conflict",
                "file": exc.rel,
                "expected_hash": exc.expected,
                "actual_hash": exc.actual,
            }
        )
        return 1
    finally:
        if lock_path is not None:
            _release_deploy_lock(lock_path)


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
        help="CAS-lite deploy of the repo tree into its live target (staged/atomic, "
        "single-writer lock, pre-write CAS, post-write parity, receipt); "
        "backs the live tree up first; idempotent",
    )
    group.add_argument(
        "--reconcile-skills",
        action="store_true",
        help="read-only D-001 inventory of repo + live skill surfaces; "
        "route one-sided/conflicting copies without selecting a winner",
    )
    parser.add_argument(
        "--target",
        choices=DEPLOY_TARGETS,
        default="harness",
        help="which tree to deploy (ONE per call); only used with --deploy",
    )
    args = parser.parse_args(argv)
    if args.reconcile_skills:
        code, _report = reconcile_skills()
        return code
    if args.bootstrap:
        return bootstrap()
    if args.deploy:
        return deploy(target=args.target)
    return install(check=args.check)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
