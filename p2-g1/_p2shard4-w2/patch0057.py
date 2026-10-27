from pathlib import Path
HERE = Path("command-center/p2-wave/probes/AUD-0057")

# ---- 1. census.py: sha helper + pinned re-derivation -------------------
c = (HERE / "census.py").read_text(encoding="utf-8")
anchor = "def run_census() -> dict[str, Any]:"
addition = '''def sha256_norm(path: Path) -> str:
    import hashlib

    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def census_pinned(paths: list[Path]) -> dict[str, Any]:
    """Mechanically different re-derivation over an EXPLICIT file list.

    shard4-w2 pivot 2026-10-25 (unit retry policy, AGENTS 4b): after two
    transient-tree strikes on the whole-tree live recount (concurrent wave-2
    shards write into the counted domain between emit and probe), probe1 pins
    the artifact's counted file set by CRLF-normalized sha256 and recomputes
    the census over exactly that set. Unchanged files must re-derive exactly;
    files another writer touched are disclosed as drift, never silently
    refolded into a rerun.
    """
    fixture_root = HERE / "fixtures"
    product: list[Path] = []
    tests: list[Path] = []
    for path in paths:
        if is_test_path(path):
            tests.append(path)
        else:
            product.append(path)
    params: list[DefaultParam] = []
    parse_errors: list[str] = []
    tools_root = REPO / "tools"
    for path in product:
        if parse_ast(path) is None:
            parse_errors.append(rel(path))
            continue
        root = fixture_root if "fixtures" in path.parts else tools_root
        params.extend(collect_functions(path, root))
    calls: list[CallSite] = []
    for path in tests:
        calls.extend(collect_calls(path))
    rows = classify(params, calls)
    per_file: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = per_file.setdefault(
            row["file"], {"n_defaults": 0, "n_exercised": 0}
        )
        entry["n_defaults"] += 1
        if row["status"] == "exercised":
            entry["n_exercised"] += 1
    return {
        "n_defaults": len(rows),
        "n_exercised": sum(1 for r in rows if r["status"] == "exercised"),
        "n_unexercised": sum(1 for r in rows if r["status"] == "unexercised"),
        "n_no_test_calls": sum(1 for r in rows if r["status"] == "no-test-calls"),
        "parse_errors": parse_errors,
        "per_file": per_file,
        "rows": [public_row(r) for r in rows],
    }


''' + anchor
assert anchor in c, "run_census anchor missing"
c = c.replace(anchor, addition, 1)
# extend run_census return with file_hashes + per_file
ret_anchor = '''        "unexercised": unexercised,
        "no_test_calls": no_calls,
        "planted": planted,
        "require_complete": require_complete,
        "all_rows": rows,
    }'''
ret_new = '''        "unexercised": unexercised,
        "no_test_calls": no_calls,
        "planted": planted,
        "require_complete": require_complete,
        "all_rows": rows,
        "per_file": {
            r["file"]: pf
            for r, pf in (
                (
                    row,
                    per_file_entry(row["file"], rows),
                )
            )
            for row in []
        } or _per_file(rows),
        "file_hashes": {
            rel(p): sha256_norm(p) for p in product + tests
        },
    }


def _per_file(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = out.setdefault(row["file"], {"n_defaults": 0, "n_exercised": 0})
        entry["n_defaults"] += 1
        if row["status"] == "exercised":
            entry["n_exercised"] += 1
    return out'''
assert ret_anchor in c, "return anchor missing"
c = c.replace(ret_anchor, ret_new, 1)
(HERE / "census.py").write_text(c, encoding="utf-8")
print("census.py patched")
