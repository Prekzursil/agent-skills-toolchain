"""Planted repo vs live registration trees for IMP-0038."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

PLANTED: dict[str, str] = {
    "repo_only_skill": "skill:repo-only-plant",
    "repo_only_hook": "hook:repo-only",
    "repo_only_rule": "rule:repo-only.md",
    "repo_only_command": "command:repo-only.md",
    "live_only_skill": "skill:live-only-plant",
    "live_only_hook": "hook:live-only",
    "live_only_rule": "rule:live-only.md",
    "live_only_command": "command:live-only.md",
    "shared_skill": "skill:shared",
    "shared_hook": "hook:pre-tool",
    "shared_rule": "rule:common/keep.md",
    "shared_command": "command:ping.md",
    "forgotten_skill": "skill:forgotten-from-manifest",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _dump(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _skill(root: Path, name: str, body: str) -> None:
    _write(root / "skills" / name / "SKILL.md", body)


def _hook(root: Path, stem: str, body: dict[str, Any]) -> None:
    _dump(root / "hooks" / f"hook.{stem}.json", body)


def _populate_shared(root: Path) -> None:
    _skill(root, "shared", "# shared skill\n")
    _hook(root, "pre-tool", {"id": "pre-tool", "event": "PreToolUse"})
    _write(root / "rules" / "common" / "keep.md", "# keep\n")
    _write(root / "commands" / "ping.md", "# ping\n")


def _populate_repo_only(root: Path, *, include_forgotten: bool) -> None:
    _skill(root, "repo-only-plant", "# repo-only skill\n")
    _hook(root, "repo-only", {"id": "repo-only", "event": "SessionStart"})
    _write(root / "rules" / "repo-only.md", "# repo-only\n")
    _write(root / "commands" / "repo-only.md", "# repo-only\n")
    if include_forgotten:
        _skill(root, "forgotten-from-manifest", "# forgotten from repo manifest\n")


def _populate_live_only(root: Path) -> None:
    _skill(root, "live-only-plant", "# live-only skill\n")
    _hook(root, "live-only", {"id": "live-only", "event": "Stop"})
    _write(root / "rules" / "live-only.md", "# live-only\n")
    _write(root / "commands" / "live-only.md", "# live-only\n")


def _write_manifests(root: Path, *, kind: str, omit_forgotten: bool) -> None:
    skills = ["shared"]
    hooks = ["pre-tool"]
    rules = ["common/keep.md"]
    commands = ["ping.md"]
    if kind == "repo":
        skills = ["repo-only-plant", "shared"]
        hooks = ["pre-tool", "repo-only"]
        rules = ["common/keep.md", "repo-only.md"]
        commands = ["ping.md", "repo-only.md"]
        if not omit_forgotten:
            pass
        # forgotten file exists on gap trees but is omitted from the manifest
    else:
        skills = ["live-only-plant", "shared"]
        hooks = ["pre-tool", "live-only"]
        rules = ["common/keep.md", "live-only.md"]
        commands = ["ping.md", "live-only.md"]
    _dump(root / "skills" / "DEPLOYED-MANIFEST.json", {"skills": skills})
    _dump(root / "hooks" / "_dispatch" / "manifest.json", {"hooks": hooks})
    _dump(root / "rules" / "RULES-MANIFEST.json", {"rules": rules})
    _dump(root / "commands" / "COMMANDS-MANIFEST.json", {"commands": commands})
    plugin = {
        "name": "imp-0038-fixture",
        "version": "0.0.0-fixture",
        "skills": [f"skills/{s}/SKILL.md" for s in skills],
        "hooks": [f"hooks/hook.{h}.json" for h in hooks],
        "rules": [f"rules/{r}" for r in rules],
        "commands": [f"commands/{c}" for c in commands],
    }
    _dump(root / "plugin.json", plugin)


def build_control_trees(
    dest: str | Path,
    *,
    omit_forgotten_from_repo_manifest: bool = False,
) -> dict[str, Path]:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    repo = dest / "repo"
    live = dest / "live"
    _populate_shared(repo)
    _populate_repo_only(repo, include_forgotten=omit_forgotten_from_repo_manifest)
    _write_manifests(repo, kind="repo", omit_forgotten=omit_forgotten_from_repo_manifest)
    _populate_shared(live)
    _populate_live_only(live)
    _write_manifests(live, kind="live", omit_forgotten=False)
    return {"repo": repo, "live": live}
