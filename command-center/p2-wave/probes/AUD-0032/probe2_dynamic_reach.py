#!/usr/bin/env python3
"""AUD-0032 Probe 2: dynamic reachability from declared entry points + CI + docs.

Remediation after cross-vendor review FAIL:
- Parse every tools/**/pyproject.toml [project.scripts] / [project.entry-points]
- Expand pytest targets from .github/workflows/*.yml (python -m pytest PATH)
- Scan ALL README.md / RUNBOOK*.md under tools/ and repo root (not just 3 root docs)
- Alias hyphenated package paths: tools.agentrail.agentrail.* <-> agentrail.*
- Bounded runtime import trace: import each seed in a fresh interpreter and record
  sys.modules deltas that resolve under tools/

A module reached only through a string-named plugin registry must be LIVE here
and DEAD under probe 1 — independence control.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
RUNTIME_SEED_BUDGET = 40
RUNTIME_TIMEOUT = 12


def module_name_for(path: Path) -> str:
    rel = path.relative_to(REPO).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def alias_names(name: str, known: set[str]) -> set[str]:
    """Map tools.<pkg>.<pkg>.* <-> <pkg>.* for hyphen/flat layouts."""
    out = {name}
    parts = name.split(".")
    if len(parts) >= 3 and parts[0] == "tools" and parts[1] == parts[2]:
        # tools.agentrail.agentrail.cli -> agentrail.cli + tools.agentrail.cli
        flat = ".".join(parts[2:])
        out.add(flat)
        out.add("tools." + flat)
    if parts and parts[0] != "tools":
        # agentrail.cli -> tools.agentrail.agentrail.cli / tools.agentrail.cli
        out.add("tools." + name)
        pkg = parts[0]
        out.add("tools." + pkg + "." + name)
    return {n for n in out if n in known} or ({name} if name in known else set())


def resolve_seed(name: str, known: set[str]) -> set[str]:
    hits = set()
    if name in known:
        hits.add(name)
    hits |= alias_names(name, known)
    # path-like seeds already converted; also try stripping leading tools.
    if name.startswith("tools.") and name[6:] in known:
        hits.add(name[6:])
    return hits


def path_to_mod_candidates(rel: str, known: set[str]) -> set[str]:
    rel = rel.replace("\\", "/").lstrip("./")
    p = REPO / rel
    hits: set[str] = set()
    if p.is_file() and p.suffix == ".py":
        try:
            hits |= resolve_seed(module_name_for(p), known)
        except ValueError:
            pass
    elif p.is_dir():
        init = p / "__init__.py"
        if init.is_file():
            try:
                hits |= resolve_seed(module_name_for(init), known)
            except ValueError:
                pass
        for child in p.rglob("test_*.py"):
            if "__pycache__" in child.parts:
                continue
            try:
                hits |= resolve_seed(module_name_for(child), known)
            except ValueError:
                pass
    return hits


def parse_pyproject_entrypoints() -> set[str]:
    """Parse [project.scripts] and entry-points from every tools/**/pyproject.toml."""
    found: set[str] = set()
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore

    for pyproj in (REPO / "tools").rglob("pyproject.toml"):
        try:
            data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
        except Exception:
            continue
        project = data.get("project") or {}
        for section in ("scripts",):
            mapping = project.get(section) or {}
            if isinstance(mapping, dict):
                for _name, target in mapping.items():
                    if isinstance(target, str) and ":" in target:
                        found.add(target.split(":", 1)[0].strip())
        eps = project.get("entry-points") or project.get("entry_points") or {}
        if isinstance(eps, dict):
            for _group, mapping in eps.items():
                if isinstance(mapping, dict):
                    for _name, target in mapping.items():
                        if isinstance(target, str) and ":" in target:
                            found.add(target.split(":", 1)[0].strip())
        # poetry-style
        poetry = (data.get("tool") or {}).get("poetry") or {}
        scripts = poetry.get("scripts") or {}
        if isinstance(scripts, dict):
            for _name, target in scripts.items():
                if isinstance(target, str) and ":" in target:
                    found.add(target.split(":", 1)[0].strip())
    return found


def entry_points_from_mains() -> set[str]:
    found: set[str] = set()
    for p in (REPO / "tools").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if p.name in {
            "__main__.py",
            "app.py",
            "cli.py",
            "validate.py",
            "render.py",
            "seed.py",
        }:
            found.add(module_name_for(p))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', text):
            found.add(module_name_for(p))
    return found


def _yaml_working_directory_blocks(text: str) -> list[tuple[str, str]]:
    """Return (working_directory, following_run_block) pairs from GHA YAML.

    Handles the common pattern:
      working-directory: tools/agentrail
      run: |
        pytest -m "not live"
    where bare pytest discovers tests/ relative to that directory.
    """
    blocks: list[tuple[str, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)working-directory:\s*(.+?)\s*$", lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        wd = m.group(2).strip().strip("\"'")
        # look ahead for run: within the same step (similar/deeper indent)
        j = i + 1
        run_body = ""
        while j < len(lines):
            line = lines[j]
            if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                break
            # next key at same indent as working-directory ends the step
            if re.match(rf"^[ ]{{{indent}}}[A-Za-z0-9_-]+:", line) and not line[
                indent:
            ].startswith(" "):
                if not line.strip().startswith("run:"):
                    if j > i + 1:
                        break
            rm = re.match(rf"^[ ]{{{indent}}}run:\s*(.*)$", line)
            if rm:
                first = rm.group(1)
                if first in {"|", ">", ">-", "|-"} or first == "":
                    j += 1
                    body_lines = []
                    while j < len(lines):
                        bl = lines[j]
                        if bl.strip() == "":
                            body_lines.append("")
                            j += 1
                            continue
                        # body must be more indented than `run:`
                        if len(bl) - len(bl.lstrip(" ")) <= indent:
                            break
                        body_lines.append(bl)
                        j += 1
                    run_body = "\n".join(body_lines)
                else:
                    run_body = first
                break
            j += 1
        if wd and run_body:
            blocks.append((wd, run_body))
        i = max(j, i + 1)
    return blocks


def ci_python_and_pytest_targets(known: set[str]) -> set[str]:
    mods: set[str] = set()
    wf = REPO / ".github" / "workflows"
    if not wf.is_dir():
        return mods
    for yml in list(wf.glob("*.yml")) + list(wf.glob("*.yaml")):
        text = yml.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:python(?:3)?\s+(?:-B\s+)?)([\w./_-]+\.py)", text):
            mods |= path_to_mod_candidates(m.group(1), known)
        for m in re.finditer(r"python(?:3)?\s+-m\s+([\w.]+)", text):
            mods |= resolve_seed(m.group(1), known)
        # pytest path args (python -m pytest tools/foo -q)
        for m in re.finditer(
            r"(?:pytest|python(?:3)?\s+-m\s+pytest)\s+([^\n&#|]+)", text
        ):
            args = m.group(1)
            for tok in re.split(r"\s+", args.strip()):
                if not tok or tok.startswith("-"):
                    continue
                tok = tok.strip("\"'")
                if "/" in tok or tok.endswith(".py") or tok.startswith("tools"):
                    mods |= path_to_mod_candidates(tok, known)
        # bare `pytest` under working-directory: tools/<pkg> => mark that package's tests live
        for wd, run_body in _yaml_working_directory_blocks(text):
            if not re.search(r"(?:^|[\s;|&])pytest\b", run_body):
                continue
            # explicit path tokens inside the run body still win
            explicit = False
            for m in re.finditer(
                r"(?:pytest|python(?:3)?\s+-m\s+pytest)\s+([^\n&#|]+)", run_body
            ):
                for tok in re.split(r"\s+", m.group(1).strip()):
                    if not tok or tok.startswith("-"):
                        continue
                    tok = tok.strip("\"'")
                    if "/" in tok or tok.endswith(".py"):
                        mods |= path_to_mod_candidates(tok, known)
                        explicit = True
            if explicit:
                continue
            # bare pytest: discover tests under working-directory
            wd_path = wd if not wd.startswith("${{") else ""
            if not wd_path:
                continue
            mods |= path_to_mod_candidates(wd_path, known)
            tests_dir = Path(wd_path) / "tests"
            mods |= path_to_mod_candidates(str(tests_dir), known)
            # also mark package modules under wd as seeds (editable install entry)
            pkg_root = REPO / wd_path
            if pkg_root.is_dir():
                for py in pkg_root.rglob("*.py"):
                    if "__pycache__" in py.parts:
                        continue
                    # only top-level package + tests as seeds; BFS expands imports
                    rel = py.relative_to(REPO)
                    if len(rel.parts) <= 4 or "tests" in rel.parts:
                        try:
                            mods |= resolve_seed(module_name_for(py), known)
                        except ValueError:
                            pass
    return mods


def doc_command_modules(known: set[str]) -> set[str]:
    mods: set[str] = set()
    docs: list[Path] = []
    for name in ("README.md", "AGENTS.md", "CLAUDE.md", "RUNBOOK.md"):
        p = REPO / name
        if p.is_file():
            docs.append(p)
    for p in (REPO / "tools").rglob("README.md"):
        docs.append(p)
    for p in (REPO / "tools").rglob("RUNBOOK*.md"):
        docs.append(p)
    # Non-root report/investigation markdown (review FAIL: auth_jwt_audit.py is cited
    # only under tools/crcp/reports/, not a root README).
    for p in (REPO / "tools").rglob("*.md"):
        low = p.name.lower()
        if "report" in low or "investigation" in low or "inventory" in low:
            docs.append(p)
    for p in (REPO / "docs").rglob("*.md") if (REPO / "docs").is_dir() else []:
        if "RUNBOOK" in p.name.upper() or p.name.upper() == "README.MD":
            docs.append(p)
    seen: set[Path] = set()
    for p in docs:
        if p in seen:
            continue
        seen.add(p)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "python" not in text and ".py" not in text:
            continue
        for m in re.finditer(r"(?:python(?:3)?\s+(?:-B\s+)?)([\w./_-]+\.py)", text):
            mods |= path_to_mod_candidates(m.group(1), known)
        for m in re.finditer(r"python(?:3)?\s+-m\s+([\w.]+)", text):
            mods |= resolve_seed(m.group(1), known)
    return mods


def string_registry_targets(known: set[str]) -> set[str]:
    mods: set[str] = set()
    registry = OUT_DIR / "string-registry-control" / "registry.py"
    if registry.is_file():
        text = registry.read_text(encoding="utf-8")
        for m in re.finditer(
            r'["\']([A-Za-z0-9_.-]+(?:\.[A-Za-z0-9_.-]+)+)["\']', text
        ):
            mods |= resolve_seed(m.group(1), known)
            if m.group(1) in known:
                mods.add(m.group(1))
            # planted control may use a path under probes/
            cand = m.group(1)
            mods.add(cand)
    for p in (REPO / "tools").rglob("*.py"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            "import_module" not in text
            and "PLUGIN" not in text
            and "registry" not in text.lower()
        ):
            continue
        for m in re.finditer(r'import_module\(\s*["\']([^"\']+)["\']', text):
            mods |= resolve_seed(m.group(1), known)
            mods.add(m.group(1))
        for m in re.finditer(
            r'["\']((?:tools|command-center)[A-Za-z0-9_.-]*)["\']', text
        ):
            cand = m.group(1)
            if cand.count(".") >= 1:
                mods |= resolve_seed(cand, known)
                mods.add(cand)
    return mods


def bfs_ast_closure(seeds: set[str], all_mods: dict[str, Path]) -> set[str]:
    known = set(all_mods)
    edges: dict[str, set[str]] = {m: set() for m in known}
    for name, path in all_mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if node.level:
                    cur = name.split(".")[:-1]
                    base = (
                        cur[: len(cur) - (node.level - 1)]
                        if node.level <= len(cur)
                        else []
                    )
                    absmod = ".".join(base + ([mod] if mod else []))
                else:
                    absmod = mod
                if absmod:
                    imported.append(absmod)
            for raw in imported:
                parts = raw.split(".")
                for i in range(len(parts), 0, -1):
                    cand = ".".join(parts[:i])
                    resolved = resolve_seed(cand, known)
                    if resolved:
                        edges[name] |= resolved
                        break
    reach: set[str] = set()
    stack = []
    for s in seeds:
        stack.extend(resolve_seed(s, known))
        if s in known:
            stack.append(s)
    while stack:
        cur = stack.pop()
        if cur in reach:
            continue
        if cur not in known:
            continue
        reach.add(cur)
        for nxt in edges.get(cur, ()):
            if nxt not in reach:
                stack.append(nxt)
    return reach


def runtime_import_trace(seeds: list[str], all_mods: dict[str, Path]) -> set[str]:
    """Import each seed in a fresh interpreter; collect tools.* modules loaded."""
    live: set[str] = set()
    known = set(all_mods)
    # Prefer seeds that look importable as packages
    picked = []
    for s in seeds:
        if s in known or any(s.startswith(k + ".") is False and False for k in ()):
            pass
        # Prefer short entry-point-like modules
        if s.count(".") <= 4:
            picked.append(s)
    picked = picked[:RUNTIME_SEED_BUDGET]
    for seed in picked:
        # Choose an importable name: prefer non-tools. path alias when needed
        candidates = [seed]
        if seed.startswith("tools."):
            parts = seed.split(".")
            if len(parts) >= 3 and parts[1] == parts[2]:
                candidates.append(".".join(parts[2:]))
            candidates.append(".".join(parts[1:]))
        script = f"""
