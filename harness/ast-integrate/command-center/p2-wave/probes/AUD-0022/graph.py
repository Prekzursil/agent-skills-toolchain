"""AUD-0022 graph primitives: lock-tree parse, installed-metadata parse, depth, duplicates.

Two mechanically different builders share only this detector. Probe 1 feeds lock
documents (resolver frozen trees). Probe 2 feeds dist-info METADATA and
node_modules package.json from an isolated tree. Host site-packages are never
the repo closure.
"""
from __future__ import annotations

import json
import re
import tomllib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
}
LIVE_SKIP_PREFIXES = (
    "command-center/p2-wave/probes",
    "command-center/p2-wave/cloud-ok",
    "command-center/p2-wave/scw-pull",
    "command-center/p2-wave/ovh-monitor",
    "command-center/p2-wave/error-pull",
)


def norm_py(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def node_id(ecosystem: str, name: str, version: str) -> str:
    if ecosystem == "pypi":
        name = norm_py(name)
    return f"{ecosystem}:{name}@{version}"


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)
    roots: list[str] = field(default_factory=list)

    def add_node(
        self,
        ecosystem: str,
        name: str,
        version: str,
        *,
        source: str = "",
        extra: dict | None = None,
    ) -> str:
        nid = node_id(ecosystem, name, version)
        rec = self.nodes.setdefault(
            nid,
            {
                "id": nid,
                "ecosystem": ecosystem,
                "name": norm_py(name) if ecosystem == "pypi" else name,
                "version": str(version),
                "depth": None,
                "sources": [],
            },
        )
        if source and source not in rec["sources"]:
            rec["sources"].append(source)
        if extra:
            rec.update(extra)
        return nid

    def add_edge(self, src: str, dst: str) -> None:
        if src and dst and src != dst:
            self.edges.add((src, dst))

    def assign_depths(self) -> int:
        adj: dict[str, list[str]] = defaultdict(list)
        for a, b in self.edges:
            adj[a].append(b)
        for nid, rec in self.nodes.items():
            rec["depth"] = None
        q: deque[str] = deque()
        seen: set[str] = set()
        for r in self.roots:
            if r in self.nodes and r not in seen:
                self.nodes[r]["depth"] = 1
                seen.add(r)
                q.append(r)
        while q:
            cur = q.popleft()
            d = int(self.nodes[cur]["depth"])
            for nxt in adj.get(cur, ()):
                if nxt not in self.nodes:
                    continue
                nd = d + 1
                prev = self.nodes[nxt]["depth"]
                if prev is None or nd < prev:
                    self.nodes[nxt]["depth"] = nd
                    q.append(nxt)
        depths = [n["depth"] for n in self.nodes.values() if n["depth"] is not None]
        return max(depths) if depths else 0

    def to_public(self) -> dict[str, Any]:
        max_depth = self.assign_depths()
        nodes = sorted(self.nodes.values(), key=lambda n: n["id"])
        edges = [
            {"from": a, "to": b} for a, b in sorted(self.edges)
        ]
        dups = find_duplicates(nodes)
        return {
            "nodes": [
                {
                    "id": n["id"],
                    "ecosystem": n["ecosystem"],
                    "name": n["name"],
                    "version": n["version"],
                    "depth": n["depth"],
                }
                for n in nodes
            ],
            "edges": edges,
            "max_depth": max_depth,
            "duplicate_versions": dups,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }


