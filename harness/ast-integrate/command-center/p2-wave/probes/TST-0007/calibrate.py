#!/usr/bin/env python3
"""Calibrate C3 meaningful-minimum-size from real receipt sizes.

The ledger guessed DEFAULT_MIN_BYTES (1024, then 512). This module measures
the live worktree corpus and derives the default as the 0th percentile
(observed minimum) of receipt-class files — a named percentile of a measured
distribution, not a round constant.

Histogram n>=200 is satisfied by the receipt-class set plus additional
on-disk JSON unit artifacts (manifests and manifest-registered JSON), each
row labelled by class so supporting JSON cannot silently become the floor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
REDUCER = REPO / "lib" / "completion_reducer.py"

RECEIPT_CLASSES = frozenset(
    {
        "catalog-output",
        "receipts-dir",
        "confirmation",
        "phase-output",
        "research-output",
        "subagent-return",
    }
)

HISTOGRAM_EDGES = (
    0,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
    262144,
    10**12,
)
HISTOGRAM_LABELS = (
    "<64",
    "64-127",
    "128-255",
    "256-511",
    "512-1023",
    "1024-2047",
    "2048-4095",
    "4096-8191",
    "8192-16383",
    "16384-32767",
    "32768-65535",
    "65536-131071",
    "131072-262143",
    ">=262144",
)

SKIP_PARTS = frozenset({"node_modules", "runtime", "published", "vendor", ".git"})
SKIP_NAMES = frozenset(
    {
        "WORK-UNIT-CATALOG.json",
        "package-lock.json",
        "CLAIM-REGISTRY.json",
    }
)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _is_skipped(path: Path) -> bool:
    if path.name in SKIP_NAMES:
        return True
    return any(part in SKIP_PARTS for part in path.parts)


def _add(rows: list[dict[str, Any]], seen: set[Path], path: Path, klass: str) -> None:
    if not path.is_file() or _is_skipped(path):
        return
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    rows.append(
        {
            "path": _rel(path),
            "bytes": path.stat().st_size,
            "class": klass,
        }
    )


def _load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def collect_receipt_class(repo: Path | None = None) -> list[dict[str, Any]]:
    """Unit-output receipts the C3 floor is meant to protect."""
    root = repo or REPO
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()

    catalog = _load_catalog()
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if rel:
            _add(rows, seen, root / rel, "catalog-output")

    for path in sorted((root / "command-center" / "receipts").glob("*.json")):
        _add(rows, seen, path, "receipts-dir")
    for path in sorted((root / "command-center" / "confirmation").glob("*.json")):
        _add(rows, seen, path, "confirmation")
    for path in sorted((root / "command-center" / "phase3").rglob("*.json")):
        _add(rows, seen, path, "phase-output")
    phase4 = root / "command-center" / "phase4"
    if phase4.is_dir():
        for path in sorted(phase4.rglob("*.json")):
            _add(rows, seen, path, "phase-output")
    research = root / "command-center" / "research"
    if research.is_dir():
        for path in sorted(research.rglob("*.json")):
            _add(rows, seen, path, "research-output")
    probes = root / "command-center" / "p2-wave" / "probes"
    if probes.is_dir():
        for path in sorted(probes.glob("*/SUBAGENT-RETURN.json")):
            _add(rows, seen, path, "subagent-return")
    rows.sort(key=lambda r: (r["path"], r["class"]))
    return rows


def _manifest_json_candidates(root: Path) -> list[tuple[Path, str]]:
    probes = root / "command-center" / "p2-wave" / "probes"
    out: list[tuple[Path, str]] = []
    if not probes.is_dir():
        return out
    for man in sorted(probes.glob("*/UNIT-ARTIFACT-MANIFEST.json")):
        try:
            doc = json.loads(man.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for art in doc.get("artifacts") or []:
            if not isinstance(art, dict):
                continue
            rel = str(art.get("path") or "").replace("\\", "/")
            if not rel.endswith(".json"):
                continue
            path = root / rel
            if not path.is_file():
                continue
            parts = Path(rel).parts
            if "fixtures" in parts:
                klass = "manifest-json-fixture"
            else:
                klass = "manifest-json"
            out.append((path, klass))
    out.sort(key=lambda item: _rel(item[0]))
    return out


def collect_histogram_corpus(repo: Path | None = None) -> list[dict[str, Any]]:
    """Receipt-class rows plus enough real JSON artifacts to reach n>=200."""
    root = repo or REPO
    rows = collect_receipt_class(root)
    seen = {(root / r["path"]).resolve() for r in rows}

    probes = root / "command-center" / "p2-wave" / "probes"
    if probes.is_dir():
        for path in sorted(probes.glob("*/UNIT-ARTIFACT-MANIFEST.json")):
            _add(rows, seen, path, "unit-artifact-manifest")

    extras = _manifest_json_candidates(root)
    # Prefer non-fixture JSON until n>=200, then fixtures if still short.
    extras.sort(key=lambda item: (0 if item[1] == "manifest-json" else 1, _rel(item[0])))
    for path, klass in extras:
        if len(rows) >= 200:
            break
        _add(rows, seen, path, klass)
    # If still short, take the rest (honest: labelled, not invented).
    if len(rows) < 200:
        for path, klass in extras:
            _add(rows, seen, path, klass)
    rows.sort(key=lambda r: (r["path"], r["class"]))
    return rows


def percentile(values: list[int], p: float) -> float:
    """Linear-interpolation percentile. p in [0, 100]."""
    if not values:
        raise ValueError("percentile of empty sample")
    if p < 0 or p > 100:
        raise ValueError(f"percentile {p} out of range")
    xs = sorted(int(v) for v in values)
    if len(xs) == 1:
        return float(xs[0])
    k = (p / 100.0) * (len(xs) - 1)
    lo = int(k)
    hi = min(len(xs) - 1, lo + 1)
    if lo == hi:
        return float(xs[lo])
    frac = k - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def histogram(values: list[int]) -> list[dict[str, Any]]:
    counts = [0] * len(HISTOGRAM_LABELS)
    for n in values:
        placed = False
        for i in range(len(HISTOGRAM_EDGES) - 1):
            if HISTOGRAM_EDGES[i] <= n < HISTOGRAM_EDGES[i + 1]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return [
        {
            "bucket": HISTOGRAM_LABELS[i],
            "lo": HISTOGRAM_EDGES[i],
            "hi": HISTOGRAM_EDGES[i + 1] - 1 if i < len(HISTOGRAM_LABELS) - 1 else None,
            "count": counts[i],
        }
        for i in range(len(HISTOGRAM_LABELS))
    ]


def derive_threshold(receipt_sizes: list[int]) -> dict[str, Any]:
    """Default = 0th percentile (observed minimum) of receipt-class sizes.

    Every measured real receipt meets this floor. Empty/stub files below the
    observed minimum fail. This is a named percentile of a measured sample,
    not 512/1024/128 guessed from habit.
    """
    if not receipt_sizes:
        raise ValueError("no receipt-class sizes")
    sizes = sorted(int(v) for v in receipt_sizes)
    p0 = int(sizes[0])
    return {
        "percentile": 0,
        "percentile_name": "p0-observed-minimum",
        "threshold": p0,
        "rule": (
            "MIN_BYTES_DEFAULT is the 0th percentile (min) of live "
            "receipt-class file sizes"
        ),
        "observed_min": sizes[0],
        "observed_max": sizes[-1],
        "percentiles": {
            "p0": float(sizes[0]),
            "p1": percentile(sizes, 1),
            "p5": percentile(sizes, 5),
            "p10": percentile(sizes, 10),
            "p25": percentile(sizes, 25),
            "p50": percentile(sizes, 50),
            "p75": percentile(sizes, 75),
            "p90": percentile(sizes, 90),
            "p95": percentile(sizes, 95),
            "p100": float(sizes[-1]),
        },
        "guessed_constants_rejected": [128, 512, 1024],
    }


def live_default_from_source(path: Path | None = None) -> int | None:
    text = (path or REDUCER).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("MIN_BYTES_DEFAULT"):
            _, _, rest = stripped.partition("=")
            token = rest.split("#", 1)[0].strip()
            try:
                return int(token)
            except ValueError:
                return None
    return None


def class_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        klass = str(row.get("class") or "unknown")
        out[klass] = out.get(klass, 0) + 1
    return dict(sorted(out.items()))


def run(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    receipt_rows = collect_receipt_class(root)
    hist_rows = collect_histogram_corpus(root)
    receipt_sizes = [int(r["bytes"]) for r in receipt_rows]
    hist_sizes = [int(r["bytes"]) for r in hist_rows]
    derived = derive_threshold(receipt_sizes)
    source_default = live_default_from_source(root / "lib" / "completion_reducer.py")
    return {
        "n_receipt_class": len(receipt_rows),
        "n_histogram": len(hist_rows),
        "n_required": 200,
        "histogram_meets_200": len(hist_rows) >= 200,
        "receipt_class_counts": class_counts(receipt_rows),
        "histogram_class_counts": class_counts(hist_rows),
        "receipt_rows": receipt_rows,
        "histogram_rows": hist_rows,
        "histogram": histogram(hist_sizes),
        "receipt_histogram": histogram(receipt_sizes),
        "derivation": derived,
        "threshold": derived["threshold"],
        "percentile": derived["percentile"],
        "source_MIN_BYTES_DEFAULT": source_default,
        "source_matches_threshold": source_default == derived["threshold"],
        "reducer_path": "lib/completion_reducer.py",
    }


def main() -> int:
    result = run(REPO)
    slim = {k: v for k, v in result.items() if k not in {"receipt_rows", "histogram_rows"}}
    print(json.dumps(slim, indent=1, sort_keys=True))
    print(
        f"n_receipt_class={result['n_receipt_class']} "
        f"n_histogram={result['n_histogram']} "
        f"threshold={result['threshold']} "
        f"p0={result['derivation']['percentiles']['p0']} "
        f"source_default={result['source_MIN_BYTES_DEFAULT']} "
        f"match={result['source_matches_threshold']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
