"""CI-gate census: enumerate test suites, enumerate gates, join, report ungated.

A suite is a directory that contains a collectable test module (test_*.py or
*_test.py) as a direct child. A gate is a GitHub Actions step whose command
invokes a test runner and is allowed to fail the job (not continue-on-error).
A suite is GATED when at least one such step collects it; otherwise UNGATED.
A suite nobody runs is not coverage.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL_ROOT = HERE / "fixtures" / "control-estate"
AUD0041 = HERE.parent / "AUD-0041" / "probe1-yaml-inventory.json"

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
    "htmlcov",
}
SKIP_PREFIXES = (
    "command-center/p2-wave/probes/",
)
TEST_FILE_RE = re.compile(r"^(test_.*\.py|.*_test\.py)$")
RUNNER_RE = re.compile(
    r"(?:python(?:3)?\s+-m\s+pytest|\bpytest\b|python(?:3)?\s+-m\s+unittest|"
    r"npm\s+(?:run\s+)?test|\bnpx\s+vitest\b|\bcargo\s+test\b|\bgo\s+test\b)",
    re.I,
)
FLAG_TAKES_VALUE = {
    "-k",
    "-m",
    "-o",
    "-c",
    "-p",
    "-n",
    "--ignore",
    "--cov",
    "--cov-report",
    "--cov-fail-under",
    "--rootdir",
    "--maxfail",
    "--tb",
    "--junitxml",
    "--import-mode",
    "--cov-config",
    "--basetemp",
    "--durations",
    "--color",
    "--override-ini",
    "--deselect",
    "--confcutdir",
    "--pythonpath",
    "--doctest-glob",
    "--numprocesses",
}
BARE_FLAGS = {
    "-q",
    "-v",
    "-s",
    "-x",
    "-vv",
    "-qq",
    "--version",
    "--collect-only",
    "--nf",
    "--ff",
    "--lf",
    "--cache-clear",
    "--strict-markers",
    "--continue-on-collection-errors",
}
INSTALL_RE = re.compile(
    r"^(?:pip3?|python(?:3)?\s+-m\s+pip)\s+install\b",
    re.I,
)
PIP_MODULE_RE = re.compile(r"-m\s+pip\b", re.I)
FOR_LOOP_RE = re.compile(
    r"\bfor\s+(\w+)\s+in\s+(.+?);?\s+do\b(.*?)\bdone\b",
    re.S,
)
CD_RE = re.compile(r"^cd\s+(.+)$")
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
KNOWN_GATED = "known_gated/tests"
CWD_GATED = "cwd_gated/tests"
KNOWN_UNGATED = "ungated_pkg/tests"
CATALOG_INPUTS = (
    ".github/workflows/quality.yml",
    ".github/workflows/no-runtime-junk.yml",
)


def posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _skipped_rel(rel: str) -> bool:
    if not rel or rel == ".":
        return False
    for prefix in SKIP_PREFIXES:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return True
    return False


def enumerate_suites(root: Path) -> list[dict[str, Any]]:
    """Every directory that directly contains a test module is a suite."""
    root = root.resolve()
    suites: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.endswith(".egg-info")
        )
        rel_dir = Path(dirpath).resolve().relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        if _skipped_rel(rel_dir):
            dirnames[:] = []
            continue
        test_files = sorted(f for f in filenames if TEST_FILE_RE.match(f))
        if not test_files:
            continue
        path = rel_dir if rel_dir else "."
        suites.append(
            {
                "path": path,
                "n_test_files": len(test_files),
                "test_files": test_files,
            }
        )
    suites.sort(key=lambda s: s["path"])
    return suites


def _strip_comment(line: str) -> str:
    in_s = False
    in_d = False
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_d:
            in_s = not in_s
            out.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            out.append(ch)
        elif ch == "#" and not in_s and not in_d:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _parse_block(lines: list[str], start: int, parent_indent: int, fold: bool = False) -> tuple[str, int]:
    chunks: list[str] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            chunks.append("")
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= parent_indent:
            break
        chunks.append(raw[parent_indent + 1 :] if indent > parent_indent else raw.lstrip())
        i += 1
    if fold:
        joined = " ".join(c.strip() for c in chunks if c.strip())
        return joined, i
    return "\n".join(chunks).strip("\n"), i


def parse_workflow_gates(path: Path, *, root: Path) -> list[dict[str, Any]]:
    """Harvest test-runner steps from a GitHub Actions workflow YAML."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        rel = posix(path, root)
    except ValueError:
        rel = path.name
    gates: list[dict[str, Any]] = []
    job_id = "unknown"
    job_name = ""
    default_wd = ""
    i = 0
    in_jobs = False
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body = _strip_comment(raw)
        key_m = re.match(r"^(\s*)(?:- )?(?:\"([^\"]+)\"|'([^']+)'|([A-Za-z0-9_.-]+))\s*:\s*(.*)$", body)
        if indent == 0 and re.match(r"^jobs\s*:", body):
            in_jobs = True
            i += 1
            continue
        if in_jobs and indent == 2 and key_m and not body.lstrip().startswith("- "):
            job_id = key_m.group(2) or key_m.group(3) or key_m.group(4) or "unknown"
            job_name = ""
            default_wd = ""
            i += 1
            continue
        if in_jobs and indent == 4 and re.match(r"^\s+name\s*:", body) and job_id:
            job_name = body.split(":", 1)[1].strip().strip("\"'")
            i += 1
            continue
        if in_jobs and indent >= 6 and "working-directory" in body and "defaults" in "\n".join(lines[max(0, i - 6) : i + 1]):
            # job-level defaults.run.working-directory
            if re.search(r"working-directory\s*:", body):
                default_wd = body.split(":", 1)[1].strip().strip("\"'")
            i += 1
            continue
        if in_jobs and indent in (4, 6) and re.match(r"^\s+steps\s*:", body):
            i += 1
            while i < len(lines):
                raw_s = lines[i]
                st = raw_s.strip()
                if not st or st.startswith("#"):
                    i += 1
                    continue
                sind = len(raw_s) - len(raw_s.lstrip(" "))
                if sind <= 4 and not st.startswith("- "):
                    break
                if st.startswith("- ") or (sind == 6 and raw_s.lstrip().startswith("- ")):
                    step, i = _parse_step(lines, i, rel, job_id, job_name, default_wd)
                    if step is not None:
                        gates.append(step)
                    continue
                i += 1
            continue
        i += 1
    return gates


