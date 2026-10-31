"""Live AST census of RNG sites for TST-0027 (rebuild).

Classifies every RNG call site under the given roots:
  records  - the site passes an explicit seed and records the seed it used;
  takes    - the site takes a seed parameter without emitting it into results;
  discards - the site consumes unseeded entropy (random.* / fresh SystemRandom
             / time-based) so a failure it produces is unreproducible noise.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _classify(src: str, rel: str) -> dict:
    tree = ast.parse(src)
    info = {
        "path": rel,
        "records_seed": False,
        "takes_seed_param": False,
        "unseeded_entropy": False,
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", getattr(fn, "id", ""))
            if name in {"seed", "randrange", "randint", "random", "choice", "shuffle", "randbytes"}:
                owner = getattr(fn.value, "id", "") if isinstance(getattr(fn, "value", None), ast.Name) else ""
                if owner == "random" or name == "randbytes":
                    info["unseeded_entropy"] = True
            if name == "seed":
                info["records_seed"] = True
        if isinstance(node, ast.FunctionDef):
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if "seed" in arg.arg.lower():
                    info["takes_seed_param"] = True
        if isinstance(node, ast.Return):
            s = ast.dump(node)
            if "seed" in s:
                info["records_seed"] = True
    return info


def census(repo: Path, roots: list[str] | None = None) -> dict:
    repo = Path(repo)
    roots = roots or ["tools/testinfra"]
    records, takes, discards = [], [], []
    for root in roots:
        base = repo / root
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            try:
                src = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if "random" not in src and "seed" not in src:
                continue
            info = _classify(src, p.relative_to(repo).as_posix())
            if info["records_seed"]:
                records.append(info)
            elif info["takes_seed_param"]:
                takes.append(info)
            elif info["unseeded_entropy"]:
                discards.append(info)
    return {
        "roots": roots,
        "records_seed": [r["path"] for r in records],
        "takes_seed_param": [r["path"] for r in takes],
        "discards_seed": [r["path"] for r in discards],
        "counts": {"records": len(records), "takes": len(takes), "discards": len(discards)},
    }
