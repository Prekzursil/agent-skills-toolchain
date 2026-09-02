#!/usr/bin/env python3
"""Shared helpers for TST-0256: parse the guide, census trees, run documented commands."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GUIDE_REL = "docs/layout-migration.md"
GUIDE = REPO / GUIDE_REL
CAPTURED_REL = "command-center/p2-wave/probes/TST-0256/fixtures/captured-old"
CAPTURED = REPO / CAPTURED_REL
PROVENANCE_REL = "command-center/p2-wave/probes/TST-0256/fixtures/PROVENANCE.json"
PROVENANCE = REPO / PROVENANCE_REL
SOURCE_ROOT_REL = "command-center/p2-wave/probes/ARC-0007/fixtures/repo"
MIGRATE_REL = "tools/layout/migrate.py"
APPLY_CMD = 'python3 tools/layout/migrate.py apply --tree "$TREE"'
HASH_CMD = 'python3 tools/layout/migrate.py hash --tree "$TREE"'


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(lf_bytes(data)).hexdigest()


def walk_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def census(tree: Path) -> list[dict]:
    rows: list[dict] = []
    for path in walk_files(tree):
        rel = path.relative_to(tree).as_posix()
        data = lf_bytes(path.read_bytes())
        rows.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    return rows


def tree_hash_from_census(rows: list[dict]) -> str:
    lines = [f"{r['path']}\t{r['sha256']}\t{r['bytes']}" for r in rows]
    blob = "\n".join(lines) + ("\n" if lines else "")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def tree_diff(left: list[dict], right: list[dict]) -> list[dict]:
    a = {r["path"]: r for r in left}
    b = {r["path"]: r for r in right}
    diffs: list[dict] = []
    for path in sorted(set(a) | set(b)):
        if a.get(path) != b.get(path):
            diffs.append(
                {
                    "path": path,
                    "left": a.get(path),
                    "right": b.get(path),
                }
            )
    return diffs


def parse_mapping(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")]
        if len(cells) != 2:
            continue
        src, dst = cells
        if src.lower() == "from" or dst.lower() == "to":
            continue
        if set(src.replace(":", "").replace("-", "").replace(" ", "")) == set():
            continue
        if not src.endswith("/"):
            continue
        if not dst.endswith("/"):
            dst = dst + "/"
        rows.append((src, dst))
    if len(rows) < 3:
        raise RuntimeError(f"guide mapping table has {len(rows)} rows; need >=3")
    return rows


def extract_fenced_commands(text: str) -> list[str]:
    blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", text, flags=re.DOTALL)
    cmds: list[str] = []
    for block in blocks:
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cmds.append(line)
    return cmds


def documented_apply_command(text: str | None = None) -> str:
    body = text if text is not None else GUIDE.read_text(encoding="utf-8")
    cmds = extract_fenced_commands(body)
    apply_cmds = [c for c in cmds if "migrate.py apply" in c]
    if not apply_cmds:
        raise RuntimeError("docs/layout-migration.md has no fenced apply command")
    return apply_cmds[0]


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def oracle_apply(src: Path, dest: Path, mapping: list[tuple[str, str]]) -> list[dict]:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in walk_files(src):
        rel = path.relative_to(src).as_posix()
        mapped = None
        for prefix, dst in mapping:
            if rel.startswith(prefix):
                mapped = dst + rel[len(prefix) :]
                break
        if mapped is None:
            raise RuntimeError(f"oracle refused unmapped path {rel}")
        target = dest / mapped
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return census(dest)


def run_documented(cmd: str, tree: Path, timeout: int = 60) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TREE"] = str(tree)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def work_copy() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="tst0256-")


def last_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"no JSON object in output: {text[-500:]}")
    return json.loads(text[start : end + 1])