def find_duplicates(nodes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Packages that appear at two or more distinct versions in the same closure."""
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for n in nodes:
        eco = str(n.get("ecosystem") or "")
        name = str(n.get("name") or "")
        ver = str(n.get("version") or "")
        if not eco or not name or not ver:
            continue
        key_name = norm_py(name) if eco == "pypi" else name
        groups[(eco, key_name)].add(ver)
    out = []
    for (eco, name), vers in sorted(groups.items()):
        if len(vers) >= 2:
            out.append(
                {"ecosystem": eco, "name": name, "versions": sorted(vers)}
            )
    return out


def merge_graphs(*graphs: Graph) -> Graph:
    out = Graph()
    for g in graphs:
        for nid, rec in g.nodes.items():
            out.add_node(
                rec["ecosystem"],
                rec["name"],
                rec["version"],
                source=";".join(rec.get("sources") or []),
            )
            out.nodes[nid]["sources"] = list(
                dict.fromkeys(
                    (out.nodes[nid].get("sources") or [])
                    + (rec.get("sources") or [])
                )
            )
        out.edges |= set(g.edges)
        for r in g.roots:
            if r not in out.roots:
                out.roots.append(r)
    return out


# --------------------------------------------------------------------------- npm lock (resolver tree)
def npm_child_key(parent_key: str, dep_name: str, packages: dict) -> str | None:
    search = parent_key
    while True:
        cand = (
            f"{search}/node_modules/{dep_name}"
            if search
            else f"node_modules/{dep_name}"
        )
        if cand in packages:
            return cand
        if not search:
            return None
        marker = "/node_modules/"
        idx = search.rfind(marker)
        if idx < 0:
            if search.startswith("node_modules/"):
                search = ""
                continue
            return None
        search = search[:idx]


def parse_npm_lock(doc: dict[str, Any], *, source: str = "package-lock.json") -> Graph:
    g = Graph()
    packages = doc.get("packages")
    if not isinstance(packages, dict):
        return g
    key_to_id: dict[str, str] = {}
    for key, ent in packages.items():
        if key == "" or not isinstance(ent, dict):
            continue
        if ent.get("link") is True:
            continue
        name = str(ent.get("name") or key.rsplit("node_modules/", 1)[-1])
        ver = str(ent.get("version") or "")
        if not name or not ver:
            continue
        nid = g.add_node("npm", name, ver, source=f"{source}:{key}")
        key_to_id[key] = nid
    root = packages.get("") if isinstance(packages.get(""), dict) else {}
    root_deps = {}
    for field in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        block = root.get(field) if isinstance(root.get(field), dict) else {}
        root_deps.update(block)
    for dep_name in root_deps:
        ck = npm_child_key("", dep_name, packages)
        if ck and ck in key_to_id:
            g.roots.append(key_to_id[ck])
    g.roots = list(dict.fromkeys(g.roots))
    for key, ent in packages.items():
        if key == "" or not isinstance(ent, dict) or key not in key_to_id:
            continue
        src = key_to_id[key]
        deps = ent.get("dependencies") if isinstance(ent.get("dependencies"), dict) else {}
        for dep_name in deps:
            ck = npm_child_key(key, dep_name, packages)
            if ck and ck in key_to_id:
                g.add_edge(src, key_to_id[ck])
    return g


def parse_npm_lock_path(path: Path) -> Graph:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return Graph()
    return parse_npm_lock(doc, source=path.as_posix())


# --------------------------------------------------------------------------- uv.lock (resolver tree)
def parse_uv_lock(doc: dict[str, Any], *, source: str = "uv.lock") -> Graph:
    g = Graph()
    pkgs = doc.get("package")
    if not isinstance(pkgs, list):
        return g
    name_to_id: dict[str, str] = {}
    virtual: set[str] = set()
    for ent in pkgs:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "")
        ver = str(ent.get("version") or "")
        src = ent.get("source") if isinstance(ent.get("source"), dict) else {}
        is_virtual = bool(src.get("virtual") or src.get("editable") or src.get("directory"))
        if not name or not ver:
            continue
        if is_virtual:
            virtual.add(norm_py(name))
            continue
        nid = g.add_node("pypi", name, ver, source=source)
        name_to_id[norm_py(name)] = nid
    for ent in pkgs:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "")
        src = ent.get("source") if isinstance(ent.get("source"), dict) else {}
        is_virtual = bool(src.get("virtual") or src.get("editable") or src.get("directory"))
        deps = ent.get("dependencies") if isinstance(ent.get("dependencies"), list) else []
        parent_id = None if is_virtual else name_to_id.get(norm_py(name))
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            child = name_to_id.get(norm_py(str(dep.get("name") or "")))
            if not child:
                continue
            if is_virtual:
                g.roots.append(child)
            elif parent_id:
                g.add_edge(parent_id, child)
    g.roots = list(dict.fromkeys(g.roots))
    if not g.roots:
        pointed = {b for _, b in g.edges}
        g.roots = [nid for nid in g.nodes if nid not in pointed]
    return g


def parse_uv_lock_path(path: Path) -> Graph:
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    return parse_uv_lock(doc, source=path.as_posix())


# --------------------------------------------------------------------------- installed METADATA (probe 2)
def _parse_metadata_text(text: str) -> dict[str, Any]:
    name = ""
    version = ""
    requires: list[str] = []
    for line in text.splitlines():
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("Requires-Dist:"):
            raw = line.split(":", 1)[1].strip()
            m = REQ_NAME.match(raw.split(";")[0])
            if m:
                requires.append(m.group(1))
    return {"name": name, "version": version, "requires": requires}


def parse_dist_info_tree(root: Path, *, source_label: str = "") -> Graph:
    g = Graph()
    if not root.is_dir():
        return g
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    recs: list[tuple[str, list[str]]] = []
    for meta in sorted(root.rglob("METADATA")):
        if not meta.parent.name.endswith(".dist-info"):
            continue
        parsed = _parse_metadata_text(meta.read_text(encoding="utf-8", errors="replace"))
        if not parsed["name"] or not parsed["version"]:
            continue
        rel = meta.as_posix()
        nid = g.add_node(
            "pypi",
            parsed["name"],
            parsed["version"],
            source=source_label or rel,
        )
        name_to_ids[norm_py(parsed["name"])].append(nid)
        recs.append((nid, parsed["requires"]))
    for nid, reqs in recs:
        for req in reqs:
            children = name_to_ids.get(norm_py(req)) or []
            for child in children:
                g.add_edge(nid, child)
    pointed = {b for _, b in g.edges}
    g.roots = [nid for nid in g.nodes if nid not in pointed]
    return g


def is_nm_package_json(path: Path) -> bool:
    d = path.parent
    if d.parent.name == "node_modules":
        return True
    if d.parent.name.startswith("@") and d.parent.parent.name == "node_modules":
        return True
    return False


def parse_node_modules_tree(root: Path, *, source_label: str = "") -> Graph:
    """Walk installed package.json files. Does not read lockfiles."""
    g = Graph()
    if not root.is_dir():
        return g
    path_to_id: dict[str, str] = {}
    pkgs: list[tuple[Path, dict]] = []
    for pj in sorted(root.rglob("package.json")):
        if not is_nm_package_json(pj):
            continue
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        name = str(data.get("name") or pj.parent.name)
        ver = str(data.get("version") or "")
        if not name or not ver:
            continue
        nid = g.add_node(
            "npm",
            name,
            ver,
            source=source_label or pj.as_posix(),
        )
        path_to_id[pj.parent.as_posix()] = nid
        pkgs.append((pj.parent, data))

    def resolve_dep(pkg_dir: Path, dep_name: str) -> str | None:
        cur = pkg_dir
        while True:
            scoped = None
            if dep_name.startswith("@") and "/" in dep_name:
                scoped = cur / "node_modules" / dep_name
            cand = scoped or (cur / "node_modules" / dep_name)
            key = cand.as_posix()
            if key in path_to_id:
                return path_to_id[key]
            if cur.parent == cur:
                return None
            # climb to the enclosing node_modules parent
            if cur.name == "node_modules":
                cur = cur.parent
                continue
            if cur.parent.name == "node_modules":
                cur = cur.parent.parent
                continue
            if cur.parent.name.startswith("@") and cur.parent.parent.name == "node_modules":
                cur = cur.parent.parent.parent
                continue
            cur = cur.parent

    for pkg_dir, data in pkgs:
        src = path_to_id[pkg_dir.as_posix()]
        deps = data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}
        for dep_name in deps:
            child = resolve_dep(pkg_dir, str(dep_name))
            if child:
                g.add_edge(src, child)
    pointed = {b for _, b in g.edges}
    g.roots = [nid for nid in g.nodes if nid not in pointed]
    return g


# --------------------------------------------------------------------------- live worktree + upstream tables
def _rel(repo: Path, path: Path) -> str:
    try:
        rel = path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
    return "" if rel == "." else rel


def skip_live(rel: str) -> bool:
    rel = rel.replace("\\", "/").lstrip("./")
    for prefix in LIVE_SKIP_PREFIXES:
        p = prefix.rstrip("/")
        if rel == p or rel.startswith(p + "/"):
            return True
    return False


def _prune(repo: Path, root: str, dirs: list[str]) -> None:
    dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
    rel = _rel(repo, Path(root)).replace("\\", "/")
    kept: list[str] = []
    for d in dirs:
        child = f"{rel}/{d}" if rel else d
        if skip_live(child):
            continue
        kept.append(d)
    dirs[:] = kept


def iter_files(repo: Path, names: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in _os_walk(repo):
        _prune(repo, root, dirs)
        rootp = Path(root)
        for n in names:
            if n in files:
                p = rootp / n
                rel = _rel(repo, p)
                if not skip_live(rel):
                    out.append(p)
    return sorted(out, key=lambda p: _rel(repo, p))


def artifact_payload(doc: dict) -> dict:
    """Domain payload: report when present, else the document itself."""
    rep = doc.get("report")
    if isinstance(rep, dict) and ("graph" in rep or rep.get("kind") == "audit-graph"):
        return rep
    return doc


def _os_walk(repo: Path):
    import os

    for root, dirs, files in os.walk(repo):
        yield root, dirs, files


def parse_pyproject_directs(path: Path) -> dict[str, str]:
    try:
        d = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    deps: dict[str, str] = {}
    for raw in (d.get("project") or {}).get("dependencies") or []:
        m = REQ_NAME.match(str(raw))
        if m:
            deps[norm_py(m.group(1))] = str(raw)
    for extra in ((d.get("project") or {}).get("optional-dependencies") or {}).values():
        for raw in extra or []:
            m = REQ_NAME.match(str(raw))
            if m:
                deps.setdefault(norm_py(m.group(1)), str(raw))
    for raw in (d.get("build-system") or {}).get("requires") or []:
        m = REQ_NAME.match(str(raw))
        if m:
            deps.setdefault(norm_py(m.group(1)), f"build-system:{raw}")
    return deps


def _lockfile_row(repo: Path, path: Path, graph: Graph, ecosystem: str) -> dict[str, Any]:
    pub = graph.to_public()
    return {
        "path": _rel(repo, path),
        "ecosystem": ecosystem,
        "node_count": pub["node_count"],
        "edge_count": pub["edge_count"],
        "max_depth": pub["max_depth"],
        "duplicate_versions": pub["duplicate_versions"],
    }


def _within_lockfile_duplicates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Packages with two or more versions inside one lockfile closure."""
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for row in rows:
        for d in row.get("duplicate_versions") or []:
            key = (d.get("ecosystem"), d.get("name"), tuple(d.get("versions") or []))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "ecosystem": d["ecosystem"],
                    "name": d["name"],
                    "versions": list(d["versions"]),
                }
            )
    return out


