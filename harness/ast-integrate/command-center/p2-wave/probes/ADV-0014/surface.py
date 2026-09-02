#!/usr/bin/env python3
"""ADV-0014: extract vendor argv/MCP names from source and diff against live surfaces."""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0014"
OUTPUT_REL = "command-center/adversarial/ADV-0014-vendor-cli-surface-drift.json"
SCHEMA_REL = "command-center/schema/stale-premise-reprobe.schema.json"
LIVE_CURSOR = HERE / "fixtures" / "live_cursor_mcp.json"
AUD0060_CURSOR = (
    REPO / "command-center/p2-wave/probes/AUD-0060/session_cursor_mcp.json"
)

VENDOR_BINS = (
    "claude",
    "codex",
    "gh",
    "git",
    "uv",
    "node",
    "docker",
    "wsl",
)
SCAN_ROOTS = ("tools",)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        ".pytest_cache",
        ".cursor",
        "p2-wave",
    }
)
FLAG_TOKEN = re.compile(r"^(-{1,2}[A-Za-z][A-Za-z0-9-]*)(?:=.*)?$")
HELP_FLAG = re.compile(r"(?<![\w-])(-{1,2}[A-Za-z][A-Za-z0-9-]*)")
MCP_NAME = re.compile(r"\bmcp__[A-Za-z0-9][A-Za-z0-9_-]*__[A-Za-z0-9][A-Za-z0-9_-]*\b")
GIT_RECIPE = re.compile(r"\bgit\s+(archive|cat-file|show)\b")
SUBCOMMAND = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
CONTROL_BIN = "git"
CONTROL_VALID_FLAG = "--version"
CONTROL_INVALID_FLAG = "--adv0014-not-a-real-flag"
VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})

SENTINEL = (
    "SUCCESS:ADV-0014 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0014 <reason>."
)
QUESTION = (
    "For every vendor command, flag and endpoint the program depends on "
    "(claude, codex, gh, git, uv, node, docker, wsl and each mounted MCP), "
    "does the invocation the code actually issues still exist and still mean "
    "the same thing today?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0014/probe1_help.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0014/probe2_live_schema.py"
)


