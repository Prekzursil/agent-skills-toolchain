"""Scratch worktrees for CC-0012 freeze-gate probes."""
from __future__ import annotations

import sys
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "freeze"))
import lib as F  # noqa: E402

UNFROZEN_REL = "command-center/receipts/_cc0012_unfrozen_control.json"


def copy_freeze_tree(repo: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    ledger = F.loads_json(repo / F.LEDGER_REL)
    rels = [
        F.LEDGER_REL,
        F.RULES_REL,
        F.LAUNCHER_VER_REL,
        F.FIXTURE_REL,
    ]
    for directory in (repo / F.MIGRATIONS_REL, repo / F.SNAPSHOTS_REL):
        if directory.is_dir():
            for p in directory.rglob("*"):
                if p.is_file():
                    rels.append(p.relative_to(repo).as_posix())
    seen: set[str] = set()
    for rel in rels:
        if rel in seen:
            continue
        seen.add(rel)
        src = repo / rel
        if not src.is_file():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    for row in ledger.get("frozen_paths") or []:
        rel = str(row["path"])
        snap = repo / F.snapshot_rel(rel)
        src = snap if snap.is_file() else repo / rel
        if not src.is_file():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())


def first_schema(ledger: dict) -> str:
    for row in ledger.get("frozen_paths") or []:
        if row.get("kind") == "schema":
            return str(row["path"])
    raise RuntimeError("no frozen schema in ledger")


def mutate_schema_text(path: Path, token: str) -> None:
    doc = F.loads_json(path)
    if isinstance(doc, dict):
        doc["x_cc0012_probe_token"] = token
        path.write_text(F.dumps_canon(doc), encoding="utf-8")
        return
    path.write_bytes(path.read_bytes() + b"\n")


def write_schema_v1_v2_migration(scratch: Path, target_rel: str) -> str:
    rel = "command-center/freeze/migrations/m0002_schema_title_v1_v2.py"
    dest = scratch / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (
            "from typing import Any\n"
            "MIGRATION_ID = 'm0002_schema_title_v1_v2'\n"
            "FROM_VERSION = 1\n"
            "TO_VERSION = 2\n"
            f"TARGETS = [{target_rel!r}]\n"
            "MARKER = 'x_cc0012_migrated'\n"
            "\n"
            "def up(doc: Any) -> dict:\n"
            "    if not isinstance(doc, dict):\n"
            "        raise TypeError('schema migration expects object')\n"
            "    out = dict(doc)\n"
            "    out['schema_version'] = 2\n"
            "    out[MARKER] = True\n"
            "    return out\n"
            "\n"
            "def down(doc: Any) -> dict:\n"
            "    if not isinstance(doc, dict):\n"
            "        raise TypeError('schema migration expects object')\n"
            "    out = dict(doc)\n"
            "    out.pop(MARKER, None)\n"
            "    out.pop('schema_version', None)\n"
            "    return out\n"
        ),
        encoding="utf-8",
    )
    return rel