def _parse_step(
    lines: list[str],
    start: int,
    rel: str,
    job_id: str,
    job_name: str,
    default_wd: str,
) -> tuple[dict[str, Any] | None, int]:
    raw0 = lines[start]
    indent = len(raw0) - len(raw0.lstrip(" "))
    # first line may be "- name: foo" or "- run: ..."
    first = raw0.lstrip()
    if first.startswith("- "):
        first = first[2:]
    fields: dict[str, str] = {}
    order: list[str] = []
    rest = first.strip()
    if rest:
        if ":" in rest:
            k, _, v = rest.partition(":")
            k = k.strip()
            v = v.strip()
            if v in ("|", ">", "|-", ">-", "|+", ">+"):
                block, nxt = _parse_block(
                    lines, start + 1, indent + 2, fold=v.startswith(">")
                )
                fields[k] = block
                order.append(k)
                start = nxt - 1
            else:
                fields[k] = v.strip("\"'")
                order.append(k)
        else:
            fields["_raw"] = rest
    i = start + 1
    while i < len(lines):
        raw = lines[i]
        st = raw.strip()
        if not st or st.startswith("#"):
            i += 1
            continue
        sind = len(raw) - len(raw.lstrip(" "))
        if sind <= indent:
            break
        if st.startswith("- ") and sind <= indent + 2:
            break
        body = _strip_comment(raw)
        km = re.match(r"^\s+([A-Za-z0-9_.-]+)\s*:\s*(.*)$", body)
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2).strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+") or (val == "" and i + 1 < len(lines) and (len(lines[i + 1]) - len(lines[i + 1].lstrip(" "))) > sind):
            fold = val.startswith(">") if val else False
            block, nxt = _parse_block(lines, i + 1, sind, fold=fold)
            fields[key] = block
            order.append(key)
            i = nxt
            continue
        fields[key] = val.strip("\"'")
        order.append(key)
        i += 1
    command = fields.get("run") or ""
    if not command:
        return None, i
    coe = str(fields.get("continue-on-error") or "").lower() in {"true", "yes"}
    wd = fields.get("working-directory") or default_wd or ""
    name = fields.get("name") or f"step-{start}"
    can_turn_red = not coe
    analysis = (
        analyze_command(command, wd)
        if can_turn_red
        else {"runner": "none", "collect_paths": [], "ignore_paths": []}
    )
    collect = analysis["collect_paths"]
    runner = analysis["runner"]
    is_test_gate = runner in {"pytest", "unittest", "npm", "node"}
    return (
        {
            "id": f"{rel}::{job_id}::{name}",
            "workflow": rel,
            "job_id": job_id,
            "job_name": job_name,
            "step_name": name,
            "command": command,
            "working_directory": wd,
            "continue_on_error": coe,
            "can_turn_red": can_turn_red,
            "is_test_runner": is_test_gate,
            "runner": runner,
            "collect_paths": collect,
            "ignore_paths": analysis["ignore_paths"],
        },
        i,
    )


