#!/usr/bin/env python3
"""Declared-vs-read configuration parity for BLD-0005.

Left set: keys declared in plugin/marketplace/settings-schema/workflow-preset/
coverage-threshold JSON, plus WORK-UNIT-CATALOG.json defaults.
Right set: configuration read sites (os.environ.get / getenv / os.environ[],
cfg[...], settings.get, argparse dest, Get-ItemProperty, ${ENV} in YAML/PS).

A key read only under tests/fixtures classifies FIXTURE-ONLY, not product-orphan.
Use-vs-mention: comments, docstrings, and this unit's own probe tree are not
read sites. Live product scans skip command-center/p2-wave/probes/.

Strike-1/2 were structured Python AST + PS/YAML regex. The catalog pivot
(whole-tree token scan of read-shaped lines) is signal 2 and always runs.
"""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PLANTED_ORPHAN = "BLD0005_PLANTED_ORPHAN_KEY"
PLANTED_UNDECLARED = "BLD0005_PLANTED_UNDECLARED_ENV"
PLANTED_FIXTURE = "BLD0005_PLANTED_FIXTURE_ONLY_KEY"
PLANTED_MATCHED = "BLD0005_PLANTED_MATCHED_KEY"
REVIEWER_ORPHANS = (
    PLANTED_ORPHAN,
    "BLD0005_ORPHAN_TWO",
    "BLD0005_ORPHAN_THREE",
    "BLD0005_ORPHAN_FOUR",
    "BLD0005_ORPHAN_FIVE",
)

SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".cursor",
        "dist",
        "build",
    }
)
SKIP_SUFFIX = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".woff",
        ".woff2",
        ".pdf",
        ".zip",
        ".gz",
        ".whl",
    }
)
MAX_BYTES = 2_000_000
OWN_UNIT_PARTS = ("command-center", "p2-wave", "probes", "BLD-0005")
PROBES_PARTS = ("command-center", "p2-wave", "probes")
TEST_DIR_NAMES = frozenset({"tests", "test"})
MANIFEST_STRUCTURAL = frozenset(
    {
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "logo",
        "hooks",
        "skills",
        "rules",
        "docs",
        "plugins",
        "id",
        "category",
        "plugin_id",
        "schema",
        "stages",
        "stopping",
        "_generated",
        "_comment",
        "$schema",
        "$id",
        "$defs",
        "definitions",
        "title",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "if",
        "then",
        "else",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "enum",
        "const",
        "default",
        "examples",
        "description",
    }
)
CONFIG_NEST_KEYS = frozenset(
    {"config", "settings", "env", "environment", "parameters", "options", "knobs"}
)
GET_NAMES = frozenset({"get", "getenv"})
CFG_NAMES = frozenset({"cfg", "config", "settings", "conf", "environ", "os.environ"})

ENV_GET_RE = re.compile(
    r"""(?:os\.environ\.get|os\.getenv|environ\.get)\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""
)
ENV_SUB_RE = re.compile(r"""os\.environ\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]""")
SETTINGS_GET_RE = re.compile(
    r"""(?:settings|cfg|config)\.get\(\s*['"]([A-Za-z_][A-Za-z0-9_.]*)['"]"""
)
CFG_SUB_RE = re.compile(
    r"""(?:settings|cfg|config)\[\s*['"]([A-Za-z_][A-Za-z0-9_.]*)['"]\s*\]"""
)
PS_ENV_RE = re.compile(r"\$env:([A-Za-z_][A-Za-z0-9_]*)")
PS_ITEM_RE = re.compile(
    r"(?i)Get-ItemProperty\b[^\n]*?-Name\s+['\"]?([A-Za-z_][A-Za-z0-9_]*)"
)
YAML_INTERP_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
READ_SHAPED_RE = re.compile(
    r"(os\.environ|os\.getenv|environ\.get|settings\.get|cfg\[|config\.get|"
    r"Get-ItemProperty|\$env:|\$\{[A-Za-z_])",
    re.I,
)


@dataclass
class Site:
    path: str
    line: int
    snippet: str
    detector: str
    kind: str
    is_test: bool = False
    source_class: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "snippet": self.snippet[:240],
            "detector": self.detector,
            "kind": self.kind,
            "is_test": self.is_test,
            "source_class": self.source_class,
        }


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parts_from(root: Path, path: Path) -> tuple[str, ...]:
    return Path(_rel(root, path)).parts