def rel_of(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iter_py_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = base / name
            try:
                if path.stat().st_size > 1_500_000:
                    continue
            except OSError:
                continue
            yield path


def _string_prefix(node: ast.AST) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
        elif isinstance(elt, ast.Starred):
            break
        else:
            break
    return out or None


class _ArgvVisitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.hits: list[dict[str, Any]] = []

    def _record(self, argv: list[str], lineno: int, kind: str = "argv") -> None:
        binary = argv[0]
        if binary not in VENDOR_BINS:
            return
        flags = []
        for tok in argv[1:]:
            m = FLAG_TOKEN.match(tok)
            if m:
                flags.append(m.group(1))
        self.hits.append(
            {
                "binary": binary,
                "argv": argv[:12],
                "flags": flags,
                "file": self.rel,
                "line": lineno,
                "kind": kind,
            }
        )

    def visit_List(self, node: ast.List) -> None:
        argv = _string_prefix(node)
        if argv:
            self._record(argv, getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        argv = _string_prefix(node)
        if argv:
            self._record(argv, getattr(node, "lineno", 0))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name == "which" and node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                if arg0.value in VENDOR_BINS:
                    self._record([arg0.value], getattr(node, "lineno", 0), "which")
        self.generic_visit(node)


def extract_cli_invocations(repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or REPO
    hits: list[dict[str, Any]] = []
    for folder in SCAN_ROOTS:
        root = repo / folder
        if not root.is_dir():
            continue
        for path in iter_py_files(root):
            try:
                src = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            vis = _ArgvVisitor(rel_of(path, repo))
            vis.visit(tree)
            hits.extend(vis.hits)
            for m in GIT_RECIPE.finditer(src):
                line = src[: m.start()].count("\n") + 1
                hits.append(
                    {
                        "binary": "git",
                        "argv": ["git", m.group(1)],
                        "flags": [],
                        "file": rel_of(path, repo),
                        "line": line,
                        "kind": "shell-recipe",
                    }
                )
    hits.sort(key=lambda h: (h["binary"], h["file"], int(h["line"])))
    return hits


def extract_mcp_names(repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or REPO
    found: dict[str, dict[str, Any]] = {}
    for folder in SCAN_ROOTS:
        root = repo / folder
        if not root.is_dir():
            continue
        for path in iter_py_files(root):
            try:
                src = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in MCP_NAME.finditer(src):
                name = m.group(0)
                line = src[: m.start()].count("\n") + 1
                row = found.setdefault(
                    name,
                    {
                        "name": name,
                        "anchors": [],
                        "leaf": name.split("__")[-1],
                    },
                )
                row["anchors"].append(f"{rel_of(path, repo)}:{line}")
    return [found[k] for k in sorted(found)]


def parse_help_flags(text: str) -> list[str]:
    flags: list[str] = []
    seen: set[str] = set()
    for m in HELP_FLAG.finditer(text or ""):
        flag = m.group(1)
        if flag in {"-", "--"}:
            continue
        if flag not in seen:
            seen.add(flag)
            flags.append(flag)
    return flags


def run_help(binary: str, timeout: int = 20) -> dict[str, Any]:
    return run_help_argv([binary], timeout=timeout)


def run_help_argv(argv: list[str], timeout: int = 20) -> dict[str, Any]:
    binary = argv[0]
    resolved = shutil.which(binary)
    if not resolved:
        return {
            "binary": binary,
            "argv": argv + ["--help"],
            "on_path": False,
            "resolved": None,
            "exit_code": None,
            "flags": [],
            "stdout_head": "",
            "stderr_head": "",
            "error": "not-on-path",
        }
    cmd = [resolved, *argv[1:], "--help"]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "binary": binary,
            "argv": argv + ["--help"],
            "on_path": True,
            "resolved": resolved,
            "exit_code": 124,
            "flags": [],
            "stdout_head": "",
            "stderr_head": "",
            "error": "timeout",
        }
    except OSError as exc:
        return {
            "binary": binary,
            "argv": argv + ["--help"],
            "on_path": True,
            "resolved": resolved,
            "exit_code": None,
            "flags": [],
            "stdout_head": "",
            "stderr_head": "",
            "error": type(exc).__name__,
        }
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return {
        "binary": binary,
        "argv": argv + ["--help"],
        "on_path": True,
        "resolved": resolved,
        "exit_code": proc.returncode,
        "flags": parse_help_flags(combined),
        "stdout_head": (proc.stdout or "")[:2000],
        "stderr_head": (proc.stderr or "")[:400],
        "error": None,
    }


def live_flags_for_binary(
    binary: str, invocations: list[dict[str, Any]]
) -> dict[str, Any]:
    base = run_help(binary)
    flags = set(base.get("flags") or [])
    subcommands: dict[str, dict[str, Any]] = {}
    if not base.get("on_path"):
        return {"base": base, "flags": sorted(flags), "subcommands": subcommands}
    seen: set[str] = set()
    for hit in invocations:
        argv = list(hit.get("argv") or [])
        if len(argv) < 2 or not SUBCOMMAND.match(argv[1]) or argv[1] in seen:
            continue
        seen.add(argv[1])
        row = run_help_argv([binary, argv[1]])
        subcommands[argv[1]] = {
            "exit_code": row.get("exit_code"),
            "flag_count": len(row.get("flags") or []),
            "error": row.get("error"),
        }
        flags.update(row.get("flags") or [])
    return {"base": base, "flags": sorted(flags), "subcommands": subcommands}


def classify_flag(flag: str, help_flags: Iterable[str]) -> str:
    help_set = set(help_flags)
    base = flag.split("=", 1)[0]
    if flag in help_set or base in help_set:
        return "valid"
    return "invalid"


def flag_control(help_row: dict[str, Any]) -> dict[str, Any]:
    flags = help_row.get("flags") or []
    valid_class = classify_flag(CONTROL_VALID_FLAG, flags)
    invalid_class = classify_flag(CONTROL_INVALID_FLAG, flags)
    ok = (
        bool(help_row.get("on_path"))
        and valid_class == "valid"
        and invalid_class == "invalid"
    )
    return {
        "id": "ADV0014-C1-valid-and-invalid-flag",
        "binary": CONTROL_BIN,
        "valid_flag": CONTROL_VALID_FLAG,
        "invalid_flag": CONTROL_INVALID_FLAG,
        "valid_classified": valid_class,
        "invalid_classified": invalid_class,
        "fired_on_bad_state": invalid_class == "invalid",
        "silent_on_good_state": valid_class == "valid",
        "pass": ok,
        "on_path": bool(help_row.get("on_path")),
        "help_flag_count": len(flags),
    }


def load_live_mcp_tools() -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    sources: list[str] = []
    for path, label in (
        (LIVE_CURSOR, "adv0014-session-cursor"),
        (AUD0060_CURSOR, "aud0060-session-cursor"),
    ):
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        sources.append(label)
        ns = str(doc.get("namespace") or "cursor")
        for row in doc.get("tools") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or row.get("tool") or "")
            if not name:
                continue
            tools.append(
                {
                    "name": name,
                    "qualified": f"{ns}.{name}",
                    "namespace": ns,
                    "source": label,
                    "has_input_schema": isinstance(row.get("inputSchema"), dict),
                }
            )
    by_exact = {t["name"]: t for t in tools}
    by_qualified = {t["qualified"]: t for t in tools}
    return {
        "sources": sources,
        "tools": tools,
        "exact_names": sorted(by_exact),
        "qualified_names": sorted(by_qualified),
        "by_exact": by_exact,
        "by_qualified": by_qualified,
    }


def resolve_mcp_name(name: str, live: dict[str, Any]) -> dict[str, Any]:
    exact = live.get("by_exact") or {}
    qualified = live.get("by_qualified") or {}
    leaf = name.split("__")[-1] if name.startswith("mcp__") else name.split(".")[-1]
    hit = exact.get(name) or exact.get(leaf) or qualified.get(name)
    hyphen = leaf.replace("_", "-")
    under = leaf.replace("-", "_")
    hyphen_hit = exact.get(hyphen) if hyphen != leaf else None
    under_hit = exact.get(under) if under != leaf else None
    return {
        "name": name,
        "leaf": leaf,
        "exact_hit": hit is not None,
        "hyphenated_lookup": hyphen,
        "underscored_lookup": under,
        "hyphenated_hit": hyphen_hit is not None,
        "underscored_hit": under_hit is not None,
        "collapsed_would_alias": hyphen != under,
        "matched": None if hit is None else hit.get("qualified"),
    }


def hyphen_underscore_control(live: dict[str, Any]) -> dict[str, Any]:
    exact = live.get("by_exact") or {}
    present = "CreateGoal"
    hyphen_foil = "Create-Goal"
    under_foil = "Create_Goal"
    present_hit = present in exact
    hyphen_hit = hyphen_foil in exact
    under_hit = under_foil in exact
    identities_distinct = (
        hyphen_foil != present
        and under_foil != present
        and hyphen_foil != under_foil
    )
    ok = present_hit and (not hyphen_hit) and (not under_hit) and identities_distinct
    return {
        "id": "ADV0014-C2-hyphen-vs-underscore",
        "live_present": present,
        "hyphen_foil": hyphen_foil,
        "underscore_foil": under_foil,
        "present_hit": present_hit,
        "hyphen_hit": hyphen_hit,
        "underscore_hit": under_hit,
        "identities_distinct": identities_distinct,
        "fired_on_bad_state": (not hyphen_hit) and (not under_hit),
        "silent_on_good_state": present_hit,
        "pass": ok,
        "note": (
            "A doc-derived hyphenated name can look right and still miss the "
            "live schema. Create-Goal and Create_Goal are distinct from CreateGoal."
        ),
    }


def bin_target_verdict(
    binary: str,
    invocations: list[dict[str, Any]],
    live: dict[str, Any],
    control_ok: bool,
) -> dict[str, Any]:
    help_row = live.get("base") or {}
    used_flags = sorted({f for h in invocations for f in (h.get("flags") or [])})
    if not control_ok:
        verdict = "NOT-CHECKED"
        reason = "flag-control-failed-or-skipped"
    elif not help_row.get("on_path"):
        verdict = "PARTIAL" if invocations else "NOT-CHECKED"
        reason = "binary-absent-on-path"
    elif help_row.get("error"):
        verdict = "PARTIAL"
        reason = str(help_row["error"])
    else:
        live_flags = set(live.get("flags") or [])
        missing = [f for f in used_flags if classify_flag(f, live_flags) == "invalid"]
        if missing:
            verdict = "CONFIRMED"
            reason = "source-flags-absent-from-live-help:" + ",".join(missing)
        elif invocations:
            verdict = "REFUTED"
            reason = "invoked-flags-present-in-live-help-or-subcommand-only"
        else:
            verdict = "NOT-CHECKED"
            reason = "named-vendor-binary-not-invoked-in-scanned-source"
            if binary in {"git", "node"}:
                verdict = "REFUTED"
                reason = "binary-on-path-help-ok"
    return {
        "id": f"cli:{binary}",
        "kind": "vendor-cli",
        "binary": binary,
        "verdict": verdict,
        "reason": reason,
        "invocation_count": len(invocations),
        "source_flags": used_flags,
        "on_path": bool(help_row.get("on_path")),
        "help_exit_code": help_row.get("exit_code"),
        "live_flag_count": len(live.get("flags") or []),
        "subcommand_helps": live.get("subcommands") or {},
    }


def mcp_target_verdict(
    row: dict[str, Any],
    resolution: dict[str, Any],
    control_ok: bool,
) -> dict[str, Any]:
    if not control_ok:
        verdict = "NOT-CHECKED"
        reason = "hyphen-underscore-control-failed"
    elif resolution.get("exact_hit"):
        verdict = "REFUTED"
        reason = "exact-name-present-in-live-schema"
    elif resolution.get("hyphenated_hit") or resolution.get("underscored_hit"):
        verdict = "CONFIRMED"
        reason = "only-aliased-spelling-hits-live-schema"
    else:
        verdict = "CONFIRMED"
        reason = "name-absent-from-live-schema"
    return {
        "id": f"mcp:{row['name']}",
        "kind": "mcp-tool",
        "verdict": verdict,
        "reason": reason,
        "name": row["name"],
        "anchors": row.get("anchors") or [],
        "resolution": resolution,
    }


def measure_cli(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    invocations = extract_cli_invocations(repo)
    by_bin: dict[str, list[dict[str, Any]]] = {b: [] for b in VENDOR_BINS}
    for hit in invocations:
        by_bin.setdefault(hit["binary"], []).append(hit)
    lives = {
        b: live_flags_for_binary(b, by_bin.get(b) or []) for b in VENDOR_BINS
    }
    control = flag_control(lives[CONTROL_BIN]["base"])
    targets = [
        bin_target_verdict(b, by_bin.get(b) or [], lives[b], control["pass"])
        for b in VENDOR_BINS
    ]
    help_meta = {}
    stdout_head = {}
    for b, live in lives.items():
        row = live["base"]
        help_meta[b] = {
            k: v for k, v in row.items() if k not in {"stdout_head", "stderr_head"}
        }
        help_meta[b]["stdout_head_chars"] = len(row.get("stdout_head") or "")
        help_meta[b]["union_flag_count"] = len(live.get("flags") or [])
        help_meta[b]["subcommands"] = live.get("subcommands") or {}
        if row.get("on_path"):
            stdout_head[b] = row.get("stdout_head") or ""
    return {
        "probe": "probe1-extract-and-help",
        "unit_id": UNIT,
        "control": control,
        "invocations": invocations,
        "help": help_meta,
        "help_stdout_head": stdout_head,
        "targets": targets,
        "control_pass": control["pass"],
    }


def measure_mcp(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    names = extract_mcp_names(repo)
    live = load_live_mcp_tools()
    control = hyphen_underscore_control(live)
    resolutions = [resolve_mcp_name(n["name"], live) for n in names]
    targets = [
        mcp_target_verdict(n, r, control["pass"]) for n, r in zip(names, resolutions)
    ]
    planted_absent = resolve_mcp_name("mcp__adv0014__no-such-tool", live)
    planted_ok = (not planted_absent["exact_hit"]) and planted_absent[
        "collapsed_would_alias"
    ]
    return {
        "probe": "probe2-live-mcp-schema",
        "unit_id": UNIT,
        "control": control,
        "live": {
            "sources": live["sources"],
            "exact_names": live["exact_names"],
            "tool_count": len(live["tools"]),
        },
        "extracted": names,
        "resolutions": resolutions,
        "targets": targets,
        "planted_absent": planted_absent,
        "planted_absent_ok": planted_ok,
        "control_pass": control["pass"] and planted_ok,
    }


def validate_against_schema(
    doc: dict[str, Any], repo: Path | None = None
) -> tuple[bool, str]:
    repo = repo or REPO
    try:
        import jsonschema
    except ImportError:
        return False, "jsonschema-absent"
    schema_path = repo / SCHEMA_REL
    if not schema_path.is_file():
        return False, f"schema-absent:{SCHEMA_REL}"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        return False, exc.message
    except jsonschema.SchemaError as exc:
        return False, f"schema-invalid:{exc.message}"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"{type(exc).__name__}:{exc}"
    garbage = (
        {},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    )
    validator = jsonschema.Draft7Validator(schema)
    for g in garbage:
        if not list(validator.iter_errors(g)):
            return False, "schema-vacuous:garbage-accepted"
    return True, "ok"
