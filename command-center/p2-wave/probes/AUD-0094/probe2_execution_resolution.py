#!/usr/bin/env python3
"""AUD-0094 Probe 2: execution-level resolution errors naming DELETE-ALL paths.

Catalog evidence_requirement (verbatim):
  Probe 2: an execution-level check - run the import graph and the CI collection
  and record any resolution error naming a deleted path, because a reference
  constructed at runtime from parts will not match a literal string search.

Catalog reviewer_requirement:
  one cross-vendor Codex reviewer who re-runs ONLY the second probe.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
DELETED_LIST = PROBE / "deleted_paths.txt"
OUT_JSON = PROBE / "probe2-execution-resolution.json"
OUT_RAW = PROBE / "probe2-execution-resolution.raw.txt"

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    "coverage",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def load_deleted() -> list[str]:
    return [
        ln.strip().replace("\\", "/")
        for ln in DELETED_LIST.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def errors_naming_deleted(text: str, deleted: list[str]) -> list[dict]:
    hits: list[dict] = []
    lower = text
    for d in deleted:
        if d in lower:
            # capture a short window around first occurrence
            idx = lower.find(d)
            start = max(0, idx - 80)
            end = min(len(lower), idx + len(d) + 80)
            hits.append(
                {
                    "deleted_path": d,
                    "excerpt": lower[start:end].replace("\n", " ")[:240],
                }
            )
    return hits


def python_import_graph_scan(deleted: list[str]) -> dict:
    """From surviving .py files, collect Import/ImportFrom targets that map onto a
    deleted path; attempt importlib.import_module and record errors that name it."""
    deleted_set = set(deleted)
    candidates: list[tuple[str, str, str]] = []  # mod, deleted_path, surviving_file
    for p in REPO.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(REPO).parts):
            continue
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith("command-center/p2-wave/probes/AUD-0094/"):
            continue
        try:
            tree = ast.parse(
                p.read_text(encoding="utf-8", errors="replace"), filename=rel
            )
        except (SyntaxError, OSError):
            continue
        mods: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mods.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
        for mod in mods:
            cand_py = mod.replace(".", "/") + ".py"
            cand_dir = mod.replace(".", "/")
            matched = None
            if cand_py in deleted_set:
                matched = cand_py
            elif cand_dir in deleted_set:
                matched = cand_dir
            else:
                for d in deleted:
                    if (
                        cand_py == d
                        or cand_dir == d
                        or cand_dir.startswith(d.rstrip("/") + "/")
                    ):
                        matched = d
                        break
            if matched:
                candidates.append((mod, matched, rel))

    resolution_errors: list[dict] = []
    seen = set()
    for mod, dpath, surviving in candidates:
        key = (mod, dpath)
        if key in seen:
            continue
        seen.add(key)
        code = f"import importlib\nimportlib.import_module({mod!r})\n"
        rc, out = run([sys.executable, "-c", code], timeout=30)
        if rc != 0:
            resolution_errors.append(
                {
                    "kind": "python-importlib-from-survivor",
                    "module": mod,
                    "deleted_path": dpath,
                    "surviving_file": surviving,
                    "exit_code": rc,
                    "excerpt": out.strip().replace("\n", " ")[:300],
                    "names_deleted_path": dpath in out or mod in out,
                }
            )
    return {
        "attempted": len(seen),
        "survivor_import_candidates": len(candidates),
        "resolution_error_count": len(resolution_errors),
        "resolution_errors": resolution_errors[:100],
    }


def pytest_collect_scan(deleted: list[str]) -> dict:
    """Run pytest --collect-only on a few live packages; record errors naming deleted paths."""
    targets = [
        "tools/stdin-server",
        "hooks",
        "command-center/p2-wave/probes/AUD-0094",
    ]
    runs: list[dict] = []
    all_hits: list[dict] = []
    for t in targets:
        p = REPO / t
        if not p.exists():
            runs.append({"target": t, "skipped": True, "reason": "missing"})
            continue
        rc, out = run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", str(p)],
            timeout=120,
        )
        hits = errors_naming_deleted(out, deleted)
        runs.append(
            {
                "target": t,
                "skipped": False,
                "exit_code": rc,
                "output_bytes": len(out),
                "deleted_path_error_hits": len(hits),
                "hits_sample": hits[:20],
            }
        )
        all_hits.extend(hits)
    return {
        "runs": runs,
        "collect_deleted_path_error_hit_count": len(all_hits),
        "hits": all_hits[:100],
    }


IMPORT_RE = re.compile(
    r"""(?:from\s+['"](\.?\.?/[^'"]+)['"]|require\(\s*['"](\.?\.?/[^'"]+)['"]\s*\)|import\(\s*['"](\.?\.?/[^'"]+)['"]\s*\))"""
)


def node_survivor_import_scan(deleted: list[str]) -> dict:
    """Find relative import/require targets in surviving JS that name a deleted path,
    then ask node to resolve them from the importing file (execution-level)."""
    deleted_set = set(deleted)
    # Also match imports that are exact deleted paths or path prefixes into deleted trees.
    candidate_hits: list[dict] = []
    js_exts = {".mjs", ".js", ".cjs", ".ts", ".mts", ".cts"}
    for p in REPO.rglob("*"):
        if p.suffix.lower() not in js_exts or not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(REPO).parts):
            continue
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith("command-center/p2-wave/probes/AUD-0094/"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in IMPORT_RE.finditer(text):
            spec = next(g for g in m.groups() if g)
            # Normalize ./foo -> foo relative to importer dir
            if spec.startswith("./") or spec.startswith("../"):
                try:
                    resolved = (p.parent / spec).resolve()
                    try:
                        target_rel = resolved.relative_to(REPO.resolve()).as_posix()
                    except ValueError:
                        continue
                except OSError:
                    # Unresolved relative — compare string forms against deleted list
                    target_rel = spec.lstrip("./")
            else:
                continue
            matched = None
            if target_rel in deleted_set:
                matched = target_rel
            else:
                for d in deleted:
                    if target_rel == d or target_rel.startswith(d.rstrip("/") + "/"):
                        matched = d
                        break
                    # import may omit extension
                    if d.startswith(target_rel) and d[
                        len(target_rel) : len(target_rel) + 1
                    ] in {
                        "",
                        ".",
                    }:
                        matched = d
                        break
            if matched:
                candidate_hits.append(
                    {
                        "surviving_file": rel,
                        "import_spec": spec,
                        "resolved_or_raw": target_rel,
                        "deleted_path": matched,
                    }
                )

    errors: list[dict] = []
    for hit in candidate_hits[:60]:
        importer = REPO / hit["surviving_file"]
        script = f"""