def _is_own_unit(root: Path, path: Path) -> bool:
    return _parts_from(root, path)[:4] == OWN_UNIT_PARTS


def _is_probe_tree(root: Path, path: Path) -> bool:
    return _parts_from(root, path)[:3] == PROBES_PARTS


def is_test_path(rel: str) -> bool:
    parts = Path(rel).parts
    name = Path(rel).name
    if name.startswith("test_") or name == "conftest.py":
        return True
    return any(p in TEST_DIR_NAMES for p in parts)


def iter_files(
    root: Path,
    *,
    skip_own_unit: bool = True,
    skip_probe_tree: bool = False,
    suffixes: frozenset[str] | None = None,
) -> Iterator[Path]:
    """Walk files under root, pruning skip dirs (and live probe trees) in-place.

    Path.rglob does not prune; the live product scan must not descend into the
    30k-file sibling probe tree or cache directories.
    """
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        try:
            rel_dir = Path(dirpath).resolve().relative_to(root).as_posix()
        except ValueError:
            dirnames[:] = []
            continue
        parts = () if rel_dir in {".", ""} else tuple(rel_dir.split("/"))
        if skip_probe_tree and parts[:3] == PROBES_PARTS:
            dirnames[:] = []
            continue
        if skip_own_unit and parts[:4] == OWN_UNIT_PARTS:
            dirnames[:] = []
            continue
        for name in filenames:
            suf = Path(name).suffix.lower()
            if suf in SKIP_SUFFIX:
                continue
            if suffixes is not None and suf not in suffixes:
                continue
            p = Path(dirpath) / name
            try:
                if not p.is_file() or p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def _snippet(lines: list[str], idx: int) -> str:
    if idx < 0 or idx >= len(lines):
        return ""
    return lines[idx].rstrip()[:240]


def _line_of_key(text: str, key: str, start: int = 0) -> int:
    needle = f'"{key}"'
    pos = text.find(needle, start)
    if pos < 0:
        needle = f"'{key}'"
        pos = text.find(needle, start)
    if pos < 0:
        return 1
    return text.count("\n", 0, pos) + 1


def _add_decl(
    decls: dict[str, list[Site]],
    key: str,
    site: Site,
) -> None:
    if not key or key in MANIFEST_STRUCTURAL:
        return
    decls.setdefault(key, []).append(site)


def _walk_properties(
    props: dict[str, Any],
    *,
    rel: str,
    text: str,
    source_class: str,
    decls: dict[str, list[Site]],
    prefix: str = "",
) -> None:
    if not isinstance(props, dict):
        return
    for key, spec in props.items():
        if not isinstance(key, str):
            continue
        token = f"{prefix}{key}" if prefix else key
        line = _line_of_key(text, key)
        _add_decl(
            decls,
            token,
            Site(
                path=rel,
                line=line,
                snippet=_snippet(text.splitlines(), line - 1),
                detector="schema-properties",
                kind="declare",
                source_class=source_class,
            ),
        )
        if isinstance(spec, dict):
            nested = spec.get("properties")
            if isinstance(nested, dict):
                _walk_properties(
                    nested,
                    rel=rel,
                    text=text,
                    source_class=source_class,
                    decls=decls,
                    prefix=f"{token}.",
                )


