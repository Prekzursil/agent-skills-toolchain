#!/usr/bin/env python3
"""AUD-0032 dual-probe dead-code census.

Probe 1: AST Import / ImportFrom resolution. Comments, docstrings, and
         string literals are not uses.
Probe 2: BFS from declared CLI entries, tests, CI `python -m` lines, and
         documented commands, following AST imports PLUS string-named
         plugin registries (importlib.import_module, __import__, named
         registry dicts, JSON).

Planted control: aud0032_fx.plugin_only is named only as a registry string.
Probe 1 must report DEAD; probe 2 must report LIVE. If they agree, the
pair is not independent and emission is refused.
"""
from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FX_ROOT = HERE / "fixtures"
FX_PKG = "aud0032_fx"

PLUGIN_ONLY = "aud0032_fx.plugin_only"
MENTION_ONLY = "aud0032_fx.mention_only"
TRULY_DEAD = "aud0032_fx.truly_dead"
LIVE_MOD = "aud0032_fx.live_mod"
ENTRY = "aud0032_fx.entry"

SKIP_ALWAYS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "vendor",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
TARGET_SKIP_PARTS = {"tests", "test", "fixtures"}
REGISTRY_ASSIGN_NAMES = {
    "PLUGIN_REGISTRY",
    "PLUGINS",
    "REGISTRY",
    "ENTRY_POINTS",
    "COMMANDS",
    "COMMAND_REGISTRY",
}
DYNAMIC_IMPORT_ATTRS = {"import_module", "__import__"}
MOD_TOKEN_RE = re.compile(r"^[A-Za-z_][\w.]*$")
PY_M_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\b(?:\s+-\S+)*\s+-m\s+([A-Za-z_][\w.]*)"
)
PY_FILE_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\s+((?:tools|command-center)/[\w./-]+\.py)"
)


@dataclass
class FileRec:
    path: Path
    rel: str
    module: str
    is_test: bool
    is_target: bool
    tree: ast.AST | None
    syntax_ok: bool


@dataclass
class Census:
    files: list[FileRec]
    known: dict[str, FileRec]
    ast_edges: dict[str, set[str]]
    string_edges: dict[str, set[str]]
    calls: dict[str, set[str]]
    functions: dict[str, list[str]]
    cli_modules: set[str]
    seeds_probe2: set[str]
    seed_reasons: dict[str, list[str]]
    probe1_live: set[str]
    probe2_live: set[str]
    ci_files: list[str]
    doc_files: list[str]
    json_registries: list[str]


def skip_always(path: Path) -> bool:
    return any(p in SKIP_ALWAYS for p in path.parts)


def is_test_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or "test" in parts:
        return True
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_file(path: Path) -> tuple[ast.AST | None, bool]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, False
    try:
        return ast.parse(text, filename=str(path)), True
    except SyntaxError:
        return None, False


def collect_py(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*.py"):
        if skip_always(p):
            continue
        out.append(p)
    return sorted(out)


def has_main_guard(tree: ast.AST) -> bool:
    body = tree.body if isinstance(tree, ast.Module) else []
    for node in body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
            continue
        left, right = test.left, test.comparators[0]
        if not isinstance(test.ops[0], ast.Eq):
            continue
        if (
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(right, ast.Constant)
            and right.value == "__main__"
        ):
            return True
        if (
            isinstance(right, ast.Name)
            and right.id == "__name__"
            and isinstance(left, ast.Constant)
            and left.value == "__main__"
        ):
            return True
    return False


def longest_known(name: str, known: set[str]) -> str | None:
    if name in known:
        return name
    parts = name.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    return None


def resolve_relative(me: str, level: int, module: str | None) -> str:
    base = me.split(".")
    cut = max(len(base) - level, 0)
    prefix = base[:cut]
    if module:
        prefix = prefix + module.split(".")
    return ".".join(p for p in prefix if p)


def ast_import_targets(tree: ast.AST, me: str) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                abs_mod = resolve_relative(me, node.level, node.module)
                if abs_mod:
                    out.add(abs_mod)
                if node.module is None:
                    pkg = resolve_relative(me, node.level, None)
                    for alias in node.names:
                        if alias.name != "*":
                            out.add(f"{pkg}.{alias.name}" if pkg else alias.name)
            elif node.module:
                out.add(node.module)
                for alias in node.names:
                    if alias.name != "*":
                        out.add(f"{node.module}.{alias.name}")
    return out


def call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name):
            names.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            names.add(fn.attr)
    return names


