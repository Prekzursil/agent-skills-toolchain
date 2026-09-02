"""AST census of function / CLI / config defaults plus CI-invocation join."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AUD0041 = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "AUD-0041"
    / "probe1-yaml-inventory.json"
)
AUD0057 = (
    REPO
    / "command-center"
    / "audit"
    / "AUD-0057-assertion-strength-census.json"
)
PLANTED = HERE / "fixtures" / "planted_defaults.py"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
}


@dataclass
class DefaultDecl:
    key: str
    name: str
    kind: str
    func_name: str
    file: Path
    lineno: int
    pos_index: int | None
    is_kwonly: bool
    env_dependent: bool
    flags: list[str] = field(default_factory=list)
    default_repr: str = ""
    module_stem: str = ""


@dataclass
class CallHit:
    file: Path
    lineno: int
    explicit: bool
    in_test: bool
    asserting: bool
    production: bool


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def site(decl: DefaultDecl) -> str:
    return f"{rel(decl.file)}:{decl.lineno}"


def is_test_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or path.name == "planted_defaults.py"
    )


def const_repr(node: ast.AST | None) -> str:
    if node is None:
        return "<missing>"
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def is_env_expr(node: ast.AST | None) -> bool:
    if node is None:
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in {"getenv", "get"}:
            base = child.value
            if isinstance(base, ast.Name) and base.id in {"os", "environ"}:
                return True
            if isinstance(base, ast.Attribute) and base.attr == "environ":
                return True
        if isinstance(child, ast.Name) and child.id in {"getenv", "environ"}:
            return True
        if isinstance(child, ast.Subscript):
            val = child.value
            if isinstance(val, ast.Attribute) and val.attr == "environ":
                return True
            if isinstance(val, ast.Name) and val.id == "environ":
                return True
    return False


def py_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    out: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def enclosing_fn(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST | None:
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
        cur = parents.get(id(cur))
    return None


def fn_has_assert(fn: ast.AST) -> bool:
    for child in ast.walk(fn):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr.startswith("assert"):
                return True
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id in {"assertEqual", "assertTrue", "assertFalse", "raises"}:
                return True
    return False


def collect_decls(path: Path, tree: ast.AST) -> list[DefaultDecl]:
    decls: list[DefaultDecl] = []
    stem = path.stem
    planted = path.resolve() == PLANTED.resolve()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if node.name.startswith("test_") and not planted:
                continue
            skip = {"self", "cls"}
            pos = [a for a in node.args.args if a.arg not in skip]
            defaults = list(node.args.defaults)
            kind = "planted" if planted else "function_param"
            if defaults:
                start = len(pos) - len(defaults)
                for i, dnode in enumerate(defaults):
                    param = pos[start + i]
                    decls.append(
                        DefaultDecl(
                            key=f"{rel(path)}::{node.name}.{param.arg}",
                            name=param.arg,
                            kind=kind,
                            func_name=node.name,
                            file=path,
                            lineno=node.lineno,
                            pos_index=start + i,
                            is_kwonly=False,
                            env_dependent=is_env_expr(dnode),
                            default_repr=const_repr(dnode),
                            module_stem=stem,
                        )
                    )
            for arg, dnode in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if dnode is None:
                    continue
                decls.append(
                    DefaultDecl(
                        key=f"{rel(path)}::{node.name}.{arg.arg}",
                        name=arg.arg,
                        kind=kind,
                        func_name=node.name,
                        file=path,
                        lineno=node.lineno,
                        pos_index=None,
                        is_kwonly=True,
                        env_dependent=is_env_expr(dnode),
                        default_repr=const_repr(dnode),
                        module_stem=stem,
                    )
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "add_argument":
                continue
            flags: list[str] = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value.startswith("-"):
                        flags.append(arg.value)
            if not flags:
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            action = None
            if "action" in kw and isinstance(kw["action"], ast.Constant):
                action = kw["action"].value
            dest = None
            if "dest" in kw and isinstance(kw["dest"], ast.Constant):
                dest = str(kw["dest"].value)
            if dest is None:
                long = next((f for f in flags if f.startswith("--")), flags[0])
                dest = long.lstrip("-").replace("-", "_")
            env = is_env_expr(kw.get("default"))
            default_repr = const_repr(kw.get("default")) if "default" in kw else "<cli>"
            if action == "store_true":
                default_repr = "False"
            elif action == "store_false":
                default_repr = "True"
            decls.append(
                DefaultDecl(
                    key=f"{rel(path)}::CLI:{flags[0]}",
                    name=str(dest),
                    kind="cli_flag",
                    func_name="CLI",
                    file=path,
                    lineno=getattr(node, "lineno", 1),
                    pos_index=None,
                    is_kwonly=True,
                    env_dependent=env,
                    flags=flags,
                    default_repr=default_repr,
                    module_stem=stem,
                )
            )
        if isinstance(node, ast.Assign) and not planted:
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                ident = target.id
                if not (
                    ident.startswith("DEFAULT_")
                    or ident.endswith("_DEFAULT")
                    or ident == "DEFAULT"
                ):
                    continue
                decls.append(
                    DefaultDecl(
                        key=f"{rel(path)}::CONFIG:{ident}",
                        name=ident,
                        kind="config_default",
                        func_name="<module>",
                        file=path,
                        lineno=node.lineno,
                        pos_index=None,
                        is_kwonly=True,
                        env_dependent=is_env_expr(node.value),
                        default_repr=const_repr(node.value),
                        module_stem=stem,
                    )
                )
    return decls


def import_maps(tree: ast.AST) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    aliases: dict[str, str] = {}
    froms: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[-1]
                aliases[local] = alias.name.split(".")[-1]
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[-1]
            for alias in node.names:
                local = alias.asname or alias.name
                froms[local] = (mod, alias.name)
    return aliases, froms


def call_base_name(call: ast.Call) -> tuple[str | None, str | None]:
    func = call.func
    if isinstance(func, ast.Name):
        return None, func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    return None, None


def param_explicit(call: ast.Call, decl: DefaultDecl) -> bool:
    for kw in call.keywords:
        if kw.arg == decl.name:
            return True
    if decl.is_kwonly or decl.pos_index is None:
        return False
    return len(call.args) > decl.pos_index


def load_ci_commands() -> tuple[list[dict[str, Any]], bool, bool]:
    live_dir = REPO / ".github" / "workflows"
    live_present = live_dir.is_dir() and any(live_dir.glob("*.y*ml"))
    recorded_present = AUD0041.is_file()
    commands: list[dict[str, Any]] = []
    if recorded_present:
        data = json.loads(AUD0041.read_text(encoding="utf-8"))
        for wf in data.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            wf_file = str(wf.get("file") or wf.get("file") or "")
            for job in wf.get("jobs") or []:
                if not isinstance(job, dict):
                    continue
                for step in job.get("steps") or []:
                    if not isinstance(step, dict):
                        continue
                    cmd = str(step.get("command") or "")
                    if cmd:
                        commands.append(
                            {
                                "source": "AUD-0041-recorded",
                                "workflow": wf_file,
                                "live_yaml": (REPO / wf_file).is_file() if wf_file else False,
                                "command": cmd,
                            }
                        )
    if live_present:
        for yml in sorted(live_dir.glob("*.y*ml")):
            text = yml.read_text(encoding="utf-8", errors="replace")
            commands.append(
                {
                    "source": "live-github",
                    "workflow": rel(yml),
                    "live_yaml": True,
                    "command": text,
                }
            )
    return commands, live_present, recorded_present


def tool_invoked(cmd: str, tool_file: Path) -> bool:
    name = tool_file.name
    posix = rel(tool_file)
    return name in cmd or posix in cmd


def flag_passed(cmd: str, flags: Iterable[str]) -> bool:
    return any(flag in cmd for flag in flags)


def classify(
    decl: DefaultDecl,
    hits: list[CallHit],
    ci_cmds: list[dict[str, Any]],
) -> dict[str, Any]:
    explicit = [h for h in hits if h.explicit]
    omitted = [h for h in hits if not h.explicit]
    omitted_asserting = [h for h in omitted if h.in_test and h.asserting]
    omitted_empty_test = [h for h in omitted if h.in_test and not h.asserting]
    omitted_prod = [h for h in omitted if h.production]

    ci_tool = [
        c
        for c in ci_cmds
        if decl.kind == "cli_flag" and tool_invoked(c["command"], decl.file)
    ]
    ci_flag = [c for c in ci_tool if flag_passed(c["command"], decl.flags)]

    if decl.env_dependent:
        classification = "ENVIRONMENT-DEPENDENT"
        reason = "DEFAULT-FROM-ENV"
        reported_unexercised = False
    elif decl.kind == "cli_flag" and ci_tool:
        if ci_flag:
            classification = "EXERCISED"
            reason = "CI-PASSES-FLAG"
            reported_unexercised = False
        else:
            classification = "UNEXERCISED"
            reason = "CI-OMITS-FLAG"
            reported_unexercised = True
    elif omitted_asserting or omitted_prod:
        classification = "EXERCISED"
        reason = (
            "OMITTED-BY-ASSERTING-TEST" if omitted_asserting else "OMITTED-IN-PRODUCTION"
        )
        reported_unexercised = False
    elif omitted_empty_test and not omitted_asserting and not omitted_prod:
        classification = "UNEXERCISED"
        reason = "EMPTY-TEST-ONLY"
        reported_unexercised = True
    else:
        classification = "UNEXERCISED"
        reason = "DEFAULT-NEVER-USED"
        reported_unexercised = True

    return {
        "key": decl.key,
        "name": decl.name,
        "kind": decl.kind,
        "func_name": decl.func_name,
        "declaration_site": site(decl),
        "default_repr": decl.default_repr,
        "flags": list(decl.flags),
        "env_dependent": decl.env_dependent,
        "explicit_call_site_count": len(explicit),
        "omitted_asserting_test_count": len(omitted_asserting),
        "omitted_empty_test_count": len(omitted_empty_test),
        "omitted_production_count": len(omitted_prod),
        "explicit_examples": [f"{rel(h.file)}:{h.lineno}" for h in explicit[:5]],
        "omitted_examples": [f"{rel(h.file)}:{h.lineno}" for h in omitted[:5]],
        "ci_tool_invocations": len(ci_tool),
        "ci_flag_passed": len(ci_flag),
        "classification": classification,
        "reason": reason,
        "reported_unexercised": reported_unexercised,
    }


def run_census() -> dict[str, Any]:
    roots = [REPO / "tools", PLANTED]
    files: list[Path] = []
    for root in roots:
        files.extend(py_files(root))
    files = sorted(set(files))

    decls: list[DefaultDecl] = []
    parsed: dict[Path, ast.AST] = {}
    for path in files:
        tree = parse(path)
        if tree is None:
            continue
        parsed[path] = tree
        decls.extend(collect_decls(path, tree))

    hits: dict[str, list[CallHit]] = {d.key: [] for d in decls}
    fn_in_file: dict[tuple[str, str], list[DefaultDecl]] = {}
    for decl in decls:
        if decl.kind in {"function_param", "planted"}:
            fn_in_file.setdefault((rel(decl.file), decl.func_name), []).append(decl)
            fn_in_file.setdefault((decl.module_stem, decl.func_name), []).append(decl)

    for path, tree in parsed.items():
        aliases, froms = import_maps(tree)
        parents = parent_map(tree)
        test = is_test_path(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            base, fname = call_base_name(node)
            if not fname:
                continue
            candidates: list[DefaultDecl] = []
            if base is None:
                if fname in froms:
                    mod, orig = froms[fname]
                    candidates.extend(fn_in_file.get((mod, orig), []))
                else:
                    candidates.extend(fn_in_file.get((rel(path), fname), []))
            else:
                if base in aliases:
                    candidates.extend(fn_in_file.get((aliases[base], fname), []))
                elif base == path.stem:
                    candidates.extend(fn_in_file.get((rel(path), fname), []))
            if not candidates:
                continue
            fn_node = enclosing_fn(node, parents)
            asserting = bool(fn_node and fn_has_assert(fn_node))
            production = not test
            seen: set[str] = set()
            for decl in candidates:
                if decl.key in seen:
                    continue
                seen.add(decl.key)
                hits[decl.key].append(
                    CallHit(
                        file=path,
                        lineno=getattr(node, "lineno", 1),
                        explicit=param_explicit(node, decl),
                        in_test=test,
                        asserting=asserting,
                        production=production,
                    )
                )

    ci_cmds, live_gh, rec_inv = load_ci_commands()
    rows = [classify(d, hits[d.key], ci_cmds) for d in decls]
    unexercised = [r for r in rows if r["reported_unexercised"]]
    env_rows = [r for r in rows if r["classification"] == "ENVIRONMENT-DEPENDENT"]
    exercised = [r for r in rows if r["classification"] == "EXERCISED"]

    validate_cli = next(
        (
            r
            for r in rows
            if r["kind"] == "cli_flag"
            and r["name"] == "require_complete"
            and "validate.py" in r["declaration_site"]
        ),
        None,
    )
    validate_fn = next(
        (
            r
            for r in rows
            if r["kind"] == "function_param"
            and r["name"] == "require_complete"
            and r["func_name"] == "validate"
            and "validate.py" in r["declaration_site"]
        ),
        None,
    )
    planted = {r["func_name"]: r for r in rows if r["kind"] == "planted"}

    validate_inv = [
        c
        for c in ci_cmds
        if "validate.py" in c["command"] and "command-center" in c["command"]
    ]
    require_passed = [c for c in validate_inv if "--require-complete" in c["command"]]

    return {
        "scope": {
            "roots": ["tools/", rel(PLANTED)],
            "bound": (
                "Shipped Python under tools/ plus BLD-0042 planted fixtures. "
                "Not a whole-repo walk of command-center/p2-wave probes."
            ),
            "files_parsed": len(parsed),
            "python_files": len(files),
        },
        "defaults_enumerated": len(rows),
        "rows": rows,
        "unexercised": unexercised,
        "exercised": exercised,
        "environment_dependent": env_rows,
        "ci_join": {
            "live_github_workflows_present": live_gh,
            "recorded_inventory_present": rec_inv,
            "recorded_inventory_path": rel(AUD0041),
            "commands_collected": len(ci_cmds),
            "validate_py_invocations": len(validate_inv),
            "require_complete_flag_passed": len(require_passed),
            "validate_invocation_examples": [
                {
                    "workflow": c["workflow"],
                    "source": c["source"],
                    "live_yaml": c["live_yaml"],
                    "command_excerpt": c["command"][:400],
                }
                for c in validate_inv[:4]
            ],
        },
        "consumed_aud_0057": {
            "path": rel(AUD0057),
            "present": AUD0057.is_file(),
            "note": (
                "AUD-0057 artifact is ABSENT on this worktree. BLD-0042 still "
                "performs its own AST census and the CI-invocation join."
            ),
        },
        "known": {
            "require_complete_cli": validate_cli,
            "require_complete_fn": validate_fn,
            "planted": planted,
        },
    }


def control_results(census: dict[str, Any]) -> list[dict[str, Any]]:
    known = census["known"]
    cli = known.get("require_complete_cli") or {}
    planted = known.get("planted") or {}
    exercised = planted.get("planted_exercised") or {}
    env = planted.get("planted_env") or {}
    never_omitted = planted.get("planted_never_omitted") or {}
    empty = planted.get("planted_empty_test_only") or {}
    ci = census["ci_join"]

    c1_ok = (
        bool(cli)
        and cli.get("classification") == "UNEXERCISED"
        and cli.get("reason") == "CI-OMITS-FLAG"
        and int(ci.get("validate_py_invocations") or 0) >= 1
        and int(ci.get("require_complete_flag_passed") or 0) == 0
    )
    c2_ok = (
        bool(exercised)
        and exercised.get("classification") == "EXERCISED"
        and not exercised.get("reported_unexercised")
    )
    c3_ok = (
        bool(env)
        and env.get("classification") == "ENVIRONMENT-DEPENDENT"
        and not env.get("reported_unexercised")
    )
    extra_ok = (
        bool(never_omitted)
        and never_omitted.get("classification") == "UNEXERCISED"
        and bool(empty)
        and empty.get("reason") == "EMPTY-TEST-ONLY"
    )
    return [
        {
            "id": "require_complete_ci_bare",
            "expected": (
                "CLI --require-complete UNEXERCISED (CI-OMITS-FLAG) while CI "
                "invokes validate.py bare"
            ),
            "observed": (
                f"cli={cli.get('classification')}/{cli.get('reason')} "
                f"ci_invocations={ci.get('validate_py_invocations')} "
                f"flag_passed={ci.get('require_complete_flag_passed')} "
                f"live_github={ci.get('live_github_workflows_present')} "
                f"aud0041={ci.get('recorded_inventory_present')}"
            ),
            "result": "PASS" if c1_ok else "FAIL",
        },
        {
            "id": "asserting_test_not_reported",
            "expected": "planted_exercised EXERCISED and absent from unexercised report",
            "observed": (
                f"class={exercised.get('classification')} "
                f"reported_unexercised={exercised.get('reported_unexercised')} "
                f"omitted_asserting={exercised.get('omitted_asserting_test_count')}"
            ),
            "result": "PASS" if c2_ok else "FAIL",
        },
        {
            "id": "env_default_separate",
            "expected": "planted_env ENVIRONMENT-DEPENDENT, not EXERCISED",
            "observed": (
                f"class={env.get('classification')} "
                f"reported_unexercised={env.get('reported_unexercised')}"
            ),
            "result": "PASS" if c3_ok else "FAIL",
        },
        {
            "id": "never_used_and_empty_test",
            "expected": "planted_never_omitted UNEXERCISED; empty-test-only still UNEXERCISED",
            "observed": (
                f"never={never_omitted.get('classification')}/{never_omitted.get('reason')} "
                f"empty={empty.get('classification')}/{empty.get('reason')}"
            ),
            "result": "PASS" if extra_ok else "FAIL",
        },
    ]


if __name__ == "__main__":
    doc = run_census()
    controls = control_results(doc)
    print(
        json.dumps(
            {
                "defaults_enumerated": doc["defaults_enumerated"],
                "unexercised": len(doc["unexercised"]),
                "ci_join": doc["ci_join"],
                "controls": controls,
                "require_complete_cli": doc["known"]["require_complete_cli"],
                "planted": {
                    k: {
                        "classification": v.get("classification"),
                        "reason": v.get("reason"),
                    }
                    for k, v in (doc["known"]["planted"] or {}).items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if any(c["result"] != "PASS" for c in controls[:3]):
        raise SystemExit(1)