def extract_json_config_keys(
    path: Path,
    rel: str,
    source_class: str,
    decls: dict[str, list[Site]],
) -> None:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return

    def take_mapping(obj: Any, nest: str) -> None:
        if not isinstance(obj, dict):
            return
        for key in obj:
            if not isinstance(key, str):
                continue
            line = _line_of_key(text, key)
            _add_decl(
                decls,
                key,
                Site(
                    path=rel,
                    line=line,
                    snippet=_snippet(text.splitlines(), line - 1),
                    detector=f"json:{nest}",
                    kind="declare",
                    source_class=source_class,
                ),
            )

    for nest in CONFIG_NEST_KEYS:
        if nest in data:
            take_mapping(data.get(nest), nest)
    contributes = data.get("contributes")
    if isinstance(contributes, dict):
        conf = contributes.get("configuration")
        if isinstance(conf, dict) and isinstance(conf.get("properties"), dict):
            _walk_properties(
                conf["properties"],
                rel=rel,
                text=text,
                source_class=source_class,
                decls=decls,
            )
    if source_class == "settings_schema" and isinstance(data.get("properties"), dict):
        _walk_properties(
            data["properties"],
            rel=rel,
            text=text,
            source_class=source_class,
            decls=decls,
        )
    if source_class == "coverage_thresholds":
        take_mapping(data, "coverage")
    if source_class in {"plugin_manifest", "marketplace_manifest"}:
        # Top-level non-structural scalars/objects that look like knobs, not lists of paths.
        for key, val in data.items():
            if key in CONFIG_NEST_KEYS or key in MANIFEST_STRUCTURAL:
                continue
            if key.startswith("_") or key.startswith("$"):
                continue
            if isinstance(val, (list, dict)) and key not in {"config", "settings"}:
                continue
            line = _line_of_key(text, key)
            _add_decl(
                decls,
                key,
                Site(
                    path=rel,
                    line=line,
                    snippet=_snippet(text.splitlines(), line - 1),
                    detector="json:toplevel",
                    kind="declare",
                    source_class=source_class,
                ),
            )


def extract_catalog_defaults(
    path: Path, rel: str, decls: dict[str, list[Site]]
) -> None:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    defaults = data.get("defaults") if isinstance(data, dict) else None
    if not isinstance(defaults, dict):
        return
    start = text.find('"defaults"')
    for key in defaults:
        if not isinstance(key, str):
            continue
        line = _line_of_key(text, key, start if start >= 0 else 0)
        _add_decl(
            decls,
            key,
            Site(
                path=rel,
                line=line,
                snippet=_snippet(text.splitlines(), line - 1),
                detector="catalog-defaults",
                kind="declare",
                source_class="catalog_defaults",
            ),
        )


def classify_declaration_file(rel: str, name: str) -> str | None:
    low = rel.replace("\\", "/").lower()
    # Sibling unit fixtures and routing-estate copies are not shipped config.
    if "/fixtures/" in f"/{low}/" or "/_work/" in f"/{low}/":
        return None
    if name == "plugin.json":
        return "plugin_manifest"
    if name == "marketplace.json":
        return "marketplace_manifest"
    if name.endswith(".coverage-thresholds.json") or name == ".coverage-thresholds.json":
        return "coverage_thresholds"
    if "settings" in name.lower() and (
        name.endswith(".schema.json") or name.endswith("settings.json")
    ):
        return "settings_schema"
    # Catalog declared space is workflow presets, not every JSON with "preset"
    # in the filename (councilspec dumps, validation reports).
    if "/workflows/" in f"/{low}/" or low.endswith("/workflows.json"):
        return "workflow_preset"
    return None


