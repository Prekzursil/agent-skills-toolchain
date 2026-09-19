#!/usr/bin/env python3
"""AUD-0031 Probe 2: runtime coverage of non-test entry points for tools/lib.

An import is not a use. This probe runs non-test JS entry points under
NODE_V8_COVERAGE and records which tools/lib/*.mjs files have executed ranges.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-runtime-coverage.json"
OUT_RAW = PROBE / "probe2-runtime-coverage.raw.txt"
LIB = REPO / "tools" / "lib"
CONTROL = PROBE / "mention-only-control" / "mention_only.mjs"

SALVAGE_FILES = [
    "security.mjs",
    "workspace.mjs",
    "git-diff.mjs",
    "handled-ledger.mjs",
    "net-allowlist.mjs",
    "codex-invocation.mjs",
]

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
}


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def is_testish(path: Path | str) -> bool:
    s = str(path).replace("\\", "/").lower()
    name = Path(s).name
    if "/tests/" in f"/{s}/" or "/test/" in f"/{s}/" or "/__tests__/" in f"/{s}/":
        return True
    if name.endswith((".test.mjs", ".test.js", ".spec.mjs", ".spec.js")):
        return True
    if "test" in name and name.endswith((".mjs", ".js")):
        # e.g. test_fanout_schema.mjs
        if name.startswith("test") or ".test." in name:
            return True
    return False


def load_package_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def collect_entry_points() -> list[dict]:
    """Non-test JS entry points: package main/exports/bin + selected scripts."""
    entries: list[dict] = []
    seen: set[str] = set()

    def add(path: Path, kind: str, via: str) -> None:
        if not path.is_file():
            return
        if path.suffix not in {".mjs", ".js", ".cjs"}:
            return
        if is_testish(path):
            return
        # never treat tools/lib modules themselves as consumer entry points
        try:
            if path.resolve().parent == LIB.resolve():
                return
        except OSError:
            return
        key = rel(path)
        if key in seen:
            return
        seen.add(key)
        entries.append({"path": key, "kind": kind, "via": via})

    # Root + tools/**/package.json
    pkg_files = [REPO / "package.json"]
    tools = REPO / "tools"
    if tools.is_dir():
        for p in tools.rglob("package.json"):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            pkg_files.append(p)

    for pkg_path in pkg_files:
        meta = load_package_json(pkg_path)
        if not meta:
            continue
        base = pkg_path.parent
        via = rel(pkg_path)
        main = meta.get("main")
        if isinstance(main, str):
            add(base / main, "package.main", via)
        exports = meta.get("exports")
        if isinstance(exports, str):
            add(base / exports, "package.exports", via)
        elif isinstance(exports, dict):
            for _k, v in exports.items():
                if isinstance(v, str):
                    add(base / v, "package.exports", via)
                elif isinstance(v, dict):
                    for field in ("import", "require", "default", "node"):
                        if isinstance(v.get(field), str):
                            add(base / v[field], "package.exports", via)
        bins = meta.get("bin")
        if isinstance(bins, str):
            add(base / bins, "package.bin", via)
        elif isinstance(bins, dict):
            for _n, b in bins.items():
                if isinstance(b, str):
                    add(base / b, "package.bin", via)
        scripts = meta.get("scripts") or {}
        if isinstance(scripts, dict):
            # Only non-test scripts that look like `node <file>`
            for sname, scmd in scripts.items():
                if not isinstance(scmd, str):
                    continue
                if "test" in sname.lower():
                    continue
                parts = scmd.split()
                if parts and parts[0] in {"node", "nodejs"} and len(parts) >= 2:
                    cand = parts[1]
                    if cand.startswith("-"):
                        continue
                    add(base / cand, f"package.scripts.{sname}", via)

    # CI workflow node file invocations (non-test)
    wf = REPO / ".github" / "workflows"
    if wf.is_dir():
        for yml in list(wf.glob("*.yml")) + list(wf.glob("*.yaml")):
            try:
                text = yml.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                stripped = line.strip()
                if "node " not in stripped:
                    continue
                if "test" in stripped.lower():
                    continue
                # crude: node path/to/file.mjs
                toks = stripped.replace("|", " ").split()
                for i, t in enumerate(toks):
                    if t in {"node", "nodejs"} and i + 1 < len(toks):
                        cand = toks[i + 1].strip("'\"")
                        if cand.endswith(
                            (".mjs", ".js", ".cjs")
                        ) and not cand.startswith("-"):
                            add(REPO / cand, "ci-workflow", rel(yml))

    # Always include the mention-only control as a negative runtime seed
    if CONTROL.is_file():
        key = rel(CONTROL)
        if key not in seen:
            seen.add(key)
            entries.append(
                {
                    "path": key,
                    "kind": "planted-mention-only-control",
                    "via": "AUD-0031-control",
                }
            )
    return entries


def parse_coverage_dir(cov_dir: Path) -> dict[str, dict]:
    """Map absolute file path -> {ranges_executed, functions_count, ...}."""
    lib_root = str(LIB.resolve())
    hits: dict[str, dict] = {}
    for f in cov_dir.glob("coverage-*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        result = data.get("result") or []
        for script in result:
            url = script.get("url") or ""
            # file:///path
            if url.startswith("file://"):
                path = url[len("file://") :]
            else:
                path = url
            if not path.startswith(lib_root):
                continue
            # count executed ranges (count > 0)
            executed = 0
            total = 0
            for fn in script.get("functions") or []:
                for rng in fn.get("ranges") or []:
                    total += 1
                    if (rng.get("count") or 0) > 0:
                        executed += 1
            prev = hits.get(path)
            if prev is None or executed > prev["ranges_executed"]:
                hits[path] = {
                    "path": path,
                    "ranges_total": total,
                    "ranges_executed": executed,
                    "source": rel(f),
                }
    return hits


def run_entry(entry: dict, cov_root: Path) -> dict:
    path = REPO / entry["path"]
    cov_dir = cov_root / entry["path"].replace("/", "__")
    if cov_dir.exists():
        shutil.rmtree(cov_dir, ignore_errors=True)
    cov_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["NODE_V8_COVERAGE"] = str(cov_dir)
    # Import/run the entry as ESM; do not execute package test runners.
    # Use dynamic import so side-effect-only modules still load.
    script = (
        "const p = process.argv[1]; "
        "import(p).then(() => { console.log('ENTRY_OK', p); })"
        ".catch((e) => { console.error('ENTRY_ERR', p, e && e.message); process.exitCode = 0; });"
    )
    try:
        r = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(path.resolve())],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired:
        out = "TIMEOUT"
        rc = 124
    except OSError as e:
        out = f"{type(e).__name__}: {e}"
        rc = 127
    cov = parse_coverage_dir(cov_dir)
    lib_hits = []
    for name in SALVAGE_FILES:
        abs_p = str((LIB / name).resolve())
        info = cov.get(abs_p)
        if info and info["ranges_executed"] > 0:
            lib_hits.append(
                {
                    "module": name,
                    "ranges_executed": info["ranges_executed"],
                    "ranges_total": info["ranges_total"],
                }
            )
    return {
        "entry": entry,
        "exit_code": rc,
        "output_tail": out[-800:],
        "tools_lib_modules_executed": lib_hits,
        "tools_lib_executed_count": len(lib_hits),
        "coverage_files": len(list(cov_dir.glob("coverage-*.json"))),
    }


def main() -> int:
    mods = [n for n in SALVAGE_FILES if (LIB / n).is_file()]
    if len(mods) != 6:
        print(f"FAILED:AUD-0031-probe2 expected 6 modules, found {len(mods)}")
        return 1

    entries = collect_entry_points()
    # Exclude planted control from the "production" entry set for headline counts
    prod_entries = [e for e in entries if e["kind"] != "planted-mention-only-control"]
    control_entries = [
        e for e in entries if e["kind"] == "planted-mention-only-control"
    ]

    cov_root = Path(tempfile.mkdtemp(prefix="aud0031-cov-"))
    try:
        results = []
        for e in prod_entries:
            results.append(run_entry(e, cov_root))
        control_results = [run_entry(e, cov_root) for e in control_entries]
    finally:
        shutil.rmtree(cov_root, ignore_errors=True)

    executed_modules: dict[str, list[dict]] = {m: [] for m in mods}
    for row in results:
        for hit in row["tools_lib_modules_executed"]:
            executed_modules[hit["module"]].append(
                {
                    "entry": row["entry"]["path"],
                    "kind": row["entry"]["kind"],
                    "ranges_executed": hit["ranges_executed"],
                }
            )

    modules_executed = sorted(m for m, xs in executed_modules.items() if xs)
    modules_never_executed = sorted(m for m, xs in executed_modules.items() if not xs)

    control_executed = []
    for row in control_results:
        control_executed.extend(row["tools_lib_modules_executed"])
    mention_control_runtime_ok = len(control_executed) == 0

    # Independence vs probe1: probe2 measures execution, not textual import.
    result = {
        "unit": "AUD-0031",
        "probe": 2,
        "method": "node-v8-coverage-non-test-entry-points",
        "salvage_modules": mods,
        "entry_point_count": len(prod_entries),
        "entry_points": prod_entries,
        "runs": [
            {
                "path": r["entry"]["path"],
                "kind": r["entry"]["kind"],
                "exit_code": r["exit_code"],
                "tools_lib_executed_count": r["tools_lib_executed_count"],
                "tools_lib_modules_executed": r["tools_lib_modules_executed"],
                "coverage_files": r["coverage_files"],
                "output_tail": r["output_tail"],
            }
            for r in results
        ],
        "modules_executed_by_non_test_entries": modules_executed,
        "modules_never_executed_by_non_test_entries": modules_never_executed,
        "modules_executed_count": len(modules_executed),
        "modules_never_executed_count": len(modules_never_executed),
        "executed_detail": executed_modules,
        "planted_mention_control": {
            "path": rel(CONTROL),
            "tools_lib_modules_executed": control_executed,
            "ok": mention_control_runtime_ok,
        },
        "ok": mention_control_runtime_ok and len(mods) == 6,
    }

    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0031 NAMED PROBE 2: runtime coverage trace of non-test entry points for tools/lib modules",
        "catalog_verbatim=Probe 2: a runtime coverage trace of the non-test entry points recording which tools/lib modules are actually executed - an import is not a use.",
        "unit=AUD-0031",
        f"salvage_module_count={len(mods)}",
        f"entry_point_count={len(prod_entries)}",
        f"modules_executed_count={len(modules_executed)}",
        f"modules_executed={modules_executed}",
        f"modules_never_executed_count={len(modules_never_executed)}",
        f"modules_never_executed={modules_never_executed}",
        f"planted_mention_control_runtime_ok={mention_control_runtime_ok}",
        f"planted_mention_control_executed={control_executed}",
        "ENTRY-RUNS-BEGIN",
    ]
    for r in results:
        mods_hit = ",".join(h["module"] for h in r["tools_lib_modules_executed"]) or "-"
        lines.append(
            f"RUN\t{r['entry']['path']}\tkind={r['entry']['kind']}\texit={r['exit_code']}\t"
            f"lib_executed={r['tools_lib_executed_count']}\tmodules={mods_hit}\tcov_files={r['coverage_files']}"
        )
    lines.append("ENTRY-RUNS-END")
    if result["ok"]:
        lines.append("SUCCESS:AUD-0031-probe2")
    else:
        lines.append("FAILED:AUD-0031-probe2")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