def _join_continuations(command: str) -> str:
    return command.replace("\\\r\n", " ").replace("\\\n", " ").replace("\r\n", "\n")


def _split_statements(text: str) -> list[str]:
    parts: list[str] = []
    for line in text.split("\n"):
        line = _strip_comment(line).strip()
        if not line:
            continue
        buf: list[str] = []
        i = 0
        in_s = False
        in_d = False
        depth = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" and not in_d:
                in_s = not in_s
                buf.append(ch)
            elif ch == '"' and not in_s:
                in_d = not in_d
                buf.append(ch)
            elif not in_s and not in_d:
                if ch == "(":
                    depth += 1
                    buf.append(ch)
                elif ch == ")":
                    depth = max(0, depth - 1)
                    buf.append(ch)
                elif depth == 0 and (line.startswith("&&", i) or line.startswith("||", i)):
                    stmt = "".join(buf).strip()
                    if stmt:
                        parts.append(stmt)
                    buf = []
                    i += 2
                    continue
                elif depth == 0 and ch == ";":
                    stmt = "".join(buf).strip()
                    if stmt:
                        parts.append(stmt)
                    buf = []
                    i += 1
                    continue
                else:
                    buf.append(ch)
            else:
                buf.append(ch)
            i += 1
        stmt = "".join(buf).strip()
        if stmt:
            parts.append(stmt)
    return parts


def _unwrap(stmt: str) -> str:
    s = stmt.strip()
    while s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    return s


def _safe_split(stmt: str) -> list[str]:
    try:
        return shlex.split(stmt, posix=True)
    except ValueError:
        return stmt.split()


def _is_install(stmt: str) -> bool:
    s = _unwrap(stmt)
    if INSTALL_RE.match(s):
        return True
    if PIP_MODULE_RE.search(s) and "install" in s:
        return True
    return False


