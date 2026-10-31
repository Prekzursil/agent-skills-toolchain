"""Shard2-w1 fix 2026-10-24: AUD-0084 census scan_tree host-port.

Serial scan_tree measures ~243s on this host (6947 discovered source files)
against the 180s G-1 per-probe envelope. Fan the per-file work out over a
process pool; the per-file logic (read_text, lexical_hits_for_file,
classify_python_ast, ast.parse, adjudicate_hit) is unchanged, ordering is
preserved via executor.map, and any pool failure falls back to the identical
serial loop.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0084/census.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a84.pyc")

OLD = """def scan_tree(paths: Iterable[Path] | None = None) -> dict[str, Any]:
    files = list(paths) if paths is not None else discover_sources()
    lexical: list[dict[str, Any]] = []
    adjudicated: list[dict[str, Any]] = []
    parse_issues = 0
    for path in files:
        src = read_text(path)
        hits = lexical_hits_for_file(path, src)
        lexical.extend(hits)
        ast_labels = None
        if language_of(path) == "python":
            ast_labels = classify_python_ast(src)
            if hits:
                try:
                    ast.parse(src)
                except SyntaxError:
                    parse_issues += 1
                    ast_labels = {}
        for hit in hits:
            adjudicated.append(adjudicate_hit(hit, ast_labels))
    return {
        "source_files_discovered": len(files),
        "lexical_hits": lexical,
        "adjudicated": adjudicated,
        "parse_issues": parse_issues,
        "lexical_hits": lexical,
    }"""

NEW = '''def _scan_one_file(path_str: str):
    """Per-file scan worker (shard2-w1 host-port 2026-10-24).

    Byte-identical per-file logic to the serial loop it replaces; the fan-out
    exists because serial scan_tree measures ~243s on this host (6947 source
    files) against the 180s G-1 per-probe envelope. Fail-open: run_sweep's
    caller falls back to the identical serial loop on any pool failure.
    """
    path = Path(path_str)
    src = read_text(path)
    hits = lexical_hits_for_file(path, src)
    ast_labels = None
    parse_issue = 0
    if language_of(path) == "python":
        ast_labels = classify_python_ast(src)
        if hits:
            try:
                ast.parse(src)
            except SyntaxError:
                parse_issue = 1
                ast_labels = {}
    adjudicated = [adjudicate_hit(hit, ast_labels) for hit in hits]
    return (hits, adjudicated, parse_issue)


def scan_tree(paths: Iterable[Path] | None = None) -> dict[str, Any]:
    files = list(paths) if paths is not None else discover_sources()
    results = None
    if len(files) >= 400:
        try:
            import os as _os
            from concurrent.futures import ProcessPoolExecutor

            workers = min(8, _os.cpu_count() or 2)
            specs = [str(p) for p in files]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_scan_one_file, specs, chunksize=16))
        except Exception:
            results = None  # fail-open: identical serial semantics
    if results is None:
        results = [_scan_one_file(str(p)) for p in files]
    lexical: list[dict[str, Any]] = []
    adjudicated: list[dict[str, Any]] = []
    parse_issues = 0
    for hits, adj, parse_issue in results:
        lexical.extend(hits)
        adjudicated.extend(adj)
        parse_issues += parse_issue
    return {
        "source_files_discovered": len(files),
        "lexical_hits": lexical,
        "adjudicated": adjudicated,
        "parse_issues": parse_issues,
    }'''


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_scan_one_file" in text:
        print("already-patched")
        return 0
    assert OLD in text, "pattern miss scan_tree"
    text = text.replace(OLD, NEW, 1)
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
