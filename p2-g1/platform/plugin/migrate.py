"""Migration from old layouts + compatibility diagnostics.

**Migration.** Legacy layouts are recognised by *fingerprints* — a set of paths that must be
present and a set that must be absent — so a half-migrated tree cannot match two layouts at once.
Each step is dry-runnable, idempotent (running it twice is a no-op) and **invertible**; the ledger
records the inverse of every applied step, so a failed migration is undoable rather than a
half-moved tree.

**Diagnostics.** ``diagnose()`` answers "will this work here, and if not, exactly why" across the
three axes that actually break: client version, OS + launch adapter, and shell. It reports facts
with their probe, never a bare verdict.
"""

from __future__ import annotations

import json
import os
import platform as _platform  # stdlib; see the note in detect_shell()
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError
from .fsops import atomic_write_bytes, content_hash, iter_files, relposix, safe_join
from .manifest import Manifest
from .proc import INTERPRETERS, current_os, probe_interpreter

# --------------------------------------------------------------------------- legacy layouts


@dataclass(frozen=True)
class LayoutFingerprint:
    """A legacy layout is identified by what MUST be there and what MUST NOT."""

    ident: str
    description: str
    require: tuple[str, ...]
    forbid: tuple[str, ...] = ()

    def matches(self, root: Path) -> bool:
        return all((root / r).exists() for r in self.require) and not any(
            (root / f).exists() for f in self.forbid
        )


LEGACY_LAYOUTS: tuple[LayoutFingerprint, ...] = (
    LayoutFingerprint(
        "flat-v0",
        "v0: payload unpacked flat at the prefix root, no versions/ directory",
        require=("plugin.json",),
        forbid=("versions", "state/installed.json"),
    ),
    LayoutFingerprint(
        "single-current-v1",
        "v1: a single 'current/' directory instead of versions/<semver>/",
        require=("current/plugin.json",),
        forbid=("versions",),
    ),
    LayoutFingerprint(
        "unversioned-manifest-v2",
        "v2: versions/ present but the manifest lives at the old top-level path",
        require=("versions", "plugin.json"),
        forbid=(".claude-plugin/plugin.json",),
    ),
)


@dataclass
class MigrationStep:
    ident: str
    description: str
    apply: Callable[[], None]
    invert: Callable[[], None]
    inverse_description: str

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.ident,
            "description": self.description,
            "inverse": self.inverse_description,
        }


@dataclass
class MigrationPlan:
    layout: str
    steps: list[MigrationStep] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "migration-step",
            "detected_layout": self.layout,
            "step_count": len(self.steps),
            "steps": [s.as_dict() for s in self.steps],
        }


def detect_layout(root: Path) -> list[str]:
    """Every legacy fingerprint that matches. More than one match is ``E_MIGRATE`` (ambiguous)."""
    return [f.ident for f in LEGACY_LAYOUTS if f.matches(root)]


def _move(src: Path, dest: Path) -> tuple[Callable[[], None], Callable[[], None]]:
    def apply() -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return  # idempotent
        shutil.move(str(src), str(dest))

    def invert() -> None:
        if dest.exists() and not src.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(src))

    return apply, invert


def plan_migration(root: Path, *, version: str) -> MigrationPlan:
    """Build the ordered, invertible step list for whichever legacy layout is present."""
    matches = detect_layout(root)
    if not matches:
        return MigrationPlan(layout="none")
    if len(matches) > 1:
        raise PluginError(
            "E_MIGRATE",
            f"root matches {len(matches)} mutually exclusive legacy layouts: {', '.join(matches)}",
            context={
                "hint": "a half-migrated tree; restore from a backup before migrating"
            },
        )
    layout = matches[0]
    plan = MigrationPlan(layout=layout)
    vdir = root / "versions" / version
    if layout == "flat-v0":
        for f in sorted(
            p for p in root.iterdir() if p.name not in {"versions", "state", "userdata"}
        ):
            apply, invert = _move(f, vdir / f.name)
            plan.steps.append(
                MigrationStep(
                    f"move:{f.name}",
                    f"move {f.name} -> versions/{version}/{f.name}",
                    apply,
                    invert,
                    f"move versions/{version}/{f.name} -> {f.name}",
                )
            )
        plan.steps.append(_manifest_relocation_step(vdir, version))
    elif layout == "single-current-v1":
        apply, invert = _move(root / "current", vdir)
        plan.steps.append(
            MigrationStep(
                "move:current",
                f"move current/ -> versions/{version}/",
                apply,
                invert,
                f"move versions/{version}/ -> current/",
            )
        )
        plan.steps.append(_manifest_relocation_step(vdir, version))
    elif layout == "unversioned-manifest-v2":
        plan.steps.append(_manifest_relocation_step(root, version))
    return plan


def _manifest_relocation_step(base: Path, version: str) -> MigrationStep:
    old = base / "plugin.json"
    new = base / ".claude-plugin" / "plugin.json"

    def apply() -> None:
        if new.exists() or not old.exists():
            return
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))

    def invert() -> None:
        if new.exists() and not old.exists():
            shutil.move(str(new), str(old))

    return MigrationStep(
        "relocate:manifest",
        "move plugin.json -> .claude-plugin/plugin.json",
        apply,
        invert,
        "move .claude-plugin/plugin.json -> plugin.json",
    )