def collect_declarations(
    root: Path,
    *,
    live: bool,
) -> dict[str, list[Site]]:
    decls: dict[str, list[Site]] = {}
    skip_probes = live
    for path in iter_files(
        root,
        skip_own_unit=live,
        skip_probe_tree=skip_probes,
        suffixes=frozenset({".json"}),
    ):
        rel = _rel(root, path)
        name = path.name
        if live and rel.replace("\\", "/") == "command-center/WORK-UNIT-CATALOG.json":
            extract_catalog_defaults(path, rel, decls)
            continue
        klass = classify_declaration_file(rel, name)
        if klass is None:
            continue
        extract_json_config_keys(path, rel, klass, decls)
    # Fixture trees may not contain the catalog; that is expected.
    if live:
        cat = root / "command-center" / "WORK-UNIT-CATALOG.json"
        if cat.is_file():
            extract_catalog_defaults(
                cat, "command-center/WORK-UNIT-CATALOG.json", decls
            )
    return decls


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dest_from_add_argument(call: ast.Call) -> list[str]:
    dest = None
    flags: list[str] = []
    for kw in call.keywords:
        if kw.arg == "dest":
            dest = _const_str(kw.value)
    for arg in call.args:
        s = _const_str(arg)
        if s:
            flags.append(s)
    if dest:
        return [dest]
    for flag in flags:
        if flag.startswith("--") and len(flag) > 2:
            return [flag[2:].replace("-", "_")]
    return []