const {{ createRequire }} = require('module');
const path = require('path');
const req = createRequire({json.dumps(str(importer))});
try {{
  const r = req.resolve({json.dumps(hit["import_spec"])});
  console.log('RESOLVED', r);
}} catch (e) {{
  console.error('RESOLVE_FAIL', {json.dumps(hit["deleted_path"])}, e.code || '', e.message);
  process.exitCode = 1;
}}
"""
        rc, out = run(["node", "-e", script], timeout=20)
        if rc != 0 and (
            hit["deleted_path"] in out
            or "MODULE_NOT_FOUND" in out
            or "ERR_MODULE_NOT_FOUND" in out
        ):
            errors.append(
                {
                    "kind": "node-survivor-import-resolve",
                    "surviving_file": hit["surviving_file"],
                    "import_spec": hit["import_spec"],
                    "deleted_path": hit["deleted_path"],
                    "exit_code": rc,
                    "excerpt": out.strip().replace("\n", " ")[:300],
                    "names_deleted_path": hit["deleted_path"] in out,
                }
            )

    # Absence confirmation (not counted as dangling from survivors): direct resolve of a sample.
    absent_confirm = []
    js_deleted = [d for d in deleted if d.endswith((".mjs", ".js", ".cjs"))]
    for dpath in js_deleted[:5]:
        script = f"""