def _expand_for_loops(command: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (command without for-blocks, extra (body, yaml_wd_unused) expansions)."""
    text = _join_continuations(command)
    extras: list[str] = []

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        raw_values = match.group(2).replace("\n", " ").strip()
        body = match.group(3)
        try:
            values = shlex.split(raw_values, posix=True)
        except ValueError:
            values = raw_values.split()
        values = [v for v in values if v not in {"do", "in"}]
        for val in values:
            expanded = body
            expanded = expanded.replace(f"${{{var}}}", val)
            expanded = expanded.replace(f"${var}", val)
            extras.append(expanded)
        return "\n"

    remainder = FOR_LOOP_RE.sub(repl, text)
    return remainder, extras


def _looks_like_path(token: str) -> bool:
    if not token or token.startswith("-"):
        return False
    if token in {
        "python",
        "python3",
        "pip",
        "pip3",
        "then",
        "do",
        "fi",
        "done",
        "echo",
        "set",
        "for",
        "npm",
        "npx",
        "true",
        "false",
        "exit",
        "cd",
    }:
        return False
    if token.startswith("::"):
        return False
    if "/" in token or token.endswith(".py") or token in {".", "tests", "test", "platform", "hooks"}:
        return True
    if token.endswith(".cjs") or token.endswith(".mjs") or token.endswith(".js"):
        return True
    return False


def _resolve_path(path: str, working_directory: str) -> str:
    p = path.replace("\\", "/").strip("/")
    wd = (working_directory or "").replace("\\", "/").strip("/")
    if p in {"", "."}:
        return wd if wd else "."
    if wd:
        return f"{wd}/{p}"
    return p


def _find_pytest(tokens: list[str]) -> tuple[int, str] | None:
    i = 0
    while i < len(tokens) and ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return None
    if i + 2 < len(tokens) and tokens[i + 1] == "-m" and tokens[i + 2] in {"pytest", "unittest"}:
        exe = tokens[i]
        if (
            re.match(r"^python(?:3(?:\.\d+)?)?$", exe)
            or "python" in exe.lower()
            or exe.endswith("/python")
            or exe.endswith("/python3")
        ):
            return i + 3, tokens[i + 2]
    if tokens[i] == "pytest":
        return i + 1, "pytest"
    return None


def _extract_pytest_paths(tokens: list[str], start: int) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    ignores: list[str] = []
    skip_next = False
    i = start
    while i < len(tokens):
        t = tokens[i]
        if skip_next:
            skip_next = False
            i += 1
            continue
        if t in {"&&", "||", ";", "|", "then", "do", "fi", "done"}:
            break
        if t.startswith("--ignore="):
            ignores.append(t.split("=", 1)[1].strip("\"'"))
            i += 1
            continue
        if t == "--ignore" and i + 1 < len(tokens):
            ignores.append(tokens[i + 1].strip("\"'"))
            i += 2
            continue
        if t.startswith("--") and "=" in t:
            i += 1
            continue
        if t.startswith("-"):
            base = t.split("=", 1)[0]
            if t not in BARE_FLAGS and base in FLAG_TAKES_VALUE and "=" not in t:
                skip_next = True
            i += 1
            continue
        if _looks_like_path(t):
            paths.append(t.strip("\"'"))
        i += 1
    return paths, ignores


def _npm_test(tokens: list[str]) -> bool:
    i = 0
    while i < len(tokens) and ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return False
    if tokens[i] == "npm" and i + 1 < len(tokens) and tokens[i + 1] == "test":
        return True
    if (
        tokens[i] == "npm"
        and i + 2 < len(tokens)
        and tokens[i + 1] == "run"
        and tokens[i + 2] in {"test", "tests"}
    ):
        return True
    if tokens[i] == "npx" and i + 1 < len(tokens) and tokens[i + 1] in {"vitest", "mocha"}:
        return True
    return False


def _parse_statement(
    stmt: str, working_directory: str
) -> dict[str, Any] | None:
    s = _unwrap(stmt)
    if not s or s.startswith("echo ") or s == "set -e" or s.startswith("set -"):
        return None
    if _is_install(s):
        return None
    cd_m = CD_RE.match(s)
    if cd_m:
        target = cd_m.group(1).strip().strip("\"'")
        return {"cd": _resolve_path(target, working_directory)}
    tokens = _safe_split(s)
    if not tokens:
        return None
    found = _find_pytest(tokens)
    if found is not None:
        start, kind = found
        paths, ignores = _extract_pytest_paths(tokens, start)
        if not paths:
            paths = ["."]
        return {
            "runner": "unittest" if kind == "unittest" else "pytest",
            "collect_paths": paths,
            "ignore_paths": ignores,
        }
    if _npm_test(tokens):
        return {"runner": "npm", "collect_paths": ["."], "ignore_paths": []}
    return None


def analyze_command(command: str, working_directory: str = "") -> dict[str, Any]:
    """Classify a workflow `run:` script: pytest/unittest collect vs npm vs none.

    Python suites are only joined to pytest/unittest invocations. Root `npm test`
    must not mark every test_*.py directory GATED.
    """
    remainder, extras = _expand_for_loops(command)
    chunks = [remainder, *extras]
    runners: list[str] = []
    collect: list[str] = []
    ignores: list[str] = []
    wd = (working_directory or "").replace("\\", "/").strip("/")
    for chunk in chunks:
        local_wd = wd
        for stmt in _split_statements(chunk):
            pending = [_unwrap(stmt)]
            queue = pending
            while queue:
                current = _unwrap(queue.pop(0))
                if "&&" in current or "||" in current or ";" in current:
                    inner = _split_statements(current)
                    if len(inner) > 1:
                        queue = inner + queue
                        continue
                parsed = _parse_statement(current, local_wd)
                if parsed is None:
                    continue
                if "cd" in parsed:
                    local_wd = parsed["cd"]
                    continue
                runner = parsed["runner"]
                runners.append(runner)
                for p in parsed["collect_paths"]:
                    collect.append(_resolve_path(p, local_wd))
                for ign in parsed["ignore_paths"]:
                    ignores.append(_resolve_path(ign, local_wd))
    out_c: list[str] = []
    seen_c: set[str] = set()
    for p in collect:
        if p not in seen_c:
            seen_c.add(p)
            out_c.append(p)
    out_i: list[str] = []
    seen_i: set[str] = set()
    for p in ignores:
        if p not in seen_i:
            seen_i.add(p)
            out_i.append(p)
    runner = "none"
    if "pytest" in runners:
        runner = "pytest"
    elif "unittest" in runners:
        runner = "unittest"
    elif "npm" in runners:
        runner = "npm"
    return {"runner": runner, "collect_paths": out_c, "ignore_paths": out_i}


def collect_paths(command: str, working_directory: str = "") -> list[str]:
    """Pytest/unittest collect paths only. npm/node runners return []."""
    info = analyze_command(command, working_directory)
    if info["runner"] not in {"pytest", "unittest"}:
        return []
    return info["collect_paths"]


def path_covers(collect: str, suite: str) -> bool:
    c = collect.replace("\\", "/").strip("/") or "."
    s = suite.replace("\\", "/").strip("/") or "."
    if c == ".":
        return True
    if s == ".":
        return c == "."
    if s == c or s.startswith(c + "/"):
        return True
    if c == s or c.startswith(s + "/"):
        return True
    return False


def ignore_excludes_suite(ignore: str, suite: str) -> bool:
    """Directory ignores drop a suite from that gate; a single file ignore does not."""
    ign = ignore.replace("\\", "/").strip("/")
    s = suite.replace("\\", "/").strip("/") or "."
    if not ign:
        return False
    if ign.endswith(".py"):
        return False
    return s == ign or s.startswith(ign + "/")


def enumerate_gates(root: Path) -> dict[str, Any]:
    wf_root = root / ".github" / "workflows"
    files: list[Path] = []
    if wf_root.is_dir():
        files = sorted(p for p in wf_root.iterdir() if p.suffix in {".yml", ".yaml"} and p.is_file())
    gates: list[dict[str, Any]] = []
    for path in files:
        gates.extend(parse_workflow_gates(path, root=root))
    present = {posix(p, root): True for p in files}
    inputs = []
    for rel in CATALOG_INPUTS:
        p = root / rel
        inputs.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return {
        "workflow_dir_present": wf_root.is_dir(),
        "workflow_files": [posix(p, root) for p in files],
        "n_workflow_files": len(files),
        "n_gates": len(gates),
        "n_test_runner_gates": sum(1 for g in gates if g["is_test_runner"]),
        "catalog_inputs": inputs,
        "gates": gates,
        "workflow_files_present_map": present,
    }


def join_table(suites: list[dict[str, Any]], gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for suite in suites:
        matching = []
        for gate in gates:
            if not gate.get("can_turn_red"):
                continue
            runner = gate.get("runner")
            if runner not in {None, "", "pytest", "unittest"}:
                continue
            if runner in {None, ""} and not (gate.get("collect_paths") or []):
                continue
            ignores = gate.get("ignore_paths") or []
            if any(ignore_excludes_suite(ign, suite["path"]) for ign in ignores):
                continue
            for collect in gate.get("collect_paths") or []:
                if path_covers(collect, suite["path"]):
                    matching.append(
                        {
                            "gate_id": gate["id"],
                            "workflow": gate["workflow"],
                            "job_id": gate["job_id"],
                            "step_name": gate["step_name"],
                            "collect_path": collect,
                        }
                    )
                    break
        classification = "GATED" if matching else "UNGATED"
        rows.append(
            {
                "suite": suite["path"],
                "n_test_files": suite["n_test_files"],
                "test_files": suite["test_files"],
                "classification": classification,
                "n_gates": len(matching),
                "gates": matching,
            }
        )
    return rows


def classify_invariants(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {"GATED", "UNGATED"}
    missing = [r["suite"] for r in rows if r.get("classification") not in classes]
    both = [
        r["suite"]
        for r in rows
        if r.get("classification") == "GATED" and r.get("n_gates", 0) == 0
    ]
    ungated_listed = [r["suite"] for r in rows if r["classification"] == "UNGATED"]
    gated_listed = [r["suite"] for r in rows if r["classification"] == "GATED"]
    return {
        "every_suite_classified": len(missing) == 0 and len(rows) == len(set(r["suite"] for r in rows)),
        "unclassified": missing,
        "gated_without_gate": both,
        "ungated_suites": ungated_listed,
        "gated_suites": gated_listed,
        "n_suites": len(rows),
        "n_gated": len(gated_listed),
        "n_ungated": len(ungated_listed),
    }


def census(root: Path) -> dict[str, Any]:
    suites = enumerate_suites(root)
    gate_info = enumerate_gates(root)
    rows = join_table(suites, gate_info["gates"])
    inv = classify_invariants(rows)
    return {
        "root": str(root),
        "suites": suites,
        "gates": gate_info,
        "join": rows,
        "invariants": inv,
        "ungated_count": inv["n_ungated"],
        "gated_count": inv["n_gated"],
        "suite_count": inv["n_suites"],
    }


def historical_inventory_join(live_suites: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Join THIS worktree's suites against AUD-0041's workflow transcript.

    Not live CI. The worktree may not contain .github/workflows. Labeled so.
    """
    if not AUD0041.is_file():
        return None
    doc = json.loads(AUD0041.read_text(encoding="utf-8"))
    fake_gates = []
    for wf in doc.get("workflows") or []:
        wf_file = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            job_id = str(job.get("job_id") or "job")
            for step in job.get("steps") or []:
                command = str(step.get("command") or "")
                name = str(step.get("name") or f"step-{step.get('index')}")
                info = analyze_command(command, "")
                collect = [p for p in info["collect_paths"] if p not in {".", ""}]
                fake_gates.append(
                    {
                        "id": f"{wf_file}::{job_id}::{name}",
                        "workflow": wf_file,
                        "job_id": job_id,
                        "job_name": str(job.get("name") or ""),
                        "step_name": name,
                        "command": command,
                        "working_directory": "",
                        "continue_on_error": False,
                        "can_turn_red": True,
                        "is_test_runner": info["runner"] in {"pytest", "unittest"},
                        "runner": info["runner"],
                        "collect_paths": collect,
                        "ignore_paths": info["ignore_paths"],
                    }
                )
    rows = join_table(live_suites, fake_gates)
    inv = classify_invariants(rows)
    return {
        "live": False,
        "source": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
        "label": "historical-inventory-not-live",
        "ungated_count": inv["n_ungated"],
        "gated_count": inv["n_gated"],
        "suite_count": inv["n_suites"],
        "ungated_suites": inv["ungated_suites"],
        "gated_suites": inv["gated_suites"],
    }


def assert_every_suite_classified(report: dict[str, Any]) -> None:
    inv = report["invariants"]
    if not inv["every_suite_classified"]:
        raise AssertionError(f"unclassified suites: {inv['unclassified']}")
    if inv["gated_without_gate"]:
        raise AssertionError(f"GATED with zero gates: {inv['gated_without_gate']}")
    for row in report["join"]:
        if row["classification"] not in {"GATED", "UNGATED"}:
            raise AssertionError(f"bad class {row}")
        if row["classification"] == "UNGATED" and row["n_gates"] != 0:
            raise AssertionError(f"UNGATED but has gates: {row}")
        if row["classification"] == "GATED" and row["n_gates"] < 1:
            raise AssertionError(f"GATED but no gates: {row}")


def assert_ungated_listed_by_path(report: dict[str, Any]) -> None:
    inv = report["invariants"]
    listed = inv["ungated_suites"]
    from_rows = [r["suite"] for r in report["join"] if r["classification"] == "UNGATED"]
    if listed != from_rows:
        raise AssertionError(f"ungated list mismatch {listed} vs {from_rows}")
    if any(not isinstance(s, str) or not s.strip() for s in listed):
        raise AssertionError("ungated path malformed")
    if inv["n_ungated"] != len(listed):
        raise AssertionError("ungated count != listed length")
    if listed != sorted(listed):
        raise AssertionError("ungated suites not listed in sorted path order")


def assert_known_gated_joined(report: dict[str, Any]) -> None:
    by = {r["suite"]: r for r in report["join"]}
    if KNOWN_GATED not in by:
        raise AssertionError(f"known gated suite {KNOWN_GATED} missing from join")
    row = by[KNOWN_GATED]
    if row["classification"] != "GATED":
        raise AssertionError(f"{KNOWN_GATED} classified {row['classification']}, want GATED")
    if not any(g["workflow"].endswith("quality.yml") for g in row["gates"]):
        raise AssertionError(f"{KNOWN_GATED} not joined to quality.yml: {row['gates']}")
    if CWD_GATED in by and by[CWD_GATED]["classification"] != "GATED":
        raise AssertionError(f"{CWD_GATED} should be GATED via working-directory")
    if KNOWN_UNGATED not in by:
        raise AssertionError(f"ungated control {KNOWN_UNGATED} missing")
    if by[KNOWN_UNGATED]["classification"] != "UNGATED":
        raise AssertionError(f"{KNOWN_UNGATED} must stay UNGATED")
    if by[KNOWN_UNGATED]["n_gates"] != 0:
        raise AssertionError(f"{KNOWN_UNGATED} matched a gate")


def control_census() -> dict[str, Any]:
    if not CONTROL_ROOT.is_dir():
        raise FileNotFoundError(CONTROL_ROOT)
    return census(CONTROL_ROOT)


def live_census() -> dict[str, Any]:
    return census(REPO)
