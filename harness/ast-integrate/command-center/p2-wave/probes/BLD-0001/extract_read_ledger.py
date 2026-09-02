#!/usr/bin/env python3
"""Read-ledger extractor for BLD-0001.

Walks session JSONL for Read / Grep / Glob / Bash-cat (and Shell-cat) tool_use
input paths, normalises them to repo-relative form, and set-differences the
ledger against an inventory (git ls-files, or a frozen list, or a filesystem
walk when this tree has no .git).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_PREFIXES = (
    "C:/Users/Prekzursil/source/ast-integrate/",
    "c:/Users/Prekzursil/source/ast-integrate/",
    "/c/Users/Prekzursil/source/ast-integrate/",
    "/mnt/c/Users/Prekzursil/source/ast-integrate/",
    "/opt/p2/ast-integrate/",
)
READ_TOOLS = frozenset({"Read", "Grep", "Glob", "Bash", "Shell"})
CAT_CMDS = frozenset(
    {"cat", "head", "tail", "type", "get-content", "gc", "more", "less"}
)
CRIT_RANK = {
    "executable": 5,
    "schema": 4,
    "ci-config": 3,
    "doc": 2,
    "fixture": 1,
    "other": 0,
}
DEFAULT_READ_CAP = 524288
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".cursor",
    }
)
CITE_RE = re.compile(
    r"(?:^|[\s`\"'(])([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+):(\d+)"
)
DRIVE_RE = re.compile(r"^([A-Za-z]):/")


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def normalize_path(raw: str, repo_root: Path | None = None) -> str | None:
    if not isinstance(raw, str):
        return None
    s = raw.strip().strip("\"'").strip()
    if not s or s in {".", ".."}:
        return None
    if s.lower().startswith("file://"):
        rest = s[7:]
        if rest.startswith("/") and not rest.startswith("///") and DRIVE_RE.match(
            rest.lstrip("/").replace("\\", "/")[:3] if False else ""
        ):
            s = rest
        else:
            s = rest[1:] if rest.startswith("/") and not rest.startswith("//") else rest
            if s.startswith("/") and len(s) >= 3 and s[2] == ":":
                s = s[1:]
    s = s.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    if s.startswith("file:/"):
        s = s[5:].lstrip("/")
        if re.match(r"^[A-Za-z]:", s) is None and not s.startswith("/"):
            s = "/" + s
    m = DRIVE_RE.match(s)
    if m:
        s = m.group(1).upper() + s[1:]
    lowered = s.replace("\\", "/")
    for prefix in REPO_PREFIXES:
        if lowered.lower().startswith(prefix.lower()):
            s = s[len(prefix) :]
            break
    if repo_root is not None:
        root = repo_root.resolve().as_posix().rstrip("/") + "/"
        posix = s if s.startswith("/") else s
        abs_try = posix
        if abs_try.lower().startswith(root.lower()):
            s = abs_try[len(root) :]
        else:
            try:
                candidate = Path(s)
                if candidate.is_absolute():
                    rel = candidate.resolve().relative_to(repo_root.resolve())
                    s = rel.as_posix()
            except (OSError, ValueError):
                pass
    s = s.lstrip("./")
    if not s or s.startswith("/") or re.match(r"^[A-Za-z]:/", s):
        return None
    if any(ch in s for ch in "*?[]"):
        return None
    if "://" in s:
        return None
    s = s.replace("\\", "/")
    cite = re.match(r"^(.+\.[A-Za-z0-9]+):(\d+)$", s)
    if cite:
        s = cite.group(1)
    return s or None


def walk_objects(obj: Any) -> Iterator[dict]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_objects(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_objects(item)


def paths_from_bash(command: str) -> list[str]:
    if not command or not isinstance(command, str):
        return []
    found: list[str] = []
    for chunk in re.split(r"[;&\n|]+", command):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            toks = shlex.split(chunk, posix=True)
        except ValueError:
            toks = chunk.split()
        i = 0
        while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
            i += 1
        if i >= len(toks):
            continue
        cmd = Path(toks[i]).name.lower()
        if cmd not in CAT_CMDS:
            continue
        for tok in toks[i + 1 :]:
            if tok.startswith("-") or tok in {">", ">>", "<"}:
                continue
            found.append(tok)
    return found


def tool_paths(node: dict) -> list[tuple[str, str]]:
    """Return (raw, tool_name) pairs from one tool_use-shaped object."""
    name = node.get("name")
    inp = node.get("input")
    typ = node.get("type")
    if not isinstance(name, str) or name not in READ_TOOLS:
        return []
    if typ not in {None, "tool_use"} and not isinstance(inp, dict):
        return []
    if not isinstance(inp, dict):
        return []
    raws: list[str] = []
    if name == "Read":
        for key in ("file_path", "path", "target_file"):
            val = inp.get(key)
            if isinstance(val, str):
                raws.append(val)
    elif name == "Grep":
        val = inp.get("path")
        if isinstance(val, str):
            raws.append(val)
        paths = inp.get("paths")
        if isinstance(paths, list):
            raws.extend(p for p in paths if isinstance(p, str))
    elif name == "Glob":
        val = inp.get("target_directory")
        if isinstance(val, str):
            raws.append(val)
    elif name in {"Bash", "Shell"}:
        cmd = inp.get("command")
        if isinstance(cmd, str):
            raws.extend(paths_from_bash(cmd))
    return [(raw, name) for raw in raws]


def parse_jsonl_file(path: Path) -> tuple[int, list[tuple[str, str, str]]]:
    """Return (tool_use_count, list of (raw, tool, transcript))."""
    tool_uses = 0
    hits: list[tuple[str, str, str]] = []
    rel = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        for node in walk_objects(obj):
            name = node.get("name")
            typ = node.get("type")
            inp = node.get("input")
            is_tool = typ == "tool_use" or (
                isinstance(name, str)
                and name in READ_TOOLS
                and isinstance(inp, dict)
            )
            if not is_tool or not isinstance(name, str) or name not in READ_TOOLS:
                continue
            if not isinstance(inp, dict):
                continue
            tool_uses += 1
            for raw, tool in tool_paths(node):
                hits.append((raw, tool, rel))
    return tool_uses, hits


def iter_jsonl(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".jsonl":
            yield path
        elif path.is_dir():
            yield from sorted(p for p in path.rglob("*.jsonl") if p.is_file())


def collect_ledger(
    transcripts: Iterable[Path],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    files = sorted({p.resolve() for p in iter_jsonl(transcripts)})
    tool_uses = 0
    raw_by_norm: dict[str, list[str]] = {}
    tools_by_norm: dict[str, set[str]] = {}
    for path in files:
        n, hits = parse_jsonl_file(path)
        tool_uses += n
        for raw, tool, _src in hits:
            norm = normalize_path(raw, repo_root=repo_root)
            if not norm:
                continue
            raw_by_norm.setdefault(norm, [])
            if raw not in raw_by_norm[norm]:
                raw_by_norm[norm].append(raw)
            tools_by_norm.setdefault(norm, set()).add(tool)
    ledger = sorted(raw_by_norm)
    return {
        "tool_use_records_parsed": tool_uses,
        "transcript_files": [p.as_posix() for p in files],
        "ledger": ledger,
        "raw_forms": raw_by_norm,
        "tools": {k: sorted(v) for k, v in tools_by_norm.items()},
        "ledger_count": len(ledger),
    }


def load_inventory(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        rel = line.strip().replace("\\", "/")
        if not rel or rel.startswith("#"):
            continue
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def walk_inventory(root: Path) -> list[str]:
    out: list[str] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in sorted(filenames):
            if name.endswith((".pyc", ".pyo")):
                continue
            rel = (base / name).relative_to(root).as_posix()
            out.append(rel)
    return out


def os_walk(root: Path):
    import os

    return os.walk(root)


def git_ls_files(root: Path) -> list[str] | None:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    names = [n.replace("\\", "/") for n in proc.stdout.decode("utf-8").split("\0") if n]
    return names


def criticality(path: str) -> str:
    p = path.replace("\\", "/").lower()
    name = p.rsplit("/", 1)[-1]
    if name.endswith((".py", ".sh", ".bash", ".ps1", ".js", ".mjs", ".ts", ".exe")):
        return "executable"
    if name.endswith(".schema.json") or "/schema/" in p:
        return "schema"
    if (
        p.startswith(".github/")
        or "/workflows/" in p
        or name in {"makefile", "azure-pipelines.yml"}
        or ((name.endswith(".yml") or name.endswith(".yaml")) and ("ci" in p or "workflow" in p))
    ):
        return "ci-config"
    if "/fixtures/" in p or "/testdata/" in p:
        return "fixture"
    if name.endswith((".md", ".rst", ".txt")):
        return "doc"
    return "other"


def in_scope(path: str, prefixes: tuple[str, ...]) -> bool:
    p = path.replace("\\", "/")
    if not prefixes:
        return True
    return any(p == pref.rstrip("/") or p.startswith(pref) for pref in prefixes)


def reason_for(
    path: str,
    tree: Path | None,
    read_cap: int,
    prefixes: tuple[str, ...],
) -> str:
    if prefixes and not in_scope(path, prefixes):
        return "out-of-scope"
    if tree is None:
        return "never-routed"
    fp = tree / path
    if not fp.is_file():
        return "never-routed"
    try:
        data = fp.read_bytes()
    except OSError:
        return "unreadable-form"
    if len(data) > read_cap:
        return "oversized"
    if b"\x00" in data:
        return "unreadable-form"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "unreadable-form"
    return "never-routed"


def citations_from_receipts(paths: Iterable[Path]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in CITE_RE.finditer(text):
            rel = normalize_path(match.group(1).replace("\\", "/"))
            if rel and rel not in seen:
                seen.add(rel)
                found.append(rel)
    return found


def classify_unread(
    inventory: list[str],
    ledger: set[str],
    tree: Path | None,
    read_cap: int,
    prefixes: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in inventory:
        if rel in ledger:
            continue
        size = None
        if tree is not None:
            fp = tree / rel
            if fp.is_file():
                try:
                    size = fp.stat().st_size
                except OSError:
                    size = None
        rows.append(
            {
                "path": rel,
                "criticality": criticality(rel),
                "criticality_rank": CRIT_RANK.get(criticality(rel), 0),
                "reason_code": reason_for(rel, tree, read_cap, prefixes),
                "bytes": size,
            }
        )
    rows.sort(key=lambda r: (-int(r["criticality_rank"]), r["path"]))
    return rows


def census(
    *,
    transcripts: list[Path],
    inventory: list[str],
    tree: Path | None,
    repo_root: Path | None,
    extractor_path: Path,
    transcript_glob: str,
    read_cap: int = DEFAULT_READ_CAP,
    scope_prefixes: tuple[str, ...] = (),
    known_read: str | None = None,
    known_unread: str | None = None,
    cited_paths: list[str] | None = None,
) -> dict[str, Any]:
    extracted = collect_ledger(transcripts, repo_root=repo_root)
    ledger_set = set(extracted["ledger"])
    unread = classify_unread(
        inventory, ledger_set, tree, read_cap, scope_prefixes
    )
    unread_paths = {row["path"] for row in unread}
    cited = cited_paths or []
    cited_ok = all(p not in unread_paths for p in cited if p in inventory)
    known_read_ok = True
    if known_read:
        known_read_ok = known_read in ledger_set and known_read not in unread_paths
    known_unread_ok = True
    if known_unread:
        known_unread_ok = known_unread in unread_paths
    collapse = {
        path: forms
        for path, forms in extracted["raw_forms"].items()
        if len(forms) > 1
    }
    return {
        "tool_use_records_parsed": extracted["tool_use_records_parsed"],
        "transcript_files": extracted["transcript_files"],
        "transcript_file_count": len(extracted["transcript_files"]),
        "transcript_glob": transcript_glob,
        "inventory_count": len(inventory),
        "ledger": extracted["ledger"],
        "ledger_count": extracted["ledger_count"],
        "raw_forms": extracted["raw_forms"],
        "tools": extracted["tools"],
        "path_form_collapse": collapse,
        "unread": unread,
        "unread_count": len(unread),
        "extractor_path": extractor_path.as_posix(),
        "extractor_sha256": sha256_file(extractor_path) if extractor_path.is_file() else "",
        "read_cap_bytes": read_cap,
        "scope_prefixes": list(scope_prefixes),
        "known_read": known_read,
        "known_unread": known_unread,
        "known_read_absent_from_unread": known_read_ok,
        "known_unread_present": known_unread_ok,
        "cited_paths": cited,
        "cited_absent_from_unread": cited_ok,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BLD-0001 read-ledger census")
    p.add_argument("--transcripts", action="append", default=[], help="JSONL file or directory")
    p.add_argument("--inventory", help="Frozen git-ls-files listing")
    p.add_argument("--tree", help="Tree to classify unread files against")
    p.add_argument("--repo-root", help="Repo root for path normalisation")
    p.add_argument("--glob-label", default="", help="Transcript glob recorded in the receipt")
    p.add_argument("--read-cap", type=int, default=DEFAULT_READ_CAP)
    p.add_argument("--scope-prefix", action="append", default=[])
    p.add_argument("--known-read")
    p.add_argument("--known-unread")
    p.add_argument("--json-out")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    extractor = Path(__file__).resolve()
    transcripts = [Path(x) for x in args.transcripts]
    if not transcripts:
        print("FAILED:extract_read_ledger no --transcripts")
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    tree = Path(args.tree).resolve() if args.tree else None
    if args.inventory:
        inventory = load_inventory(Path(args.inventory))
    elif tree is not None:
        inventory = walk_inventory(tree)
    elif repo_root is not None:
        inventory = git_ls_files(repo_root) or walk_inventory(repo_root)
    else:
        print("FAILED:extract_read_ledger no inventory")
        return 2
    prefixes = tuple(args.scope_prefix)
    result = census(
        transcripts=transcripts,
        inventory=inventory,
        tree=tree or repo_root,
        repo_root=repo_root or tree,
        extractor_path=extractor,
        transcript_glob=args.glob_label or ",".join(args.transcripts),
        read_cap=args.read_cap,
        scope_prefixes=prefixes,
        known_read=args.known_read,
        known_unread=args.known_unread,
    )
    text = canonical_dumps(result)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
