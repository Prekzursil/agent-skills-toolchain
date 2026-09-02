"""Deterministic 100-payload sample from this estate's agent probe outputs."""
from __future__ import annotations

from pathlib import Path

N_REQUIRED = 100

_SKIP_PARTS = {"runtime", "node_modules", "egg-info", "TST-0006"}


def iter_candidates(repo: Path) -> list[Path]:
    probes = repo / "command-center" / "p2-wave" / "probes"
    ranked: list[tuple[int, str, Path]] = []
    for path in probes.rglob("*"):
        if not path.is_file() or path.suffix != ".json":
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        name = path.name
        if name == "_validate_out.json":
            rank = 0
        elif name.endswith("_validate_out.json") or name == "_revalidate_out.json":
            rank = 1
        elif name in {"_measure_out.json", "_refute_out.json"}:
            rank = 2
        elif name.startswith("_strike"):
            rank = 3
        elif name == "SUBAGENT-RETURN.json":
            rank = 4
        elif name.startswith("_extract") or name.startswith("_inspect"):
            rank = 5
        else:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < 400 or size > 8_000_000:
            continue
        rel = path.relative_to(repo).as_posix()
        ranked.append((rank, rel, path))
    ranked.sort()
    return [p for _, _, p in ranked]


def select_payloads(repo: Path, n: int = N_REQUIRED) -> list[Path]:
    cands = iter_candidates(repo)
    if len(cands) < n:
        raise SystemExit(
            f"FAILED:TST-0006 corpus too small: {len(cands)} < {n}"
        )
    # Stratify: payloads that contain a markdown fence are kept first so the
    # illustrative-path false-positive rate has a real denominator.
    fenced: list[Path] = []
    rest: list[Path] = []
    for path in cands:
        try:
            blob = path.read_bytes()
        except OSError:
            rest.append(path)
            continue
        if b"```" in blob:
            fenced.append(path)
        else:
            rest.append(path)
    ordered = fenced + rest
    return ordered[:n]
