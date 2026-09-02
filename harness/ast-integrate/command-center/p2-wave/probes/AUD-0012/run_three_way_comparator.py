#!/usr/bin/env python3
"""Three-way skills drift comparator for AUD-0012.

Trees: repo skills/ vs ~/.agents/skills vs ~/.claude/skills.

Probe 1 instrument: set comparison of relative paths (seven-bucket partition).
Probe 2 instrument: sha256 of LF-normalized bytes per path present in all three,
classified so a two-directional split is not labelled one-directional deploy lag.

Does not mutate the live trees or the repo skills/ tree. Controls run in scratch copies.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

UNIT = "AUD-0012"
TREE_IDS = ("repo", "agents", "claude")
SKIP_DIR_NAMES = {".git", "__pycache__", ".hg", ".svn"}
SKIP_FILE_NAMES = {".ds_store"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd"}
CONTENT_CLASSES = (
    "identical_all_three",
    "only_repo_differs",
    "only_agents_differs",
    "only_claude_differs",
    "all_three_pairwise_distinct",
)
BUCKETS = (
    "only_repo",
    "only_agents",
    "only_claude",
    "repo_and_agents_not_claude",
    "repo_and_claude_not_agents",
    "agents_and_claude_not_repo",
    "all_three",
)


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return parent
    raise RuntimeError("AUD-0012: cannot locate worktree root")


def live_tree_paths(repo: Path | None = None) -> dict[str, Path]:
    repo = repo or repo_root()
    home = Path.home()
    return {
        "repo": repo / "skills",
        "agents": home / ".agents" / "skills",
        "claude": home / ".claude" / "skills",
    }


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _skip_file(path: Path) -> bool:
    if path.name.lower() in SKIP_FILE_NAMES:
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".")
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if _skip_file(path) or path.is_symlink() or not path.is_file():
                continue
            out.append(path)
    return out


def rel_index(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): p for p in iter_files(root)}


def tree_record(tree_id: str, root: Path) -> dict[str, Any]:
    present = root.is_dir()
    idx = rel_index(root)
    return {
        "id": tree_id,
        "path": str(root),
        "present": present,
        "absent_reason": None if present else "directory-does-not-exist",
        "file_count": len(idx),
        "paths": sorted(idx),
    }


def path_sets(indices: dict[str, dict[str, Path]]) -> dict[str, Any]:
    repo = set(indices.get("repo") or {})
    agents = set(indices.get("agents") or {})
    claude = set(indices.get("claude") or {})
    buckets = {
        "only_repo": sorted(repo - agents - claude),
        "only_agents": sorted(agents - repo - claude),
        "only_claude": sorted(claude - repo - agents),
        "repo_and_agents_not_claude": sorted((repo & agents) - claude),
        "repo_and_claude_not_agents": sorted((repo & claude) - agents),
        "agents_and_claude_not_repo": sorted((agents & claude) - repo),
        "all_three": sorted(repo & agents & claude),
    }
    in_one_or_two = [p for key in BUCKETS[:-1] for p in buckets[key]]
    return {
        "buckets": buckets,
        "counts": {key: len(val) for key, val in buckets.items()},
        "in_one_or_two": in_one_or_two,
        "in_one_or_two_count": len(in_one_or_two),
        "union_count": len(repo | agents | claude),
    }


def hashes_for_index(idx: dict[str, Path]) -> dict[str, str]:
    return {rel: sha256_hex(lf_bytes(path.read_bytes())) for rel, path in idx.items()}


def classify_triple(h_repo: str, h_agents: str, h_claude: str) -> str:
    if h_repo == h_agents == h_claude:
        return "identical_all_three"
    if h_agents == h_claude and h_repo != h_agents:
        return "only_repo_differs"
    if h_repo == h_claude and h_agents != h_repo:
        return "only_agents_differs"
    if h_repo == h_agents and h_claude != h_repo:
        return "only_claude_differs"
    return "all_three_pairwise_distinct"


def content_partition(indices: dict[str, dict[str, Path]]) -> dict[str, Any]:
    hashes = {tid: hashes_for_index(idx) for tid, idx in indices.items()}
    all_three = sorted(
        set(indices.get("repo") or {})
        & set(indices.get("agents") or {})
        & set(indices.get("claude") or {})
    )
    rows: list[dict[str, Any]] = []
    by_class: dict[str, list[str]] = {c: [] for c in CONTENT_CLASSES}
    for rel in all_three:
        triple = {
            "repo": hashes["repo"][rel],
            "agents": hashes["agents"][rel],
            "claude": hashes["claude"][rel],
        }
        klass = classify_triple(triple["repo"], triple["agents"], triple["claude"])
        row = {
            "path": rel,
            "sha256": triple,
            "class": klass,
            "one_directional": klass.startswith("only_"),
            "two_directional": klass == "all_three_pairwise_distinct",
        }
        rows.append(row)
        by_class[klass].append(rel)
    divergent = [r["path"] for r in rows if r["class"] != "identical_all_three"]
    return {
        "all_three_count": len(all_three),
        "divergent_paths": divergent,
        "divergent_count": len(divergent),
        "by_class": {k: {"count": len(v), "paths": v} for k, v in by_class.items()},
        "rows": rows,
        "hashes_by_tree": hashes,
        "note": (
            "all_three_pairwise_distinct is two-directional and is not labelled "
            "deploy-lag. only_*_differs is one-directional (two trees match)."
        ),
    }


def write_tree(root: Path, files: dict[str, bytes]) -> None:
    if root.exists():
        shutil.rmtree(root)
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def indices_from_roots(roots: dict[str, Path]) -> dict[str, dict[str, Path]]:
    return {tid: rel_index(root) for tid, root in roots.items()}


def live_world(repo: Path | None = None) -> dict[str, Any]:
    roots = live_tree_paths(repo)
    records = {tid: tree_record(tid, root) for tid, root in roots.items()}
    indices = indices_from_roots(roots)
    sets = path_sets(indices)
    content = content_partition(indices)
    return {
        "home": str(Path.home()),
        "trees": records,
        "roots": {tid: str(root) for tid, root in roots.items()},
        "path_sets": sets,
        "content": content,
        "indices": indices,
    }


def path_set_control(base: Path) -> dict[str, Any]:
    files = {
        "repo": {
            "only-repo/SKILL.md": b"r\n",
            "ra/SKILL.md": b"ra\n",
            "rc/SKILL.md": b"rc\n",
            "all/SKILL.md": b"all\n",
        },
        "agents": {
            "only-agents/SKILL.md": b"a\n",
            "ra/SKILL.md": b"ra\n",
            "ac/SKILL.md": b"ac\n",
            "all/SKILL.md": b"all\n",
        },
        "claude": {
            "only-claude/SKILL.md": b"c\n",
            "rc/SKILL.md": b"rc\n",
            "ac/SKILL.md": b"ac\n",
            "all/SKILL.md": b"all\n",
        },
    }
    roots = {}
    for tid, mapping in files.items():
        root = base / tid
        write_tree(root, mapping)
        roots[tid] = root
    expected = {
        "only_repo": ["only-repo/SKILL.md"],
        "only_agents": ["only-agents/SKILL.md"],
        "only_claude": ["only-claude/SKILL.md"],
        "repo_and_agents_not_claude": ["ra/SKILL.md"],
        "repo_and_claude_not_agents": ["rc/SKILL.md"],
        "agents_and_claude_not_repo": ["ac/SKILL.md"],
        "all_three": ["all/SKILL.md"],
    }
    got = path_sets(indices_from_roots(roots))["buckets"]
    errors = []
    for key, exp in expected.items():
        if got[key] != exp:
            errors.append(f"{key}: got {got[key]} expected {exp}")
    return {
        "id": "AUD-0012-C0-seven-bucket-path-set",
        "kind": "planted-control",
        "description": (
            "Scratch three-way trees plant one path in each of the seven membership "
            "buckets. Empty live trees must not make a broken path-set comparator look green."
        ),
        "pass": not errors,
        "errors": errors,
        "expected": expected,
        "got": got,
    }


def one_byte_control(base: Path) -> dict[str, Any]:
    identical = {
        "shared/SKILL.md": b"hello world\n",
        "other/SKILL.md": b"same other\n",
        "third/SKILL.md": b"third file\n",
    }

    def build(subdir: str, mutate: bool) -> dict[str, Any]:
        roots: dict[str, Path] = {}
        for tid in TREE_IDS:
            files = dict(identical)
            if tid == "agents":
                files["other/SKILL.md"] = b"same other\r\n"
                if mutate:
                    files["shared/SKILL.md"] = b"hello worlD\n"
            root = base / subdir / tid
            write_tree(root, files)
            roots[tid] = root
        return content_partition(indices_from_roots(roots))

    good = build("good", mutate=False)
    bad = build("bad", mutate=True)
    errors = []
    if good["divergent_count"] != 0:
        errors.append(f"good-state divergent_count={good['divergent_count']} want 0")
    if good["all_three_count"] != 3:
        errors.append(f"good all_three_count={good['all_three_count']} want 3")
    if bad["divergent_count"] != 1:
        errors.append(f"bad-state divergent_count={bad['divergent_count']} want 1")
    if bad["divergent_paths"] != ["shared/SKILL.md"]:
        errors.append(f"bad-state paths={bad['divergent_paths']} want ['shared/SKILL.md']")
    if bad["all_three_count"] != 3:
        errors.append("bad-state did not keep three shared paths (not-all check needs n=3)")
    if bad["by_class"]["only_agents_differs"]["paths"] != ["shared/SKILL.md"]:
        errors.append("one-byte plant was not classified only_agents_differs")
    if "other/SKILL.md" in bad["divergent_paths"]:
        errors.append("CRLF-only other/SKILL.md was flagged as content divergence")
    return {
        "id": "AUD-0012-C1-one-byte-in-one-tree",
        "kind": "planted-control",
        "description": (
            "Introduce a one-byte content change in exactly one tree and confirm the "
            "comparator reports exactly one divergent path, not zero and not all. "
            "A CRLF-only sibling in the mutated tree must stay identical after LF normalisation."
        ),
        "pass": not errors,
        "errors": errors,
        "good_state_divergent": good["divergent_paths"],
        "bad_state_divergent": bad["divergent_paths"],
        "silent_on_good_state": good["divergent_count"] == 0,
        "fired_on_bad_state": bad["divergent_paths"] == ["shared/SKILL.md"],
        "eol_only_not_flagged": "other/SKILL.md" not in bad["divergent_paths"],
        "not_all": bad["divergent_count"] == 1 and bad["all_three_count"] == 3,
    }


def two_directional_control(base: Path) -> dict[str, Any]:
    files = {
        "repo": {"split/SKILL.md": b"AAA\n", "same/SKILL.md": b"same\n"},
        "agents": {"split/SKILL.md": b"BBB\n", "same/SKILL.md": b"same\n"},
        "claude": {"split/SKILL.md": b"CCC\n", "same/SKILL.md": b"same\n"},
    }
    roots: dict[str, Path] = {}
    for tid, mapping in files.items():
        root = base / tid
        write_tree(root, mapping)
        roots[tid] = root
    part = content_partition(indices_from_roots(roots))
    errors = []
    if part["by_class"]["all_three_pairwise_distinct"]["paths"] != ["split/SKILL.md"]:
        errors.append(
            "split/SKILL.md was not classified all_three_pairwise_distinct: "
            + str(part["by_class"])
        )
    if part["by_class"]["only_repo_differs"]["count"] != 0:
        errors.append("two-directional split collapsed into only_repo_differs/deploy-lag")
    if part["divergent_paths"] != ["split/SKILL.md"]:
        errors.append(f"divergent={part['divergent_paths']}")
    row = next((r for r in part["rows"] if r["path"] == "split/SKILL.md"), None)
    if row is None or row["one_directional"] or not row["two_directional"]:
        errors.append("split labelled one-directional")
    return {
        "id": "AUD-0012-C2-two-directional-not-deploy-lag",
        "kind": "planted-control",
        "description": (
            "Three pairwise-distinct hashes on one shared path must be reported as "
            "all_three_pairwise_distinct, not as a one-directional deploy lag."
        ),
        "pass": not errors,
        "errors": errors,
        "divergent_paths": part["divergent_paths"],
        "class_for_split": None if row is None else row["class"],
        "two_directional": None if row is None else row["two_directional"],
    }