class _PyReads(ast.NodeVisitor):
    def __init__(self, rel: str, lines: list[str], is_test: bool) -> None:
        self.rel = rel
        self.lines = lines
        self.is_test = is_test
        self.reads: list[tuple[str, Site]] = []

    def _site(self, node: ast.AST, key: str, detector: str) -> Site:
        line = getattr(node, "lineno", 1)
        return Site(
            path=self.rel,
            line=line,
            snippet=_snippet(self.lines, line - 1),
            detector=detector,
            kind="read",
            is_test=self.is_test,
            source_class="python",
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        tail = name.rsplit(".", 1)[-1]
        if tail in GET_NAMES and node.args:
            key = _const_str(node.args[0])
            if key:
                det = "ast:getenv" if "env" in name.lower() else "ast:get"
                if name.endswith("environ.get") or name.endswith("getenv"):
                    det = "ast:getenv"
                elif name.endswith("settings.get") or name.endswith("config.get"):
                    det = "ast:settings.get"
                self.reads.append((key, self._site(node, key, det)))
        if tail == "add_argument":
            for dest in _dest_from_add_argument(node):
                self.reads.append((dest, self._site(node, dest, "ast:argparse")))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        name = _call_name(node.value)
        key = None
        sl = node.slice
        key = _const_str(sl)
        if key and (
            name.endswith("environ")
            or name in CFG_NAMES
            or name.rsplit(".", 1)[-1] in CFG_NAMES
        ):
            det = "ast:environ[]" if "environ" in name else "ast:cfg[]"
            self.reads.append((key, self._site(node, key, det)))
        self.generic_visit(node)


def collect_python_reads(path: Path, rel: str) -> list[tuple[str, Site]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    visitor = _PyReads(rel, text.splitlines(), is_test_path(rel))
    visitor.visit(tree)
    return visitor.reads


def collect_regex_reads(path: Path, rel: str) -> list[tuple[str, Site]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    out: list[tuple[str, Site]] = []
    suffix = path.suffix.lower()
    is_test = is_test_path(rel)

    def add(key: str, line: int, detector: str, klass: str) -> None:
        out.append(
            (
                key,
                Site(
                    path=rel,
                    line=line,
                    snippet=_snippet(lines, line - 1),
                    detector=detector,
                    kind="read",
                    is_test=is_test,
                    source_class=klass,
                ),
            )
        )

    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if suffix == ".py" and stripped.startswith("#"):
            continue
        if suffix in {".ps1", ".psm1"}:
            if stripped.startswith("#"):
                continue
            for m in PS_ENV_RE.finditer(line):
                add(m.group(1), i, "ps:$env", "powershell")
            for m in PS_ITEM_RE.finditer(line):
                add(m.group(1), i, "ps:Get-ItemProperty", "powershell")
        if suffix in {".yml", ".yaml"}:
            if stripped.startswith("#"):
                continue
            for m in YAML_INTERP_RE.finditer(line):
                add(m.group(1), i, "yaml:${}", "yaml")
    return out


def _distinctive(key: str) -> bool:
    if not key:
        return False
    if len(key) >= 8 or "_" in key:
        return True
    return key.isupper() and len(key) >= 4


def token_scan_reads(
    path: Path, rel: str, keys: Iterable[str]
) -> list[tuple[str, Site]]:
    """Signal 2: whole-tree token scan.

    Read-shaped lines (getenv/cfg/Get-ItemProperty/${}) count for every key.
    Distinctive declared keys also match as quoted identifiers in Python — the
    catalog pivot after a grep that would miss `defaults.get(field)` loops.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    is_test = is_test_path(rel)
    wanted = [k for k in keys if k]
    suffix = path.suffix.lower()
    out: list[tuple[str, Site]] = []
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        shaped = bool(READ_SHAPED_RE.search(line))
        for key in wanted:
            if key not in line:
                continue
            detector = None
            if shaped:
                detector = "token-scan:read-shaped"
            elif suffix == ".py" and _distinctive(key):
                if re.search(rf"""['"]{re.escape(key)}['"]""", line):
                    detector = "token-scan:quoted"
            if detector is None:
                continue
            out.append(
                (
                    key,
                    Site(
                        path=rel,
                        line=i,
                        snippet=_snippet(lines, i - 1),
                        detector=detector,
                        kind="read",
                        is_test=is_test,
                        source_class=suffix.lstrip(".") or "token",
                    ),
                )
            )
    return out


def collect_reads(
    root: Path,
    *,
    live: bool,
    declared_keys: Iterable[str] = (),
) -> dict[str, list[Site]]:
    reads: dict[str, list[Site]] = {}
    code_suffixes = frozenset({".py", ".ps1", ".psm1", ".yml", ".yaml"})
    files = list(
        iter_files(
            root,
            skip_own_unit=live,
            skip_probe_tree=live,
            suffixes=code_suffixes,
        )
    )
    for path in files:
        rel = _rel(root, path)
        pairs: list[tuple[str, Site]] = []
        if path.suffix.lower() == ".py":
            pairs.extend(collect_python_reads(path, rel))
        pairs.extend(collect_regex_reads(path, rel))
        for key, site in pairs:
            reads.setdefault(key, []).append(site)
    declared = list(declared_keys)
    if declared:
        for path in files:
            rel = _rel(root, path)
            for key, site in token_scan_reads(path, rel, declared):
                existing = {(s.path, s.line, s.detector) for s in reads.get(key, [])}
                if (site.path, site.line, site.detector) not in existing:
                    reads.setdefault(key, []).append(site)
    return reads


def _first(sites: list[Site] | None) -> dict[str, Any] | None:
    if not sites:
        return None
    s = sites[0]
    return {"path": s.path, "line": s.line, "snippet": s.snippet[:240]}


JSON_SCHEMA_NOISE = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "$comment",
        "additionalProperties",
        "additionalItems",
    }
)
KNOB_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def looks_like_knob(key: str) -> bool:
    """Drop argparse dests, paths, and JSON-pointer fragments from UNDECLARED.

    Declared keys keep their extractor identity; this filter is only applied
    to the read-minus-declared set so a planted getenv still classifies.
    """
    if not key or key in MANIFEST_STRUCTURAL or key in JSON_SCHEMA_NOISE:
        return False
    if key[0] in "$@/*<" or "/" in key:
        return False
    if not KNOB_RE.match(key):
        return False
    if len(key) < 2:
        return False
    return True


def classify(
    decls: dict[str, list[Site]], reads: dict[str, list[Site]]
) -> dict[str, Any]:
    only_left: list[dict[str, Any]] = []
    only_right: list[dict[str, Any]] = []
    fixture_only: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []

    for key, dsites in sorted(decls.items()):
        rsites = reads.get(key) or []
        product = [s for s in rsites if not s.is_test]
        tests = [s for s in rsites if s.is_test]
        row = {
            "key": key,
            "declaration_site": _first(dsites),
            "read_site": _first(product) or _first(tests),
            "declaration_count": len(dsites),
            "read_count": len(rsites),
            "source_class": dsites[0].source_class if dsites else "",
        }
        if product:
            row["classification"] = "MATCHED"
            matched.append(row)
        elif tests:
            row["classification"] = "FIXTURE-ONLY"
            row["read_site_absent_product"] = True
            fixture_only.append(row)
        else:
            row["classification"] = "ORPHAN"
            row["read_site"] = None
            row["grep_absent"] = True
            only_left.append(row)

    for key, rsites in sorted(reads.items()):
        if key in decls:
            continue
        if not looks_like_knob(key):
            continue
        product = [s for s in rsites if not s.is_test]
        tests = [s for s in rsites if s.is_test]
        row = {
            "key": key,
            "declaration_site": None,
            "read_site": _first(product) or _first(tests),
            "read_count": len(rsites),
            "source_class": (product or tests)[0].source_class if (product or tests) else "",
        }
        if product:
            row["classification"] = "UNDECLARED"
            only_right.append(row)
        elif tests:
            row["classification"] = "FIXTURE-ONLY"
            fixture_only.append(row)

    return {
        "only_left": only_left,
        "only_right": only_right,
        "fixture_only": fixture_only,
        "matched": matched,
        "counts": {
            "declared": len(decls),
            "read": len(reads),
            "only_left": len(only_left),
            "only_right": len(only_right),
            "fixture_only": len(fixture_only),
            "matched": len(matched),
        },
    }


def source_census(root: Path, *, live: bool) -> list[dict[str, Any]]:
    classes = [
        "plugin_manifest",
        "marketplace_manifest",
        "settings_schema",
        "workflow_preset",
        "coverage_thresholds",
        "catalog_defaults",
    ]
    found: dict[str, list[str]] = {c: [] for c in classes}
    if live:
        cat = "command-center/WORK-UNIT-CATALOG.json"
        if (root / cat).is_file():
            found["catalog_defaults"].append(cat)
    for path in iter_files(
        root,
        skip_own_unit=live,
        skip_probe_tree=live,
        suffixes=frozenset({".json"}),
    ):
        rel = _rel(root, path)
        klass = classify_declaration_file(rel, path.name)
        if klass:
            found[klass].append(rel)
    rows = []
    for c in classes:
        paths = sorted(set(found[c]))
        rows.append(
            {
                "class": c,
                "present": bool(paths),
                "count": len(paths),
                "paths": paths[:40],
            }
        )
    return rows


def scan(root: Path, *, live: bool) -> dict[str, Any]:
    decls = collect_declarations(root, live=live)
    reads = collect_reads(root, live=live, declared_keys=decls.keys())
    matrix = classify(decls, reads)
    matrix["sources"] = source_census(root, live=live)
    matrix["declared_keys"] = sorted(decls)
    matrix["read_keys"] = sorted(reads)
    return matrix


def run_controls(fixture_root: Path) -> dict[str, Any]:
    """Four catalog tests plus both-states on the planted orphan."""
    matrix = scan(fixture_root, live=False)
    left = {r["key"] for r in matrix["only_left"]}
    right = {r["key"] for r in matrix["only_right"]}
    fixture = {r["key"] for r in matrix["fixture_only"]}
    matched = {r["key"] for r in matrix["matched"]}

    t1 = PLANTED_ORPHAN in left and PLANTED_ORPHAN not in right
    t2 = PLANTED_UNDECLARED in right and PLANTED_UNDECLARED not in left
    t3 = PLANTED_FIXTURE in fixture and PLANTED_FIXTURE not in left
    t4 = PLANTED_MATCHED in matched and PLANTED_MATCHED not in left and PLANTED_MATCHED not in right

    # Both-states: drop the planted unused key; detector must go silent on it.
    plugin = fixture_root / "plugin.json"
    original = plugin.read_text(encoding="utf-8")
    silent_ok = False
    try:
        data = json.loads(original)
        cfg = data.get("config")
        if isinstance(cfg, dict) and PLANTED_ORPHAN in cfg:
            cfg.pop(PLANTED_ORPHAN)
            plugin.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        muted = scan(fixture_root, live=False)
        silent_ok = PLANTED_ORPHAN not in {r["key"] for r in muted["only_left"]}
    finally:
        plugin.write_text(original, encoding="utf-8")

    tests = [
        {
            "id": "planted-orphan",
            "name": "unused key planted in the manifest is reported as an orphan",
            "result": "PASS" if t1 else "FAIL",
            "key": PLANTED_ORPHAN,
        },
        {
            "id": "planted-undeclared",
            "name": "getenv of an undeclared variable is reported as an undeclared knob",
            "result": "PASS" if t2 else "FAIL",
            "key": PLANTED_UNDECLARED,
        },
        {
            "id": "fixture-only",
            "name": "key read only inside tests classifies FIXTURE-ONLY, not product-orphan",
            "result": "PASS" if t3 else "FAIL",
            "key": PLANTED_FIXTURE,
        },
        {
            "id": "negative-matched",
            "name": "declared key with a real read site appears in neither orphan set",
            "result": "PASS" if t4 else "FAIL",
            "key": PLANTED_MATCHED,
        },
        {
            "id": "both-states-orphan",
            "name": "removing the planted unused key makes the orphan detector silent",
            "result": "PASS" if silent_ok else "FAIL",
            "key": PLANTED_ORPHAN,
        },
    ]
    extra_orphans = [k for k in REVIEWER_ORPHANS if k in left]
    return {
        "pass": all(t["result"] == "PASS" for t in tests),
        "tests": tests,
        "matrix_counts": matrix["counts"],
        "reviewer_orphan_keys": extra_orphans,
        "left": sorted(left),
        "right": sorted(right),
        "fixture_only": sorted(fixture),
        "matched": sorted(matched),
    }


def find_read_sites_for_key(
    root: Path, key: str, *, skip_paths: Iterable[str] = ()
) -> list[dict[str, Any]]:
    """Independent reviewer grep: structured + read-shaped token, whole tree."""
    skip = {p.replace("\\", "/") for p in skip_paths}
    hits: list[dict[str, Any]] = []
    suffixes = frozenset({".py", ".ps1", ".psm1", ".yml", ".yaml"})
    needle = key.encode("utf-8")
    for path in iter_files(root, skip_own_unit=False, skip_probe_tree=False, suffixes=suffixes):
        rel = _rel(root, path)
        if rel.replace("\\", "/") in skip:
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if needle not in raw:
            continue
        pairs: list[tuple[str, Site]] = []
        if path.suffix.lower() == ".py":
            pairs.extend(collect_python_reads(path, rel))
        pairs.extend(collect_regex_reads(path, rel))
        pairs.extend(token_scan_reads(path, rel, [key]))
        for k, site in pairs:
            if k != key:
                continue
            hits.append(site.as_dict())
    # Dedup by path:line:detector
    seen: set[tuple[str, int, str]] = set()
    uniq: list[dict[str, Any]] = []
    for h in hits:
        sig = (h["path"], h["line"], h["detector"])
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(h)
    return uniq


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO
    live = "--fixture" not in sys.argv
    doc = scan(target, live=live)
    print(json.dumps(doc["counts"], indent=2, sort_keys=True))
    print(f"declared={doc['counts']['declared']} orphan={doc['counts']['only_left']} undeclared={doc['counts']['only_right']}")
