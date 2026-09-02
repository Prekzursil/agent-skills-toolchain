"""Plugin hooks/skills loader: `$schema` is annotation, never a silent unload.

Regression this unit pins: Codex HooksFile serde(deny_unknown_fields) treated a
JSON-Schema `$schema` key as unknown, failed the whole deserialize, and the
client swallowed that into a silent ZERO loaded hooks while every file was
still on disk.

This client:
  * allows `$schema` as a reserved annotation (load set identical with/without)
  * reports a loud named error when a hook/skill file is missing (never empty
    the inventory without saying why)
  * exposes two independent signals: (a) inventory count after resolve, (b)
    fire-each-hook side-effect markers
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOWED_TOP = frozenset({"$schema", "hooks", "skills"})
BODY_KEYS = frozenset({"hooks", "skills"})
SCHEMA_KEY = "$schema"


class LoadError(Exception):
    """Loud load failure. Never used to mean 'zero hooks, no reason'."""


@dataclass
class HookSpec:
    hook_id: str
    event: str
    command: str
    path: Path


@dataclass
class SkillSpec:
    skill_id: str
    path: Path


@dataclass
class LoadReport:
    mode: str
    schema_present: bool
    hook_ids: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unknown_keys: list[str] = field(default_factory=list)
    declared_hook_ids: list[str] = field(default_factory=list)
    declared_skill_ids: list[str] = field(default_factory=list)
    fired: dict[str, str] = field(default_factory=dict)

    @property
    def hook_count(self) -> int:
        return len(self.hook_ids)

    @property
    def skill_count(self) -> int:
        return len(self.skill_ids)

    @property
    def loud(self) -> bool:
        return bool(self.errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "schema_present": self.schema_present,
            "hook_ids": list(self.hook_ids),
            "skill_ids": list(self.skill_ids),
            "hook_count": self.hook_count,
            "skill_count": self.skill_count,
            "errors": list(self.errors),
            "unknown_keys": list(self.unknown_keys),
            "declared_hook_ids": list(self.declared_hook_ids),
            "declared_skill_ids": list(self.declared_skill_ids),
            "fired": dict(self.fired),
            "loud": self.loud,
        }


def _read_doc(manifest: Path) -> dict[str, Any]:
    text = manifest.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise LoadError(f"{manifest}: top-level JSON must be an object")
    return doc


def _declared_hooks(root: Path, doc: dict[str, Any]) -> list[HookSpec]:
    hooks_obj = doc.get("hooks")
    if hooks_obj is None:
        raise LoadError(f"{root}: missing required key 'hooks'")
    if not isinstance(hooks_obj, dict):
        raise LoadError(f"{root}: 'hooks' must be an object keyed by event")
    out: list[HookSpec] = []
    for event, entries in hooks_obj.items():
        if not isinstance(entries, list):
            raise LoadError(f"{root}: hooks.{event} must be an array")
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise LoadError(f"{root}: hooks.{event}[{i}] must be an object")
            hid = str(entry.get("id") or "").strip()
            cmd = str(entry.get("command") or "").strip()
            if not hid or not cmd:
                raise LoadError(
                    f"{root}: hooks.{event}[{i}] needs non-empty id and command"
                )
            out.append(
                HookSpec(
                    hook_id=hid,
                    event=str(event),
                    command=cmd,
                    path=(root / cmd).resolve(),
                )
            )
    return out


def _declared_skills(root: Path, doc: dict[str, Any]) -> list[SkillSpec]:
    raw = doc.get("skills")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise LoadError(f"{root}: 'skills' must be an array")
    out: list[SkillSpec] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise LoadError(f"{root}: skills[{i}] must be an object")
        sid = str(entry.get("id") or "").strip()
        rel = str(entry.get("path") or "").strip()
        if not sid or not rel:
            raise LoadError(f"{root}: skills[{i}] needs non-empty id and path")
        out.append(SkillSpec(skill_id=sid, path=(root / rel).resolve()))
    return out


def _resolve(report: LoadReport, hooks: list[HookSpec], skills: list[SkillSpec]) -> None:
    """Count resolved files. Missing files drop the count AND are named in errors."""
    for spec in hooks:
        if spec.path.is_file():
            report.hook_ids.append(spec.hook_id)
        else:
            report.errors.append(
                f"hook {spec.hook_id} failed to load: missing file {spec.command}"
            )
    for spec in skills:
        if spec.path.is_file():
            report.skill_ids.append(spec.skill_id)
        else:
            report.errors.append(
                f"skill {spec.skill_id} failed to load: missing file {spec.path.name}"
            )


def load(manifest: Path, *, mode: str = "allow-schema") -> LoadReport:
    """Inventory load (signal a). Does not execute hooks."""
    manifest = Path(manifest)
    root = manifest.parent
    doc = _read_doc(manifest)
    schema_present = SCHEMA_KEY in doc
    unknown = sorted(k for k in doc.keys() if k not in ALLOWED_TOP)

    if mode == "deny-unknown-silent":
        # Codex-shaped mutant: extra top-level keys (including `$schema`)
        # fail the whole parse and the client swallows that into empty sets.
        extra = sorted(k for k in doc.keys() if k not in BODY_KEYS)
        report = LoadReport(
            mode=mode,
            schema_present=schema_present,
            unknown_keys=extra,
            declared_hook_ids=[],
            declared_skill_ids=[],
        )
        if extra:
            return report
        hooks = _declared_hooks(root, doc)
        skills = _declared_skills(root, doc)
        report.declared_hook_ids = [h.hook_id for h in hooks]
        report.declared_skill_ids = [s.skill_id for s in skills]
        _resolve(report, hooks, skills)
        return report

    if mode == "count-declared-only":
        # Vacuous mutant: count JSON listings, ignore whether files exist.
        hooks = _declared_hooks(root, doc)
        skills = _declared_skills(root, doc)
        return LoadReport(
            mode=mode,
            schema_present=schema_present,
            hook_ids=[h.hook_id for h in hooks],
            skill_ids=[s.skill_id for s in skills],
            declared_hook_ids=[h.hook_id for h in hooks],
            declared_skill_ids=[s.skill_id for s in skills],
            unknown_keys=unknown,
        )

    if unknown:
        raise LoadError(
            "unknown top-level field(s) "
            + ",".join(unknown)
            + " (only $schema is reserved as annotation)"
        )

    hooks = _declared_hooks(root, doc)
    skills = _declared_skills(root, doc)
    report = LoadReport(
        mode=mode,
        schema_present=schema_present,
        unknown_keys=unknown,
        declared_hook_ids=[h.hook_id for h in hooks],
        declared_skill_ids=[s.skill_id for s in skills],
    )
    _resolve(report, hooks, skills)
    return report


def fire_each(manifest: Path, marker_dir: Path) -> LoadReport:
    """Independent signal (b): trigger every resolved hook and observe a side effect."""
    report = load(manifest, mode="allow-schema")
    manifest = Path(manifest)
    root = manifest.parent
    doc = _read_doc(manifest)
    hooks = {h.hook_id: h for h in _declared_hooks(root, doc)}
    marker_dir = Path(marker_dir)
    marker_dir.mkdir(parents=True, exist_ok=True)
    for hid in report.hook_ids:
        spec = hooks[hid]
        env = os.environ.copy()
        env["HOOK_MARKER_DIR"] = str(marker_dir)
        env["HOOK_ID"] = hid
        env["HOOK_EVENT"] = spec.event
        proc = subprocess.run(
            [sys.executable, "-B", str(spec.path)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        marker = marker_dir / hid
        if proc.returncode != 0:
            report.errors.append(
                f"hook {hid} fired with exit {proc.returncode}: "
                + ((proc.stderr or proc.stdout or "")[-400:])
            )
            continue
        if not marker.is_file():
            report.errors.append(f"hook {hid} exited 0 but wrote no marker")
            continue
        report.fired[hid] = marker.read_text(encoding="utf-8").strip()
    return report


def inventory_equals(a: LoadReport, b: LoadReport) -> bool:
    return a.hook_ids == b.hook_ids and a.skill_ids == b.skill_ids