def migrate(root: Path, *, version: str, dry_run: bool = False) -> dict[str, object]:
    """Apply the plan, recording each step and its inverse. Rolls back on any failure."""
    plan = plan_migration(root, version=version)
    ledger: dict[str, object] = {
        "artifact": "migration-ledger",
        "root": str(root),
        "detected_layout": plan.layout,
        "dry_run": dry_run,
        "started_at": round(time.time(), 3),
        "applied": [],
        "rolled_back": [],
        "ok": True,
    }
    if plan.layout == "none":
        ledger["note"] = "no legacy layout detected; nothing to migrate"
        return ledger
    if dry_run:
        ledger["would_apply"] = [s.as_dict() for s in plan.steps]
        return ledger
    applied: list[MigrationStep] = []
    try:
        for step in plan.steps:
            step.apply()
            applied.append(step)
            ledger["applied"].append(step.as_dict())  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 - a failed migration must undo, then report
        for step in reversed(applied):
            try:
                step.invert()
                ledger["rolled_back"].append(step.ident)  # type: ignore[union-attr]
            except Exception as undo_exc:  # noqa: BLE001
                ledger.setdefault("undo_failures", []).append(
                    f"{step.ident}: {undo_exc}"
                )  # type: ignore[union-attr]
        ledger["ok"] = False
        ledger["error"] = str(exc)
        raise PluginError(
            "E_MIGRATE",
            f"migration failed and was rolled back: {exc}",
            context={"layout": plan.layout, "steps_undone": len(applied)},
        ) from exc
    ledger["finished_at"] = round(time.time(), 3)
    return ledger


def write_ledger(path: Path, ledger: dict[str, object]) -> None:
    atomic_write_bytes(
        path, (json.dumps(ledger, indent=2, sort_keys=True) + "\n").encode()
    )


# --------------------------------------------------------------------------- diagnostics


def detect_shell() -> dict[str, object]:
    """What shell would actually run a script here. Facts + the probe that produced each."""
    facts: dict[str, object] = {
        "os": current_os(),
        # `import platform` is safe despite this repo having a top-level `platform/` directory:
        # a regular stdlib module outranks an implicit namespace package, and that was probed on
        # this box (see platform/lib/wfdsl/conftest.py). It is aliased `_platform` so a reader
        # cannot mistake it for the build root, and `platform/__init__.py` must never be created.
        "platform_release": _platform.release(),
        "python": sys.version.split()[0],
        "comspec": os.environ.get("COMSPEC"),
        "shell_env": os.environ.get("SHELL"),
        "msystem": os.environ.get("MSYSTEM"),
        "msys_no_pathconv": os.environ.get("MSYS_NO_PATHCONV"),
    }
    bash = shutil.which("bash")
    facts["bash_which"] = bash
    # On Windows a bare `bash` on PATH is often WSL's system32\bash.exe, which mangles Windows
    # paths and rejects CRLF. Naming it is the difference between a working and a broken adapter.
    facts["bash_is_probably_wsl"] = bool(
        bash
        and current_os() == "windows"
        and "system32" in bash.replace("/", "\\").lower()
    )
    facts["git_bash_present"] = Path(r"C:\Program Files\Git\bin\bash.exe").exists()
    return facts


def diagnose(
    manifest: Manifest | None = None, *, client_version: str | None = None
) -> dict[str, object]:
    """Compatibility diagnostics (IMP-0046) across client, OS, and shell."""
    doc: dict[str, object] = {
        "artifact": "compatibility",
        "os": current_os(),
        "shell": detect_shell(),
        "interpreters": [probe_interpreter(i).as_dict() for i in sorted(INTERPRETERS)],
        "client": None,
        "compatible": None,
        "reasons": [],
    }
    if manifest is not None:
        reasons: list[str] = []
        osn = current_os()
        os_ok = osn in manifest.platforms
        if not os_ok:
            reasons.append(f"platform {osn!r} is not in {list(manifest.platforms)}")
        client_ok = True
        if client_version:
            client_ok, why = manifest.negotiate(client_version)
            doc["client"] = {"version": client_version, "ok": client_ok, "reason": why}
            if not client_ok:
                reasons.append(why)
        required = [
            str(i["id"]) for i in manifest.interpreters if bool(i.get("required", True))
        ]
        for ident in required:
            p = probe_interpreter(ident)
            if not p.found or not p.meets_floor:
                reasons.append(f"required interpreter {ident}: {p.detail}")
        adapter_reasons: list[str] = []
        for ep in manifest.entrypoints:
            if not ep.interpreter:
                continue
            try:
                from .proc import launch_argv

                launch_argv(ep.interpreter, Path(ep.path), list(ep.args), os_name=osn)
            except PluginError as exc:
                adapter_reasons.append(f"{ep.ident}: {exc.detail}")
        reasons.extend(adapter_reasons)
        doc["required_interpreters"] = required
        doc["compatible"] = not reasons
        doc["reasons"] = reasons
        doc["plugin"] = {
            "name": manifest.name,
            "version": manifest.version,
            "min_client": manifest.min_client,
            "platforms": list(manifest.platforms),
        }
    return doc


def adopt_live_tree(root: Path, live: Path) -> dict[str, object]:
    """Inventory an existing live tree so a first install can adopt rather than clobber it.

    Migration from an old layout is not only about moving files in the prefix: a user may already
    have hand-installed content in the live target. This records what is there, hashed the same
    EOL-normalised way the drift classifier hashes, so the first ``sync`` can classify instead of
    overwrite.
    """
    if not live.exists():
        return {
            "artifact": "live-adoption",
            "live_root": str(live),
            "present": False,
            "files": [],
        }
    files = [
        {"path": relposix(live, f), "sha256": content_hash(f)} for f in iter_files(live)
    ]
    return {
        "artifact": "live-adoption",
        "live_root": str(live),
        "present": True,
        "file_count": len(files),
        "files": files,
        "root": str(root),
    }


def safe_target(root: Path, rel: str) -> Path:
    return safe_join(root, rel)
