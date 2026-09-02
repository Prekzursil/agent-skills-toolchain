"""Planted two-directional registry/disk estate plus host-path hunt.

The Prompt One 284-row file is not on this Linux worktree. Detector
controls and both-direction counts run against this planted estate.
Host trees and host registry paths are still searched and reported.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DISK = HERE / "fixtures" / "estate" / "disk"
REGISTRY = HERE / "fixtures" / "estate" / "registry.json"

CATALOG_PINNED_N = 284
HOST_REGISTRY_SHA256 = "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"

HOST_REGISTRY_CANDIDATES = (
    Path.home() / ".claude" / "harness-restore-20260806" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "p2-wave" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)

HOST_SWEEP_ROOTS = (
    Path.home() / ".claude" / "workflows",
    Path.home() / ".claude" / "skills",
    Path.home() / ".claude" / "commands",
    Path.home() / ".agents" / "skills",
    REPO / "skills",
    REPO / "tools",
    REPO / ".github" / "workflows",
)

CTRL_PRESENT_ID = "wf-ctrl-present"
CTRL_ABSENT_ID = "wf-ctrl-absent"
CTRL_EMPTY_ID = "wf-ctrl-empty"
STALE_ID = "wf-stale-deleted"
MISS_LIVE_ID = "wf-missed-live"
EXT_ONLY_ID = "wf-ext-only"
FM_ONLY_ID = "wf-frontmatter-only"
SKILL_ID = "wf-skill-missed"
CMD_ID = "wf-cmd-missed"

PRESENT_REL = "workflows/present-hit.md"
EMPTY_REL = "workflows/wf-ctrl-empty.md"
ABSENT_REL = "workflows/__wfa0009_known_absent_does_not_exist.md"
STALE_REL = "workflows/deleted-from-disk.md"
DECOY_REL = "readme.md"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def present_path() -> Path:
    return DISK / PRESENT_REL


def empty_path() -> Path:
    return DISK / EMPTY_REL


def absent_path() -> Path:
    return DISK / ABSENT_REL


def decoy_path() -> Path:
    return DISK / DECOY_REL


def candidate(cid: str, name: str, family: str, provenance: str, origin: str) -> dict:
    return {
        "id": cid,
        "name": name,
        "family": family,
        "provenance": provenance,
        "origin": origin,
        "does": "planted WFA-0009 control row",
        "license": "UNLICENSED-FIXTURE",
        "maintenance": "probe-owned",
        "mechanisms": ["existence-probe", "inverse-sweep"],
        "notes": "Linux-worktree detector control; not a Prompt One 284-row substitute",
        "runtime": "none",
        "classification": "CONTROL",
        "evidence": "command-center/p2-wave/probes/WFA-0009/estate.py",
    }


def build_estate() -> dict:
    _wipe(DISK)
    DISK.mkdir(parents=True, exist_ok=True)

    _write(
        DISK / PRESENT_REL,
        "---\n"
        f"id: {CTRL_PRESENT_ID}\n"
        "name: present-hit\n"
        "description: known-present non-empty workflow for the existence probe\n"
        "---\n"
        "# present-hit\n"
        "This file must be classified HIT, never PRESENT-EMPTY.\n",
    )
    empty = DISK / EMPTY_REL
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_bytes(b"")

    _write(
        DISK / "workflows" / "missed-live.md",
        "---\n"
        f"id: {MISS_LIVE_ID}\n"
        "name: missed-live\n"
        "description: live workflow Prompt One discovery missed\n"
        "---\n"
        "body of a live workflow that is not in the registry.\n",
    )
    _write(
        DISK / ".github" / "workflows" / f"{EXT_ONLY_ID}.yml",
        "on:\n"
        "  push:\n"
        "jobs:\n"
        "  t:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: true\n",
    )
    _write(
        DISK / "notes" / "orphan-frontmatter.md",
        "---\n"
        f"id: {FM_ONLY_ID}\n"
        "name: frontmatter-only\n"
        "description: discovered only by YAML frontmatter, not by workflows-dir extension\n"
        "---\n"
        "not under workflows/; not a GitHub workflow; frontmatter is the signal.\n",
    )
    _write(
        DISK / "skills" / "skill.missed" / "SKILL.md",
        "---\n"
        f"id: {SKILL_ID}\n"
        "name: skill-missed\n"
        "description: planted live skill the registry missed\n"
        "---\n"
        "# skill-missed\n",
    )
    _write(
        DISK / "commands" / "cmd-missed.md",
        "---\n"
        f"id: {CMD_ID}\n"
        "name: cmd-missed\n"
        "description: planted live command the registry missed\n"
        "---\n"
        "command body\n",
    )
    _write(
        DISK / DECOY_REL,
        "This decoy has no YAML frontmatter and is not under workflows/.\n"
        "A sweeper that treats every .md as a workflow is a detector failure.\n",
    )

    registry = {
        "artifact": "WFA-0009-PLANTED-REGISTRY",
        "note": (
            "Not the Prompt One 284-row file. Host copy sha256 "
            f"{HOST_REGISTRY_SHA256} is absent on this Linux worktree."
        ),
        "candidates": [
            candidate(
                CTRL_PRESENT_ID,
                "present-hit.md",
                "A-saved-workflow",
                PRESENT_REL,
                "fixture",
            ),
            candidate(
                CTRL_ABSENT_ID,
                "known-absent.md",
                "A-saved-workflow",
                ABSENT_REL,
                "fixture",
            ),
            candidate(
                CTRL_EMPTY_ID,
                "wf-ctrl-empty.md",
                "A-saved-workflow",
                EMPTY_REL,
                "fixture",
            ),
            candidate(
                STALE_ID,
                "deleted-from-disk.md",
                "B-repo-workflow",
                STALE_REL,
                "fixture",
            ),
        ],
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "disk": str(DISK),
        "registry": str(REGISTRY),
        "registry_sha256": sha256_file(REGISTRY),
        "n_candidates": len(registry["candidates"]),
    }


def hunt_host_registry() -> list[dict]:
    rows = []
    for p in HOST_REGISTRY_CANDIDATES:
        exists = False
        size = 0
        digest = None
        try:
            exists = p.is_file()
            if exists:
                size = p.stat().st_size
                digest = sha256_file(p)
        except OSError:
            exists = False
        rows.append(
            {
                "path": str(p),
                "exists": exists,
                "bytes": size,
                "sha256": digest,
                "matches_inspect_sha256": digest == HOST_REGISTRY_SHA256,
            }
        )
    return rows


def hunt_host_trees() -> list[dict]:
    rows = []
    for p in HOST_SWEEP_ROOTS:
        is_dir = False
        n = 0
        try:
            is_dir = p.is_dir()
            if is_dir:
                n = sum(1 for q in p.rglob("*") if q.is_file())
        except OSError:
            is_dir = False
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": is_dir,
                "file_count": n,
            }
        )
    return rows


def load_fixture_candidates() -> list[dict]:
    if not REGISTRY.is_file():
        build_estate()
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = doc.get("candidates") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("id")]
