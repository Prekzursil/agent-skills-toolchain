#!/usr/bin/env python3
"""AUD-0031 Probe 1: reverse-reference search over the JS import graph.

Excludes test modules. Use-vs-mention safe: comments/docstrings stripped before
import-spec extraction, then asserted via the planted mention-only fixture.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-reverse-refs.json"
OUT_RAW = PROBE / "probe1-reverse-refs.raw.txt"
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
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "_r2_tmp",
}

JS_SUFFIXES = {".mjs", ".js", ".cjs", ".ts", ".tsx"}

FROM_RE = re.compile(
    r"""(?xs)
    \b(?:import|export)\s+(?:type\s+)?
    (?:(?!;)[\s\S]{0,500}?)
    \bfrom\s+['"]([^'"]+)['"]
    """
)
SIDE_EFFECT_IMPORT_RE = re.compile(r"""\bimport\s+['"]([^'"]+)['"]""")
DYNAMIC_IMPORT_RE = re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)""")
REQUIRE_RE = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def is_test_path(path: Path) -> bool:
    parts = {x.lower() for x in path.parts}
    name = path.name.lower()
    if "tests" in parts or "test" in parts or "__tests__" in parts:
        return True
    if name.endswith((".test.mjs", ".test.js", ".spec.mjs", ".spec.js")):
        return True
    if name.startswith("test_") or name.startswith("test-"):
        return True
    # workspace package test helpers
    if path.parent.name in {"test", "tests", "__tests__"}:
        return True
    return False