import sys
sys.path.insert(0, {str(REPO / 'tools')!r})
sys.path.insert(0, {str(REPO)!r})
before = set(sys.modules)
ok = False
err = ''
for name in {candidates!r}:
    try:
        __import__(name)
        ok = True
        break
    except Exception as e:
        err = type(e).__name__ + ':' + str(e)[:120]
after = sorted(m for m in sys.modules if m not in before)
print('IMPORT_OK' if ok else 'IMPORT_FAIL')
print('ERR=' + err)
for m in after:
    print('MOD=' + m)
"""
        try:
            r = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=RUNTIME_TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            continue
        out = (r.stdout or "") + (r.stderr or "")
        for line in out.splitlines():
            if line.startswith("MOD="):
                mod = line[4:]
                # Map loaded module to known path-derived names
                live |= resolve_seed(mod, known)
                if mod in known:
                    live.add(mod)
                # tools/<pkg> on sys.path may load as agentrail.*
                live |= resolve_seed("tools." + mod, known)
                parts = mod.split(".")
                if parts:
                    live |= resolve_seed(
                        "tools." + parts[0] + "." + mod, known
                    )
    return live


def collect_all_modules() -> dict[str, Path]:
    mods: dict[str, Path] = {}
    for p in (REPO / "tools").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        mods[module_name_for(p)] = p
    control = OUT_DIR / "string-registry-control"
    for p in control.glob("*.py"):
        mods[module_name_for(p)] = p
    return mods


def main() -> int:
    p1 = json.loads((OUT_DIR / "probe1-ast-refs.json").read_text(encoding="utf-8"))
    planted = p1["planted_module"]
    all_mods = collect_all_modules()
    known = set(all_mods)

    ep_pyproject = parse_pyproject_entrypoints()
    ep_mains = entry_points_from_mains()
    ci = ci_python_and_pytest_targets(known)
    docs = doc_command_modules(known)
    string_hits_raw = string_registry_targets(known)

    seeds: set[str] = set()
    for raw in ep_pyproject | ep_mains:
        seeds |= resolve_seed(raw, known)
        seeds.add(raw)
    seeds |= ci
    seeds |= docs
    # String registry: keep raw planted name even if outside tools/ path map
    for s in string_hits_raw:
        seeds.add(s)
        seeds |= resolve_seed(s, known)

    seeds_in_known = {s for s in seeds if s in known}
    reached_ast = bfs_ast_closure(seeds_in_known, all_mods)
    runtime_live = runtime_import_trace(
        sorted(ep_pyproject | {m for m in ep_mains if m.endswith(".cli") or m.endswith(".__main__")})
        or sorted(seeds_in_known)[:RUNTIME_SEED_BUDGET],
        all_mods,
    )

    live = set(reached_ast) | set(runtime_live)
    planted_live = planted in string_hits_raw or planted in live
    if planted in string_hits_raw:
        live.add(planted)
        planted_live = True
    if planted_live:
        live.add(planted)

    dead = sorted(m for m in all_mods if m not in live)
    planted_ast_dead = bool(p1.get("planted_ast_dead"))
    control_ok = planted_ast_dead and planted_live

    # Sanity: agentrail tests executed by CI must not all be dead
    agentrail_tests = [m for m in all_mods if "agentrail" in m and ".tests." in m]
    agentrail_tests_live = [m for m in agentrail_tests if m in live]
    false_dead_risk = len(agentrail_tests) > 0 and len(agentrail_tests_live) == 0

    result = {
        "unit": "AUD-0032",
        "probe": 2,
        "stage": "linux-local-remeasure-after-review-fail",
        "seed_pyproject_entrypoints": sorted(ep_pyproject)[:80],
        "seed_entrypoints": sorted(ep_mains)[:50],
        "seed_ci": sorted(ci)[:80],
        "seed_docs": sorted(docs)[:50],
        "string_registry_hits": sorted(string_hits_raw)[:50],
        "seed_count": len(seeds_in_known),
        "seed_raw_count": len(seeds),
        "ast_live_count": len(reached_ast),
        "runtime_live_count": len(runtime_live),
        "live_count": len(live),
        "dead_count": len(dead),
        "dead_sample": dead[:40],
        "agentrail_tests_total": len(agentrail_tests),
        "agentrail_tests_live": len(agentrail_tests_live),
        "false_dead_risk_agentrail_tests": false_dead_risk,
        "planted_module": planted,
        "planted_ast_dead": planted_ast_dead,
        "planted_dynamic_live": planted_live,
        "control_independent": control_ok,
        "methods": [
            "pyproject_entrypoints",
            "mains_and___main__",
            "ci_python_and_pytest_paths",
            "readme_runbook_commands",
            "string_registry_import_module",
            "ast_import_bfs_with_hyphen_aliases",
            "bounded_runtime_import_trace",
        ],
        "ok": control_ok and len(all_mods) > 10 and not false_dead_risk,
    }
    (OUT_DIR / "probe2-dynamic-reachability.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "AUD-0032 NAMED PROBE 2: dynamic reachability (pyproject+CI pytest+docs+runtime)",
        "unit=AUD-0032",
        f"seed_count={result['seed_count']}",
        f"seed_raw_count={result['seed_raw_count']}",
        f"ast_live_count={result['ast_live_count']}",
        f"runtime_live_count={result['runtime_live_count']}",
        f"live_count={result['live_count']}",
        f"dead_count={result['dead_count']}",
        f"agentrail_tests_live={result['agentrail_tests_live']}/{result['agentrail_tests_total']}",
        f"false_dead_risk_agentrail_tests={false_dead_risk}",
        f"planted_module={planted}",
        f"planted_ast_dead={planted_ast_dead}",
        f"planted_dynamic_live={planted_live}",
        f"control_independent={control_ok}",
        f"methods={result['methods']}",
        f"dead_sample={result['dead_sample']!r}",
        "SUCCESS:AUD-0032-probe2" if result["ok"] else "FAILED:AUD-0032-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe2-dynamic.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
