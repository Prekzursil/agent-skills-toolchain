#!/usr/bin/env python3
"""jq-over-JSONL second extractor for BLD-0001.

Mechanically different from extract_read_ledger.parse_jsonl_file: jq walks
objects, this wrapper only normalises and diffs against the inventory.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract_read_ledger import (  # noqa: E402
    canonical_dumps,
    classify_unread,
    load_inventory,
    normalize_path,
    paths_from_bash,
    walk_inventory,
)

JQ_FILTER = HERE / "jq_extract.jq"


def jq_rows(jsonl: Path) -> list[dict]:
    if not shutil.which("jq"):
        raise RuntimeError("jq binary is required for the BLD-0001 reviewer extractor")
    proc = subprocess.run(
        ["jq", "-c", "-f", str(JQ_FILTER), str(jsonl)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in {0, 4}:
        # jq returns 4 on empty/no match for some versions; 0 is success.
        raise RuntimeError(f"jq failed rc={proc.returncode} {(proc.stderr or '')[-500:]}")
    rows: list[dict] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def ledger_from_jq(
    transcripts: list[Path],
    repo_root: Path | None,
) -> tuple[list[str], int]:
    files = []
    for t in transcripts:
        if t.is_file() and t.suffix == ".jsonl":
            files.append(t)
        elif t.is_dir():
            files.extend(sorted(t.rglob("*.jsonl")))
    ledger: set[str] = set()
    tool_uses = 0
    for path in files:
        for row in jq_rows(path):
            name = row.get("name")
            if not isinstance(name, str):
                continue
            tool_uses += 1
            raws: list[str] = []
            if name == "Read":
                for key in ("file_path", "path"):
                    val = row.get(key)
                    if isinstance(val, str):
                        raws.append(val)
            elif name == "Grep":
                val = row.get("path")
                if isinstance(val, str):
                    raws.append(val)
            elif name == "Glob":
                val = row.get("target_directory")
                if isinstance(val, str):
                    raws.append(val)
            elif name in {"Bash", "Shell"}:
                cmd = row.get("command")
                if isinstance(cmd, str):
                    raws.extend(paths_from_bash(cmd))
            for raw in raws:
                norm = normalize_path(raw, repo_root=repo_root)
                if norm:
                    ledger.add(norm)
    return sorted(ledger), tool_uses


def unread_from_jq(
    transcripts: list[Path],
    inventory: list[str],
    tree: Path | None,
    repo_root: Path | None,
    read_cap: int,
    prefixes: tuple[str, ...],
) -> dict:
    ledger, tool_uses = ledger_from_jq(transcripts, repo_root)
    unread = classify_unread(inventory, set(ledger), tree, read_cap, prefixes)
    return {
        "reviewer": "jq",
        "tool_use_records_parsed": tool_uses,
        "ledger_count": len(ledger),
        "unread_count": len(unread),
        "ledger": ledger,
        "unread_paths": [r["path"] for r in unread],
    }


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--transcripts", action="append", required=True)
    p.add_argument("--inventory")
    p.add_argument("--tree")
    p.add_argument("--repo-root")
    p.add_argument("--read-cap", type=int, default=524288)
    p.add_argument("--scope-prefix", action="append", default=[])
    p.add_argument("--json-out")
    args = p.parse_args()
    transcripts = [Path(x) for x in args.transcripts]
    tree = Path(args.tree).resolve() if args.tree else None
    repo_root = Path(args.repo_root).resolve() if args.repo_root else tree
    if args.inventory:
        inventory = load_inventory(Path(args.inventory))
    elif tree is not None:
        inventory = walk_inventory(tree)
    else:
        print("FAILED:jq_reviewer no inventory")
        return 2
    doc = unread_from_jq(
        transcripts,
        inventory,
        tree,
        repo_root,
        args.read_cap,
        tuple(args.scope_prefix),
    )
    text = canonical_dumps(doc)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