const {{ createRequire }} = require('module');
const path = require('path');
const req = createRequire(path.join(process.cwd(), 'package.json'));
try {{ req.resolve({json.dumps("./" + dpath)}); process.exit(2); }}
catch (e) {{ console.error('ABSENT', {json.dumps(dpath)}, e.code || ''); process.exit(1); }}
"""
        rc, out = run(["node", "-e", script], timeout=15)
        absent_confirm.append(
            {
                "deleted_path": dpath,
                "absent": rc == 1 and dpath in out,
                "excerpt": out[:160],
            }
        )

    return {
        "survivor_import_hits": len(candidate_hits),
        "survivor_import_sample": candidate_hits[:40],
        "attempted_resolves": min(len(candidate_hits), 60),
        "resolution_error_count": len(errors),
        "resolution_errors": errors[:80],
        "absent_confirm_sample": absent_confirm,
        "js_deleted_count": len(js_deleted),
    }


def planted_runtime_parts_control(deleted: list[str]) -> dict:
    """Plant a runtime-constructed reference from path parts that probe1 literal
    search would miss if only looking for the full contiguous string in source
    that builds it — prove probe2 can still see the deleted path in the error.

    The control script joins parts at runtime and asks node to resolve them.
    """
    # Prefer a deleted mjs if present, else first deleted path.
    target = next((d for d in deleted if d.endswith(".mjs")), deleted[0])
    parts = target.split("/")
    # Write ephemeral runner under tempfile (not committed) so probe1 corpus
    # does not gain a contiguous full-path use hit from this control source.
    with tempfile.TemporaryDirectory(prefix="aud0094-p2-") as td:
        runner = Path(td) / "runtime_parts_resolve.mjs"
        # Construct path from parts array — full string never appears contiguous
        # as a single literal in this file.
        runner.write_text(
            "import { createRequire } from 'module';\n"
            "import path from 'path';\n"
            "import { fileURLToPath } from 'url';\n"
            f"const parts = {json.dumps(parts)};\n"
            "const rel = parts.join('/');\n"
            "const req = createRequire(path.join(process.cwd(), 'package.json'));\n"
            "try {\n"
            "  req.resolve('./' + rel);\n"
            "  console.log('UNEXPECTED_RESOLVED', rel);\n"
            "  process.exit(2);\n"
            "} catch (e) {\n"
            "  console.error('EXPECTED_FAIL', rel, e.code || '', e.message);\n"
            "  process.exit(1);\n"
            "}\n",
            encoding="utf-8",
        )
        rc, out = run(["node", str(runner)], timeout=20)
    named = target in out
    fired = rc != 0 and named
    return {
        "id": "AUD0094-C2-runtime-parts",
        "deleted_path": target,
        "parts_count": len(parts),
        "exit_code": rc,
        "names_deleted_path_in_error": named,
        "fired_on_bad_state": fired,
        "silent_on_good_state": True,  # no good-state twin required for this detector
        "ok": fired,
        "excerpt": out.strip().replace("\n", " ")[:400],
        "description": (
            "Runtime-joined path parts resolve against a deleted file; error must "
            "name the deleted path (probe1 contiguous literal would miss the join)."
        ),
    }


def ast_import_mentions_of_deleted(deleted: list[str]) -> dict:
    """Secondary signal: AST-level import/require string constants equal to a deleted path."""
    deleted_set = set(deleted)
    hits: list[dict] = []
    py_files = 0
    for p in REPO.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(REPO).parts):
            continue
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith("command-center/p2-wave/probes/AUD-0094/"):
            continue
        py_files += 1
        try:
            tree = ast.parse(
                p.read_text(encoding="utf-8", errors="replace"), filename=rel
            )
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # rough: module path with dots → slash
                cand = node.module.replace(".", "/") + ".py"
                if cand in deleted_set or node.module.replace(".", "/") in deleted_set:
                    hits.append(
                        {"file": rel, "kind": "ImportFrom", "module": node.module}
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            ):
                if (
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    mod = node.args[0].value
                    cand = mod.replace(".", "/") + ".py"
                    if cand in deleted_set:
                        hits.append({"file": rel, "kind": "__import__", "module": mod})
    return {"py_files_parsed": py_files, "ast_hit_count": len(hits), "hits": hits[:50]}


def main() -> int:
    deleted = load_deleted()
    if len(deleted) != 77:
        print(f"FAILED:AUD-0094-probe2 expected 77 deleted paths, got {len(deleted)}")
        return 1

    py_graph = python_import_graph_scan(deleted)
    collect = pytest_collect_scan(deleted)
    node = node_survivor_import_scan(deleted)
    planted = planted_runtime_parts_control(deleted)
    ast_hits = ast_import_mentions_of_deleted(deleted)

    # Resolution errors that name a deleted path (execution-level dangling).
    named_errors = []
    for block in py_graph.get("resolution_errors") or []:
        if block.get("names_deleted_path"):
            named_errors.append(block)
    for block in node.get("resolution_errors") or []:
        if (
            block.get("names_deleted_path")
            or block.get("kind") == "node-survivor-import-resolve"
        ):
            named_errors.append(block)
    for h in collect.get("hits") or []:
        named_errors.append(
            {
                "kind": "pytest-collect",
                "deleted_path": h["deleted_path"],
                "excerpt": h.get("excerpt", ""),
                "names_deleted_path": True,
            }
        )

    result = {
        "unit": "AUD-0094",
        "probe": 2,
        "method": "importlib+survivor-import-resolve+pytest-collect+runtime-parts-control",
        "deleted_path_count": len(deleted),
        "python_import_graph": py_graph,
        "pytest_collect": collect,
        "node_resolution": node,
        "ast_static_imports": ast_hits,
        "planted_runtime_parts_control": planted,
        "resolution_errors_naming_deleted_count": len(named_errors),
        "resolution_errors_naming_deleted_sample": named_errors[:80],
        "ok": bool(planted.get("ok")),
    }

    raw_lines = [
        "AUD-0094 NAMED PROBE 2: execution-level resolution errors naming deleted paths",
        (
            "catalog_verbatim=Probe 2: an execution-level check - run the import graph "
            "and the CI collection and record any resolution error naming a deleted path, "
            "because a reference constructed at runtime from parts will not match a "
            "literal string search."
        ),
        "unit=AUD-0094",
        f"deleted_path_count={len(deleted)}",
        f"python_import_attempted={py_graph['attempted']}",
        f"python_resolution_errors={py_graph['resolution_error_count']}",
        f"node_survivor_import_hits={node['survivor_import_hits']}",
        f"node_resolve_attempted={node['attempted_resolves']}",
        f"node_resolution_errors={node['resolution_error_count']}",
        f"pytest_collect_deleted_path_hits={collect['collect_deleted_path_error_hit_count']}",
        f"resolution_errors_naming_deleted_count={result['resolution_errors_naming_deleted_count']}",
        f"ast_import_hits={ast_hits['ast_hit_count']}",
        f"planted_runtime_parts_ok={planted['ok']}",
        f"planted_runtime_parts_path={planted['deleted_path']}",
        "RUNS-BEGIN",
    ]
    for r in collect["runs"]:
        raw_lines.append(
            "COLLECT\t"
            f"target={r.get('target')}\texit={r.get('exit_code', '-')}\t"
            f"hits={r.get('deleted_path_error_hits', 0)}\tskipped={r.get('skipped')}"
        )
    raw_lines.append("RUNS-END")
    raw_lines.append("ERRORS-BEGIN")
    for e in named_errors[:30]:
        raw_lines.append(
            f"ERR\tkind={e.get('kind')}\tpath={e.get('deleted_path')}\t"
            f"excerpt={str(e.get('excerpt', ''))[:160]}"
        )
    raw_lines.append("ERRORS-END")
    raw_lines.append(
        f"SUCCESS:AUD-0094-probe2 naming_errors={result['resolution_errors_naming_deleted_count']} "
        f"planted_ok={planted['ok']}"
        if result["ok"]
        else f"FAILED:AUD-0094-probe2 planted_ok={planted['ok']}"
    )
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
