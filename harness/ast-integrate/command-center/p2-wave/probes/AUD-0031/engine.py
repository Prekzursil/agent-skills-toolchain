"""AUD-0031 salvage-consumption detectors.

Probe 1: AST import-graph reverse-reference (never grep).
Probe 2: runtime coverage of non-test entry points (import is not a use).
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from shutil import which
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
LIB_HOME = TOOLS / "lib"

SKIP_DIRS = {
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
    ".tox",
}

CATALOG_ROSTER = [
    "net-allowlist.mjs",
    "security.mjs",
    "git-diff.mjs",
    "handled-ledger.mjs",
    "codex-invocation.mjs",
    "workspace.mjs",
]

JS_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx"}
PY_EXT = {".py"}
SRC_EXT = JS_EXT | PY_EXT

IMPORT_FROM_RE = re.compile(
    r"""(?:^|[^\w$])(?:import|export)\s+[\s\S]*?\sfrom\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)
IMPORT_CALL_RE = re.compile(
    r"""(?:^|[^\w$])import\s*\(\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
REQUIRE_RE = re.compile(
    r"""(?:^|[^\w$])require\s*\(\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
EXPORT_ALL_RE = re.compile(
    r"""(?:^|[^\w$])export\s+\*\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def roster() -> list[dict[str, Any]]:
    names: list[str] = []
    if LIB_HOME.is_dir():
        for p in sorted(LIB_HOME.iterdir()):
            if p.is_file() and p.suffix in {".mjs", ".js", ".cjs", ".py"}:
                names.append(p.name)
    if len(names) != 6:
        names = list(CATALOG_ROSTER)
    rows = []
    for name in names:
        stem = Path(name).stem
        rows.append(
            {
                "filename": name,
                "stem": stem,
                "rel": f"tools/lib/{name}",
                "py_mod": "tools.lib." + stem.replace("-", "_"),
                "present_on_disk": (LIB_HOME / name).is_file(),
            }
        )
    return rows


def is_test_path(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1].lower()
    if any(p.lower() in {"test", "tests", "__tests__", "spec", "specs"} for p in parts):
        return True
    if name.startswith("test_"):
        return True
    if name.endswith(("_test.py", "_test.js", "_test.mjs")):
        return True
    if ".test." in name or ".spec." in name:
        return True
    return False


def is_out_of_scope(rel: str) -> bool:
    """Fixtures, build output, and this unit's own probes are not production callers."""
    posix = rel.replace("\\", "/")
    parts = posix.split("/")
    skip = {
        "fixtures",
        "fixture",
        "dist",
        "vendor",
        "node_modules",
        "salvaged-from-scratch",
    }
    if any(p.lower() in skip for p in parts):
        return True
    if posix.startswith("command-center/p2-wave/probes/AUD-0031/"):
        return True
    return False


def is_salvage_home(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    return posix == "tools/lib" or posix.startswith("tools/lib/")


def iter_source_files() -> list[Path]:
    out: list[Path] = []
    roots = [TOOLS]
    extra = REPO / "lib"
    if extra.is_dir():
        roots.append(extra)
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                path = Path(dirpath) / fn
                if path.suffix.lower() not in SRC_EXT:
                    continue
                rel = path.relative_to(REPO).as_posix()
                if is_out_of_scope(rel):
                    continue
                if path.name == "unit_manifest.py":
                    continue
                out.append(path)
    return sorted(out)


def strip_js_comments(src: str) -> str:
    out: list[str] = []
    i, n, state = 0, len(src), "code"
    while i < n:
        ch, nxt = src[i], src[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            if ch == "'":
                state = "sq"
            elif ch == '"':
                state = "dq"
            elif ch == "`":
                state = "tmpl"
            out.append(ch)
            i += 1
            continue
        if state == "line":
            out.append(ch if ch == "\n" else " ")
            if ch == "\n":
                state = "code"
            i += 1
            continue
        if state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                out.append("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
            continue
        quote = {"sq": "'", "dq": '"', "tmpl": "`"}[state]
        if ch == "\\" and i + 1 < n:
            out.extend((ch, src[i + 1]))
            i += 2
            continue
        out.append(ch)
        if ch == quote:
            state = "code"
        i += 1
    return "".join(out)


def js_import_specs(src: str) -> list[str]:
    code = strip_js_comments(src)
    specs: list[str] = []
    for rx in (IMPORT_FROM_RE, IMPORT_CALL_RE, REQUIRE_RE, EXPORT_ALL_RE):
        specs.extend(m.group(1) for m in rx.finditer(code))
    return specs


def py_import_specs(src: str, filename: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.append(("from", ("." * (node.level or 0)) + mod))
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if name in {"import_module", "__import__"} and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    out.append(("dynamic", arg0.value))
    return out


def match_salvage(spec: str, rows: list[dict[str, Any]], from_file: Path) -> str | None:
    s = spec.replace("\\", "/").strip()
    if not s:
        return None
    for row in rows:
        rel, fn, stem, py = row["rel"], row["filename"], row["stem"], row["py_mod"]
        if rel in s or s.endswith("/" + fn):
            return rel
        if s in {f"tools/lib/{stem}", f"./tools/lib/{stem}"}:
            return rel
        if s == py or s.startswith(py + "."):
            return rel
        if s in {f"@prekzursil/tools-lib/{stem}", f"@prekzursil/tools-lib/{fn}"}:
            return rel
    if s in {"@prekzursil/tools-lib", "tools/lib", "tools.lib"}:
        return "tools/lib"
    if s.startswith("."):
        try:
            rel_p = (from_file.parent / s).resolve().relative_to(REPO).as_posix()
        except (OSError, ValueError):
            return None
        for row in rows:
            stem_path = row["rel"].rsplit(".", 1)[0]
            if rel_p in {row["rel"], stem_path}:
                return row["rel"]
        if rel_p.startswith("tools/lib/"):
            return rel_p
    return None


def reverse_refs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    consumers: dict[str, list[dict[str, str]]] = defaultdict(list)
    scanned = skipped = errors = 0
    for path in iter_source_files():
        rel = path.relative_to(REPO).as_posix()
        if is_test_path(rel) or is_out_of_scope(rel):
            skipped += 1
            continue
        if is_salvage_home(rel):
            # The salvaged tree is the subject, not a non-test caller of itself.
            skipped += 1
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            errors += 1
            continue
        specs = (
            py_import_specs(text, rel)
            if path.suffix.lower() in PY_EXT
            else [("js", s) for s in js_import_specs(text)]
        )
        seen: set[str] = set()
        for kind, spec in specs:
            hit = match_salvage(spec, rows, path)
            if not hit:
                continue
            key = f"{rel}:{hit}:{spec}"
            if key in seen:
                continue
            seen.add(key)
            consumers[hit].append({"path": rel, "kind": kind, "specifier": spec})
    return {
        "method": "ast-import-graph-reverse-ref",
        "used_grep": False,
        "files_scanned": scanned,
        "test_files_excluded": skipped,
        "parse_errors": errors,
        "consumers_by_module": dict(sorted(consumers.items())),
    }


def mention_control(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = rows[0]["rel"]
    stem_py = rows[0]["stem"].replace("-", "_")
    mention_py = (
        f'"""Planted mention of {target} in a docstring only."""\n'
        f"# comment also names {target}\n"
        "def unused():\n    return 0\n"
    )
    import_py = f"import {rows[0]['py_mod']}\n"
    mention_js = (
        f"/**\n * Docblock names {target} and must not count.\n */\n"
        f"// line comment names {target}\n"
        "export function unused() { return 1; }\n"
    )
    import_js = (
        f'import allow from "{target}";\n'
        "export function unused() { return allow; }\n"
    )

    def hits_for(path: Path) -> list[str]:
        text = path.read_text(encoding="utf-8")
        specs = (
            py_import_specs(text, path.name)
            if path.suffix == ".py"
            else [("js", s) for s in js_import_specs(text)]
        )
        found = []
        for _kind, spec in specs:
            hit = match_salvage(spec, rows, path)
            if hit:
                found.append(hit)
        return found

    with tempfile.TemporaryDirectory(prefix="aud0031-mention-") as tmp:
        tdir = Path(tmp)
        (tdir / "mention_only.py").write_text(mention_py, encoding="utf-8")
        (tdir / "real_import.py").write_text(import_py, encoding="utf-8")
        (tdir / "mention_only.mjs").write_text(mention_js, encoding="utf-8")
        (tdir / "real_import.mjs").write_text(import_js, encoding="utf-8")
        mention_hits = hits_for(tdir / "mention_only.py") + hits_for(tdir / "mention_only.mjs")
        import_hits = hits_for(tdir / "real_import.py") + hits_for(tdir / "real_import.mjs")
        grep_would_fire = target in mention_py and target in mention_js
        silent = mention_hits == []
        fired = any(h == target or h.endswith("/" + rows[0]["filename"]) for h in import_hits)
        return {
            "id": "use-vs-mention",
            "kind": "use-vs-mention",
            "description": (
                "A module named only inside a docstring or a comment must NOT "
                "count as a consumer; a real import of the same module must."
            ),
            "target": target,
            "mention_hits": mention_hits,
            "import_hits": import_hits,
            "grep_would_fire_on_mention": grep_would_fire,
            "silent_on_mention": silent,
            "fired_on_import": fired,
            "passed": bool(silent and fired and grep_would_fire),
        }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def run_py_entry(entry: Path, *, call: str = "", timeout: int = 8) -> dict[str, Any]:
    script = r"""
import json, runpy, sys
from pathlib import Path
entry = Path(sys.argv[1])
call_name = sys.argv[2] if len(sys.argv) > 2 else ""
sys.path.insert(0, str(entry.parent))
hits = []
def tracer(frame, event, arg):
    if event != "call":
        return tracer
    fn = frame.f_code.co_filename.replace("\\", "/")
    if "/tools/lib/" in fn or fn.endswith("salvage_stub.py") or "salvage_stub.py" in fn:
        hits.append({"file": fn, "func": frame.f_code.co_name, "line": frame.f_lineno})
    return tracer
sys.settrace(tracer)
err = None
try:
    ns = runpy.run_path(str(entry), run_name="__aud0031_entry__")
    if call_name and callable(ns.get(call_name)):
        ns[call_name]()
except Exception as exc:
    err = f"{type(exc).__name__}: {exc}"
finally:
    sys.settrace(None)
loaded = []
for name, mod in sys.modules.items():
    f = getattr(mod, "__file__", None) or ""
    if "tools/lib" in f.replace("\\", "/") or "tools.lib" in name:
        loaded.append({"name": name, "file": f})
print(json.dumps({"hits": hits, "loaded": loaded, "error": err}))
"""
    cmd = [sys.executable, "-B", "-c", script, str(entry)]
    if call:
        cmd.append(call)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired:
        return {"path": _rel(entry), "timeout": True, "hits": [], "loaded": [], "error": "TIMEOUT"}
    payload: dict[str, Any] = {}
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    err = payload.get("error")
    if err is None and proc.returncode != 0:
        err = (proc.stderr or "")[-400:]
    return {
        "path": _rel(entry),
        "exit_code": proc.returncode,
        "hits": payload.get("hits") or [],
        "loaded": payload.get("loaded") or [],
        "error": err,
        "timeout": False,
    }


def run_js_entry(entry: Path, timeout: int = 8) -> dict[str, Any]:
    node = which("node")
    if not node:
        return {"path": _rel(entry), "error": "node-absent", "hits": [], "skipped": True}
    script = r"""
import { pathToFileURL } from "node:url";
import { registerHooks } from "node:module";
const entry = process.argv[1];
const hits = [];
registerHooks({
  load(url, context, nextLoad) {
    if (url.includes("/tools/lib/") || url.includes("salvage_stub.mjs") || url.includes("salvage_stub.mjs")) {
      hits.push(url);
    }
    return nextLoad(url, context);
  }
});
let error = null;
try {
  const mod = await import(pathToFileURL(entry).href);
  if (typeof mod.main === "function") await mod.main();
} catch (e) {
  error = `${e && e.name}: ${e && e.message}`;
}
console.log(JSON.stringify({ hits, error }));
"""
    try:
        proc = subprocess.run(
            [node, "--input-type=module", "-e", script, str(entry)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"path": _rel(entry), "timeout": True, "hits": [], "error": "TIMEOUT"}
    payload: dict[str, Any] = {}
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    return {
        "path": _rel(entry),
        "exit_code": proc.returncode,
        "hits": payload.get("hits") or [],
        "error": payload.get("error"),
        "timeout": False,
        "stderr_tail": (proc.stderr or "")[-300:],
        "skipped": False,
    }


def live_entry_points() -> list[Path]:
    found: list[Path] = []
    for path in iter_source_files():
        rel = path.relative_to(REPO).as_posix()
        if is_test_path(rel) or is_out_of_scope(rel) or path.suffix.lower() != ".py":
            continue
        if is_salvage_home(rel):
            continue
        if path.name == "conftest.py":
            continue
        if "/command-center/" in ("/" + rel):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if 'if __name__ == "__main__"' in text or "if __name__ == '__main__'" in text:
            found.append(path)
        elif path.name in {"__main__.py", "cli.py", "main.py"}:
            found.append(path)
    return found[:8]


def import_vs_use_control() -> dict[str, Any]:
    stub_py = "USED = {'n': 0}\ndef used():\n    USED['n'] += 1\n    return USED['n']\n"
    import_only = "import salvage_stub\ndef main():\n    return 0\n"
    execute = "import salvage_stub\ndef main():\n    return salvage_stub.used()\n"
    stub_js = "export function used() { return 1; }\n"
    import_only_js = "import { used } from './salvage_stub.mjs';\nexport function main() { return 0; }\n"
    execute_js = "import { used } from './salvage_stub.mjs';\nexport function main() { return used(); }\n"
    with tempfile.TemporaryDirectory(prefix="aud0031-use-") as tmp:
        tdir = Path(tmp)
        (tdir / "salvage_stub.py").write_text(stub_py, encoding="utf-8")
        (tdir / "import_only.py").write_text(import_only, encoding="utf-8")
        (tdir / "execute.py").write_text(execute, encoding="utf-8")
        (tdir / "salvage_stub.mjs").write_text(stub_js, encoding="utf-8")
        (tdir / "import_only.mjs").write_text(import_only_js, encoding="utf-8")
        (tdir / "execute.mjs").write_text(execute_js, encoding="utf-8")
        io = run_py_entry(tdir / "import_only.py", call="main")
        ex = run_py_entry(tdir / "execute.py", call="main")
        io_used = any(h.get("func") == "used" for h in io.get("hits") or [])
        ex_used = any(h.get("func") == "used" for h in ex.get("hits") or [])
        js_io = run_js_entry(tdir / "import_only.mjs")
        js_ex = run_js_entry(tdir / "execute.mjs")
        js_ok = True
        if not js_io.get("skipped"):
            js_ok = not js_ex.get("error")
        # Python both-states is the required discriminator; JS is extra if hooks work.
        passed = (not io_used) and ex_used
        return {
            "id": "import-is-not-a-use",
            "kind": "runtime-coverage",
            "description": (
                "A salvaged module imported but never invoked must not count as "
                "executed; a call to used() must count."
            ),
            "python_import_only_executed_used": io_used,
            "python_execute_executed_used": ex_used,
            "python_import_only_error": io.get("error"),
            "python_execute_error": ex.get("error"),
            "js_import_only_error": js_io.get("error"),
            "js_execute_error": js_ex.get("error"),
            "js_control_ran": not bool(js_io.get("skipped")),
            "passed": bool(passed),
        }


def live_runtime_trace() -> dict[str, Any]:
    traces = []
    executed_lib: set[str] = set()
    loaded_lib: set[str] = set()
    for entry in live_entry_points():
        tr = run_py_entry(entry, call="")
        traces.append(
            {
                "path": tr.get("path"),
                "error": tr.get("error"),
                "timeout": tr.get("timeout"),
                "hit_count": len(tr.get("hits") or []),
                "loaded_count": len(tr.get("loaded") or []),
            }
        )
        for h in tr.get("hits") or []:
            fn = str(h.get("file") or "").replace("\\", "/")
            if "/tools/lib/" in fn:
                executed_lib.add(fn)
        for m in tr.get("loaded") or []:
            f = str(m.get("file") or "").replace("\\", "/")
            if "/tools/lib/" in f:
                loaded_lib.add(f)
    js_traces = []
    js_entries = []
    for p in iter_source_files():
        rel = p.relative_to(REPO).as_posix()
        if p.suffix.lower() not in JS_EXT:
            continue
        if is_test_path(rel) or is_out_of_scope(rel) or is_salvage_home(rel):
            continue
        js_entries.append(p)
        if len(js_entries) >= 8:
            break
    for entry in js_entries:
        tr = run_js_entry(entry)
        js_traces.append(
            {
                "path": tr.get("path"),
                "error": tr.get("error"),
                "skipped": tr.get("skipped"),
                "hit_count": len(tr.get("hits") or []),
            }
        )
        for h in tr.get("hits") or []:
            if "/tools/lib/" in str(h):
                executed_lib.add(str(h))
    return {
        "method": "runtime-coverage-trace",
        "python_entries_attempted": len(traces),
        "js_entries_attempted": len(js_traces),
        "python_traces": traces,
        "js_traces": js_traces,
        "tools_lib_loaded": sorted(loaded_lib),
        "tools_lib_executed": sorted(executed_lib),
        "lib_home_exists": LIB_HOME.is_dir(),
        "lib_home_file_count": (
            len([p for p in LIB_HOME.iterdir() if p.is_file()]) if LIB_HOME.is_dir() else 0
        ),
    }


def module_rows(
    rows: list[dict[str, Any]], refs: dict[str, Any], runtime: dict[str, Any]
) -> list[dict[str, Any]]:
    cons = refs.get("consumers_by_module") or refs.get("consumers_by_module") or {}
    executed = runtime.get("tools_lib_executed") or []
    loaded = runtime.get("tools_lib_loaded") or []
    pkg_callers = cons.get("tools/lib") or []
    out = []
    for row in rows:
        rel = row["rel"]
        own = cons.get(rel) or []
        n = len(own)
        exec_hit = any(rel in str(x) or ("/" + row["filename"]) in str(x) for x in executed)
        load_hit = any(rel in str(x) or ("/" + row["filename"]) in str(x) for x in loaded)
        measurable = n > 0 or exec_hit
        if measurable:
            verdict = "CONSUMED"
        elif not row["present_on_disk"]:
            verdict = "ABSENT-AND-UNCONSUMED"
        else:
            verdict = "PRESENT-BUT-UNCONSUMED"
        out.append(
            {
                "module": rel,
                "filename": row["filename"],
                "present_on_disk": row["present_on_disk"],
                "non_test_import_consumers": own,
                "non_test_import_consumer_count": n,
                "package_level_importers": pkg_callers,
                "runtime_loaded": load_hit,
                "runtime_executed": exec_hit,
                "salvage_measurable": measurable,
                "verdict": verdict,
            }
        )
    return out


def summarize(modules: list[dict[str, Any]]) -> dict[str, Any]:
    consumed = [r for r in modules if r["salvage_measurable"]]
    absent = [r for r in modules if not r["present_on_disk"]]
    return {
        "roster_count": len(modules),
        "present_on_disk": len(modules) - len(absent),
        "absent_on_disk": len(absent),
        "modules_with_non_test_consumers": len(consumed),
        "modules_with_zero_non_test_consumers": len(modules) - len(consumed),
        "salvage_achieved_measurable_consumption": len(consumed) > 0,
        "lib_home": "tools/lib/",
        "lib_home_exists": LIB_HOME.is_dir(),
    }


def measure() -> dict[str, Any]:
    rows = roster()
    refs = reverse_refs(rows)
    mention = mention_control(rows)
    runtime = live_runtime_trace()
    use = import_vs_use_control()
    modules = module_rows(rows, refs, runtime)
    return {
        "roster": rows,
        "probe1": refs,
        "mention_control": mention,
        "probe2": runtime,
        "import_vs_use_control": use,
        "modules": modules,
        "summary": summarize(modules),
    }