def live_resolver_graph(repo: Path) -> tuple[Graph, dict[str, Any]]:
    """Probe 1 live input: lockfiles that are the resolver's frozen tree."""
    locks_npm = iter_files(repo, ("package-lock.json", "npm-shrinkwrap.json"))
    locks_uv = iter_files(repo, ("uv.lock",))
    graphs: list[Graph] = []
    rows: list[dict[str, Any]] = []
    for p in locks_npm:
        g = parse_npm_lock_path(p)
        graphs.append(g)
        rows.append(_lockfile_row(repo, p, g, "npm"))
    for p in locks_uv:
        g = parse_uv_lock_path(p)
        graphs.append(g)
        rows.append(_lockfile_row(repo, p, g, "pypi"))
    g = merge_graphs(*graphs) if graphs else Graph()
    within = _within_lockfile_duplicates(rows)
    merged = g.to_public()
    census = {
        "npm_lockfiles": [_rel(repo, p) for p in locks_npm],
        "uv_lockfiles": [_rel(repo, p) for p in locks_uv],
        "lockfile_count": len(locks_npm) + len(locks_uv),
        "per_lockfile": rows,
        "within_lockfile_duplicates": within,
        "max_depth_within_lockfile": max((r["max_depth"] for r in rows), default=0),
        "merged_duplicate_versions": merged["duplicate_versions"],
        "cross_lockfile_version_spread": [
            d
            for d in merged["duplicate_versions"]
            if (d.get("ecosystem"), d.get("name"))
            not in {(x["ecosystem"], x["name"]) for x in within}
        ],
    }
    return g, census