def public_functions(tree: ast.AST) -> list[str]:
    names: list[str] = []
    body = tree.body if isinstance(tree, ast.Module) else []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def dynamic_import_strings(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        attr = None
        if isinstance(fn, ast.Name):
            attr = fn.id
        elif isinstance(fn, ast.Attribute):
            attr = fn.attr
        if attr not in DYNAMIC_IMPORT_ATTRS:
            continue
        if node.args:
            s = _const_str(node.args[0])
            if s:
                out.add(s)
    return out


def registry_dict_strings(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    body = tree.body if isinstance(tree, ast.Module) else []
    for node in body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(n in REGISTRY_ASSIGN_NAMES for n in names):
            continue
        val = node.value
        if not isinstance(val, ast.Dict):
            continue
        for v in val.values:
            s = _const_str(v)
            if s and MOD_TOKEN_RE.match(s):
                out.add(s)
    return out


def json_module_strings(path: Path, known: set[str]) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    found: set[str] = set()

    def walk(obj: object) -> None:
        if isinstance(obj, str):
            if obj in known or longest_known(obj, known):
                found.add(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return found


def command_modules(text: str) -> set[str]:
    found: set[str] = set()
    for m in PY_M_RE.finditer(text):
        found.add(m.group(1))
    for m in PY_FILE_RE.finditer(text):
        rel = m.group(1).replace("\\", "/")
        found.add(rel[:-3].replace("/", "."))
    return found


def bfs(seeds: list[str] | set[str], edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [s for s in seeds if s]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in edges.get(cur, ()):
            if nxt not in seen:
                stack.append(nxt)
    return seen


def load_files() -> list[FileRec]:
    recs: list[FileRec] = []

    def add(path: Path, root: Path, *, force_target: bool | None) -> None:
        rel = path.relative_to(REPO).as_posix()
        mod = module_name(path, root)
        test = is_test_path(path)
        if force_target is None:
            extra_skip = any(
                p in TARGET_SKIP_PARTS for p in path.relative_to(root).parts[:-1]
            )
            target = (not test) and (not extra_skip)
        else:
            target = force_target and not test
        tree, ok = parse_file(path)
        recs.append(
            FileRec(
                path=path,
                rel=rel,
                module=mod,
                is_test=test,
                is_target=target,
                tree=tree,
                syntax_ok=ok,
            )
        )

    fx_pkg = FX_ROOT / FX_PKG
    for p in collect_py(fx_pkg):
        add(p, FX_ROOT, force_target=not is_test_path(p))

    tools = REPO / "tools"
    for p in collect_py(tools):
        parts = set(p.relative_to(tools).parts)
        if "fixtures" in parts:
            continue
        add(p, REPO, force_target=None)

    return recs


def build() -> Census:
    files = load_files()
    known = {f.module: f for f in files}
    known_names = set(known)
    siblings: dict[tuple[str, str], str] = {}
    for f in files:
        siblings[(f.path.parent.as_posix(), f.path.stem)] = f.module

    ast_edges: dict[str, set[str]] = defaultdict(set)
    string_edges: dict[str, set[str]] = defaultdict(set)
    calls: dict[str, set[str]] = {}
    functions: dict[str, list[str]] = {}
    cli_modules: set[str] = set()

    def bind(name: str) -> str | None:
        return longest_known(name, known_names)

    for f in files:
        if not f.tree:
            continue
        functions[f.module] = public_functions(f.tree)
        calls[f.module] = call_names(f.tree)
        if (has_main_guard(f.tree) or f.path.name == "__main__.py") and f.is_target:
            cli_modules.add(f.module)

        for t in ast_import_targets(f.tree, f.module):
            hit = bind(t)
            if hit is None:
                first = t.split(".")[0]
                hit = siblings.get((f.path.parent.as_posix(), first))
            if hit and hit != f.module:
                ast_edges[f.module].add(hit)

        for s in dynamic_import_strings(f.tree) | registry_dict_strings(f.tree):
            hit = bind(s)
            if hit and hit != f.module:
                string_edges[f.module].add(hit)

    json_registries: list[str] = []
    for p in (FX_ROOT / FX_PKG).glob("*.json"):
        mods = json_module_strings(p, known_names)
        if not mods:
            continue
        json_registries.append(p.relative_to(REPO).as_posix())
        src = ENTRY if ENTRY in known_names else FX_PKG
        for m in mods:
            hit = bind(m)
            if hit:
                string_edges[src].add(hit)

    ci_files: list[str] = []
    doc_files: list[str] = []
    seed_reasons: dict[str, list[str]] = defaultdict(list)
    seeds: set[str] = set()

    search: list[Path] = []
    gh = REPO / ".github" / "workflows"
    if gh.is_dir():
        search.extend(gh.glob("*.yml"))
        search.extend(gh.glob("*.yaml"))
    fx = FX_ROOT / FX_PKG
    search.extend(fx.glob("*.yml"))
    search.extend(fx.glob("*.yaml"))
    for pattern in ("README*", "RUNBOOK*", "*.md"):
        search.extend(REPO.glob(pattern))
        search.extend((REPO / "tools").glob(pattern))
        search.extend(fx.glob(pattern))

    seen_paths: set[str] = set()
    for p in search:
        if not p.is_file():
            continue
        rel = p.relative_to(REPO).as_posix()
        if rel in seen_paths:
            continue
        if "fixtures" in p.parts and FX_PKG not in p.parts:
            continue
        seen_paths.add(rel)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        bound = {bind(m) for m in command_modules(text)}
        bound.discard(None)
        if not bound:
            continue
        kind = "ci" if p.suffix.lower() in {".yml", ".yaml"} else "docs"
        if kind == "ci":
            ci_files.append(rel)
        else:
            doc_files.append(rel)
        for m in bound:
            assert m is not None
            seeds.add(m)
            seed_reasons[m].append(f"{kind}:{rel}")

    for m in cli_modules:
        seeds.add(m)
        seed_reasons[m].append("cli-main-guard")

    for f in files:
        if f.is_test:
            seeds.add(f.module)
            seed_reasons[f.module].append("test")

    reverse_ast: set[str] = set()
    for dsts in ast_edges.values():
        reverse_ast.update(dsts)
    probe1_live = set(reverse_ast)

    union: dict[str, set[str]] = defaultdict(set)
    for src, dsts in ast_edges.items():
        union[src].update(dsts)
    for src, dsts in string_edges.items():
        union[src].update(dsts)
    probe2_live = bfs(seeds, union)

    return Census(
        files=files,
        known=known,
        ast_edges={k: set(v) for k, v in ast_edges.items()},
        string_edges={k: set(v) for k, v in string_edges.items()},
        calls=calls,
        functions=functions,
        cli_modules=cli_modules,
        seeds_probe2=seeds,
        seed_reasons=dict(seed_reasons),
        probe1_live=probe1_live,
        probe2_live=probe2_live,
        ci_files=sorted(set(ci_files)),
        doc_files=sorted(set(doc_files)),
        json_registries=json_registries,
    )


def module_targets(c: Census) -> list[FileRec]:
    return [f for f in c.files if f.is_target]


def control_report(c: Census) -> dict:
    p1_plugin = PLUGIN_ONLY in c.probe1_live
    p2_plugin = PLUGIN_ONLY in c.probe2_live
    p1_live = LIVE_MOD in c.probe1_live
    p2_live = LIVE_MOD in c.probe2_live
    p1_dead = TRULY_DEAD in c.probe1_live
    p2_dead = TRULY_DEAD in c.probe2_live
    p1_mention = MENTION_ONLY in c.probe1_live
    p2_mention = MENTION_ONLY in c.probe2_live

    ast_only: dict[str, set[str]] = defaultdict(set)
    for src, dsts in c.ast_edges.items():
        ast_only[src].update(dsts)
    p2_no_string = bfs(c.seeds_probe2, ast_only)
    strawman_dead = PLUGIN_ONLY not in p2_no_string

    independent = (
        (not p1_plugin)
        and p2_plugin
        and strawman_dead
        and p1_live
        and p2_live
        and (not p1_dead)
        and (not p2_dead)
        and (not p1_mention)
        and (not p2_mention)
    )
    return {
        "id": "AUD-0032-C-registry-string",
        "kind": "string-registry-only",
        "module": PLUGIN_ONLY,
        "probe1_verdict": "LIVE" if p1_plugin else "DEAD",
        "probe2_verdict": "LIVE" if p2_plugin else "DEAD",
        "probe2_without_string_edges": (
            "LIVE" if PLUGIN_ONLY in p2_no_string else "DEAD"
        ),
        "strawman_string_edges_required": strawman_dead,
        "independent": independent,
        "live_mod": {
            "probe1": "LIVE" if p1_live else "DEAD",
            "probe2": "LIVE" if p2_live else "DEAD",
        },
        "truly_dead": {
            "probe1": "LIVE" if p1_dead else "DEAD",
            "probe2": "LIVE" if p2_dead else "DEAD",
        },
        "mention_only": {
            "probe1": "LIVE" if p1_mention else "DEAD",
            "probe2": "LIVE" if p2_mention else "DEAD",
        },
        "want": {
            "plugin_only": {"probe1": "DEAD", "probe2": "LIVE"},
            "live_mod": {"probe1": "LIVE", "probe2": "LIVE"},
            "truly_dead": {"probe1": "DEAD", "probe2": "DEAD"},
            "mention_only": {"probe1": "DEAD", "probe2": "DEAD"},
        },
    }


def function_items(c: Census, *, tools_dead_cap: int = 40) -> tuple[list[dict], int]:
    items: list[dict] = []
    tools_dead: list[dict] = []
    called: set[str] = set()
    for names in c.calls.values():
        called.update(names)

    for f in c.files:
        if not f.is_target:
            continue
        for fn in c.functions.get(f.module, []):
            p1 = "LIVE" if fn in called else "DEAD"
            p2_mod = f.module in c.probe2_live
            p2 = "LIVE" if (p2_mod and fn in called) else "DEAD"
            row = {
                "id": f"{f.module}:{fn}",
                "kind": "function",
                "path": f.rel,
                "module": f.module,
                "name": fn,
                "probe1_verdict": p1,
                "probe2_verdict": p2,
                "call_resolution": "unqualified-name-match",
            }
            if f.module.startswith(FX_PKG):
                items.append(row)
            elif p1 == "DEAD" and p2 == "DEAD":
                tools_dead.append(row)
    tools_dead.sort(key=lambda r: r["id"])
    items.extend(tools_dead[:tools_dead_cap])
    return items, len(tools_dead)


def cli_items(c: Census) -> list[dict]:
    items: list[dict] = []
    for m in sorted(c.cli_modules):
        rec = c.known.get(m)
        if rec is None:
            continue
        items.append(
            {
                "id": m,
                "kind": "cli-entry",
                "path": rec.rel,
                "probe1_verdict": "LIVE" if m in c.probe1_live else "DEAD",
                "probe2_verdict": "LIVE" if m in c.probe2_live else "DEAD",
                "seed_reasons": c.seed_reasons.get(m, ["cli-main-guard"]),
            }
        )
    return items


def module_items(c: Census) -> list[dict]:
    items: list[dict] = []
    for f in sorted(module_targets(c), key=lambda x: x.module):
        items.append(
            {
                "id": f.module,
                "kind": "module",
                "path": f.rel,
                "probe1_verdict": "LIVE" if f.module in c.probe1_live else "DEAD",
                "probe2_verdict": "LIVE" if f.module in c.probe2_live else "DEAD",
                "syntax_ok": f.syntax_ok,
                "universe": "control" if f.module.startswith(FX_PKG) else "tools",
            }
        )
    return items


def probe1_payload(c: Census) -> dict:
    mods = module_items(c)
    fx = [m for m in mods if m["universe"] == "control"]
    return {
        "probe": "probe1-ast-symbol-refs",
        "method": "ast.Import/ImportFrom; comments and string literals ignored",
        "control_modules": fx,
        "plugin_only": "LIVE" if PLUGIN_ONLY in c.probe1_live else "DEAD",
        "live_mod": "LIVE" if LIVE_MOD in c.probe1_live else "DEAD",
        "truly_dead": "LIVE" if TRULY_DEAD in c.probe1_live else "DEAD",
        "mention_only": "LIVE" if MENTION_ONLY in c.probe1_live else "DEAD",
        "tools_modules": sum(1 for m in mods if m["universe"] == "tools"),
        "tools_dead": sum(
            1
            for m in mods
            if m["universe"] == "tools" and m["probe1_verdict"] == "DEAD"
        ),
    }


def probe2_payload(c: Census) -> dict:
    mods = module_items(c)
    fx = [m for m in mods if m["universe"] == "control"]
    return {
        "probe": "probe2-dynamic-reachability",
        "method": (
            "BFS from CLI __main__ guards, tests, CI python -m lines, "
            "README/RUNBOOK python -m lines, plus string-named registries"
        ),
        "seeds": sorted(c.seeds_probe2),
        "ci_files": c.ci_files,
        "doc_files": c.doc_files,
        "json_registries": c.json_registries,
        "control_modules": fx,
        "plugin_only": "LIVE" if PLUGIN_ONLY in c.probe2_live else "DEAD",
        "live_mod": "LIVE" if LIVE_MOD in c.probe2_live else "DEAD",
        "truly_dead": "LIVE" if TRULY_DEAD in c.probe2_live else "DEAD",
        "mention_only": "LIVE" if MENTION_ONLY in c.probe2_live else "DEAD",
        "string_edge_count": sum(len(v) for v in c.string_edges.values()),
        "tools_modules": sum(1 for m in mods if m["universe"] == "tools"),
        "tools_dead": sum(
            1
            for m in mods
            if m["universe"] == "tools" and m["probe2_verdict"] == "DEAD"
        ),
    }


def inventory(c: Census) -> dict:
    mods = module_items(c)
    fn_items, tools_fn_dead_total = function_items(c)
    clis = cli_items(c)
    control = control_report(c)
    tools_mods = [m for m in mods if m["universe"] == "tools"]
    disagree = [m for m in mods if m["probe1_verdict"] != m["probe2_verdict"]]
    both_dead = [
        m
        for m in mods
        if m["probe1_verdict"] == "DEAD" and m["probe2_verdict"] == "DEAD"
    ]
    return {
        "modules": mods,
        "functions": fn_items,
        "cli_entries": clis,
        "planted_control": control,
        "tallies": {
            "modules_scanned": len(mods),
            "tools_modules": len(tools_mods),
            "control_modules": sum(1 for m in mods if m["universe"] == "control"),
            "probe1_dead": sum(1 for m in mods if m["probe1_verdict"] == "DEAD"),
            "probe2_dead": sum(1 for m in mods if m["probe2_verdict"] == "DEAD"),
            "both_dead": len(both_dead),
            "disagree": len(disagree),
            "cli_entries": len(clis),
            "functions_listed": len(fn_items),
            "tools_functions_both_dead_total": tools_fn_dead_total,
        },
        "both_dead_modules": [m["id"] for m in both_dead],
        "disagree_modules": [
            {
                "id": m["id"],
                "probe1": m["probe1_verdict"],
                "probe2": m["probe2_verdict"],
            }
            for m in disagree
        ],
        "probe1": probe1_payload(c),
        "probe2": probe2_payload(c),
        "ci_files": c.ci_files,
        "doc_files": c.doc_files,
        "aud0030_graph_present": (
            REPO / "command-center/p2-wave/probes/AUD-0030/probe1-ast-graph.json"
        ).is_file(),
    }


def assert_control(c: Census) -> None:
    ctl = control_report(c)
    if not ctl["independent"]:
        raise SystemExit(
            "FAILED:AUD-0032 planted string-registry control did not discriminate "
            f"{json.dumps(ctl, sort_keys=True)}"
        )


if __name__ == "__main__":
    cen = build()
    assert_control(cen)
    print(json.dumps(control_report(cen), indent=2, sort_keys=True))
