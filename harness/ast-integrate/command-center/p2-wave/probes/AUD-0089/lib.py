"""Shared discovery and dual-analyzer helpers for AUD-0089."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VENDOR = HERE / "vendor"
FIXTURE = HERE / "fixtures" / "planted_ccn_control.py"
PINNED_PATH = HERE / "PINNED.json"
CCN_THRESHOLD = 15
PINNED_LIZARD = "1.17.10"
PINNED_RADON = "6.0.1"

SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
    "venv",
}

if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))


def load_pins() -> dict[str, Any]:
    return json.loads(PINNED_PATH.read_text(encoding="utf-8"))


def ensure_vendor() -> tuple[str, str]:
    import lizard
    import radon

    liz_ver = str(getattr(lizard, "version", ""))
    rad_ver = str(getattr(radon, "__version__", ""))
    if liz_ver != PINNED_LIZARD:
        raise RuntimeError(f"lizard version {liz_ver!r} != pinned {PINNED_LIZARD}")
    if rad_ver != PINNED_RADON:
        raise RuntimeError(f"radon version {rad_ver!r} != pinned {PINNED_RADON}")
    return liz_ver, rad_ver


def is_probe_tree(path: Path) -> bool:
    parts = path.parts
    try:
        idx = parts.index("p2-wave")
    except ValueError:
        return False
    return "probes" in parts[idx:]


def discover_python(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if is_probe_tree(path):
            continue
        files.append(path)
    return sorted(files)


def rel_of(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _unqual(name: str) -> str:
    return name.split(".")[-1]


def lizard_functions(paths: list[Path]) -> list[dict[str, Any]]:
    import lizard

    rows: list[dict[str, Any]] = []
    for path in paths:
        info = lizard.analyze_file(str(path))
        rel = rel_of(path)
        for func in info.function_list:
            name = str(func.name)
            rows.append(
                {
                    "analyzer": "lizard",
                    "ccn": int(func.cyclomatic_complexity),
                    "end_line": int(getattr(func, "end_line", 0) or 0),
                    "file": rel,
                    "id": f"{rel}::{_unqual(name)}",
                    "name": name,
                    "nloc": int(getattr(func, "nloc", 0) or 0),
                    "parameter_count": int(getattr(func, "parameter_count", 0) or 0),
                    "start_line": int(func.start_line),
                    "unqualified_name": _unqual(name),
                }
            )
    rows.sort(key=lambda r: (-r["ccn"], r["file"], r["start_line"], r["name"]))
    return rows


def radon_functions(paths: list[Path]) -> list[dict[str, Any]]:
    from radon.complexity import cc_visit
    from radon.visitors import Function

    rows: list[dict[str, Any]] = []
    for path in paths:
        rel = rel_of(path)
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            blocks = cc_visit(src)
        except SyntaxError as exc:
            rows.append(
                {
                    "analyzer": "radon",
                    "ccn": 0,
                    "end_line": 0,
                    "file": rel,
                    "id": f"{rel}::<syntax-error>",
                    "name": f"<syntax-error:{exc.msg}>",
                    "nloc": 0,
                    "parameter_count": 0,
                    "start_line": int(getattr(exc, "lineno", 0) or 0),
                    "unqualified_name": "<syntax-error>",
                    "parse_error": True,
                }
            )
            continue
        for block in blocks:
            if not isinstance(block, Function):
                continue
            name = str(block.fullname or block.name)
            rows.append(
                {
                    "analyzer": "radon",
                    "ccn": int(block.complexity),
                    "end_line": int(getattr(block, "endline", 0) or 0),
                    "file": rel,
                    "id": f"{rel}::{_unqual(name)}",
                    "name": name,
                    "nloc": 0,
                    "parameter_count": 0,
                    "start_line": int(block.lineno),
                    "unqualified_name": _unqual(name),
                }
            )
    rows.sort(key=lambda r: (-r["ccn"], r["file"], r["start_line"], r["name"]))
    return rows


def histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {
        "1-5": 0,
        "6-10": 0,
        "11-15": 0,
        "16-20": 0,
        "21-30": 0,
        "31-40": 0,
        "41+": 0,
    }
    for row in rows:
        ccn = int(row["ccn"])
        if ccn <= 5:
            buckets["1-5"] += 1
        elif ccn <= 10:
            buckets["6-10"] += 1
        elif ccn <= 15:
            buckets["11-15"] += 1
        elif ccn <= 20:
            buckets["16-20"] += 1
        elif ccn <= 30:
            buckets["21-30"] += 1
        elif ccn <= 40:
            buckets["31-40"] += 1
        else:
            buckets["41+"] += 1
    return buckets


def per_module(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[int]] = {}
    for row in rows:
        grouped.setdefault(str(row["file"]), []).append(int(row["ccn"]))
    out: list[dict[str, Any]] = []
    for file_rel, ccns in sorted(grouped.items()):
        over = [c for c in ccns if c > CCN_THRESHOLD]
        out.append(
            {
                "file": file_rel,
                "function_count": len(ccns),
                "max_ccn": max(ccns) if ccns else 0,
                "mean_ccn": round(sum(ccns) / len(ccns), 3) if ccns else 0.0,
                "n_over_ccn_15": len(over),
            }
        )
    out.sort(key=lambda r: (-r["max_ccn"], -r["n_over_ccn_15"], r["file"]))
    return out


def over_threshold(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if int(r["ccn"]) > CCN_THRESHOLD]


def top_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    clean = [r for r in rows if not r.get("parse_error")]
    return clean[0] if clean else None


def ranking_comparison(
    lizard_rows: list[dict[str, Any]], radon_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    liz_top = top_row(lizard_rows)
    rad_top = top_row(radon_rows)
    agree = (
        liz_top is not None
        and rad_top is not None
        and liz_top["file"] == rad_top["file"]
        and liz_top["unqualified_name"] == rad_top["unqualified_name"]
    )
    liz_over = {r["id"] for r in over_threshold(lizard_rows)}
    rad_over = {r["id"] for r in over_threshold(radon_rows)}
    return {
        "agree_on_top_function": agree,
        "ccn_threshold": CCN_THRESHOLD,
        "headline_most_complex": (
            {
                "file": liz_top["file"],
                "name": liz_top["name"],
                "lizard_ccn": liz_top["ccn"],
                "radon_ccn": rad_top["ccn"] if rad_top else None,
            }
            if agree and liz_top is not None and rad_top is not None
            else None
        ),
        "lizard_only_over_15": sorted(liz_over - rad_over),
        "lizard_over_15_count": len(liz_over),
        "lizard_top": liz_top,
        "radon_only_over_15": sorted(rad_over - liz_over),
        "radon_over_15_count": len(rad_over),
        "radon_top": rad_top,
        "reason": (
            "both analyzers rank the same function as most complex"
            if agree
            else "analyzers disagree on the top entry; no single most-complex function is reported"
        ),
    }


def fixture_control() -> dict[str, Any]:
    paths = [FIXTURE]
    liz = lizard_functions(paths)
    rad = radon_functions(paths)
    liz_top = top_row(liz)
    rad_top = top_row(rad)
    liz_high = next(r for r in liz if r["unqualified_name"] == "planted_high_ccn")
    liz_low = next(r for r in liz if r["unqualified_name"] == "planted_low_ccn")
    rad_high = next(r for r in rad if r["unqualified_name"] == "planted_high_ccn")
    rad_low = next(r for r in rad if r["unqualified_name"] == "planted_low_ccn")
    both_rank_high = (
        liz_top is not None
        and rad_top is not None
        and liz_top["unqualified_name"] == "planted_high_ccn"
        and rad_top["unqualified_name"] == "planted_high_ccn"
    )
    high_exceeds = liz_high["ccn"] > CCN_THRESHOLD and rad_high["ccn"] > CCN_THRESHOLD
    low_silent = liz_low["ccn"] <= CCN_THRESHOLD and rad_low["ccn"] <= CCN_THRESHOLD
    return {
        "fixture": rel_of(FIXTURE),
        "fired_on_bad_state": both_rank_high and high_exceeds,
        "lizard": {"high": liz_high, "low": liz_low, "top": liz_top},
        "radon": {"high": rad_high, "low": rad_low, "top": rad_top},
        "silent_on_good_state": low_silent,
    }


def dump(path: Path, doc: Any) -> None:
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def other_language_census(repo: Path | None = None) -> dict[str, int]:
    root = repo or REPO
    counts: Counter[str] = Counter()
    for ext in (".js", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp"):
        for path in root.rglob(f"*{ext}"):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if is_probe_tree(path):
                continue
            counts[ext] += 1
    return dict(sorted(counts.items()))