def strip_js_comments(src: str) -> str:
    """Replace // and /* */ comments with spaces; preserve string/template text
    so real import('...') / from '...' specs remain matchable. Mentions that
    live only inside comments are removed (use-vs-mention control)."""
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            out.append(" ")
            out.append(" ")
            i += 2
            while i < n - 1 and not (src[i] == "*" and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i < n - 1:
                out.append(" ")
                out.append(" ")
                i += 2
            continue
        if ch in {'"', "'"}:
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = src[i]
                out.append(c)
                i += 1
                if c == "\\" and i < n:
                    out.append(src[i])
                    i += 1
                    continue
                if c == quote:
                    break
            continue
        if ch == "`":
            out.append(ch)
            i += 1
            while i < n:
                c = src[i]
                out.append(c)
                i += 1
                if c == "\\" and i < n:
                    out.append(src[i])
                    i += 1
                    continue
                if c == "`":
                    break
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_specs(src: str) -> list[str]:
    cleaned = strip_js_comments(src)
    specs: list[str] = []
    for rx in (FROM_RE, SIDE_EFFECT_IMPORT_RE, DYNAMIC_IMPORT_RE, REQUIRE_RE):
        for m in rx.finditer(cleaned):
            specs.append(m.group(1))
    seen: set[str] = set()
    out: list[str] = []
    for s in specs:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def resolve_spec(importer: Path, spec: str) -> Path | None:
    if spec.startswith("@prekzursil/tools-lib"):
        rest = spec[len("@prekzursil/tools-lib") :].lstrip("/")
        if not rest:
            return None
        # package exports are "./security" etc.
        cand = LIB / f"{rest}.mjs"
        if cand.is_file():
            return cand.resolve()
        cand2 = LIB / rest
        if cand2.is_file():
            return cand2.resolve()
        return None
    if "tools/lib/" in spec.replace("\\", "/"):
        # path-like absolute-from-repo or relative that includes tools/lib/
        norm = spec.replace("\\", "/")
        idx = norm.find("tools/lib/")
        tail = norm[idx + len("tools/lib/") :]
        cand = LIB / tail
        if cand.is_file():
            return cand.resolve()
        if not tail.endswith(".mjs"):
            cand = LIB / f"{tail}.mjs"
            if cand.is_file():
                return cand.resolve()
    if spec.startswith("."):
        base = (importer.parent / spec).resolve()
        candidates = [base]
        if not base.suffix:
            candidates.extend(
                [
                    Path(str(base) + ".mjs"),
                    Path(str(base) + ".js"),
                    base / "index.mjs",
                    base / "index.js",
                ]
            )
        lib_root = LIB.resolve()
        for c in candidates:
            try:
                if not c.is_file():
                    continue
                resolved = c.resolve()
                if resolved.parent == lib_root or lib_root in resolved.parents:
                    return resolved
            except OSError:
                continue
    return None


def salvage_modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for name in SALVAGE_FILES:
        p = LIB / name
        if p.is_file():
            out[name] = p.resolve()
    return out


def iter_js_files() -> list[Path]:
    files: list[Path] = []
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in JS_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


def main() -> int:
    mods = salvage_modules()
    if len(mods) != 6:
        print(f"FAILED:AUD-0031-probe1 expected 6 salvage modules, found {len(mods)}")
        return 1

    # Ensure planted control exists
    CONTROL.parent.mkdir(parents=True, exist_ok=True)
    if not CONTROL.is_file():
        print(f"FAILED:AUD-0031-probe1 missing planted control {CONTROL}")
        return 1

    control_text = CONTROL.read_text(encoding="utf-8")
    # Raw text MUST mention modules (so the control is meaningful)
    raw_mentions = sum(
        1
        for m in SALVAGE_FILES
        if m in control_text or f"tools-lib/{m.replace('.mjs', '')}" in control_text
    )
    control_specs_after_strip = extract_specs(control_text)
    control_resolved = []
    for spec in control_specs_after_strip:
        r = resolve_spec(CONTROL, spec)
        if r is not None:
            control_resolved.append(rel(r))

    consumers: dict[str, list[dict]] = {m: [] for m in mods}
    mentions_only_hits: list[dict] = []
    files_scanned = 0
    import_sites = 0
    test_import_sites = 0

    for path in iter_js_files():
        # skip the salvage modules themselves as "consumers"
        try:
            if path.resolve() in mods.values():
                continue
        except OSError:
            continue
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        specs = extract_specs(text)
        if not specs:
            # also check raw mention of tools/lib for diagnostics (not counted)
            if "tools/lib/" in text or "@prekzursil/tools-lib" in text:
                if path.resolve() == CONTROL.resolve():
                    mentions_only_hits.append(
                        {
                            "path": rel(path),
                            "kind": "planted-mention-only",
                            "raw_mentions": raw_mentions,
                        }
                    )
            continue
        is_test = is_test_path(path)
        for spec in specs:
            resolved = resolve_spec(path, spec)
            if resolved is None:
                continue
            for mod_name, mod_path in mods.items():
                if resolved == mod_path:
                    import_sites += 1
                    if is_test:
                        test_import_sites += 1
                    else:
                        consumers[mod_name].append(
                            {
                                "path": rel(path),
                                "spec": spec,
                                "is_test": False,
                            }
                        )
                    break

    # Deduplicate consumers per module by path
    for mod_name in consumers:
        seen = set()
        uniq = []
        for c in consumers[mod_name]:
            if c["path"] in seen:
                continue
            seen.add(c["path"])
            uniq.append(c)
        consumers[mod_name] = uniq

    # AUD-0030 import graph note (Python-only; JS salvage not covered)
    aud30 = REPO / "command-center" / "audit" / "AUD-0030-import-graph-cycles.json"
    aud30_note = {
        "path": rel(aud30) if aud30.is_file() else None,
        "exists": aud30.is_file(),
        "covers_tools_lib_js": False,
        "reason": (
            "AUD-0030 scopes tools/**/*.py; tools/lib salvage is Node/ESM (.mjs). "
            "Probe 1 therefore builds a JS reverse-ref graph independently."
        ),
    }

    zero_consumer_modules = sorted(m for m, cs in consumers.items() if len(cs) == 0)
    modules_with_consumers = sorted(m for m, cs in consumers.items() if len(cs) > 0)
    total_non_test_consumers = sum(len(cs) for cs in consumers.values())

    # use-vs-mention control: planted file must produce ZERO resolved import edges
    mention_control_ok = (
        raw_mentions >= 6
        and len(control_resolved) == 0
        and CONTROL.name
        not in {c["path"].split("/")[-1] for cs in consumers.values() for c in cs}
    )
    # stronger: no consumer path equals the control file
    control_rel = rel(CONTROL)
    control_counted = any(
        c["path"] == control_rel for cs in consumers.values() for c in cs
    )
    mention_control_ok = mention_control_ok and not control_counted

    result = {
        "unit": "AUD-0031",
        "probe": 1,
        "method": "js-import-reverse-ref-comment-stripped",
        "salvage_modules": sorted(mods),
        "salvage_module_count": len(mods),
        "files_scanned": files_scanned,
        "import_sites_to_salvage": import_sites,
        "test_import_sites": test_import_sites,
        "non_test_consumer_edges": total_non_test_consumers,
        "modules_with_non_test_consumers": modules_with_consumers,
        "modules_with_zero_non_test_consumers": zero_consumer_modules,
        "zero_non_test_consumer_count": len(zero_consumer_modules),
        "consumers_by_module": {m: consumers[m] for m in sorted(consumers)},
        "aud0030_import_graph": aud30_note,
        "planted_mention_control": {
            "path": control_rel,
            "raw_text_mentions_salvage_modules": raw_mentions,
            "resolved_import_edges_after_strip": control_resolved,
            "counted_as_consumer": control_counted,
            "ok": mention_control_ok,
        },
        "ok": mention_control_ok and len(mods) == 6,
    }

    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0031 NAMED PROBE 1: reverse-reference search over the import graph, excluding test modules",
        "catalog_verbatim=Probe 1: reverse-reference search over the import graph, excluding test modules.",
        "unit=AUD-0031",
        f"salvage_module_count={len(mods)}",
        f"salvage_modules={sorted(mods)}",
        f"files_scanned={files_scanned}",
        f"import_sites_to_salvage={import_sites}",
        f"test_import_sites={test_import_sites}",
        f"non_test_consumer_edges={total_non_test_consumers}",
        f"modules_with_non_test_consumers={modules_with_consumers}",
        f"modules_with_zero_non_test_consumers={zero_consumer_modules}",
        f"zero_non_test_consumer_count={len(zero_consumer_modules)}",
        f"aud0030_covers_tools_lib_js={aud30_note['covers_tools_lib_js']}",
        f"planted_mention_raw_mentions={raw_mentions}",
        f"planted_mention_resolved_edges={control_resolved}",
        f"planted_mention_counted_as_consumer={control_counted}",
        f"planted_mention_control_ok={mention_control_ok}",
        "CONSUMERS-BY-MODULE-BEGIN",
    ]
    for m in sorted(consumers):
        paths = [c["path"] for c in consumers[m]] or ["(none)"]
        lines.append(f"MODULE\t{m}\tnon_test_consumers={len(consumers[m])}\t{paths}")
    lines.append("CONSUMERS-BY-MODULE-END")
    if mention_control_ok and result["ok"]:
        lines.append("SUCCESS:AUD-0031-probe1")
    else:
        lines.append("FAILED:AUD-0031-probe1")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
