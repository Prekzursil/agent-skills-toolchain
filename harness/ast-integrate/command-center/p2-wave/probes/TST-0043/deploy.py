#!/usr/bin/env python3
"""Skill deploy gate: malformed SKILL.md is REJECTED with an explicit log line.

Silence on a malformed skill is a failure of this unit, not a pass. A skill
that fails the contract is not copied into the live tree.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from contract import SkillCheck, check_tree, discover_skill_files

ACCEPT_PREFIX = "ACCEPT"
REJECT_PREFIX = "REJECT"


def format_reject(skill_id: str, reason: str, rel: str) -> str:
    return f"{REJECT_PREFIX} skill={skill_id} reason={reason} path={rel}"


def format_accept(skill_id: str, rel: str) -> str:
    return f"{ACCEPT_PREFIX} skill={skill_id} path={rel}"


@dataclass
class DeployResult:
    ok: bool
    accepted: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)

    def reject_lines(self) -> list[str]:
        return [ln for ln in self.log_lines if ln.startswith(REJECT_PREFIX + " ")]

    def accept_lines(self) -> list[str]:
        return [ln for ln in self.log_lines if ln.startswith(ACCEPT_PREFIX + " ")]


def _copy_skill(src_md: Path, dest_root: Path, skill_id: str) -> Path:
    dest = dest_root / "skills" / skill_id / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_md, dest)
    return dest


def deploy_tree(src_root: Path, dest_root: Path) -> DeployResult:
    """Validate then copy. Rejected skills never appear under dest_root."""
    dest_root.mkdir(parents=True, exist_ok=True)
    result = DeployResult(ok=True)
    checks = check_tree(src_root)
    if not checks:
        result.ok = False
        result.log_lines.append("REJECT skill=* reason=NO_SKILLS path=skills/")
        return result
    by_path = {c.path: c for c in checks}
    for md in discover_skill_files(src_root):
        rel = md.relative_to(src_root).as_posix()
        check: SkillCheck = by_path.get(rel) or check_skill_fallback(md, src_root)
        if check.ok:
            _copy_skill(md, dest_root, check.skill_id)
            line = format_accept(check.skill_id, rel)
            result.log_lines.append(line)
            result.accepted.append(check.skill_id)
            result.installed.append(f"skills/{check.skill_id}/SKILL.md")
        else:
            reason = check.primary_reason()
            line = format_reject(check.skill_id, reason, rel)
            result.log_lines.append(line)
            result.rejected.append(
                {"skill_id": check.skill_id, "reason": reason, "path": rel}
            )
            result.ok = False
    return result


def check_skill_fallback(md: Path, src_root: Path) -> SkillCheck:
    from contract import check_skill_file

    return check_skill_file(md, tree_root=src_root)


def silent_skip_deploy(src_root: Path, dest_root: Path) -> DeployResult:
    """Known-broken mutant: copy everything, log nothing on malformed skills.

    Used only as a negative control. A suite that cannot distinguish this
    mutant from deploy_tree would treat silence as a pass.
    """
    dest_root.mkdir(parents=True, exist_ok=True)
    result = DeployResult(ok=True)
    for md in discover_skill_files(src_root):
        skill_id = md.parent.name
        rel = md.relative_to(src_root).as_posix()
        _copy_skill(md, dest_root, skill_id)
        result.accepted.append(skill_id)
        result.installed.append(f"skills/{skill_id}/SKILL.md")
        result.log_lines.append(f"copied {rel}")
    return result