def live_resolver_snapshot(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Canonical live lock-tree public graph used by emit and both probes."""
    g, census = live_resolver_graph(repo)
    pub = g.to_public()
    pub["duplicate_versions"] = census["within_lockfile_duplicates"]
    pub["max_depth"] = census["max_depth_within_lockfile"]
    pub["duplicate_scope"] = "per-lockfile-closure"
    return pub, census


def live_installed_graph(repo: Path) -> tuple[Graph, dict[str, Any]]:
    """Probe 2 live input: in-tree installed metadata, never host site-packages."""
    nm_roots: list[Path] = []
    dist_roots: list[Path] = []
    skip_nm = SKIP_DIR_NAMES | {"node_modules"}
    for root, dirs, files in _os_walk(repo):
        dirs[:] = [d for d in dirs if d not in skip_nm]
        rootp = Path(root)
        rel = _rel(repo, rootp)
        if skip_live(rel):
            dirs[:] = []
            continue
        _prune(repo, root, dirs)
        try:
            children = list(rootp.iterdir())
        except OSError:
            continue
        if (rootp / "node_modules").is_dir():
            nm_roots.append(rootp / "node_modules")
        if any(p.name.endswith(".dist-info") for p in children if p.is_dir()):
            dist_roots.append(rootp)
    graphs = [parse_node_modules_tree(p) for p in nm_roots]
    graphs += [parse_dist_info_tree(p) for p in dist_roots]
    g = merge_graphs(*graphs) if graphs else Graph()
    census = {
        "node_modules_trees": [_rel(repo, p) for p in nm_roots],
        "dist_info_trees": [_rel(repo, p) for p in dist_roots],
        "host_site_packages_consulted": False,
    }
    return g, census


def live_installed_snapshot(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Canonical live installed-metadata public graph used by emit and probe 2."""
    g, census = live_installed_graph(repo)
    return g.to_public(), census


def live_manifest_census(repo: Path) -> dict[str, Any]:
    pyprojects = iter_files(repo, ("pyproject.toml",))
    packages_json = iter_files(repo, ("package.json",))
    reqs = [
        p
        for p in iter_files(
            repo,
            (
                "requirements.txt",
                "requirements-dev.txt",
                "requirements.in",
            ),
        )
    ]
    py_direct: dict[str, set[str]] = defaultdict(set)
    py_rows = []
    for p in pyprojects:
        deps = parse_pyproject_directs(p)
        py_rows.append(
            {
                "path": _rel(repo, p),
                "declared": deps,
                "declared_dep_count": len(deps),
            }
        )
        for n, s in deps.items():
            py_direct[n].add(s)
    return {
        "pyproject_toml": [_rel(repo, p) for p in pyprojects],
        "package_json": [_rel(repo, p) for p in packages_json],
        "requirements": [_rel(repo, p) for p in reqs],
        "python_manifest_rows": py_rows,
        "python_declared_multi_spec": {
            k: sorted(v) for k, v in sorted(py_direct.items()) if len(v) > 1
        },
    }


def load_upstream_directs(repo: Path) -> dict[str, Any]:
    p20 = repo / "command-center/p2-wave/probes/AUD-0020/probe1-manifests.json"
    p21 = repo / "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json"
    a20 = repo / "command-center/audit/AUD-0020-python-dep-inventory.json"
    a21 = repo / "command-center/audit/AUD-0021-node-dep-inventory.json"

    def load(path: Path):
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    py = load(p20)
    node = load(p21)
    py_specs: dict[str, set[str]] = defaultdict(set)
    py_present = 0
    py_missing = 0
    if isinstance(py, list):
        for row in py:
            if not isinstance(row, dict):
                continue
            man = str(row.get("manifest") or "")
            if man and (repo / man).is_file():
                py_present += 1
            else:
                py_missing += 1
            for n, s in (row.get("declared") or {}).items():
                py_specs[norm_py(str(n))].add(str(s))
    node_specs: dict[str, set[str]] = defaultdict(set)
    node_present = 0
    node_missing = 0
    if isinstance(node, list):
        for row in node:
            if not isinstance(row, dict):
                continue
            man = str(row.get("path") or "")
            if man and (repo / man).is_file():
                node_present += 1
            else:
                node_missing += 1
            deps = row.get("dependencies") or {}
            if isinstance(deps, dict):
                for block in deps.values():
                    if isinstance(block, dict):
                        for n, s in block.items():
                            node_specs[str(n)].add(str(s))
    return {
        "aud0020_probe_table": p20.is_file(),
        "aud0021_probe_table": p21.is_file(),
        "aud0020_output_artifact": a20.is_file(),
        "aud0021_output_artifact": a21.is_file(),
        "python_manifest_rows": len(py) if isinstance(py, list) else 0,
        "node_manifest_rows": len(node) if isinstance(node, list) else 0,
        "python_manifests_present_on_disk": py_present,
        "python_manifests_missing_on_disk": py_missing,
        "node_manifests_present_on_disk": node_present,
        "node_manifests_missing_on_disk": node_missing,
        "python_declared_multi_spec": {
            k: sorted(v) for k, v in sorted(py_specs.items()) if len(v) > 1
        },
        "node_declared_multi_spec": {
            k: sorted(v) for k, v in sorted(node_specs.items()) if len(v) > 1
        },
        "note": (
            "Probe tables are the catalog input 'direct dependency tables'. "
            "They are not a resolved transitive closure. Official AUD-0020/"
            "AUD-0021 output_path artifacts are recorded present/absent "
            "separately. Retrying a missing official artifact as if it were "
            "the closure would be a detector failure."
        ),
    }


def name_version_set(pub: dict[str, Any], ecosystem: str) -> set[tuple[str, str]]:
    out = set()
    for n in pub.get("nodes") or []:
        if n.get("ecosystem") == ecosystem:
            out.add((str(n.get("name")), str(n.get("version"))))
    return out
